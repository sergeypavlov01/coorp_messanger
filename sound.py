"""Звуковое уведомление о новом сообщении."""

import logging

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from config import NOTIFY_SOUND

log = logging.getLogger(__name__)


class SoundNotifier:
    """Проигрывает короткий звук при новом входящем сообщении."""

    def __init__(self):
        self._effect: QSoundEffect | None = None

        if not NOTIFY_SOUND.exists():
            log.warning("Файл звука не найден: %s", NOTIFY_SOUND)
            return

        self._effect = QSoundEffect()
        self._effect.setSource(QUrl.fromLocalFile(str(NOTIFY_SOUND)))
        self._effect.setVolume(0.6)
        self._effect.statusChanged.connect(
            lambda s: log.info("QSoundEffect status: %s", s)
        )

    def play(self) -> None:
        if self._effect is None:
            return
        if self._effect.isPlaying():
            self._effect.stop()
        self._effect.play()