"""Оркестратор: связывает экраны, хранилище и WebSocket."""

import asyncio
import logging
import re
from collections.abc import Coroutine
from typing import Any

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow, QMessageBox
from qasync import asyncClose

import ui
from config import (
    PAGE_AUTH, PAGE_CHAT, PAGE_LIST, REFRESH_MS,
    SETTINGS_APP, SETTINGS_ORG,
)
from models import Chat, User
from screens import AuthScreen, ChatListScreen, ChatScreen
from sound import SoundNotifier
from storage import JsonStorage, Storage
from themes import ThemeManager
from websocket_client import WebSocketClient

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app

        self.ui = ui.Ui_MainWindow()
        self.ui.setupUi(self)

        # сервисы
        self.storage: Storage = JsonStorage()
        self.theme = ThemeManager()
        self.sound = SoundNotifier()
        self.ws = WebSocketClient(self)
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        # состояние
        self._tasks: set[asyncio.Task] = set()
        self._username = ""
        self._my_id: int | None = None
        self._my_name = ""
        self._authorized = False
        self._current_page = PAGE_AUTH

        # экраны
        self._auth = AuthScreen(self.ui)
        self._list = ChatListScreen(self.ui)
        self._chat = ChatScreen(self.ui)

        self._wire_signals()
        self._apply_initial_state()

        QTimer.singleShot(0, self._start)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._render_chat_list)
        self._refresh_timer.start(REFRESH_MS)

    # =================================================================
    #  Инициализация
    # =================================================================

    def _wire_signals(self):
        self._auth.login_requested.connect(self._on_login)
        self._list.chat_selected.connect(self._on_chat_selected)
        self._list.add_chat_requested.connect(self._on_add_chat)
        self._list.theme_requested.connect(self._on_toggle_theme)
        self._list.clear_requested.connect(self._on_clear_chat)
        self._chat.message_submitted.connect(self._on_send)
        self._chat.back_requested.connect(self._on_back)

        self.ws.connected.connect(self._on_ws_connected)
        self.ws.disconnected.connect(self._on_ws_disconnected)
        self.ws.error.connect(self._on_ws_error)
        self.ws.message_received.connect(self._on_ws_message)

    def _apply_initial_state(self):
        self.theme.apply(self, self.ui)
        last = self.settings.value("last_username", "")
        self._auth.set_last_username(last)
        self._render_chat_list()
        self._show_page(PAGE_AUTH)

    # =================================================================
    #  Страницы
    # =================================================================

    def _show_page(self, page: int):
        self._current_page = page
        self.ui.Auth.setVisible(page == PAGE_AUTH)
        self.ui.ListChats.setVisible(page == PAGE_LIST)
        self.ui.Chat.setVisible(page == PAGE_CHAT)
        self._center_page()

    def _center_page(self):
        cw = self.ui.centralwidget
        widget = {
            PAGE_AUTH: self.ui.Auth,
            PAGE_LIST: self.ui.ListChats,
            PAGE_CHAT: self.ui.Chat,
        }.get(self._current_page)
        if widget is None:
            return
        widget.move(
            max(0, (cw.width() - widget.width()) // 2),
            max(0, (cw.height() - widget.height()) // 2),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_page()

    # =================================================================
    #  Экран авторизации
    # =================================================================

    def _on_login(self, username: str):
        self._username = username
        self.settings.setValue("last_username", username)
        self._auth.set_busy(True)
        self._authorized = False
        self.ws.open(username)

    # =================================================================
    #  Экран списка чатов
    # =================================================================

    def _render_chat_list(self):
        self._list.render(self.storage.get_users())

    def _on_chat_selected(self, chat: Chat):
        self._list.clear_unread(chat.key)
        self._chat.open_chat(chat)
        self._chat.render_messages(self.storage.get_messages(chat.key))
        self._show_page(PAGE_CHAT)

    def _on_add_chat(self):
        name, ok = QInputDialog.getText(self, "Новый чат", "Имя пользователя:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if self.storage.get_user(name) is None:
            self.storage.add_user(User(name=name))
            self.storage.flush()
        self._render_chat_list()
        self._list.select_chat(name)

    def _on_clear_chat(self, chat: Chat):
        answer = QMessageBox.question(
            self, "Очистить", f"Удалить историю чата «{chat.name}»?"
        )
        if answer != QMessageBox.Yes:
            return
        self.storage.clear_chat(chat.key)
        self.storage.flush()
        self._chat.clear_messages()
        self._list.clear_unread(chat.key)

    def _on_toggle_theme(self):
        self.theme.toggle()
        self.theme.apply(self, self.ui)

    # =================================================================
    #  Экран диалога
    # =================================================================

    def _on_send(self, text: str):
        chat = self._chat.chat
        if chat is None:
            return
        if not self.ws.is_open():
            QMessageBox.warning(self, "Нет связи", "Соединение не установлено")
            return

        if chat.is_general:
            self._store_and_render(chat, self._username, text)
            self.ws.send_broadcast(text)
            return

        peer = chat.peer
        if peer is None or not peer.id:
            QMessageBox.information(
                self, "Нет id",
                f"У пользователя {chat.name} пока неизвестен id.\n"
                "Он появится, когда тот напишет первым."
            )
            return

        self._store_and_render(chat, "Вы", text)
        self.ws.send_private(text, peer)

    def _on_back(self):
        self._chat.chat = None
        self._show_page(PAGE_LIST)

    # =================================================================
    #  WebSocket
    # =================================================================

    def _on_ws_connected(self):
        self.ws.set_name()

    def _on_ws_disconnected(self):
        self._authorized = False
        self.storage.flush()
        self._auth.set_busy(False)
        self._show_page(PAGE_AUTH)

    def _on_ws_error(self, code: str):
        self._auth.set_busy(False)
        QMessageBox.warning(self, "Ошибка соединения", str(code))

    def _on_ws_message(self, data: dict):
        kind = data.get("respType", "")

        if kind == "success":
            text = data.get("successText", "")
            if text.startswith("User with ID"):
                self._authorize(text)
            else:
                log.info("Сервер: %s", text)

        elif kind == "iAm":
            user = data.get("user") or {}
            self._my_id = user.get("id")
            self._my_name = user.get("name", "")
            log.info("Моё id=%s, имя=%s", self._my_id, self._my_name)

        elif kind == "connectedUsers":
            users_raw = data.get("listOfUsers", [])
            for raw in users_raw:
                self.storage.add_user(User.from_dict(raw))
            self.storage.flush()
            self._render_chat_list()

        elif kind == "sendMessage":
            self._handle_incoming(data)

        elif kind == "error":
            log.warning("Сервер: %s", data.get("errorText"))

        else:
            log.info("Ответ: %s", data)

    def _authorize(self, text: str):
        if self._authorized:
            return
        self._authorized = True
        m = re.search(r"ID\s+(\d+)", text)
        if m:
            self._my_id = int(m.group(1))
        self.ws.who_am_i()
        self.ws.get_connected_users()
        self._auth.set_busy(False)
        self._show_page(PAGE_LIST)

    def _handle_incoming(self, data: dict):
        sender_raw = data.get("fromUser") or {}
        name = sender_raw.get("name", "")
        text = data.get("message", "")
        if not name:
            return

        sender = User.from_dict(sender_raw)

        # Пропускаем эхо собственных сообщений — мы их уже сохранили локально
        if self._my_id is not None and sender.id == self._my_id:
            log.info("Пропускаю эхо собственного сообщения")
            return

        self.storage.add_user(sender)
        self.storage.flush()

        is_broadcast = not (data.get("toUser") or data.get("userTo"))
        if is_broadcast:
            chat = Chat.general()
            self._store_and_render(chat, name, text, prefix="[общий] ")
        else:
            chat = Chat.direct(sender)
            self._store_and_render(chat, name, text)

        # Уведомление: если этот чат сейчас не открыт — счётчик, звук, мигание
        if not self._is_chat_active(chat.key):
            self._list.add_unread(chat.key)
            self._flash_window(name)
            self.sound.play()

        self._render_chat_list()

    # =================================================================
    #  Помощники
    # =================================================================

    def _is_chat_active(self, key: str) -> bool:
        if self._current_page != PAGE_CHAT:
            return False
        active = self._chat.chat
        return active is not None and active.key == key

    def _flash_window(self, from_name: str) -> None:
        if self.isActiveWindow():
            return
        self.setWindowTitle(f"● Новое сообщение от {from_name} — Messenger")
        QTimer.singleShot(5000, lambda: self.setWindowTitle("Messenger"))

    def _store_and_render(self, chat: Chat, author: str, text: str,
                          prefix: str = ""):
        self.storage.add_message(chat.key, author, text)
        self.storage.flush()

        active = self._chat.chat
        if active and active.key == chat.key:
            self._chat.append_message(author, text, prefix)

    # =================================================================
    #  Асинхронные задачи
    # =================================================================

    def _start(self):
        pass

    def _spawn(self, coro: Coroutine) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    @asyncClose
    async def closeEvent(self, event: Any):
        self.storage.flush()
        for t in tuple(self._tasks):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        event.accept()