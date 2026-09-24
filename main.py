"""Клиент мессенджера: авторизация, список чатов, диалог.
   Работает по WebSocket, история и список контактов хранятся локально.
"""

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

BASE_DIR = Path(__file__).parent
HISTORY_FILE = BASE_DIR / "history.json"
USERS_FILE = BASE_DIR / "users.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)


PAGE_AUTH = 0
PAGE_LIST = 1
PAGE_CHAT = 2

GENERAL_CHAT = {"id": "__general__", "name": "Общий чат", "general": True}
REFRESH_MS = 3000


# ---------------------------------------------------------------------
#  Оформление
# ---------------------------------------------------------------------

THEMES = {
    "dark": {
        "window":       "#1b1b26",
        "panel":        "#26263a",
        "header":       "#212134",
        "text":         "#e8e8f0",
        "muted":        "#9090a4",
        "border":       "#3b3b56",
        "input_bg":     "#1b1b26",
        "input_border": "#4a4a68",
        "btn_bg":       "#1f5fa8",
        "btn_hover":    "#2871bd",
        "list_line":    "#33334a",
        "list_sel":     "#1f5fa8",
    },
    "light": {
        "window":       "#e9ecf2",
        "panel":        "#ffffff",
        "header":       "#dde2ec",
        "text":         "#1c1c2a",
        "muted":        "#5f6472",
        "border":       "#c2c7d2",
        "input_bg":     "#ffffff",
        "input_border": "#b1b6c2",
        "btn_bg":       "#2c6fb5",
        "btn_hover":    "#1f5fa8",
        "list_line":    "#d3d7e0",
        "list_sel":     "#2c6fb5",
    },
}


def file_read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def file_write(path: Path, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.ui = ui.Ui_MainWindow()
        self.ui.setupUi(self)

        self.queue: asyncio.Queue = asyncio.Queue()
        self.tasks: set[asyncio.Task] = set()
        self.socket: QWebSocket | None = None

        self.username = ""
        self.my_id = None
        self.current_chat = None
        self.authorized = False

        self.settings = QSettings("coorp_messanger", "client")
        self.theme_name = self.settings.value("theme", "dark")

        # кеши
        self.history = file_read(HISTORY_FILE)
        self.users = file_read(USERS_FILE)

        self._build_screens()
        self._build_header()
        self._build_chat_list()
        self._build_messages()
        self._wire_buttons()
        self._apply_theme(self.theme_name)
        self._restore_login()

        # фоновые задачи и таймер
        QTimer.singleShot(0, self._start_tasks)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_chat_list)
        self.refresh_timer.start(REFRESH_MS)

    # -----------------------------------------------------------------
    #  Разметка
    # -----------------------------------------------------------------

    def _build_screens(self):
        self.stack = QStackedWidget()
        self.stack.addWidget(self._center(self.ui.Auth, 431, 341))
        self.stack.addWidget(self._center(self.ui.ListChats, 431, 461))
        self.stack.addWidget(self._center(self.ui.Chat, 441, 591))
        self.setCentralWidget(self.stack)
        self.stack.setCurrentIndex(PAGE_AUTH)

    def _center(self, widget, w, h):
        widget.setParent(None)
        widget.setFixedSize(w, h)
        box = QWidget()
        col = QVBoxLayout(box)
        col.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(widget)
        row.addStretch()
        col.addLayout(row)
        col.addStretch()
        return box

    def _build_header(self):
        # в ui.py шапка чата сделана из QTextBrowser, меняем на QLabel
        old = self.ui.textBrowser
        self.title_label = QLabel(old.parent())
        self.title_label.setGeometry(old.geometry())
        self.title_label.setText("")
        old.hide()

        old = self.ui.textBrowser_2
        self.status_label = QLabel(old.parent())
        self.status_label.setGeometry(old.geometry())
        self.status_label.setText("")
        old.hide()

    def _build_chat_list(self):
        for name in ("ListItem", "ListItem_2", "ListItem_3",
                     "ListItem_4", "ListItem_5", "ListItem_6"):
            getattr(self.ui, name).hide()

        self.add_button = QPushButton("Добавить", self.ui.List)
        self.add_button.setGeometry(10, 5, 200, 36)
        self.add_button.clicked.connect(self._add_chat_dialog)

        self.theme_button = QPushButton("Тема", self.ui.List)
        self.theme_button.setGeometry(220, 5, 100, 36)
        self.theme_button.clicked.connect(self._toggle_theme)

        self.clear_button = QPushButton("Очистить", self.ui.List)
        self.clear_button.setGeometry(330, 5, 91, 36)
        self.clear_button.clicked.connect(self._clear_history_dialog)

        self.chat_list = QListWidget(self.ui.List)
        self.chat_list.setGeometry(0, 50, 431, 401)
        self.chat_list.itemClicked.connect(self._open_chat)

        self._refresh_chat_list()

    def _build_messages(self):
        self.messages = QTextEdit(self.ui.Messages)
        self.messages.setGeometry(0, 0, 421, 441)
        self.messages.setReadOnly(True)

    def _wire_buttons(self):
        self.ui.pushButton.clicked.connect(self._login)
        self.ui.pushButton_2.clicked.connect(self._send)
        self.ui.lineEdit_2.returnPressed.connect(self._send)
        self.ui.pushButton_3.clicked.connect(self._back_to_list)

    def _restore_login(self):
        last = self.settings.value("last_username", "")
        if last:
            self.ui.lineEdit.setText(last)

    # -----------------------------------------------------------------
    #  Стили
    # -----------------------------------------------------------------

    def _apply_theme(self, name):
        if name not in THEMES:
            name = "dark"
        self.theme_name = name
        t = THEMES[name]

        self.setStyleSheet(f"QMainWindow {{ background-color: {t['window']}; }}")

        for w in (self.ui.Auth, self.ui.Chat, self.ui.ListChats):
            w.setStyleSheet(
                f"background-color: {t['panel']}; border-radius: 18px;"
            )

        for w in (self.ui.Menu, self.ui.Menu_2):
            w.setStyleSheet(
                f"background-color: {t['header']};"
                "border-radius: 0;"
                "border-top-left-radius: 18px;"
                "border-top-right-radius: 18px;"
            )

        self.ui.Messages.setStyleSheet(f"border: 1px solid {t['border']};")
        self.ui.List.setStyleSheet("background: transparent;")

        for lbl in (self.ui.label, self.ui.label_2, self.ui.label_3):
            lbl.setStyleSheet(
                f"color: {t['text']}; background: transparent;"
            )

        edit_qss = (
            f"QLineEdit {{"
            f"  background: {t['input_bg']};"
            f"  color: {t['text']};"
            f"  border: 1px solid {t['input_border']};"
            f"  border-radius: 6px;"
            f"  padding: 4px 8px;"
            f"}}"
        )
        self.ui.lineEdit.setStyleSheet(edit_qss)
        self.ui.lineEdit_2.setStyleSheet(edit_qss)

        btn_qss = (
            f"QPushButton {{"
            f"  background: {t['btn_bg']};"
            f"  color: #ffffff;"
            f"  border: 1px solid {t['border']};"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{ background: {t['btn_hover']}; }}"
            f"QPushButton:disabled {{ background: {t['border']}; }}"
        )
        for b in (self.ui.pushButton, self.ui.pushButton_2, self.ui.pushButton_3,
                  self.add_button, self.theme_button, self.clear_button):
            b.setStyleSheet(btn_qss)

        self.chat_list.setStyleSheet(
            f"QListWidget {{"
            f"  background: transparent; border: none;"
            f"  color: {t['text']}; font-size: 13px;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 10px 14px;"
            f"  border-bottom: 1px solid {t['list_line']};"
            f"}}"
            f"QListWidget::item:selected {{ background: {t['list_sel']}; }}"
        )

        self.messages.setStyleSheet(
            f"QTextEdit {{"
            f"  background: transparent; border: none;"
            f"  color: {t['text']}; font-size: 13px; padding: 8px;"
            f"}}"
        )

        self.title_label.setStyleSheet(
            f"color: {t['text']}; font-size: 15px; background: transparent;"
        )
        self.status_label.setStyleSheet(
            f"color: {t['muted']}; font-size: 11px; background: transparent;"
        )

        self.theme_button.setText(
            "Светлая" if name == "dark" else "Тёмная"
        )

    def _toggle_theme(self):
        new = "light" if self.theme_name == "dark" else "dark"
        self._apply_theme(new)
        self.settings.setValue("theme", new)

    # -----------------------------------------------------------------
    #  Кеш
    # -----------------------------------------------------------------

    def _chat_key(self, chat):
        return chat.get("name") or str(chat.get("id", ""))

    def _remember_user(self, user):
        name = user.get("name")
        if not name:
            return
        self.users[name] = {"id": user.get("id"), "name": name}
        file_write(USERS_FILE, self.users)

    def _add_to_history(self, key, author, text):
        self.history.setdefault(key, []).append({
            "author": author,
            "text": text,
            "ts": time.time(),
        })
        if len(self.history[key]) > 500:
            self.history[key] = self.history[key][-500:]
        file_write(HISTORY_FILE, self.history)

    def _render_history(self, key):
        self.messages.clear()
        for m in self.history.get(key, []):
            self.messages.append(
                f"<b>{m.get('author','')}:</b> {m.get('text','')}"
            )
        bar = self.messages.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _refresh_chat_list(self):
        """Перерисовывает список из кеша. Держит текущий выбор."""
        selected_name = None
        if self.chat_list.currentItem():
            selected_name = self._chat_key(
                self.chat_list.currentItem().data(Qt.UserRole) or {}
            )

        self.chat_list.blockSignals(True)
        self.chat_list.clear()

        item = QListWidgetItem(GENERAL_CHAT["name"])
        item.setData(Qt.UserRole, GENERAL_CHAT)
        self.chat_list.addItem(item)

        for name in sorted(self.users.keys()):
            u = self.users[name]
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, {"id": u.get("id"), "name": name})
            self.chat_list.addItem(it)

        if selected_name:
            for i in range(self.chat_list.count()):
                u = self.chat_list.item(i).data(Qt.UserRole) or {}
                if u.get("name") == selected_name:
                    self.chat_list.setCurrentRow(i)
                    break

        self.chat_list.blockSignals(False)

    # -----------------------------------------------------------------
    #  Кнопки
    # -----------------------------------------------------------------

    def _login(self):
        name = self.ui.lineEdit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите имя")
            return

        self.username = name
        self.settings.setValue("last_username", name)

        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton.setText("Подключение")
        self.authorized = False

        if self.socket is not None:
            self.socket.close()
            self.socket = None

        self._spawn(self._connect(name))

    def _send(self):
        text = self.ui.lineEdit_2.text().strip()
        if not text or self.current_chat is None:
            return
        self.ui.lineEdit_2.clear()

        if self.current_chat.get("general"):
            self._spawn(self._send_message(text, None))
        else:
            self._spawn(self._send_message(text, self.current_chat))

    def _back_to_list(self):
        self.current_chat = None
        self.messages.clear()
        self.stack.setCurrentIndex(PAGE_LIST)

    def _open_chat(self, item):
        user = item.data(Qt.UserRole)
        if not user:
            return

        self.current_chat = user
        self.title_label.setText(user.get("name", ""))
        self.status_label.setText(
            "трансляция" if user.get("general") else "online"
        )
        self._render_history(self._chat_key(user))
        self.stack.setCurrentIndex(PAGE_CHAT)

    def _add_chat_dialog(self):
        name, ok = QInputDialog.getText(self, "Новый чат", "Имя пользователя:")
        if not ok or not name.strip():
            return
        name = name.strip()

        if name not in self.users:
            self.users[name] = {"id": None, "name": name}
            file_write(USERS_FILE, self.users)

        self._refresh_chat_list()
        for i in range(self.chat_list.count()):
            u = self.chat_list.item(i).data(Qt.UserRole) or {}
            if u.get("name") == name:
                self.chat_list.setCurrentRow(i)
                break

    def _clear_history_dialog(self):
        item = self.chat_list.currentItem()
        if not item:
            return
        user = item.data(Qt.UserRole) or {}
        key = self._chat_key(user)

        answer = QMessageBox.question(
            self, "Очистить", f"Удалить историю чата с «{key}»?"
        )
        if answer != QMessageBox.Yes:
            return

        self.history.pop(key, None)
        file_write(HISTORY_FILE, self.history)
        self.messages.clear()

    # -----------------------------------------------------------------
    #  WebSocket
    # -----------------------------------------------------------------

    def _start_tasks(self):
        self._spawn(self._process())

    def _on_connected(self):
        log.info("Соединение установлено")
        if self.socket is None:
            return
        self.socket.sendTextMessage(
            json.dumps({"reqType": "setMyName", "newName": self.username})
        )

    def _on_disconnected(self):
        log.info("Соединение разорвано")
        self.authorized = False
        file_write(HISTORY_FILE, self.history)
        file_write(USERS_FILE, self.users)
        self.stack.setCurrentIndex(PAGE_AUTH)
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("Войти")

    def _on_error(self, code):
        log.warning("Ошибка WebSocket: %s", code)
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("Войти")

    def _on_text(self, message):
        if message == "CONNECTED":
            return
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            log.warning("Не JSON: %r", message)
            return
        self.queue.put_nowait(data)

    async def _connect(self, username):
        self.socket = QWebSocket()
        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.textMessageReceived.connect(self._on_text)
        self.socket.errorOccurred.connect(self._on_error)
        self.socket.open(QUrl(WS_URL))

        try:
            await asyncio.Event().wait()
        finally:
            if self.socket is not None and self.socket.isValid():
                self.socket.close()
            self.socket = None

    async def _send_message(self, text, user_to=None):
        if self.socket is None or not self.socket.isValid():
            QMessageBox.warning(self, "Нет связи", "Соединение не установлено")
            return

        if user_to is None:
            self.socket.sendTextMessage(
                json.dumps({"reqType": "reqSendAll", "message": text})
            )
            self._store(GENERAL_CHAT, self.username, text)
            return

        if not user_to.get("id"):
            QMessageBox.information(
                self, "Нет id",
                f"У пользователя {user_to.get('name')} пока неизвестен id.\n"
                "Он появится, когда тот напишет первым."
            )
            return

        self.socket.sendTextMessage(json.dumps({
            "reqType": "reqSendMessage",
            "message": text,
            "userTo": {
                "id": user_to.get("id"),
                "name": user_to.get("name"),
            },
        }))
        self._store(user_to, "Вы", text)

    async def _process(self):
        while True:
            data = await self.queue.get()
            kind = data.get("respType", "")

            if kind == "success":
                text = data.get("successText", "")
                if text.startswith("User with ID"):
                    self._authorize(data)
                else:
                    log.info("Сервер: %s", text)

            elif kind == "sendMessage":
                self._incoming(data)

            elif kind == "error":
                log.warning("Сервер: %s", data.get("errorText"))

            else:
                log.info("Ответ: %s", data)

    # -----------------------------------------------------------------
    #  События сервера
    # -----------------------------------------------------------------

    def _authorize(self, data):
        if self.authorized:
            return
        self.authorized = True

        m = re.search(r"ID\s+(\d+)", data.get("successText", ""))
        if m:
            self.my_id = int(m.group(1))

        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("Войти")
        self.stack.setCurrentIndex(PAGE_LIST)

    def _incoming(self, data):
        sender = data.get("fromUser") or {}
        name = sender.get("name", "")
        text = data.get("message", "")

        if not name:
            return

        self._remember_user(sender)

        if data.get("toUser") or data.get("userTo"):
            self._store(sender, name, text)
        else:
            self._store(GENERAL_CHAT, name, text, label="[общий] ")

        self._refresh_chat_list()

    def _store(self, chat, author, text, label=""):
        key = self._chat_key(chat)
        self._add_to_history(key, author, text)

        active_key = self._chat_key(self.current_chat) if self.current_chat else None

        if active_key == key:
            self.messages.append(f"<b>{label}{author}:</b> {text}")
            bar = self.messages.verticalScrollBar()
            bar.setValue(bar.maximum())

    # -----------------------------------------------------------------
    #  Задачи
    # -----------------------------------------------------------------

    def _spawn(self, coro: Coroutine) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task):
        self.tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            log.exception("Ошибка в фоновой задаче")

    @asyncClose
    async def closeEvent(self, event):
        file_write(HISTORY_FILE, self.history)
        file_write(USERS_FILE, self.users)

        for t in tuple(self.tasks):
            t.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        event.accept()


def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())