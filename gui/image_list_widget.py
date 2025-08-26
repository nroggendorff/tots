from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QMenu,
)
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PIL import Image
from utils import pil_to_qpixmap


class ImageListWidget(QWidget):
    draw_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, image_path: str, img: Image.Image, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.img = img
        self._setup_ui()
        self.setProperty("image_path", image_path)

    def _setup_ui(self):
        layout = QHBoxLayout()

        thumb = self.img.copy()
        thumb.thumbnail((120, 80))
        qpix = pil_to_qpixmap(thumb)
        thumb_label = QLabel()
        thumb_label.setPixmap(qpix)
        layout.addWidget(thumb_label)

        v_layout = QVBoxLayout()
        name_label = QLabel(
            self.image_path.split("/")[-1]
            if "/" in self.image_path
            else self.image_path
        )

        self.preview_label = QLabel()
        self.preview_label.setObjectName("preview_label")
        self.preview_label.setFixedSize(120, 120)
        self.preview_label.setStyleSheet("background-color: white;")

        draw_btn = QPushButton("Draw in selected region")
        draw_btn.clicked.connect(lambda: self.draw_requested.emit(self.image_path))

        v_layout.addWidget(name_label)
        v_layout.addWidget(self.preview_label)
        v_layout.addWidget(draw_btn)
        v_layout.addStretch()

        layout.addLayout(v_layout)
        self.setLayout(layout)

    def update_preview(self, preview_pixmap):
        image = preview_pixmap.toImage()

        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixel(x, y)
                color = QColor(pixel)

                if color.red() > 200 and color.green() < 100 and color.blue() < 100:
                    image.setPixel(x, y, QColor("white").rgb())

        processed_pixmap = QPixmap.fromImage(image)

        white_bg_pixmap = QPixmap(self.preview_label.size())
        white_bg_pixmap.fill(QColor("white"))

        painter = QPainter(white_bg_pixmap)
        x = (white_bg_pixmap.width() - processed_pixmap.width()) // 2
        y = (white_bg_pixmap.height() - processed_pixmap.height()) // 2
        painter.drawPixmap(x, y, processed_pixmap)
        painter.end()

        self.preview_label.setPixmap(white_bg_pixmap)

    def contextMenuEvent(self, a0):
        menu = QMenu(self)
        _ = menu.addAction("Remove")
        super().contextMenuEvent(a0)
