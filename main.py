"""Мессенджер на PySide6 + WebSocket.
   Экраны: Авторизация → Список чатов → Чат.
   Общий чат (reqSendAll) + личные (reqSendMessage).
   История — history.json. Темы — тёмная / светлая.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PySide6.QtCore import QSettings, QTimer, QUrl, Qt
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
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

HISTORY_FILE = Path(__file__).parent / "history.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


PAGE_AUTH = 0
PAGE_LIST = 1
PAGE_CHAT = 2

GENERAL_CHAT = {"id": "__general__", "name": "Общий чат", "general": True}


# =====================================================================
#  Темы
# =====================================================================
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "app_bg":      "#1e1e2e",
        "panel":       "#2a2a3e",
        "menu":        "#252538",
        "text":        "#FFFFFF",
        "text_muted":  "#B0B0C0",
        "border":      "#444466",
        "input_bg":    "#1e1e2e",
        "input_border":"#555577",
        "btn_bg":      "#0D56A6",
        "btn_hover":   "#1565C0",
        "list_border": "#3a3a55",
        "list_sel":    "#0D50A6",
        "msg_border":  "#444466",
    },
    "light": {
        "app_bg":      "#eceff4",
        "panel":       "#FFFFFF",
        "menu":        "#E4E9F2",
        "text":        "#1a1a2e",
        "text_muted":  "#666677",
        "border":      "#C0C4CC",
        "input_bg":    "#FFFFFF",
        "input_border":"#B0B4BC",
        "btn_bg":      "#1976D2",
        "btn_hover":   "#1565C0",
        "list_border": "#D0D4DC",
        "list_sel":    "#1976D2",
        "msg_border":  "#C0C4CC",
    },
}


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

        # ---------- настройки / тема ----------
        self.settings = QSettings("coorp_messanger", "chat")
        self.theme_name: str = self.settings.value("theme", "dark")

        # ---------- история ----------
        self.history: dict[str, list[dict]] = self._load_history()

        # ---------- UI ----------
        self._setup_screens()
        self._fix_header_widgets()
        self._setup_chat_list()
        self._setup_messages()
        self._connect_signals()
        self._apply_theme(self.theme_name)

        QTimer.singleShot(0, self._start_background_tasks)

    # =====================================================================
    #  Тема
    # =====================================================================

    def _apply_theme(self, name: str) -> None:
        if name not in THEMES:
            name = "dark"
        self.theme_name = name
        t = THEMES[name]

        # окно
        self.setStyleSheet(f"QMainWindow {{ background-color: {t['app_bg']}; }}")

        # панели
        for w in (self.ui.Auth, self.ui.Chat, self.ui.ListChats):
            w.setStyleSheet(
                f"background-color: {t['panel']}; border-radius: 20px;"
            )

        # шапки
        for w in (self.ui.Menu, self.ui.Menu_2):
            w.setStyleSheet(
                f"background-color: {t['menu']};"
                "border-radius: 0;"
                "border-top-left-radius: 20px;"
                "border-top-right-radius: 20px;"
            )

        # контейнер сообщений
        self.ui.Messages.setStyleSheet(
            f"border: 1px solid {t['msg_border']};"
        )

        # авторизация
        self.ui.label.setStyleSheet(
            f"color: {t['text']}; background: transparent;"
        )
        self.ui.label_2.setStyleSheet(
            f"color: {t['text']}; background: transparent;"
        )

        # заголовок списка чатов
        self.ui.label_3.setStyleSheet(
            f"color: {t['text']}; background: transparent;"
        )

        # обёртка списка
        self.ui.List.setStyleSheet("background: transparent;")

        # поля ввода
        input_qss = (
            f"QLineEdit {{"
            f"  background: {t['input_bg']};"
            f"  color: {t['text']};"
            f"  border: 1px solid {t['input_border']};"
            f"  border-radius: 6px;"
            f"  padding: 4px 8px;"
            f"}}"
        )
        self.ui.lineEdit.setStyleSheet(input_qss)
        self.ui.lineEdit_2.setStyleSheet(input_qss)

        # кнопки
        btn_qss = (
            f"QPushButton {{"
            f"  background: {t['btn_bg']};"
            f"  color: #FFFFFF;"
            f"  border: 1px solid {t['border']};"
            f"  border-radius: 6px;"
            f"  padding: 6px 12px;"
            f"  font-size: 12pt;"
            f"}}"
            f"QPushButton:hover {{ background: {t['btn_hover']}; }}"
        )
        self.ui.pushButton.setStyleSheet(btn_qss)
        self.ui.pushButton_2.setStyleSheet(btn_qss)
        self.ui.pushButton_3.setStyleSheet(btn_qss)
        self.add_btn.setStyleSheet(btn_qss)
        self.theme_btn.setStyleSheet(btn_qss)

        # список чатов
        self.chat_list.setStyleSheet(
            f"QListWidget {{"
            f"  background: transparent; border: none;"
            f"  color: {t['text']}; font-size: 12pt;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 12px;"
            f"  border-bottom: 1px solid {t['list_border']};"
            f"}}"
            f"QListWidget::item:selected {{ background: {t['list_sel']}; }}"
        )

        # окно сообщений
        self.messages_view.setStyleSheet(
            f"QTextEdit {{"
            f"  background: transparent; border: none;"
            f"  color: {t['text']}; font-size: 12pt; padding: 8px;"
            f"}}"
        )

        # шапка чата
        self.chat_title.setStyleSheet(
            f"color: {t['text']}; font-size: 14pt; background: transparent;"
        )
        self.chat_status.setStyleSheet(
            f"color: {t['text_muted']}; font-size: 9pt; background: transparent;"
        )

        # подпись на кнопке темы
        self.theme_btn.setText("Светлая" if name == "dark" else "Тёмная")

    def _on_theme_toggle(self) -> None:
        new = "light" if self.theme_name == "dark" else "dark"
        self._apply_theme(new)
        self.settings.setValue("theme", new)
        logger.info("Тема: %s", new)

    # =====================================================================
    #  История
    # =====================================================================

    def _load_history(self) -> dict[str, list[dict]]:
        if not HISTORY_FILE.exists():
            return {}
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Не удалось прочитать историю: %s", e)
        return {}

    def _save_history(self) -> None:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Не удалось сохранить историю: %s", e)

    def _chat_key(self, chat: dict) -> str:
        return chat.get("name") or str(chat.get("id", "?"))

    def _add_to_history(self, chat_key: str, author: str, text: str) -> None:
        self.history.setdefault(chat_key, []).append({
            "author": author,
            "text": text,
            "ts": time.time(),
        })
        if len(self.history[chat_key]) > 500:
            self.history[chat_key] = self.history[chat_key][-500:]
        self._save_history()

    def _render_history(self, chat_key: str) -> None:
        self.messages_view.clear()
        for msg in self.history.get(chat_key, []):
            author = msg.get("author", "?")
            text = msg.get("text", "")
            self.messages_view.append(f"<b>{author}:</b> {text}")
        sb = self.messages_view.verticalScrollBar()
        sb.setValue(sb.maximum())

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

    def _fix_header_widgets(self) -> None:
        old_title = self.ui.textBrowser
        self.chat_title = QLabel(old_title.parent())
        self.chat_title.setGeometry(old_title.geometry())
        self.chat_title.setText(old_title.toPlainText())
        old_title.hide()

        old_status = self.ui.textBrowser_2
        self.chat_status = QLabel(old_status.parent())
        self.chat_status.setGeometry(old_status.geometry())
        self.chat_status.setText("online")
        old_status.hide()

    def _setup_chat_list(self) -> None:
        for name in ("ListItem", "ListItem_2", "ListItem_3",
                     "ListItem_4", "ListItem_5", "ListItem_6"):
            getattr(self.ui, name).hide()

        self.add_btn = QPushButton("+ Новый чат", self.ui.List)
        self.add_btn.setGeometry(10, 5, 300, 38)
        self.add_btn.clicked.connect(self._on_add_chat_clicked)

        self.theme_btn = QPushButton("🌙 Тёмная", self.ui.List)
        self.theme_btn.setGeometry(320, 5, 100, 38)
        self.theme_btn.clicked.connect(self._on_theme_toggle)

        self.chat_list = QListWidget(self.ui.List)
        self.chat_list.setGeometry(0, 50, 431, 351)
        self.chat_list.itemClicked.connect(self._on_chat_open)

        self._add_general_chat_item()
        self._restore_chats_from_history()

    def _add_general_chat_item(self) -> None:
        item = QListWidgetItem(GENERAL_CHAT["name"])
        item.setData(Qt.UserRole, GENERAL_CHAT)
        self.chat_list.insertItem(0, item)

    def _restore_chats_from_history(self) -> None:
        for key in self.history.keys():
            if key == GENERAL_CHAT["name"]:
                continue
            exists = False
            for i in range(self.chat_list.count()):
                u = self.chat_list.item(i).data(Qt.UserRole) or {}
                if u.get("name") == key:
                    exists = True
                    break
            if not exists:
                item = QListWidgetItem(key)
                item.setData(Qt.UserRole, {"id": None, "name": key})
                self.chat_list.addItem(item)

    def _setup_messages(self) -> None:
        self.messages_view = QTextEdit(self.ui.Messages)
        self.messages_view.setGeometry(0, 0, 421, 441)
        self.messages_view.setReadOnly(True)

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

        self.chat_title.setText(name)
        self.chat_status.setText("broadcast" if user.get("general") else "online")

        self._render_history(self._chat_key(user))
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
        self._save_history()
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

        if user_to is None:
            payload = json.dumps({"reqType": "reqSendAll", "message": text})
            self.connection.sendTextMessage(payload)
            logger.info("→ %s", payload)
            self._store_and_show(GENERAL_CHAT, self.username, text)
            return

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
        self._store_and_show(user_to, "Вы", text)

    async def process_messages(self) -> None:
        while True:
            data = await self.message_queue.get()
            resp_type = data.get("respType", "")

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
            self._store_and_show(GENERAL_CHAT, name, text, prefix="[общий] ")
        else:
            self._ensure_chat_in_list(sender)
            self._store_and_show(sender, name, text)

    def _store_and_show(
        self, chat: dict, author: str, text: str, prefix: str = ""
    ) -> None:
        key = self._chat_key(chat)
        self._add_to_history(key, author, text)

        if self.current_chat and self._chat_key(self.current_chat) == key:
            self.messages_view.append(f"<b>{prefix}{author}:</b> {text}")
            sb = self.messages_view.verticalScrollBar()
            sb.setValue(sb.maximum())
        elif prefix:
            self.messages_view.append(f"<b>{prefix}{author}:</b> {text}")

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
        self._restore_chats_from_history()

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
        self._save_history()
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