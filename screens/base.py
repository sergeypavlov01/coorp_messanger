from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget


class BaseScreen(QObject):
    def __init__(self, widget: QWidget, parent: QObject | None = None):
        super().__init__(parent)
        self._widget = widget

    @property
    def widget(self) -> QWidget:
        return self._widget

    def show(self) -> None:
        self._widget.setVisible(True)

    def hide(self) -> None:
        self._widget.setVisible(False)

    def is_visible(self) -> bool:
        return self._widget.isVisible()