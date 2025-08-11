

import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List

from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QPixmap, QPainter, QColor, QImage, QKeySequence
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QSlider, QSpinBox, QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QFrame, QGraphicsDropShadowEffect)

from PIL import Image, ImageOps
import numpy as np
import pyautogui

@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int

def pil_to_qpixmap(pil_img):
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QPixmap()
    qimg.loadFromData(data, "RGBA")
    return qimg

class RegionSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Dialog)
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._start, self._end = QPoint(), QPoint()
        self._rubber = False
        self.selected_rect: Optional[QRect] = None

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setPen(QColor(30, 144, 255))
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if self._rubber:
            r = QRect(self._start, self._end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(r, QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QColor(30, 144, 255))
            painter.drawRect(r)

    def mousePressEvent(self, ev):
        self._start = self._end = ev.pos(); self._rubber = True; self.update()
    def mouseMoveEvent(self, ev):
        if self._rubber: self._end = ev.pos(); self.update()
    def mouseReleaseEvent(self, ev):
        self._end = ev.pos(); self._rubber = False; self.selected_rect = QRect(self._start, self._end).normalized(); self.close()

    @staticmethod
    def get_region(parent=None) -> Optional[Region]:
        sel = RegionSelector(parent); sel.show(); sel.exec_loop()
        if sel.selected_rect:
            dpr = sel.devicePixelRatioF() if hasattr(sel, "devicePixelRatioF") else 1.0
            r = sel.selected_rect
            return Region(int(r.x()*dpr), int(r.y()*dpr), int(r.width()*dpr), int(r.height()*dpr))
        return None
    def exec_loop(self):
        while self.isVisible(): QApplication.processEvents(); time.sleep(0.01)

class DotDrawerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dot Drawer")
        self.setMinimumSize(1000, 600)

        self.setStyleSheet('')

        self.selected_region: Optional[Region] = None
        self.uploaded_images: List[Tuple[str, Image.Image]] = []

        layout = QHBoxLayout(self)
        left, right = QVBoxLayout(), QVBoxLayout()
        controls = QVBoxLayout()


        controls_grid = QHBoxLayout()
        controls_col1 = QVBoxLayout()
        controls_col2 = QVBoxLayout()

        thr_label = QLabel("Threshold:")
        thr_label.setObjectName("sectionLabel")
        self.thr_slider = QSlider(Qt.Horizontal)
        self.thr_slider.setRange(0, 255)
        self.thr_slider.setValue(128)
        self.thr_slider.valueChanged.connect(self._on_settings_changed)
        controls_col1.addWidget(thr_label)
        controls_col1.addWidget(self.thr_slider)

        brush_label = QLabel("Brush size:")
        brush_label.setObjectName("sectionLabel")
        self.brush_spin = QSpinBox()
        self.brush_spin.setRange(1, 200)
        self.brush_spin.setValue(6)
        self.brush_spin.valueChanged.connect(self._on_settings_changed)
        controls_col1.addWidget(brush_label)
        controls_col1.addWidget(self.brush_spin)

        self.infer_checkbox = QCheckBox("Infer brush size")
        self.infer_checkbox.stateChanged.connect(self._on_settings_changed)
        controls_col1.addWidget(self.infer_checkbox)

        region_btn = QPushButton("Select region")
        region_btn.clicked.connect(self.select_region)
        controls_col1.addWidget(region_btn)
        self.region_info_label = QLabel("Region: (not selected)")
        self.region_info_label.setStyleSheet("color: #616161; font-size: 12px; margin-bottom: 4px;")
        controls_col1.addWidget(self.region_info_label)

        upload_btn = QPushButton("Upload image")
        upload_btn.clicked.connect(self.upload_image)
        controls_col1.addWidget(upload_btn)

        note = QLabel("Drawing will move your mouse and click. Use Cancel to stop.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #b71c1c; font-size: 11px; background: #fff3e0; border-radius: 5px; padding: 4px 8px; margin-top: 8px;")
        controls_col1.addWidget(note)
        controls_col1.addStretch()

        dot_preview_label = QLabel("Dot preview:")
        dot_preview_label.setObjectName("sectionLabel")
        self.dot_preview = QLabel()
        self.dot_preview.setFixedSize(80, 80)
        controls_col2.addWidget(dot_preview_label)
        controls_col2.addWidget(self.dot_preview)
        controls_col2.addStretch()

        controls_grid.addLayout(controls_col1)
        controls_grid.addLayout(controls_col2)
        controls.addLayout(controls_grid)
        left.addLayout(controls)

        self.img_list = QListWidget()
        self.img_list.setSpacing(6)
        right.addWidget(self.img_list)

        btns_layout = QHBoxLayout()
        self.cancel_draw_btn = QPushButton("Cancel drawing")
        self.cancel_draw_btn.setStyleSheet("font-weight: bold; background: #e53935; color: white; margin-top: 10px;")
        self.cancel_draw_btn.clicked.connect(self._cancel_drawing)
        self.cancel_draw_btn.setEnabled(False)
        btns_layout.addWidget(self.cancel_draw_btn)
        right.addLayout(btns_layout)

        layout.addLayout(left, 0)
        layout.addLayout(right, 1)
        self.setLayout(layout)
        self._stop_flag = threading.Event(); self._draw_thread: Optional[threading.Thread] = None
        self._update_dot_preview()

        self.cancel_shortcut = QShortcut(QKeySequence("F7"), self)
        self.cancel_shortcut.activated.connect(self._cancel_drawing)

    def _generate_live_preview(self, img: Image.Image) -> QPixmap:
        threshold = self.thr_slider.value()
        brush_px = self.brush_spin.value()

        if self.selected_region:
            target_w, target_h = self.selected_region.w, self.selected_region.h
        else:
            target_w, target_h = 200, 200

        img_gray = ImageOps.grayscale(img)
        scale = min(target_w / img_gray.width, target_h / img_gray.height)
        img_resized = img_gray.resize(
            (max(1, int(img_gray.width * scale)), max(1, int(img_gray.height * scale))),
            Image.LANCZOS
        )
        arr = np.array(img_resized)
        mask = arr < threshold

        preview_img = Image.new("RGB", img_resized.size, (255, 255, 255))
        dot_radius = max(1, brush_px // 2)
        for y in range(0, img_resized.height, brush_px):
            for x in range(0, img_resized.width, brush_px):
                if mask[y, x]:
                    for dy in range(-dot_radius, dot_radius + 1):
                        for dx in range(-dot_radius, dot_radius + 1):
                            if dx*dx + dy*dy <= dot_radius*dot_radius:
                                px = x + dx
                                py = y + dy
                                if 0 <= px < preview_img.width and 0 <= py < preview_img.height:
                                    preview_img.putpixel((px, py), (0, 0, 0))

        preview_img.thumbnail((120, 120))
        data = preview_img.tobytes("raw", "RGB")
        qimg = QImage(data, preview_img.width, preview_img.height, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _update_all_previews(self):
        for i in range(self.img_list.count()):
            item = self.img_list.item(i)
            widget = self.img_list.itemWidget(item)
            if widget:
                img_path = widget.property("image_path")
                img = next((im for (p, im) in self.uploaded_images if p == img_path), None)
                if img:
                    preview_label: QLabel = widget.findChild(QLabel, "preview_label")
                    if preview_label:
                        preview_label.setPixmap(self._generate_live_preview(img))

    def _on_settings_changed(self):
        self._update_dot_preview()
        self._update_all_previews()

    def _update_dot_preview(self):
        size = self.dot_preview.size()
        pix = QPixmap(size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        brush_px = self.brush_spin.value()
        r = max(2, brush_px // 2)
        center = QPoint(size.width() // 2, size.height() // 2)
        painter.setBrush(QColor(30, 144, 255))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, r, r)
        painter.end()
        self.dot_preview.setPixmap(pix)

    def select_region(self):
        self.hide()
        QApplication.processEvents()
        sel = RegionSelector.get_region(self)
        self.show()
        if sel:
            self.selected_region = sel
            self.region_info_label.setText(f"Region: x={sel.x}, y={sel.y}, w={sel.w}, h={sel.h}")
        else:
            self.region_info_label.setText("Region: (not selected)")

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open image: {e}")
            return
        self.uploaded_images.append((path, img))
        self._add_image_list_item(path, img)

    def _add_image_list_item(self, path, img: Image.Image):
        item = QListWidgetItem()
        widget = QWidget()
        h = QHBoxLayout()

        thumb = img.copy()
        thumb.thumbnail((120, 80))
        qpix = pil_to_qpixmap(thumb)
        thumb_label = QLabel()
        thumb_label.setPixmap(qpix)
        h.addWidget(thumb_label)

        v = QVBoxLayout()
        name_label = QLabel(path.split("/")[-1])

        preview_label = QLabel()
        preview_label.setObjectName("preview_label")
        preview_label.setFixedSize(120, 120)
        preview_label.setPixmap(self._generate_live_preview(img))

        draw_btn = QPushButton("Draw in selected region")
        draw_btn.clicked.connect(lambda _, p=path: self._on_draw_clicked(p))

        v.addWidget(name_label)
        v.addWidget(preview_label)
        v.addWidget(draw_btn)
        v.addStretch()

        widget.setLayout(h)
        h.addLayout(v)
        widget.setProperty("image_path", path)

        item.setSizeHint(widget.sizeHint())
        self.img_list.addItem(item)
        self.img_list.setItemWidget(item, widget)

    def _on_draw_clicked(self, image_path: str):
        img = next((im for (p, im) in self.uploaded_images if p == image_path), None)
        if img is None:
            QMessageBox.warning(self, "Error", "Image not found.")
            return

        region = self.selected_region
        if region is None:
            screen = QApplication.primaryScreen().geometry()
            s_w, s_h = screen.width(), screen.height()
            side = min(s_w, s_h)
            x = (s_w - side) // 2
            y = (s_h - side) // 2
            region = Region(x, y, side, side)
            self.selected_region = region
            self.region_info_label.setText(f"Region (auto): x={region.x}, y={region.y}, w={region.w}, h={region.h}")

        brush_px = self.brush_spin.value()
        if self.infer_checkbox.isChecked():
            img_w, img_h = img.size
            r_w, r_h = region.w, region.h
            scale = min(r_w / img_w, r_h / img_h)
            inferred = max(2, int(round(1 / scale))) if scale < 1 else max(2, int(round(2 / scale)))
            brush_px = min(max(inferred, 1), 200)
            self.brush_spin.setValue(brush_px)

        threshold = self.thr_slider.value()

        confirm = QMessageBox.question(self, "Confirm Draw",
                                       f"Start drawing '{image_path.split('/')[-1]}' in region x={region.x},y={region.y},w={region.w},h={region.h}?\n\n"
                                       f"Brush: {brush_px}px, Threshold: {threshold}\n\n"
                                       "This will move your mouse and click. You'll get a 3s countdown to cancel.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        self._stop_flag.clear()
        self.cancel_draw_btn.setEnabled(True)
        self._draw_thread = threading.Thread(target=self._draw_image_in_region, args=(img.copy(), region, brush_px, threshold))
        self._draw_thread.start()

    def _cancel_drawing(self):
        self._stop_flag.set()
        self.cancel_draw_btn.setEnabled(False)

    def _draw_image_in_region(self, img: Image.Image, region: Region, brush_px: int, threshold: int):
        try:
            img_gray = ImageOps.grayscale(img)
            img_w, img_h = img_gray.size
            scale = min(region.w / img_w, region.h / img_h)
            target_w = max(1, int(img_w * scale))
            target_h = max(1, int(img_h * scale))
            img_resized = img_gray.resize((target_w, target_h), resample=Image.LANCZOS)

            arr = np.array(img_resized)
            mask = arr < threshold 

            step = max(1, brush_px)
            positions = []
            for y in range(0, target_h, step):
                for x in range(0, target_w, step):
                    if mask[y, x]:
                        offset_x = region.x + (region.w - target_w) // 2
                        offset_y = region.y + (region.h - target_h) // 2
                        sx = offset_x + x
                        sy = offset_y + y
                        positions.append((sx, sy))

            if not positions:
                QMessageBox.information(self, "Nothing to draw", "No dark pixels found with current threshold/brush settings.")
                self.cancel_draw_btn.setEnabled(False)
                return
            for i in range(3, 0, -1):
                if self._stop_flag.is_set():
                    self.cancel_draw_btn.setEnabled(False)
                    return
                QApplication.beep()
                time.sleep(1)

            time.sleep(0.25)

            pyautogui.PAUSE = 0.01
            pyautogui.FAILSAFE = True

            for idx, (sx, sy) in enumerate(positions):
                if self._stop_flag.is_set():
                    break
                try:
                    pyautogui.moveTo(sx, sy, duration=0.02)
                    pyautogui.click()
                    if idx % 50 == 0:
                        time.sleep(0.05)
                except pyautogui.FailSafeException:
                    self._stop_flag.set()
                    break

            self.cancel_draw_btn.setEnabled(False)
            QMessageBox.information(self, "Done", "Drawing finished (or cancelled).")

        except Exception as e:
            self.cancel_draw_btn.setEnabled(False)
            QMessageBox.critical(self, "Error while drawing", str(e))

def main():
    app = QApplication(sys.argv)
    win = DotDrawerApp()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
