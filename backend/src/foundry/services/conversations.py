from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.errors import NotFoundError, ValidationError
from foundry.models import ChatMessage, ChatSession
from foundry.models.base import utcnow
from foundry.schemas import ChatSessionCreate, ChatSessionUpdate


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str


@dataclass(frozen=True)
class TokenStatus:
    budget: int
    used_total: int
    used_input: int
    used_output: int
    remaining: int
    message_count: int


class ConversationService:
    async def create(self, session: AsyncSession, payload: ChatSessionCreate) -> ChatSession:
        chat_session = ChatSession(
            pipeline_id=payload.pipeline_id,
            title=payload.title or "New conversation",
        )
        session.add(chat_session)
        await session.flush()
        await session.refresh(chat_session)
        return chat_session

    async def list(
        self, session: AsyncSession, pipeline_id: str | None = None
    ) -> list[ChatSession]:
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc())
        if pipeline_id is not None:
            statement = statement.where(ChatSession.pipeline_id == pipeline_id)
        result = await session.execute(statement)
        return list(result.scalars())

    async def get(self, session: AsyncSession, session_id: str) -> ChatSession:
        chat_session = await session.get(ChatSession, session_id)
        if chat_session is None:
            raise NotFoundError(f"Chat session not found: {session_id}")
        return chat_session

    async def update(
        self, session: AsyncSession, session_id: str, payload: ChatSessionUpdate
    ) -> ChatSession:
        chat_session = await self.get(session, session_id)
        chat_session.title = " ".join(payload.title.strip().split())
        chat_session.updated_at = utcnow()
        await session.flush()
        await session.refresh(chat_session)
        return chat_session

    async def ensure(
        self,
        session: AsyncSession,
        *,
        pipeline_id: str,
        session_id: str | None,
        title_seed: str,
    ) -> ChatSession:
        if session_id is None:
            return await self.create(
                session,
                ChatSessionCreate(
                    pipeline_id=pipeline_id,
                    title=self._title_from_message(title_seed),
                ),
            )

        chat_session = await self.get(session, session_id)
        if chat_session.pipeline_id != pipeline_id:
            raise ValidationError("Chat session belongs to a different pipeline")
        return chat_session

    async def list_messages(self, session: AsyncSession, session_id: str) -> list[ChatMessage]:
        await self.get(session, session_id)
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars())

    async def history(
        self, session: AsyncSession, session_id: str, limit: int = 12
    ) -> list[ConversationTurn]:
        messages = await self.list_messages(session, session_id)
        return [
            ConversationTurn(role=message.role, content=message.content)
            for message in messages[-limit:]
            if message.role in {"user", "assistant"}
        ]

    async def token_status(
        self, session: AsyncSession, session_id: str, budget: int
    ) -> TokenStatus:
        messages = await self.list_messages(session, session_id)
        used_input = 0
        used_output = 0
        used_total = 0
        counted_messages = 0
        for message in messages:
            if message.role != "assistant":
                continue
            usage = message.message_metadata.get("usage")
            if not isinstance(usage, dict):
                continue
            input_tokens = self._usage_int(usage, "input_tokens", "prompt_tokens")
            output_tokens = self._usage_int(usage, "output_tokens", "completion_tokens")
            total_tokens = self._usage_int(usage, "total_tokens")
            if total_tokens == 0:
                total_tokens = input_tokens + output_tokens
            used_input += input_tokens
            used_output += output_tokens
            used_total += total_tokens
            counted_messages += 1
        return TokenStatus(
            budget=budget,
            used_total=used_total,
            used_input=used_input,
            used_output=used_output,
            remaining=max(budget - used_total, 0),
            message_count=counted_messages,
        )

    async def add_message(
        self,
        session: AsyncSession,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            message_metadata=metadata or {},
        )
        session.add(message)
        chat_session = await self.get(session, session_id)
        if role == "user" and chat_session.title == "New conversation":
            chat_session.title = self._title_from_message(content)
        chat_session.updated_at = utcnow()
        await session.flush()
        await session.refresh(message)
        return message

    async def delete(self, session: AsyncSession, session_id: str) -> None:
        chat_session = await self.get(session, session_id)
        await session.delete(chat_session)
        await session.flush()

    @staticmethod
    def _title_from_message(message: str) -> str:
        title = " ".join(message.strip().split())
        if not title:
            return "New conversation"
        return title[:80]

    @staticmethod
    def _usage_int(usage: dict[object, object], *keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return 0
