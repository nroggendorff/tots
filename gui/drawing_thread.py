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
            start_x, start_y = points[0]
            pyautogui.moveTo(
                self.region.x + start_x, self.region.y + start_y, duration=0.02
            )

            pyautogui.mouseDown()

            for point in points[1:]:
                if self.stop_flag.is_set():
                    break

                px, py = point
                pyautogui.moveTo(self.region.x + px, self.region.y + py, duration=0.01)
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
            )

            if result is None:
                QApplication.beep()
                return

            img_resized, drawing_data, active_colors = result

            if not any(
                data["lines"] or data.get("scribbles", [])
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
                if data["lines"] or data.get("scribbles", [])
            ]

            bg_color = None
            bg_data = None
            if drawing_stages:
                most_common_stage = max(
                    drawing_stages,
                    key=lambda s: len(s[1]["lines"]) + len(s[1].get("scribbles", [])),
                )
                bg_color, bg_data = most_common_stage
                print(
                    f"Setting background color to '{bg_color}' "
                    f"({len(bg_data['lines'])} lines, {len(bg_data.get('scribbles', []))} scribbles) "
                    f"and skipping that stage"
                )
                self._click_color_location(bg_color)
                drawing_stages = [
                    (c, data) for (c, data) in drawing_stages if c != bg_color
                ]

            total_elements = sum(
                len(data["lines"]) + len(data.get("scribbles", []))
                for _, data in drawing_stages
            )
            elements_drawn = 0

            for stage_idx, (color_type, data) in enumerate(drawing_stages):
                if self.stop_flag.is_set():
                    break

                lines = data["lines"]
                scribbles = data.get("scribbles", [])

                print(
                    f"Starting {color_type} stage with {len(lines)} lines and {len(scribbles)} scribbles"
                )

                self._click_color_location(color_type)
                time.sleep(0.3)

                if self.stop_flag.is_set():
                    break

                for idx, line in enumerate(lines):
                    if self.stop_flag.is_set():
                        break

                    self._draw_line(line)
                    elements_drawn += 1

                    if idx % 10 == 0:
                        time.sleep(0.02)

                    if elements_drawn % 25 == 0:
                        print(
                            f"Progress: {elements_drawn}/{total_elements} elements ({color_type} stage)"
                        )

                for idx, scribble in enumerate(scribbles):
                    if self.stop_flag.is_set():
                        break

                    self._draw_line(scribble)
                    elements_drawn += 1

                    if idx % 20 == 0:
                        time.sleep(0.02)

                    if elements_drawn % 25 == 0:
                        print(
                            f"Progress: {elements_drawn}/{total_elements} elements ({color_type} stage)"
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
