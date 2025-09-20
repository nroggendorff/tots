import threading
import time
import pyautogui
from PyQt5.QtWidgets import QApplication
from PIL import Image
from models import Region, ColorLocation
from utils import process_image_for_multicolor_drawing


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

    def run(self):
        try:
            result = process_image_for_multicolor_drawing(
                self.img,
                self.region.w,
                self.region.h,
                self.threshold,
                self.brush_px,
                self.color_locations,
                None,
                self.brightness_offset,
            )

            if result is None:
                QApplication.beep()
                return

            img_resized, color_dots, active_colors = result

            positions_dict = color_dots

            if not any(positions_dict.values()):
                QApplication.beep()
                return

            for i in range(3, 0, -1):
                if self.stop_flag.is_set():
                    return
                QApplication.beep()
                time.sleep(1)

            time.sleep(0.25)

            pyautogui.PAUSE = 0.01
            pyautogui.FAILSAFE = True

            drawing_stages = [
                (color_name, positions)
                for color_name, positions in positions_dict.items()
                if positions
            ]

            bg_color = None
            bg_positions = []
            if drawing_stages:
                most_common_stage = max(drawing_stages, key=lambda s: len(s[1]))
                bg_color, bg_positions = most_common_stage
                print(
                    f"Setting background color to '{bg_color}' ({len(bg_positions)} dots) and skipping that stage"
                )
                self._click_color_location(bg_color)
                drawing_stages = [
                    (c, pos) for (c, pos) in drawing_stages if c != bg_color
                ]
            total_dots = sum(len(positions) for _, positions in drawing_stages)
            dots_drawn = 0

            for stage_idx, (color_type, positions) in enumerate(drawing_stages):
                if self.stop_flag.is_set():
                    break

                print(f"Starting {color_type} stage with {len(positions)} positions")

                self._click_color_location(color_type)

                time.sleep(0.3)

                if self.stop_flag.is_set():
                    break

                for idx, (sx, sy) in enumerate(positions):
                    if self.stop_flag.is_set():
                        break

                    try:
                        pyautogui.moveTo(
                            self.region.x + sx, self.region.y + sy, duration=0.02
                        )
                        pyautogui.click()
                        dots_drawn += 1

                        if idx % 50 == 0:
                            time.sleep(0.05)

                        if dots_drawn % 100 == 0:
                            print(
                                f"Progress: {dots_drawn}/{total_dots} dots ({color_type} stage)"
                            )

                    except pyautogui.FailSafeException:
                        self.stop_flag.set()
                        break
                    except Exception as e:
                        print(f"Error during click at {sx}, {sy}: {e}")
                        continue

                print(f"Completed {color_type} stage")

                if stage_idx < len(drawing_stages) - 1:
                    time.sleep(0.5)

            print(f"Drawing complete. Drew {dots_drawn} dots total.")

        except Exception as e:
            print(f"Error while drawing: {e}")
        finally:
            if hasattr(self.parent_widget, "cancel_draw_btn"):
                self.parent_widget.cancel_draw_btn.setEnabled(False)
