import threading
import numpy as np

from typing import Optional, List, Tuple
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFileDialog,
    QApplication,
    QShortcut,
    QGroupBox,
)
from PyQt5.QtGui import QPainter, QColor, QPixmap, QKeySequence
from PIL import Image

from models import Region, ColorLocation
from utils import (
    pil_to_qpixmap,
    process_image_for_multicolor_drawing,
    sample_color_at_location,
    rgb_to_luminance,
)
from gui.region_selector import RegionSelector
from gui.location_picker import LocationPicker
from gui.drawing_thread import DrawingThread
from gui.image_list_widget import ImageListWidget


class DotDrawerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dot Drawer")
        self.setMinimumSize(1000, 600)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.selected_region: Optional[Region] = None
        self.uploaded_images: List[Tuple[str, Image.Image]] = []

        self.color_locations = {"dark": None, "medium": None, "light": None}
        self.sampled_colors = {"dark": None, "medium": None, "light": None}

        self._stop_flag = threading.Event()
        self._draw_thread: Optional[DrawingThread] = None

        self._setup_ui()
        self._update_dot_preview()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        controls_layout = self._create_controls()
        left_layout.addLayout(controls_layout)

        self.img_list = QListWidget()
        self.img_list.setSpacing(6)
        right_layout.addWidget(self.img_list)

        buttons_layout = QHBoxLayout()
        right_layout.addLayout(buttons_layout)

        layout.addLayout(left_layout, 0)
        layout.addLayout(right_layout, 1)

    def _create_controls(self):
        controls = QVBoxLayout()
        controls_grid = QHBoxLayout()
        controls_col1 = QVBoxLayout()
        controls_col2 = QVBoxLayout()

        threshold_label = QLabel("Threshold:")
        threshold_label.setObjectName("sectionLabel")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(128)
        self.threshold_slider.valueChanged.connect(self._on_settings_changed)
        controls_col1.addWidget(threshold_label)
        controls_col1.addWidget(self.threshold_slider)

        brush_label = QLabel("Brush size:")
        brush_label.setObjectName("sectionLabel")
        self.brush_spin = QSpinBox()
        self.brush_spin.setRange(1, 200)
        self.brush_spin.setValue(6)
        self.brush_spin.valueChanged.connect(self._on_settings_changed)
        controls_col1.addWidget(brush_label)
        controls_col1.addWidget(self.brush_spin)

        region_btn = QPushButton("Select region")
        region_btn.clicked.connect(self.select_region)
        controls_col1.addWidget(region_btn)

        self.region_info_label = QLabel("Region: (not selected)")
        self.region_info_label.setStyleSheet(
            "color: #616161; font-size: 12px; margin-bottom: 4px;"
        )
        controls_col1.addWidget(self.region_info_label)

        color_group = QGroupBox("Color Locations")
        color_layout = QVBoxLayout()

        self.dark_btn = QPushButton("Set Color 1 (Darkest)")
        self.dark_btn.clicked.connect(lambda: self._pick_color_location("dark"))
        color_layout.addWidget(self.dark_btn)

        self.medium_btn = QPushButton("Set Color 2 (Medium)")
        self.medium_btn.clicked.connect(lambda: self._pick_color_location("medium"))
        color_layout.addWidget(self.medium_btn)

        self.light_btn = QPushButton("Set Color 3 (Lightest)")
        self.light_btn.clicked.connect(lambda: self._pick_color_location("light"))
        color_layout.addWidget(self.light_btn)

        clear_btn = QPushButton("Clear All Colors")
        clear_btn.clicked.connect(self._clear_all_colors)
        color_layout.addWidget(clear_btn)

        self.color_status_label = QLabel("No colors selected (will use black on white)")
        self.color_status_label.setStyleSheet(
            "color: #616161; font-size: 11px; margin-top: 4px;"
        )
        self.color_status_label.setWordWrap(True)
        color_layout.addWidget(self.color_status_label)

        color_group.setLayout(color_layout)
        controls_col1.addWidget(color_group)

        upload_btn = QPushButton("Upload image")
        upload_btn.clicked.connect(self.upload_image)
        controls_col1.addWidget(upload_btn)

        clipboard_btn = QPushButton("Upload from clipboard")
        clipboard_btn.clicked.connect(self.upload_from_clipboard)
        controls_col1.addWidget(clipboard_btn)

        note = QLabel("Drawing will move your mouse and click.")
        note.setWordWrap(True)
        note.setStyleSheet(
            "color: #b71c1c; font-size: 11px; background: #fff3e0; border-radius: 5px; padding: 4px 8px; margin-top: 8px;"
        )
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

        return controls

    def _pick_color_location(self, color_type):
        self.hide()
        QApplication.processEvents()
        location = LocationPicker.get_location(
            self, f"Click to set {color_type} color location"
        )
        self.show()
        self.setFocus()

        if location:
            self.color_locations[color_type] = location

            sampled_color = sample_color_at_location(location)
            if sampled_color:
                self.sampled_colors[color_type] = sampled_color
                print(f"Sampled color for {color_type}: {sampled_color}")

            self._update_color_status()
            self._update_all_previews()

    def _clear_all_colors(self):
        self.color_locations = {"dark": None, "medium": None, "light": None}
        self.sampled_colors = {"dark": None, "medium": None, "light": None}
        self._update_color_status()
        self._update_all_previews()

    def _update_color_status(self):
        status_parts = []
        active_colors = 0

        for color_type in ["dark", "medium", "light"]:
            loc = self.color_locations[color_type]
            sampled = self.sampled_colors[color_type]
            if loc and sampled:
                r, g, b = sampled
                luminance = rgb_to_luminance(sampled)
                status_parts.append(
                    f"{color_type.title()}: RGB({r},{g},{b}) L={luminance:.0f}"
                )
                active_colors += 1

        if active_colors == 0:
            self.color_status_label.setText(
                "No colors selected (will use black on white)"
            )
        else:
            status_text = f"Selected {active_colors} color(s):\n" + "\n".join(
                status_parts
            )
            self.color_status_label.setText(status_text)

    def focusInEvent(self, a0):
        super().focusInEvent(a0)

    def showEvent(self, a0):
        super().showEvent(a0)
        self.setFocus()
        self.activateWindow()
        self.raise_()

    def _generate_live_preview(self, img: Image.Image) -> QPixmap:
        try:
            threshold = self.threshold_slider.value()
            brush_px = self.brush_spin.value()

            target_w, target_h = (
                (self.selected_region.w, self.selected_region.h)
                if self.selected_region
                else (200, 200)
            )

            result = process_image_for_multicolor_drawing(
                img,
                target_w,
                target_h,
                threshold,
                brush_px,
                self.color_locations,
                self.sampled_colors,
            )

            if result is None:
                fallback = QPixmap(120, 120)
                fallback.fill(Qt.GlobalColor.white)
                return fallback

            img_resized, color_dots, active_colors = result

            final_w = img_resized.size[0]
            final_h = img_resized.size[1]

            preview_img = Image.new("RGB", (final_w, final_h), (255, 255, 255))
            dot_radius = max(1, brush_px // 3)

            np.random.seed(42)

            def draw_dots_with_preview_color(dots, preview_color):
                for x, y in dots:
                    for dy in range(-dot_radius, dot_radius + 1):
                        for dx in range(-dot_radius, dot_radius + 1):
                            if dx * dx + dy * dy <= dot_radius * dot_radius:
                                px = x + dx
                                py = y + dy
                                if (
                                    0 <= px < preview_img.width
                                    and 0 <= py < preview_img.height
                                ):
                                    preview_img.putpixel((px, py), preview_color)

            stages = [
                (color_name, dots) for color_name, dots in color_dots.items() if dots
            ]

            bg_color = None
            bg_rgb = (255, 255, 255)
            if stages:
                most_common_stage = max(stages, key=lambda s: len(s[1]))
                bg_color, bg_dots = most_common_stage
                stages = [(c, d) for (c, d) in stages if c != bg_color]

                if bg_color in active_colors:
                    bg_rgb = active_colors[bg_color]["rgb"]

            for color_name, dots in stages:
                if color_name in active_colors:
                    preview_color = active_colors[color_name]["rgb"]
                else:
                    preview_color = (0, 0, 0)

                draw_dots_with_preview_color(dots, preview_color)

            preview_img.thumbnail((120, 120), Image.Resampling.LANCZOS)

            final_preview = Image.new("RGB", (120, 120), bg_rgb)
            x_offset = (120 - preview_img.width) // 2
            y_offset = (120 - preview_img.height) // 2
            final_preview.paste(preview_img, (x_offset, y_offset))

            return pil_to_qpixmap(final_preview)

        except Exception as e:
            print(f"Error generating preview: {e}")
            fallback = QPixmap(120, 120)
            fallback.fill(Qt.GlobalColor.white)
            return fallback

    def _update_all_previews(self):
        try:
            for i in range(self.img_list.count()):
                item = self.img_list.item(i)
                widget = self.img_list.itemWidget(item)
                if isinstance(widget, ImageListWidget):
                    img = next(
                        (
                            im
                            for (p, im) in self.uploaded_images
                            if p == widget.image_path
                        ),
                        None,
                    )
                    if img:
                        preview_pixmap = self._generate_live_preview(img)
                        widget.update_preview(preview_pixmap)
        except Exception as e:
            print(f"Error updating previews: {e}")

    def _on_settings_changed(self):
        self._update_dot_preview()
        self._update_all_previews()

    def _update_dot_preview(self):
        size = self.dot_preview.size()
        pix = QPixmap(size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        brush_px = self.brush_spin.value()
        r = max(2, brush_px // 2)
        center = QPoint(size.width() // 2, size.height() // 2)
        painter.setBrush(QColor(30, 144, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, r, r)
        painter.end()
        self.dot_preview.setPixmap(pix)

    def select_region(self):
        self.hide()
        QApplication.processEvents()
        region = RegionSelector.get_region(self)
        self.show()
        self.setFocus()
        if region:
            self.selected_region = region
            self.region_info_label.setText(
                f"Region: x={region.x}, y={region.y}, w={region.w}, h={region.h}"
            )
            self._update_all_previews()
        else:
            self.region_info_label.setText("Region: (not selected)")

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not path:
            return
        self._load_image_from_path(path)

    def upload_from_clipboard(self):
        try:
            clipboard = QApplication.clipboard()
            pixmap = clipboard.pixmap()

            if pixmap.isNull():
                QMessageBox.information(
                    self, "No Image", "No image found in clipboard."
                )
                return

            qimg = pixmap.toImage()
            if qimg.format() != qimg.Format_ARGB32:
                qimg = qimg.convertToFormat(qimg.Format_ARGB32)

            width = qimg.width()
            height = qimg.height()
            ptr = qimg.bits()
            ptr.setsize(height * width * 4)

            arr = np.array(ptr).reshape((height, width, 4))
            arr = arr[:, :, [2, 1, 0, 3]]
            img = Image.fromarray(arr, "RGBA")

            path = f"clipboard_image_{len(self.uploaded_images)}"
            self.uploaded_images.append((path, img))
            self._add_image_list_item(path, img)

        except Exception as e:
            print(f"Error uploading from clipboard: {e}")
            QMessageBox.warning(
                self, "Error", f"Could not load image from clipboard: {e}"
            )

    def _load_image_from_path(self, path: str):
        try:
            img = Image.open(path)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open image: {e}")
            return
        self.uploaded_images.append((path, img))
        self._add_image_list_item(path, img)

    def _add_image_list_item(self, path: str, img: Image.Image):
        item = QListWidgetItem()
        widget = ImageListWidget(path, img, self)
        widget.draw_requested.connect(self._on_draw_clicked)
        widget.remove_requested.connect(self._remove_image)
        widget.update_preview(self._generate_live_preview(img))

        item.setSizeHint(widget.sizeHint())
        self.img_list.addItem(item)
        self.img_list.setItemWidget(item, widget)

    def _remove_image(self, image_path: str):
        self.uploaded_images = [
            (p, im) for (p, im) in self.uploaded_images if p != image_path
        ]

        for i in range(self.img_list.count()):
            item = self.img_list.item(i)
            widget = self.img_list.itemWidget(item)
            if isinstance(widget, ImageListWidget) and widget.image_path == image_path:
                self.img_list.takeItem(i)
                break

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
            self.region_info_label.setText(
                f"Region (auto): x={region.x}, y={region.y}, w={region.w}, h={region.h}"
            )

        brush_px = self.brush_spin.value()
        threshold = self.threshold_slider.value()

        display_name = image_path.split("/")[-1] if "/" in image_path else image_path

        active_color_count = sum(
            1 for loc in self.color_locations.values() if loc is not None
        )

        if active_color_count == 0:
            color_info = "\nColors: Black on white background (default)"
        else:
            color_info = f"\nUsing {active_color_count} selected color(s):"
            for color_type in ["dark", "medium", "light"]:
                loc = self.color_locations[color_type]
                sampled = self.sampled_colors[color_type]
                if loc and sampled:
                    r, g, b = sampled
                    luminance = rgb_to_luminance(sampled)
                    color_info += f"\n  {color_type.title()}: RGB({r},{g},{b}) L={luminance:.0f} at ({loc.x},{loc.y})"

        try:
            result = process_image_for_multicolor_drawing(
                img,
                region.w,
                region.h,
                threshold,
                brush_px,
                self.color_locations,
                self.sampled_colors,
            )

            bg_color_info = ""
            if result is not None:
                img_resized, color_dots, active_colors = result

                stages = [
                    (color_name, dots)
                    for color_name, dots in color_dots.items()
                    if dots
                ]

                if stages:
                    most_common_stage = max(stages, key=lambda s: len(s[1]))
                    bg_color, bg_dots = most_common_stage

                    if bg_color in active_colors:
                        bg_rgb = active_colors[bg_color]["rgb"]
                        bg_color_info = f"\nBackground: {bg_color.title()} RGB{bg_rgb} ({len(bg_dots)} dots - will be skipped)"
                    else:
                        bg_color_info = f"\nBackground: {bg_color.title()} ({len(bg_dots)} dots - will be skipped)"
                else:
                    bg_color_info = "\nBackground: White (no dots to draw)"
            else:
                bg_color_info = "\nBackground: Unable to determine"
        except Exception as e:
            print(f"Error determining background color: {e}")
            bg_color_info = "\nBackground: Unable to determine"

        confirm = QMessageBox.question(
            self,
            "Confirm Draw",
            f"Start drawing '{display_name}' in region x={region.x},y={region.y},w={region.w},h={region.h}?\n\n"
            f"Brush: {brush_px}px, Threshold: {threshold}{color_info}{bg_color_info}\n\n"
            "This will move your mouse and click. You'll get a 3s countdown to cancel.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self._draw_thread = DrawingThread(
            img,
            region,
            brush_px,
            threshold,
            self._stop_flag,
            self,
            self.color_locations,
        )
        self._draw_thread.start()
