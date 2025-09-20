import time
from typing import Optional
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtWidgets import QWidget, QApplication
from models import ColorLocation


class LocationPicker(QWidget):
    def __init__(self, parent=None, instruction_text="Click to set location"):
        super().__init__(parent)
        self.instruction_text = instruction_text
        self.setWindowFlags(
            Qt.WindowType(
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Dialog
            )
        )
        self.setWindowState(
            self.windowState() | Qt.WindowState(Qt.WindowState.WindowFullScreen)
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.selected_location: Optional[ColorLocation] = None

    def paintEvent(self, a0):
        painter = QPainter(self)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)

        text_rect = self.rect()
        text_rect.setHeight(100)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.instruction_text)

        painter.setPen(QColor(255, 255, 0))
        font.setPointSize(12)
        painter.setFont(font)

        help_text = "Click anywhere to set the color location. Press ESC to cancel."
        help_rect = self.rect()
        help_rect.setTop(120)
        help_rect.setHeight(50)
        painter.drawText(help_rect, Qt.AlignmentFlag.AlignCenter, help_text)

    def mousePressEvent(self, a0):
        pos = a0.globalPos()
        self.selected_location = ColorLocation(pos.x(), pos.y())
        self.close()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.selected_location = None
            self.close()
        super().keyPressEvent(a0)

    @staticmethod
    def get_location(
        parent=None, instruction_text="Click to set location"
    ) -> Optional[ColorLocation]:
        picker = LocationPicker(parent, instruction_text)
        picker.show()
        picker.exec_()
        return picker.selected_location

    def exec_(self):
        self.show()
        self.activateWindow()
        self.raise_()

        while self.isVisible():
            QApplication.processEvents()
            time.sleep(0.01)
