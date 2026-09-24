from html import escape

from PySide6.QtCore import Signal

from models import Chat
from screens.base import BaseScreen


class ChatScreen(BaseScreen):

    message_submitted = Signal(str)
    back_requested = Signal()

    def __init__(self, ui, parent=None):
        super().__init__(ui.Chat, parent)
        self._ui = ui
        self.chat: Chat | None = None

        ui.pushButton_2.clicked.connect(self._emit_send)
        ui.lineEdit_2.returnPressed.connect(self._emit_send)
        ui.pushButton_3.clicked.connect(self.back_requested.emit)

    def open_chat(self, chat: Chat) -> None:
        self.chat = chat
        self._ui.label_title.setText(chat.name)
        self._ui.label_status.setText(
            "трансляция" if chat.is_general else "online"
        )
        self.clear_messages()

    def clear_messages(self) -> None:
        self._ui.messages.clear()

    def render_messages(self, messages) -> None:
        self.clear_messages()
        for msg in messages:
            self._append_html(msg.author, msg.text)
        self._scroll_to_bottom()

    def append_message(self, author: str, text: str, prefix: str = "") -> None:
        self._append_html(f"{prefix}{author}", text)
        self._scroll_to_bottom()

    def clear_input(self) -> None:
        self._ui.lineEdit_2.clear()

    def _append_html(self, author: str, text: str) -> None:
        self._ui.messages.append(
            f"<b>{escape(author)}:</b> {escape(text)}"
        )

    def _scroll_to_bottom(self) -> None:
        bar = self._ui.messages.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _emit_send(self) -> None:
        text = self._ui.lineEdit_2.text().strip()
        if not text or self.chat is None:
            return
        self.clear_input()
        self.message_submitted.emit(text)