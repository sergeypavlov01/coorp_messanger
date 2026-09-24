"""Управление темами."""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow

from config import DEFAULT_THEME, SETTINGS_APP, SETTINGS_ORG, THEMES


class ThemeManager:

    def __init__(self):
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        name = self._settings.value("theme", DEFAULT_THEME)
        self._current = name if name in THEMES else DEFAULT_THEME

    @property
    def current(self) -> str:
        return self._current

    def toggle(self) -> str:
        self._current = "light" if self._current == "dark" else "dark"
        self._settings.setValue("theme", self._current)
        return self._current

    def apply(self, window: QMainWindow, ui) -> None:
        t = THEMES[self._current]

        window.setStyleSheet(f"QMainWindow {{ background-color: {t['window']}; }}")
        ui.centralwidget.setStyleSheet(f"background-color: {t['window']};")

        for w in (ui.Auth, ui.Chat, ui.ListChats):
            w.setStyleSheet(f"background-color: {t['panel']}; border-radius: 18px;")

        for w in (ui.Menu, ui.Menu_2):
            w.setStyleSheet(
                f"background-color: {t['header']};"
                "border-radius: 0;"
                "border-top-left-radius: 18px;"
                "border-top-right-radius: 18px;"
            )

        ui.Messages.setStyleSheet(f"border: 1px solid {t['border']};")
        ui.List.setStyleSheet("background: transparent;")

        for lbl in (ui.label, ui.label_2, ui.label_3):
            lbl.setStyleSheet(f"color: {t['text']}; background: transparent;")

        edit_qss = (
            f"QLineEdit {{ background: {t['input_bg']}; color: {t['text']};"
            f" border: 1px solid {t['input_border']}; border-radius: 6px;"
            f" padding: 4px 8px; }}"
        )
        ui.lineEdit.setStyleSheet(edit_qss)
        ui.lineEdit_2.setStyleSheet(edit_qss)

        btn_qss = (
            f"QPushButton {{ background: {t['btn_bg']}; color: #ffffff;"
            f" border: 1px solid {t['border']}; border-radius: 6px;"
            f" padding: 4px 10px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {t['btn_hover']}; }}"
            f"QPushButton:disabled {{ background: {t['border']}; }}"
        )
        for b in (ui.pushButton, ui.pushButton_2, ui.pushButton_3,
                  ui.pushButton_add, ui.pushButton_theme, ui.pushButton_clear):
            b.setStyleSheet(btn_qss)

        ui.listChats.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none;"
            f" color: {t['text']}; font-size: 13px; }}"
            f"QListWidget::item {{ padding: 10px 14px;"
            f" border-bottom: 1px solid {t['list_line']}; }}"
            f"QListWidget::item:selected {{ background: {t['list_sel']}; }}"
        )

        ui.messages.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none;"
            f" color: {t['text']}; font-size: 13px; padding: 8px; }}"
        )

        ui.label_title.setStyleSheet(
            f"color: {t['text']}; font-size: 15px; background: transparent;"
        )
        ui.label_status.setStyleSheet(
            f"color: {t['muted']}; font-size: 11px; background: transparent;"
        )

        ui.pushButton_theme.setText(
            "Светлая тема" if self._current == "dark" else "Тёмная тема"
        )