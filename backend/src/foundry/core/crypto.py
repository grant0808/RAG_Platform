import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from foundry.core.errors import ConfigurationError


class CredentialCipher:
    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path
        self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()

        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(self.key_path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as file:
            file.write(key)
        return key

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ConfigurationError("Stored provider credential cannot be decrypted") from exc


def mask_secret(secret: str) -> str:
    suffix = secret[-4:] if len(secret) >= 4 else "****"
    return f"••••••••{suffix}"
