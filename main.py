"""Минимальный каркас для самостоятельной реализации мессенджера."""

from __future__ import annotations

import ui
import asyncio
import json
import logging
import os
import sys
from collections.abc import Coroutine
from typing import Any

from dotenv import load_dotenv
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
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
        super().__init__()

        self.ui = ui.Ui_MainWindow()
        self.ui.setupUi(self)

        self.auth = self.ui.Auth
        self.list_chats = self.ui.ListChats
        self.chat = self.ui.Chat

        self.message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.connection: QWebSocket | None = None
        self.username = "student"

        # central = QWidget()
        # self.setCentralWidget(central)
        # layout = QVBoxLayout(central)

        # self.log = QTextEdit()
        # self.log.setReadOnly(True)

        # self.input = QLineEdit()
        # self.input.setPlaceholderText("Введите сообщение...")

        # self.send_button = QPushButton("Отправить")

        # self.input.returnPressed.connect(self._on_send_clicked)
        # self.send_button.clicked.connect(self._on_send_clicked)

        # layout.addWidget(self.log)
        # layout.addWidget(self.input)
        # layout.addWidget(self.send_button)

        # Запускаем подключение и обработчик очереди ТОЛЬКО когда event loop уже
        # запущен. Иначе asyncio.create_task получит неработающий loop и
        # корутина будет отброшена с RuntimeWarning "was never awaited".
        QTimer.singleShot(0, self._start_background_tasks)

    def _on_send_clicked(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.create_background_task(self.send_message(text))


    def _start_background_tasks(self) -> None:
        """Стартует фоновые корутины из контекста работающего event loop."""
        self.create_background_task(self.connect_and_receive(self.username))
        self.create_background_task(self.process_messages())

    # --- Обработчики сигналов QWebSocket -----------------------------------

    def _on_ws_connected(self) -> None:
        logger.info("Соединение с %s установлено", WS_URL)
        self.log.append("Соединение установлено")

        if self.connection is None:
            return

        payload = json.dumps({"reqType": "setMyName", "newName": self.username})
        self.connection.sendTextMessage(payload)
        logger.info("Отправлено setMyName: %s", self.username)
        self.log.append(f"setMyName: {self.username}")

    def _on_ws_disconnected(self) -> None:
        logger.warning("Соединение разорвано")
        self.log.append("Соединение разорвано")

    def _on_ws_error(self, error_code) -> None:
        logger.error("Ошибка WebSocket: %s", error_code)
        self.log.append(f"Ошибка: {error_code}")

    def _on_ws_text_message(self, message: str) -> None:
        logger.info("Получено: %s", message)
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Некорректный JSON: %r", message)
            return
        self.message_queue.put_nowait(data)

    # --- Управление фоновыми задачами --------------------------------------

    def create_background_task(
        self,
        coroutine: Coroutine[Any, Any, Any],
    ) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine)
        self.background_tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        self.background_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.exception("Фоновая задача завершилась с ошибкой")

    # --- Корутины ----------------------------------------------------------

    async def connect_and_receive(self, username: str) -> None:
        """Открывает QWebSocket-соединение и держит корутину живой."""
        self.username = username
        self.connection = QWebSocket()
        self.connection.connected.connect(self._on_ws_connected)
        self.connection.disconnected.connect(self._on_ws_disconnected)
        self.connection.textMessageReceived.connect(self._on_ws_text_message)
        self.connection.errorOccurred.connect(self._on_ws_error)

        logger.info("Подключаемся к %s", WS_URL)
        # self.log.append(f"Подключаемся к {WS_URL}...")

        self.connection.open(QUrl(WS_URL))

        try:
            # Держим корутину живой, пока окно не закроется или задача не отменена.
            await asyncio.Event().wait()
        finally:
            if self.connection is not None and self.connection.isValid():
                self.connection.close()
            self.connection = None

    async def process_messages(self) -> None:
        """Извлекает сообщения из очереди и обновляет интерфейс."""
        while True:
            data = await self.message_queue.get()
            # TODO: обработать respType из документации сервера и обновить UI.
            # self.log.append(f"<< {data}")

    async def send_message(self, text: str, user_to: dict | None = None) -> None:
        if self.connection is None or not self.connection.isValid():
            # self.log.append("Нет соединения")
            return
        if not text.strip():
            return

        if user_to is None:
            payload = json.dumps({
                "reqType": "reqSendAll",
                "message": text,
            })
        else:
            payload = json.dumps({
                "reqType": "reqSendMessage",
                "message": text,
                "userTo": user_to,
            })

        self.connection.sendTextMessage(payload)
        logger.info("Отправлено: %s", payload)
        # self.log.append(f"{text}")
    @asyncClose
    async def closeEvent(self, event: Any) -> None:
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
    sys.exit(main())