import time

from typing import Optional
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QWidget, QApplication
from models import Region


class RegionSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self._start = QPoint()
        self._end = QPoint()
        self._rubber = False
        self.selected_rect: Optional[QRect] = None

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setPen(QColor(30, 144, 255))
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if self._rubber:
            r = QRect(self._start, self._end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(r, QColor(0, 0, 0, 0))
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setPen(QColor(30, 144, 255))
            painter.drawRect(r)

    def mousePressEvent(self, a0):
        self._start = self._end = a0.pos()
        self._rubber = True
        self.update()

    def mouseMoveEvent(self, a0):
        if self._rubber:
            self._end = a0.pos()
            self.update()

    def mouseReleaseEvent(self, a0):
        self._end = a0.pos()
        self._rubber = False
        self.selected_rect = QRect(self._start, self._end).normalized()
        self.close()

    @staticmethod
    def get_region(parent=None) -> Optional[Region]:
        sel = RegionSelector(parent)
        sel.show()
        sel.exec_()
        if sel.selected_rect is not None:
            try:
                dpr = sel.devicePixelRatioF()
            except AttributeError:
                try:
                    dpr = sel.devicePixelRatio()
                except AttributeError:
                    dpr = 1.0

            r = sel.selected_rect
            return Region(
                int(r.x() * dpr),
                int(r.y() * dpr),
                int(r.width() * dpr),
                int(r.height() * dpr),
            )
        return None

    def exec_(self):
        self.show()
        self.activateWindow()
        self.raise_()

        while self.isVisible():
            QApplication.processEvents()
            time.sleep(0.01)
