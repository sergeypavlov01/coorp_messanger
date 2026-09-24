"""Хранилище: история и пользователи."""

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path

from config import HISTORY_FILE, MAX_HISTORY, USERS_FILE
from models import Message, User


class Storage(ABC):
    @abstractmethod
    def add_user(self, user: User) -> None: ...
    @abstractmethod
    def get_users(self) -> list[User]: ...
    @abstractmethod
    def get_user(self, name: str) -> User | None: ...
    @abstractmethod
    def add_message(self, chat_key: str, author: str, text: str) -> None: ...
    @abstractmethod
    def get_messages(self, chat_key: str) -> list[Message]: ...
    @abstractmethod
    def clear_chat(self, chat_key: str) -> None: ...
    @abstractmethod
    def flush(self) -> None: ...


class JsonStorage(Storage):

    def __init__(self, users_path: Path = USERS_FILE,
                 history_path: Path = HISTORY_FILE):
        self._users_path = users_path
        self._history_path = history_path
        self._users: dict[str, User] = {}
        self._history: dict[str, list[Message]] = {}
        self._load()

    def add_user(self, user: User) -> None:
        if not user.name:
            return
        existing = self._users.get(user.name)
        if existing and existing.id and not user.id:
            return
        self._users[user.name] = user

    def get_users(self) -> list[User]:
        return [self._users[k] for k in sorted(self._users)]

    def get_user(self, name: str) -> User | None:
        return self._users.get(name)

    def add_message(self, chat_key: str, author: str, text: str) -> None:
        bucket = self._history.setdefault(chat_key, [])
        bucket.append(Message(author=author, text=text, ts=time.time()))
        if len(bucket) > MAX_HISTORY:
            self._history[chat_key] = bucket[-MAX_HISTORY:]

    def get_messages(self, chat_key: str) -> list[Message]:
        return list(self._history.get(chat_key, []))

    def clear_chat(self, chat_key: str) -> None:
        self._history.pop(chat_key, None)

    def flush(self) -> None:
        self._write(self._users_path, {
            name: user.to_dict() for name, user in self._users.items()
        })
        self._write(self._history_path, {
            key: [m.to_dict() for m in msgs]
            for key, msgs in self._history.items()
        })

    def _load(self) -> None:
        users_raw = self._read(self._users_path)
        self._users = {k: User.from_dict(v) for k, v in users_raw.items()}
        history_raw = self._read(self._history_path)
        self._history = {
            k: [Message.from_dict(m) for m in v]
            for k, v in history_raw.items()
        }

    @staticmethod
    def _read(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass