"""Обёртка над QWebSocket. Точный протокол учебного сервера."""

import json
import logging

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWebSockets import QWebSocket

from config import WS_URL

log = logging.getLogger(__name__)


class WebSocketClient(QObject):

    connected = Signal()
    disconnected = Signal()
    error = Signal(str)
    message_received = Signal(dict)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._socket: QWebSocket | None = None
        self.username = ""

    def open(self, username: str) -> None:
        self.close()
        self.username = username
        self._socket = QWebSocket()
        self._socket.connected.connect(self.connected.emit)
        self._socket.disconnected.connect(self.disconnected.emit)
        self._socket.textMessageReceived.connect(self._on_text)
        self._socket.errorOccurred.connect(self._on_error)
        self._socket.open(QUrl(WS_URL))

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def is_open(self) -> bool:
        return self._socket is not None and self._socket.isValid()

    # -------- методы протокола --------

    def set_name(self) -> bool:
        return self._send({"reqType": "setMyName", "newName": self.username})

    def who_am_i(self) -> bool:
        return self._send({"reqType": "whoAmI"})

    def get_connected_users(self) -> bool:
        return self._send({"reqType": "getConnectedUsers"})

    def send_broadcast(self, text: str) -> bool:
        return self._send({"reqType": "reqSendAll", "message": text})

    def send_private(self, text: str, peer) -> bool:
        return self._send({
            "reqType": "reqSendMessage",
            "toUser": {"id": peer.id, "name": peer.name},  # ← toUser
            "message": text,
        })

    # -------- внутреннее --------

    def _send(self, payload: dict) -> bool:
        if not self.is_open():
            return False
        self._socket.sendTextMessage(json.dumps(payload, ensure_ascii=False))
        log.info("→ %s", payload)
        return True

    def _on_text(self, raw: str) -> None:
        if raw == "CONNECTED":
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Не JSON: %r", raw)
            return
        log.info("← %s", data)
        self.message_received.emit(data)

    def _on_error(self, code) -> None:
        msg = self._socket.errorString() if self._socket else ""
        log.error("Ошибка WebSocket: %s — %s", code, msg)
        self.error.emit(f"{code}: {msg}")