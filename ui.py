from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMenuBar, QPushButton, QSizePolicy,
    QStatusBar, QTextEdit, QToolBar, QWidget)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1109, 892)

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        font14 = QFont()
        font14.setPointSize(14)
        font16 = QFont()
        font16.setPointSize(16)
        font9 = QFont()
        font9.setPointSize(9)

        # ----------------------------- Auth -----------------------------
        self.Auth = QWidget(self.centralwidget)
        self.Auth.setObjectName("Auth")
        self.Auth.setGeometry(QRect(0, 0, 431, 341))

        self.label = QLabel(self.Auth)
        self.label.setObjectName("label")
        self.label.setGeometry(QRect(90, 120, 100, 26))
        self.label.setFont(font14)

        self.lineEdit = QLineEdit(self.Auth)
        self.lineEdit.setObjectName("lineEdit")
        self.lineEdit.setGeometry(QRect(90, 150, 231, 31))
        self.lineEdit.setFont(font14)

        self.label_2 = QLabel(self.Auth)
        self.label_2.setObjectName("label_2")
        self.label_2.setGeometry(QRect(160, 60, 126, 28))
        self.label_2.setFont(font16)

        self.pushButton = QPushButton(self.Auth)
        self.pushButton.setObjectName("pushButton")
        self.pushButton.setGeometry(QRect(160, 240, 113, 36))
        self.pushButton.setFont(font14)

        # --------------------------- ListChats --------------------------
        self.ListChats = QWidget(self.centralwidget)
        self.ListChats.setObjectName("ListChats")
        self.ListChats.setGeometry(QRect(0, 0, 431, 461))

        self.Menu_2 = QFrame(self.ListChats)
        self.Menu_2.setObjectName("Menu_2")
        self.Menu_2.setGeometry(QRect(0, 0, 431, 61))
        self.Menu_2.setFrameShape(QFrame.Shape.StyledPanel)
        self.Menu_2.setFrameShadow(QFrame.Shadow.Raised)

        self.label_3 = QLabel(self.Menu_2)
        self.label_3.setObjectName("label_3")
        self.label_3.setGeometry(QRect(30, 18, 200, 26))
        self.label_3.setFont(font14)

        self.List = QWidget(self.ListChats)
        self.List.setObjectName("List")
        self.List.setGeometry(QRect(0, 60, 431, 401))

        self.pushButton_add = QPushButton(self.List)
        self.pushButton_add.setObjectName("pushButton_add")
        self.pushButton_add.setGeometry(QRect(10, 5, 200, 36))
        self.pushButton_add.setFont(font14)

        self.pushButton_theme = QPushButton(self.List)
        self.pushButton_theme.setObjectName("pushButton_theme")
        self.pushButton_theme.setGeometry(QRect(215, 5, 100, 36))
        self.pushButton_theme.setFont(font14)

        self.pushButton_clear = QPushButton(self.List)
        self.pushButton_clear.setObjectName("pushButton_clear")
        self.pushButton_clear.setGeometry(QRect(320, 5, 101, 36))
        self.pushButton_clear.setFont(font14)

        self.listChats = QListWidget(self.List)
        self.listChats.setObjectName("listChats")
        self.listChats.setGeometry(QRect(0, 50, 431, 351))
        self.listChats.setFont(font14)

        # ------------------------------ Chat ----------------------------
        self.Chat = QWidget(self.centralwidget)
        self.Chat.setObjectName("Chat")
        self.Chat.setGeometry(QRect(0, 0, 441, 591))

        self.Menu = QFrame(self.Chat)
        self.Menu.setObjectName("Menu")
        self.Menu.setGeometry(QRect(0, 0, 441, 61))
        self.Menu.setFrameShape(QFrame.Shape.StyledPanel)
        self.Menu.setFrameShadow(QFrame.Shadow.Raised)

        self.label_title = QLabel(self.Menu)
        self.label_title.setObjectName("label_title")
        self.label_title.setGeometry(QRect(20, 8, 280, 28))
        self.label_title.setFont(font14)

        self.label_status = QLabel(self.Menu)
        self.label_status.setObjectName("label_status")
        self.label_status.setGeometry(QRect(22, 36, 200, 18))
        self.label_status.setFont(font9)

        self.pushButton_3 = QPushButton(self.Menu)
        self.pushButton_3.setObjectName("pushButton_3")
        self.pushButton_3.setGeometry(QRect(320, 12, 91, 34))
        self.pushButton_3.setFont(font14)

        self.Messages = QWidget(self.Chat)
        self.Messages.setObjectName("Messages")
        self.Messages.setGeometry(QRect(10, 70, 421, 441))

        self.messages = QTextEdit(self.Messages)
        self.messages.setObjectName("messages")
        self.messages.setGeometry(QRect(0, 0, 421, 441))
        self.messages.setFont(font14)
        self.messages.setReadOnly(True)

        self.lineEdit_2 = QLineEdit(self.Chat)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.lineEdit_2.setGeometry(QRect(20, 530, 281, 41))
        self.lineEdit_2.setFont(font14)

        self.pushButton_2 = QPushButton(self.Chat)
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_2.setGeometry(QRect(320, 530, 101, 41))
        self.pushButton_2.setFont(font14)

        MainWindow.setCentralWidget(self.centralwidget)

        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 1109, 33))
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.toolBar = QToolBar(MainWindow)
        self.toolBar.setObjectName("toolBar")
        MainWindow.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolBar)

        self.retranslateUi(MainWindow)
        QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QCoreApplication.translate("MainWindow", "Messenger", None))
        self.label.setText(
            QCoreApplication.translate("MainWindow", "Логин", None))
        self.label_2.setText(
            QCoreApplication.translate("MainWindow", "Авторизация", None))
        self.pushButton.setText(
            QCoreApplication.translate("MainWindow", "Войти", None))
        self.label_3.setText(
            QCoreApplication.translate("MainWindow", "Список чатов", None))
        self.pushButton_add.setText(
            QCoreApplication.translate("MainWindow", "Добавить", None))
        self.pushButton_theme.setText(
            QCoreApplication.translate("MainWindow", "Сменить тему", None))
        self.pushButton_clear.setText(
            QCoreApplication.translate("MainWindow", "Очистить", None))
        self.label_title.setText(
            QCoreApplication.translate("MainWindow", "Чат", None))
        self.label_status.setText(
            QCoreApplication.translate("MainWindow", "online", None))
        self.pushButton_3.setText(
            QCoreApplication.translate("MainWindow", "Назад", None))
        self.lineEdit_2.setPlaceholderText(
            QCoreApplication.translate("MainWindow", "Сообщение", None))
        self.pushButton_2.setText(
            QCoreApplication.translate("MainWindow", "Отправить", None))
        self.toolBar.setWindowTitle(
            QCoreApplication.translate("MainWindow", "toolBar", None))