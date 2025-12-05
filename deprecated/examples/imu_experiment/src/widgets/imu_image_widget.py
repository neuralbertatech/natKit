from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QWidget


class ImuImageWidget(QWidget):
    def __init__(self, imageFile: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.layout = QVBoxLayout()
        self.pixmap = QPixmap(imageFile)
        self.image_label = QLabel(self.layout)
        label.setPixmap(self.pixmap)
        self.setLayout(self.layout)

    def sizeHint(self):
        return QSize(40, 120)
