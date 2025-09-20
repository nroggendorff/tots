from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtGui import QPixmap, QPainter


class ImageListWidget(QWidget):
    draw_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, image_path, image, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.image = image
        self.parent = parent

        layout = QHBoxLayout(self)
        self.preview = QLabel()
        self.preview.setFixedSize(120, 120)
        self.preview.setStyleSheet("background: white; border: 1px solid #ddd;")
        layout.addWidget(self.preview)

        info_layout = QVBoxLayout()
        self.path_label = QLabel(image_path.split("/")[-1])
        self.path_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.path_label)

        btn_layout = QHBoxLayout()
        self.draw_btn = QPushButton("Draw")
        self.draw_btn.clicked.connect(self._on_draw_clicked)
        btn_layout.addWidget(self.draw_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        btn_layout.addWidget(self.remove_btn)

        info_layout.addLayout(btn_layout)
        layout.addLayout(info_layout)

    def update_preview(self, pixmap: QPixmap):
        if pixmap is not None:
            preview_size = self.preview.size()
            bg = QPixmap(preview_size)
            bg.fill(self.palette().base().color())
            painter = QPainter(bg)
            x = (preview_size.width() - pixmap.width()) // 2
            y = (preview_size.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
            painter.end()
            self.preview.setPixmap(bg)
        else:
            self.preview.clear()

    def _on_draw_clicked(self):
        self.draw_requested.emit(self.image_path)

    def _on_remove_clicked(self):
        self.remove_requested.emit(self.image_path)
