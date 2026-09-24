"""Доменные модели."""

from dataclasses import dataclass


@dataclass
class User:
    name: str
    id: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(name=data.get("name", ""), id=data.get("id"))

    def to_dict(self) -> dict:
        return {"name": self.name, "id": self.id}


@dataclass
class Message:
    author: str
    text: str
    ts: float

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            author=data.get("author", ""),
            text=data.get("text", ""),
            ts=data.get("ts", 0.0),
        )

    def to_dict(self) -> dict:
        return {"author": self.author, "text": self.text, "ts": self.ts}


@dataclass
class Chat:
    key: str
    name: str
    is_general: bool = False
    peer: User | None = None

    @classmethod
    def general(cls) -> "Chat":
        return cls(key="__general__", name="Общий чат", is_general=True)

    @classmethod
    def direct(cls, user: User) -> "Chat":
        return cls(key=user.name, name=user.name, peer=user)

    def to_payload(self) -> dict:
        return {
            "name": self.name,
            "id": self.peer.id if self.peer else None,
            "general": self.is_general,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "Chat":
        if payload.get("general"):
            return cls.general()
        return cls.direct(User(name=payload.get("name", ""), id=payload.get("id")))