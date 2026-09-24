"""Мессенджер на PySide6 + WebSocket.
   Экраны: Авторизация → Список чатов → Чат.
   Есть общий чат (reqSendAll) и личные (reqSendMessage).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from collections.abc import Coroutine
from typing import Any

from dotenv import load_dotenv
from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qasync import QEventLoop, asyncClose

import ui

load_dotenv()

HOST = os.getenv("HOST", "192.168.0.100")
PORT = int(os.getenv("PORT", "8080"))
WS_URL = os.getenv("WS_URL", f"ws://{HOST}:{PORT}/chat")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


PAGE_AUTH = 0
PAGE_LIST = 1
PAGE_CHAT = 2

GENERAL_CHAT = {"id": "__general__", "name": "🌐 Общий чат", "general": True}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.ui = ui.Ui_MainWindow()
        self.ui.setupUi(self)

        # ---------- состояние ----------
        self.message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.connection: QWebSocket | None = None
        self.username: str = ""
        self.current_chat: dict | None = None
        self.my_id: int | None = None
        self.logged_in: bool = False

        # ---------- UI ----------
        self._setup_screens()
        self._setup_chat_list()
        self._setup_messages()
        self._connect_signals()

        QTimer.singleShot(0, self._start_background_tasks)

    # =====================================================================
    #  Построение интерфейса
    # =====================================================================

    def _setup_screens(self) -> None:
        self.stack = QStackedWidget()
        self.stack.addWidget(self._wrap_centered(self.ui.Auth,      431, 341))
        self.stack.addWidget(self._wrap_centered(self.ui.ListChats, 431, 461))
        self.stack.addWidget(self._wrap_centered(self.ui.Chat,      441, 591))
        self.setCentralWidget(self.stack)
        self.stack.setCurrentIndex(PAGE_AUTH)

    def _wrap_centered(self, widget: QWidget, w: int, h: int) -> QWidget:
        widget.setParent(None)
        widget.setFixedSize(w, h)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(widget)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()
        return container

    def _setup_chat_list(self) -> None:
        for name in ("ListItem", "ListItem_2", "ListItem_3",
                     "ListItem_4", "ListItem_5", "ListItem_6"):
            getattr(self.ui, name).hide()

        self.add_btn = QPushButton("+ Новый чат", self.ui.List)
        self.add_btn.setGeometry(10, 5, 411, 38)
        self.add_btn.setStyleSheet(
            "QPushButton {"
            "  background: #0D50A6; color: #FFFFFF;"
            "  border: 1px solid #689AD3; border-radius: 6px;"
            "  font-size: 12pt;"
            "}"
            "QPushButton:hover { background: #1565C0; }"
        )
        self.add_btn.clicked.connect(self._on_add_chat_clicked)

        self.chat_list = QListWidget(self.ui.List)
        self.chat_list.setGeometry(0, 50, 431, 351)
        self.chat_list.setStyleSheet(
            "QListWidget {"
            "  background: transparent; border: none;"
            "  color: #FFFFFF; font-size: 12pt;"
            "}"
            "QListWidget::item {"
            "  padding: 12px; border-bottom: 1px solid #689AD3;"
            "}"
            "QListWidget::item:selected { background: #0D50A6; }"
        )
        self.chat_list.itemClicked.connect(self._on_chat_open)

        # Общий чат всегда первым
        self._add_general_chat_item()

    def _add_general_chat_item(self) -> None:
        item = QListWidgetItem(GENERAL_CHAT["name"])
        item.setData(Qt.UserRole, GENERAL_CHAT)
        self.chat_list.insertItem(0, item)

    def _setup_messages(self) -> None:
        self.messages_view = QTextEdit(self.ui.Messages)
        self.messages_view.setGeometry(0, 0, 421, 441)
        self.messages_view.setReadOnly(True)
        self.messages_view.setStyleSheet(
            "QTextEdit {"
            "  background: transparent; border: none;"
            "  color: #FFFFFF; font-size: 12pt; padding: 8px;"
            "}"
        )

    def _connect_signals(self) -> None:
        self.ui.pushButton.clicked.connect(self._on_login_clicked)
        self.ui.pushButton_2.clicked.connect(self._on_send_clicked)
        self.ui.lineEdit_2.returnPressed.connect(self._on_send_clicked)
        self.ui.pushButton_3.clicked.connect(self._on_back_clicked)

    # =====================================================================
    #  Кнопки
    # =====================================================================

    def _on_login_clicked(self) -> None:
        username = self.ui.lineEdit.text().strip()
        if not username:
            QMessageBox.warning(self, "Ошибка", "Введите логин")
            return

        self.username = username
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton.setText("Подключение...")

        if self.connection is not None:
            self.connection.close()
            self.connection = None

        self.logged_in = False
        self.create_background_task(self.connect_and_receive(username))

    def _on_send_clicked(self) -> None:
        text = self.ui.lineEdit_2.text().strip()
        if not text or self.current_chat is None:
            return
        self.ui.lineEdit_2.clear()

        if self.current_chat.get("general"):
            self.create_background_task(self.send_message(text, None))
        else:
            self.create_background_task(self.send_message(text, self.current_chat))

    def _on_back_clicked(self) -> None:
        self.current_chat = None
        self.messages_view.clear()
        self.stack.setCurrentIndex(PAGE_LIST)

    def _on_chat_open(self, item: QListWidgetItem) -> None:
        user = item.data(Qt.UserRole)
        if not user:
            return

        self.current_chat = user
        name = user.get("name", "?")

        self.ui.textBrowser.setHtml(
            f'<p style="font-size:14pt; color:white;">{name}</p>'
        )
        status = "broadcast" if user.get("general") else "online"
        self.ui.textBrowser_2.setHtml(
            f'<p style="color:white;">{status}</p>'
        )

        self.messages_view.clear()
        self.stack.setCurrentIndex(PAGE_CHAT)

    def _on_add_chat_clicked(self) -> None:
        name, ok = QInputDialog.getText(self, "Новый чат", "Имя пользователя:")
        if not ok or not name.strip():
            return
        name = name.strip()
        user = {"id": None, "name": name}

        for i in range(self.chat_list.count()):
            existing = self.chat_list.item(i).data(Qt.UserRole) or {}
            if existing.get("name") == name:
                self.chat_list.setCurrentRow(i)
                return

        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, user)
        self.chat_list.addItem(item)

    # =====================================================================
    #  WebSocket
    # =====================================================================

    def _start_background_tasks(self) -> None:
        self.create_background_task(self.process_messages())

    def _on_ws_connected(self) -> None:
        logger.info("Соединение установлено: %s", WS_URL)
        if self.connection is None:
            return
        payload = json.dumps({"reqType": "setMyName", "newName": self.username})
        self.connection.sendTextMessage(payload)
        logger.info("→ setMyName: %s", self.username)

    def _on_ws_disconnected(self) -> None:
        logger.warning("Соединение разорвано")
        self.logged_in = False
        self.stack.setCurrentIndex(PAGE_AUTH)
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("Войти")

    def _on_ws_error(self, error_code) -> None:
        logger.error("Ошибка WebSocket: %s", error_code)
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("Войти")

    def _on_ws_text_message(self, message: str) -> None:
        logger.info("← %s", message)
        if message == "CONNECTED":
            return
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Некорректный JSON: %r", message)
            return
        self.message_queue.put_nowait(data)

    async def connect_and_receive(self, username: str) -> None:
        self.username = username
        self.connection = QWebSocket()
        self.connection.connected.connect(self._on_ws_connected)
        self.connection.disconnected.connect(self._on_ws_disconnected)
        self.connection.textMessageReceived.connect(self._on_ws_text_message)
        self.connection.errorOccurred.connect(self._on_ws_error)

        logger.info("Подключаемся к %s", WS_URL)
        self.connection.open(QUrl(WS_URL))

        try:
            await asyncio.Event().wait()
        finally:
            if self.connection is not None and self.connection.isValid():
                self.connection.close()
            self.connection = None

    async def send_message(self, text: str, user_to: dict | None = None) -> None:
        if self.connection is None or not self.connection.isValid():
            QMessageBox.warning(self, "Нет связи", "WebSocket не подключён")
            return

        # --- ОБЩИЙ ЧАТ ---
        if user_to is None:
            payload = json.dumps({"reqType": "reqSendAll", "message": text})
            self.connection.sendTextMessage(payload)
            logger.info("→ %s", payload)
            self._append_message(self.username, text)
            return

        # --- ЛИЧНЫЙ ЧАТ ---
        if not user_to.get("id"):
            QMessageBox.information(
                self, "Подожди",
                f"У пользователя {user_to.get('name')} неизвестен ID.\n\n"
                "Пусть он напишет тебе первым — тогда id подставится, "
                "и можно будет отвечать."
            )
            return

        payload = json.dumps({
            "reqType": "reqSendMessage",
            "message": text,
            "userTo": {"id": user_to.get("id"), "name": user_to.get("name")},
        })
        self.connection.sendTextMessage(payload)
        logger.info("→ %s", payload)
        self._append_message("Вы", text)

    async def process_messages(self) -> None:
        while True:
            data = await self.message_queue.get()
            resp_type = data.get("respType", "")

            # ---- success: логин ИЛИ подтверждение отправки ----
            if resp_type == "success":
                text = data.get("successText", "")
                if text.startswith("User with ID"):
                    self._on_login_success(data)
                else:
                    logger.info("Сервер: %s", text)

            elif resp_type in ("users", "userList", "getUsers",
                               "usersList", "chats"):
                users = (data.get("users") or data.get("data")
                         or data.get("chats") or [])
                self._update_users(users)

            elif resp_type == "sendMessage":
                self._handle_incoming(data)

            elif resp_type == "error":
                logger.warning("Сервер вернул ошибку: %s", data.get("errorText"))

            else:
                logger.info("Неизвестный ответ: %s", data)

    # =====================================================================
    #  Обработка входящего сообщения
    # =====================================================================

    def _handle_incoming(self, data: dict) -> None:
        sender = data.get("fromUser") or {}
        name = sender.get("name", "?")
        text = data.get("message", "")

        to_user = data.get("toUser") or data.get("userTo")
        is_broadcast = not to_user

        logger.info("Входящее: from=%s, is_broadcast=%s", name, is_broadcast)

        if is_broadcast:
            # общий чат
            self._append_to_general(name, text)
        else:
            # личное
            self._ensure_chat_in_list(sender)
            if self.current_chat and self.current_chat.get("name") == name:
                self._append_message(name, text)

    def _append_to_general(self, author: str, text: str) -> None:
        """Кладём сообщение в общий чат. Если он открыт — покажем сразу."""
        if self.current_chat and self.current_chat.get("general"):
            self._append_message(author, text)
        else:
            # если открыт другой чат — всё равно покажем, чтобы не терять
            self._append_message(f"[общий] {author}", text)

    # =====================================================================
    #  Вспомогательные
    # =====================================================================

    def _on_login_success(self, data: dict) -> None:
        if self.logged_in:
            return
        self.logged_in = True
        logger.info("Логин ОК: %s", data.get("successText"))
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("Войти")

        text = data.get("successText", "")
        m = re.search(r"ID\s+(\d+)", text)
        if m:
            self.my_id = int(m.group(1))
            logger.info("Мой ID: %s", self.my_id)

        self.stack.setCurrentIndex(PAGE_LIST)

    def _update_users(self, users: list[dict]) -> None:
        self.chat_list.clear()
        self._add_general_chat_item()
        for u in users:
            name = u.get("name", "?")
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, u)
            self.chat_list.addItem(item)

    def _ensure_chat_in_list(self, user: dict) -> None:
        name = user.get("name", "?")
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            existing = item.data(Qt.UserRole) or {}
            if existing.get("name") == name:
                if not existing.get("general"):
                    item.setData(Qt.UserRole, user)
                return
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, user)
        self.chat_list.addItem(item)

    def _append_message(self, author: str, text: str) -> None:
        self.messages_view.append(f"<b>{author}:</b> {text}")

    # =====================================================================
    #  Фоновые задачи
    # =====================================================================

    def create_background_task(
        self, coroutine: Coroutine[Any, Any, Any],
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

    @asyncClose
    async def closeEvent(self, event: Any) -> None:
        tasks = tuple(self.background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        event.accept()


def main() -> int:
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