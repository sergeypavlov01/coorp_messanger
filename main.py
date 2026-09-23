"""Минимальный каркас для самостоятельной реализации мессенджера."""

from __future__ import annotations

import json

import websockets
from PySide6 import QtWebSockets
from PySide6.QtCore import QUrl

from websocket_client import WebSocketClient

import asyncio
import logging
import os
import sys
from collections.abc import Coroutine
from typing import Any

from dotenv import load_dotenv
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget, QVBoxLayout, QTextEdit, QPushButton, QLineEdit
from qasync import QEventLoop, asyncClose


load_dotenv()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
WS_URL = os.getenv("WS_URL", f"ws://{HOST}:{PORT}/chat")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Предоставляет безопасный каркас Qt/asyncio без готового решения задачи."""

    def __init__(self) -> None:
        """Создаёт очередь, реестр фоновых задач и пустое главное окно."""

        super().__init__()
        self.setWindowTitle("Учебный WebSocket-мессенджер")
        self.setMinimumSize(720, 480)

        # Очередь разделяет получение данных по сети и их обработку в UI.
        self.message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        # Храним ссылки только на задачи этого окна, чтобы корректно их отменить.
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.connection: QWebSocket | None = None
        self.username = "student"
        # TODO: добавьте поле для активного WebSocket-соединения.


        # TODO: замените подсказку собственными виджетами и компоновками.
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите сообщение...")

        self.send_button = QPushButton("Отправить")

        layout.addWidget(self.log)
        layout.addWidget(self.input)
        layout.addWidget(self.send_button)

        # 123
        self.create_background_task(self.connect_and_receive(self.username))

    def _on_ws_connected(self) -> None:
        """Соединение установлено — отправляем setMyName."""
        logger.info("Соединение с %s установлено", WS_URL)
        self.log.append("🟢 Соединение установлено")

        payload = json.dumps({
            "reqType": "setMyName",
            "name": self.username,
        })
        self.connection.sendTextMessage(payload)
        logger.info("Отправлено setMyName: %s", self.username)
        self.log.append(f"📤 setMyName: {self.username}")

    def _on_ws_disconnected(self) -> None:
        logger.warning("Соединение разорвано")
        self.log.append("Соединение разорвано")

    def _on_ws_error(self, error_code) -> None:
        logger.error("Ошибка WebSocket: %s", error_code)
        self.log.append(f"⚠Ошибка: {error_code}")

    def _on_ws_text_message(self, message: str) -> None:
        """Пришло сообщение — кладём словарь в очередь."""
        logger.info("Получено: %s", message)

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Некорректный JSON: %r", message)
            return

        self.message_queue.put_nowait(data)
    def create_background_task(
        self,
        coroutine: Coroutine[Any, Any, Any],
    ) -> asyncio.Task[Any]:
        """Запускает корутину, сохраняет ссылку и регистрирует обработку ошибок.

        Используйте этот метод в обработчиках кнопок вместо прямого
        ``asyncio.create_task``. Так задачи не потеряются и будут отменены при
        закрытии окна.
        """

        task = asyncio.create_task(coroutine)
        self.background_tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        """Удаляет завершённую задачу и журналирует необработанное исключение."""

        self.background_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.exception("Фоновая задача завершилась с ошибкой")

    async def connect_and_receive(self, username: str) -> None:
        self.connection.connected.connect(self._on_ws_connected)
        self.connection.disconnected.connect(self._on_ws_disconnected)
        self.connection.textMessageReceived.connect(self._on_ws_text_message)
        self.connection.errorOccurred.connect(self._on_ws_error)

        logger.info("Подключаемся к %s", WS_URL)
        self.log.append(f"🔌 Подключаемся к {WS_URL}...")

        # open() не блокирует: результат придёт сигналом connected
        self.connection.open(QUrl(WS_URL))

        try:
            # Держим корутину живой, пока окно не закроется
            await asyncio.Event().wait()
        finally:
            # При отмене задачи (закрытие окна) корректно рвём соединение
            if self.connection is not None and self.connection.isValid():
                self.connection.close()
            self.connection = None
        """Подключается, авторизуется и непрерывно принимает сообщения.

        TODO: реализуйте соединение с ``WS_URL`` через библиотеку websockets.
        
        После открытия отправьте setMyName, затем разбирайте каждый JSON-ответ
        и помещайте словарь в ``message_queue``. Продумайте переподключение.
        """

        self.username = username
        self.connection = QWebSocket()

        payload = json.dumps({
            "reqType": "setMyName",
            "name": username,
        })
        await self.connection.send(payload)
        logger.info("Отправлено setMyName: %s", username)
        self.log.append(f"setMyName: {username}")

        raise NotImplementedError("Реализуйте подключение и приём сообщений")

    async def process_messages(self) -> None:
        """Извлекает сообщения из очереди и обновляет интерфейс.

        TODO: создайте цикл с ``await self.message_queue.get()`` и обработайте
        значения respType из документации сервера. Изменять Qt-виджеты следует
        именно в этой корутине, работающей в общем event loop.
        """

        raise NotImplementedError("Реализуйте обработку входящих сообщений")

    async def send_message(
        self,
        text: str,
        user_to: dict[str, Any] | None = None,
    ) -> None:
        """Отправляет общее или личное сообщение через активное соединение.

        TODO: проверьте непустой текст и состояние соединения. Для общего
        сообщения сформируйте reqSendAll, для личного — reqSendMessage.
        """

        raise NotImplementedError("Реализуйте отправку сообщения")

    @asyncClose
    async def closeEvent(self, event: Any) -> None:
        """Отменяет только принадлежащие окну задачи и завершает закрытие."""

        tasks = tuple(self.background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        event.accept()


def main() -> int:
    """Создаёт единый цикл событий Qt/asyncio и показывает главное окно."""

    app = QApplication(sys.argv)
    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    window = MainWindow()
    window.show()
    with event_loop:
        event_loop.run_forever()
    return 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = WebSocketClient()
    client.connect_to_server(WS_URL)
    sys.exit(app.exec())
