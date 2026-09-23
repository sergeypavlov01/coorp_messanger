import json

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebSockets import QWebSocket

class WebSocketClient(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_connected)
        self.ws.textMessageReceived.connect(self.on_message)
        self.ws.error.connect(self.on_error)

    def connect_to_server(self, url):
        self.ws.open(QUrl(url))

    def on_connected(self):
        print("Соединение установлено.")
        payload = {
            "regType": "setMyName",
            "newName": "MyNewBotName"
        }
        self.ws.sendTextMessage(json.dumps(payload))
        print(f"Отправлено: {json.dumps(payload)}")
    def on_message(self, message):
        print(f"Получено сообщение: {message}")

    def on_error(self):
        print(f"Ошибка соединения: {self.ws.errorString()}")