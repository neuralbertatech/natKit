from natKit.client.gui.pyqt6.event import Event

from PyQt6.QtWidgets import QApplication

from typing import NoReturn


class PlayBeep(Event):
    def __init__(self, debug: bool = False) -> NoReturn:
        self.debug = debug

    def start(self, layout) -> NoReturn:
        if self.debug:
            print("Playing Beep")
        QApplication.beep()

    def end(self) -> NoReturn:
        pass
