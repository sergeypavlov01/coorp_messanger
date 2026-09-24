"""Точка входа."""

import asyncio
import logging
import os
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from config import WS_URL
from main_window import MainWindow
HOST = os.getenv("HOST", "192.168.0.100")
PORT = os.getenv("PORT", "8080")
WS_URL = os.getenv("WS_URL", f"ws://{HOST}:{PORT}/chat")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main() -> int:
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow(app)
    window.show()

    with loop:
        loop.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())