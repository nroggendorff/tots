import threading
import time
import pyautogui
from PyQt5.QtWidgets import QApplication
from PIL import Image
from models import Region, ColorLocation
from utils import process_image_for_edge_drawing


class DrawingThread(threading.Thread):
    def __init__(
        self,
        img: Image.Image,
        region: Region,
        brush_px: int,
        threshold: int,
        stop_flag: threading.Event,
        parent_widget,
        color_locations: dict = None,
        brightness_offset: int = 0,
        enable_fill: bool = False,
        straight_lines_only: bool = False,
        curve_resolution: int = 10,
    ):
        super().__init__()
        self.img = img.copy()
        self.region = region
        self.brush_px = brush_px
        self.threshold = threshold
        self.stop_flag = stop_flag
        self.parent_widget = parent_widget
        self.color_locations = color_locations or {}
        self.brightness_offset = brightness_offset
        self.enable_fill = enable_fill
        self.straight_lines_only = straight_lines_only
        self.curve_resolution = curve_resolution

    def _click_color_location(self, color_type: str):
        location = self.color_locations.get(color_type)

        if location:
            try:
                print(
                    f"Switching to {color_type} color at ({location.x}, {location.y})"
                )
                pyautogui.moveTo(location.x, location.y, duration=0.15)
                time.sleep(0.1)
                pyautogui.click()
                time.sleep(0.15)
                print(f"Successfully switched to {color_type} color")
            except Exception as e:
                print(f"Error clicking {color_type} color location: {e}")
        else:
            print(f"No {color_type} color location set")

    def _draw_line(self, points):
        if len(points) < 2:
            return

        try:
            if self.straight_lines_only:
                start_x, start_y = points[0]
                end_x, end_y = points[-1]

                print(
                    f"Drawing straight line: ({start_x},{start_y}) -> ({end_x},{end_y})"
                )

                pyautogui.moveTo(
                    self.region.x + start_x, self.region.y + start_y, duration=0.02
                )

                pyautogui.mouseDown()

                pyautogui.moveTo(
                    self.region.x + end_x, self.region.y + end_y, duration=0.1
                )

                pyautogui.mouseUp()
                time.sleep(0.1)
            else:
                start_x, start_y = points[0]
                pyautogui.moveTo(
                    self.region.x + start_x, self.region.y + start_y, duration=0.02
                )

                pyautogui.mouseDown()

                for point in points[1:]:
                    if self.stop_flag.is_set():
                        break

                    px, py = point
                    pyautogui.moveTo(
                        self.region.x + px, self.region.y + py, duration=0.01
                    )
                    time.sleep(0.005)

                pyautogui.mouseUp()
                time.sleep(0.01)

        except pyautogui.FailSafeException:
            self.stop_flag.set()
            pyautogui.mouseUp()
        except Exception as e:
            print(f"Error drawing line: {e}")
            pyautogui.mouseUp()

    def run(self):
        try:
            result = process_image_for_edge_drawing(
                self.img,
                self.region.w,
                self.region.h,
                self.threshold,
                self.brush_px,
                self.color_locations,
                None,
                self.brightness_offset,
                self.enable_fill,
                self.straight_lines_only,
                self.curve_resolution,
            )

            if result is None:
                QApplication.beep()
                return

            img_resized, drawing_data, active_colors = result

            print(f"Straight lines mode: {self.straight_lines_only}")
            print(f"Curve resolution: {self.curve_resolution}")
            for color_name, data in drawing_data.items():
                edge_count = len(data["edge_lines"])
                fill_count = len(data.get("fill_lines", []))
                print(f"{color_name}: {edge_count} edge lines, {fill_count} fill lines")

            if not any(
                data["edge_lines"] or data.get("fill_lines", [])
                for data in drawing_data.values()
            ):
                QApplication.beep()
                return

            for i in range(3, 0, -1):
                if self.stop_flag.is_set():
                    return
                QApplication.beep()
                time.sleep(1)

            time.sleep(0.25)

            pyautogui.PAUSE = 0.005
            pyautogui.FAILSAFE = True

            drawing_stages = [
                (color_name, data)
                for color_name, data in drawing_data.items()
                if data["edge_lines"] or data.get("fill_lines", [])
            ]

            bg_color = None
            bg_data = None
            if drawing_stages:
                most_common_stage = max(
                    drawing_stages,
                    key=lambda s: len(s[1]["edge_lines"])
                    + len(s[1].get("fill_lines", [])),
                )
                bg_color, bg_data = most_common_stage
                print(
                    f"Setting background color to '{bg_color}' "
                    f"({len(bg_data['edge_lines'])} edge lines, {len(bg_data.get('fill_lines', []))} fill lines) "
                    f"and skipping that stage"
                )
                self._click_color_location(bg_color)
                drawing_stages = [
                    (c, data) for (c, data) in drawing_stages if c != bg_color
                ]

            total_elements = sum(
                len(data["edge_lines"]) + len(data.get("fill_lines", []))
                for _, data in drawing_stages
            )
            elements_drawn = 0

            for stage_idx, (color_type, data) in enumerate(drawing_stages):
                if self.stop_flag.is_set():
                    break

                edge_lines = data["edge_lines"]
                fill_lines = data.get("fill_lines", [])

                print(
                    f"Starting {color_type} stage with {len(edge_lines)} edge lines and {len(fill_lines)} fill lines"
                )

                self._click_color_location(color_type)
                time.sleep(0.3)

                if self.stop_flag.is_set():
                    break

                for idx, line in enumerate(edge_lines):
                    if self.stop_flag.is_set():
                        break

                    self._draw_line(line)
                    elements_drawn += 1

                    if idx % 10 == 0:
                        time.sleep(0.02)

                    if elements_drawn % 25 == 0:
                        print(
                            f"Progress: {elements_drawn}/{total_elements} elements ({color_type} edge lines)"
                        )

                for idx, fill_line in enumerate(fill_lines):
                    if self.stop_flag.is_set():
                        break

                    self._draw_line(fill_line)
                    elements_drawn += 1

                    if idx % 20 == 0:
                        time.sleep(0.02)

                    if elements_drawn % 25 == 0:
                        print(
                            f"Progress: {elements_drawn}/{total_elements} elements ({color_type} fill lines)"
                        )

                print(f"Completed {color_type} stage")

                if stage_idx < len(drawing_stages) - 1:
                    time.sleep(0.5)

            print(f"Drawing complete. Drew {elements_drawn} elements total.")

        except Exception as e:
            print(f"Error while drawing: {e}")
        finally:
            if hasattr(self.parent_widget, "cancel_draw_btn"):
                self.parent_widget.cancel_draw_btn.setEnabled(False)
