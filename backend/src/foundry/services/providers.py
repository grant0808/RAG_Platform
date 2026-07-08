from datetime import UTC, datetime

import httpx
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.config import Settings
from foundry.core.crypto import CredentialCipher, mask_secret
from foundry.core.errors import ConfigurationError, NotFoundError, ProviderError, ValidationError
from foundry.models import ProviderConnection

SUPPORTED_PROVIDERS = {"openai", "anthropic", "ollama"}


class ProviderClient:
    def __init__(self, timeout_seconds: float, ollama_base_url: str) -> None:
        self.timeout = httpx.Timeout(timeout_seconds)
        self.ollama_base_url = ollama_base_url.rstrip("/")

    async def list_models(self, provider: str, credential: str) -> list[str]:
        if provider == "openai":
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {credential}"}
        elif provider == "anthropic":
            url = "https://api.anthropic.com/v1/models"
            headers = {"x-api-key": credential, "anthropic-version": "2023-06-01"}
        elif provider == "ollama":
            base_url = (credential or self.ollama_base_url).rstrip("/")
            url = f"{base_url}/api/tags"
            headers = {}
        else:
            raise ValidationError(f"Unsupported provider: {provider}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                raise ProviderError("Provider rejected the API key") from exc
            raise ProviderError(
                f"Provider model discovery failed: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Provider model discovery is unavailable") from exc

        payload = response.json()
        data = payload.get("models", []) if provider == "ollama" else payload.get("data", [])
        model_ids = sorted(
            {
                value
                for item in data
                for value in (item.get("id"), item.get("name"), item.get("model"))
                if isinstance(value, str)
            }
        )
        if provider == "openai":
            model_ids = [model for model in model_ids if model.startswith(("gpt-", "o"))]
        return model_ids


class ProviderService:
    def __init__(
        self,
        cipher: CredentialCipher,
        client: ProviderClient,
        settings: Settings,
    ) -> None:
        self.cipher = cipher
        self.client = client
        self.settings = settings

    async def connect(
        self,
        session: AsyncSession,
        provider: str,
        api_key: str,
        *,
        validate_connection: bool,
    ) -> ProviderConnection:
        provider = provider.lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValidationError(f"Unsupported provider: {provider}")
        api_key = self._normalize_credential(provider, api_key)

        models = await self.client.list_models(provider, api_key) if validate_connection else []
        result = await session.execute(
            select(ProviderConnection).where(ProviderConnection.provider == provider)
        )
        connection = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if connection is None:
            connection = ProviderConnection(
                provider=provider,
                encrypted_key=self.cipher.encrypt(api_key),
                masked_key=mask_secret(api_key),
                models=models,
                status="connected",
                last_validated_at=now,
            )
            session.add(connection)
        else:
            connection.encrypted_key = self.cipher.encrypt(api_key)
            connection.masked_key = mask_secret(api_key)
            connection.models = models
            connection.status = "connected"
            connection.last_validated_at = now
        self._sync_openai_runtime_keys(provider, api_key)
        await session.flush()
        await session.refresh(connection)
        return connection

    async def list(self, session: AsyncSession) -> list[ProviderConnection]:
        result = await session.execute(
            select(ProviderConnection).order_by(ProviderConnection.provider)
        )
        return list(result.scalars())

    async def get(self, session: AsyncSession, provider: str) -> ProviderConnection:
        result = await session.execute(
            select(ProviderConnection).where(ProviderConnection.provider == provider.lower())
        )
        connection = result.scalar_one_or_none()
        if connection is None:
            raise NotFoundError(f"Provider is not connected: {provider}")
        return connection

    async def get_api_key(self, session: AsyncSession, provider: str) -> str:
        provider = provider.lower()
        connection = await self.get(session, provider)
        try:
            return self.cipher.decrypt(connection.encrypted_key)
        except ConfigurationError:
            fallback = self._runtime_credential(provider)
            if fallback is None:
                raise
            return fallback

    async def refresh_models(self, session: AsyncSession, provider: str) -> ProviderConnection:
        connection = await self.get(session, provider)
        api_key = self.cipher.decrypt(connection.encrypted_key)
        connection.models = await self.client.list_models(provider, api_key)
        connection.last_validated_at = datetime.now(UTC)
        connection.status = "connected"
        await session.flush()
        await session.refresh(connection)
        return connection

    async def disconnect(self, session: AsyncSession, provider: str) -> None:
        provider = provider.lower()
        connection = await self.get(session, provider)
        try:
            api_key = self.cipher.decrypt(connection.encrypted_key)
        except ConfigurationError:
            api_key = None
        if api_key is not None:
            self._clear_openai_runtime_keys(provider, api_key)
        await session.delete(connection)

    def _runtime_credential(self, provider: str) -> str | None:
        if provider != "openai" or self.settings.openai_api_key is None:
            return None
        return self.settings.openai_api_key.get_secret_value()

    def _sync_openai_runtime_keys(self, provider: str, api_key: str) -> None:
        if provider != "openai":
            return
        secret = SecretStr(api_key)
        self.settings.openai_api_key = secret
        self.settings.openai_embedding_api_key = secret

    def _clear_openai_runtime_keys(self, provider: str, api_key: str) -> None:
        if provider != "openai":
            return
        if self._secret_matches(self.settings.openai_api_key, api_key):
            self.settings.openai_api_key = None
        if self._secret_matches(self.settings.openai_embedding_api_key, api_key):
            self.settings.openai_embedding_api_key = None

    @staticmethod
    def _secret_matches(secret: SecretStr | None, value: str) -> bool:
        return secret is not None and secret.get_secret_value() == value

    def _normalize_credential(self, provider: str, credential: str) -> str:
        value = credential.strip()
        if provider == "ollama":
            return (value or self.settings.ollama_base_url).rstrip("/")
        if not value:
            raise ValidationError(f"{provider} API key is required")
        return value
