from PyQt5.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect


class ImuSoundEffect:
    def __init__(self, audio_file: str):
        self.sound_effect = QSoundEffect()
        self.sound_effect.setSource(QUrl.fromLocalFile(audio_file))
        self.sound_effect.setLoopCount(-2)

    def play(self):
        self.sound_effect.play()
