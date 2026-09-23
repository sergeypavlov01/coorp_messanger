import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame, QMainWindow
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class WindowLogin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Авторизация")
