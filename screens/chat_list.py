from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidgetItem

from models import Chat, User
from screens.base import BaseScreen


class ChatListScreen(BaseScreen):

    chat_selected = Signal(Chat)
    add_chat_requested = Signal()
    theme_requested = Signal()
    clear_requested = Signal(Chat)

    def __init__(self, ui, parent=None):
        super().__init__(ui.ListChats, parent)
        self._ui = ui
        self._list = ui.listChats
        self._unread: dict[str, int] = {}

        ui.pushButton_add.clicked.connect(self.add_chat_requested.emit)
        ui.pushButton_theme.clicked.connect(self.theme_requested.emit)
        ui.pushButton_clear.clicked.connect(self._emit_clear)
        self._list.itemClicked.connect(self._on_item_clicked)

    def render(self, users: list[User]) -> None:
        selected_key = self._selected_key()

        self._list.blockSignals(True)
        self._list.clear()
        self._append_chat(Chat.general())
        for user in users:
            self._append_chat(Chat.direct(user))
        self._restore_selection(selected_key)
        self._list.blockSignals(False)

    def select_chat(self, key: str) -> None:
        for i in range(self._list.count()):
            chat = self._chat_at(i)
            if chat and chat.key == key:
                self._list.setCurrentRow(i)
                return

    def add_unread(self, key: str) -> None:
        self._unread[key] = self._unread.get(key, 0) + 1
        for i in range(self._list.count()):
            chat = self._chat_at(i)
            if chat and chat.key == key:
                self._list.item(i).setText(
                    f"{chat.name}  ({self._unread[key]})"
                )
                return

    def clear_unread(self, key: str) -> None:
        self._unread.pop(key, None)
        for i in range(self._list.count()):
            chat = self._chat_at(i)
            if chat and chat.key == key:
                self._list.item(i).setText(chat.name)
                return

    def _append_chat(self, chat: Chat) -> None:
        label = chat.name
        if chat.key in self._unread:
            label = f"{chat.name}  ({self._unread[chat.key]})"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, chat.to_payload())
        self._list.addItem(item)

    def _chat_at(self, index: int) -> Chat | None:
        item = self._list.item(index)
        if item is None:
            return None
        return Chat.from_payload(item.data(Qt.UserRole) or {})

    def _selected_key(self) -> str | None:
        row = self._list.currentRow()
        if row < 0:
            return None
        chat = self._chat_at(row)
        return chat.key if chat else None

    def _restore_selection(self, key: str | None) -> None:
        if key:
            self.select_chat(key)

    def _emit_clear(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        chat = self._chat_at(row)
        if chat:
            self.clear_requested.emit(chat)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.UserRole) or {}
        self.chat_selected.emit(Chat.from_payload(payload))