from PySide6.QtCore import Signal

from screens.base import BaseScreen


class AuthScreen(BaseScreen):

    login_requested = Signal(str)

    def __init__(self, ui, parent=None):
        super().__init__(ui.Auth, parent)
        self._ui = ui

        ui.pushButton.clicked.connect(self._emit_login)
        ui.lineEdit.returnPressed.connect(self._emit_login)

    def set_last_username(self, name: str) -> None:
        if name:
            self._ui.lineEdit.setText(name)

    def set_busy(self, busy: bool) -> None:
        self._ui.pushButton.setEnabled(not busy)
        self._ui.pushButton.setText("Подключение" if busy else "Войти")

    def _emit_login(self) -> None:
        name = self._ui.lineEdit.text().strip()
        if name:
            self.login_requested.emit(name)