from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    avito_chat_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    avito_user_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    amo_lead_id: Mapped[Optional[str]] = mapped_column(String(64))
    escalated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ProcessedAvitoInbound(Base):
    """Идемпотентность вебхуков Avito: один ключ — одна обработка (дубли и повторная доставка)."""

    __tablename__ = "processed_avito_inbound"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dedupe_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text())
    source: Mapped[Optional[str]] = mapped_column(String(64))  # avito | bot | manager
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
