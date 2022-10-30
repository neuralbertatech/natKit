from PyQt5.QtWidgets import QWidget
from typing import NoReturn


class Widget(QWidget):
    def __init__(self):
        super().__init__()

    def start(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def stop(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def on_tick(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"
