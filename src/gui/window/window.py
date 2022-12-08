from PyQt5.QtWidgets import QMainWindow
from src.gui.widget.widget import Widget
from typing import NoReturn


class Window(QMainWindow):
    def __init__(self, widget: Widget, title: str = "natKit") -> NoReturn:
        super().__init__()

        self.setWindowTitle(title)
        self.setCentralWidget(widget)
        self.widgets = [widget]
        widget.setLayout(widget.get_layout())

    def set_widget(self, widget: Widget) -> NoReturn:
        self.setCentralWidget(widget)
        self.widgets = [widget]

    def start_widgets(self) -> NoReturn:
        for widget in self.widgets:
            widget.start()

    def stop_widgets(self) -> NoReturn:
        for widget in self.widgets:
            widget.stop()
