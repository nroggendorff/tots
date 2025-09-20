import threading
import time
import pyautogui
from PyQt5.QtWidgets import QApplication
from PIL import Image
from models import Region
from utils import process_image_for_drawing, generate_dot_positions


class DrawingThread(threading.Thread):
    def __init__(
        self,
        img: Image.Image,
        region: Region,
        brush_px: int,
        threshold: int,
        stop_flag: threading.Event,
        parent_widget,
    ):
        super().__init__()
        self.img = img.copy()
        self.region = region
        self.brush_px = brush_px
        self.threshold = threshold
        self.stop_flag = stop_flag
        self.parent_widget = parent_widget

    def run(self):
        try:
            result = process_image_for_drawing(
                self.img, self.region.w, self.region.h, self.threshold, self.brush_px
            )

            if result[0] is None:
                QApplication.beep()
                return

            img_resized, mask, target_w, target_h = result

            positions = generate_dot_positions(
                mask, target_w, target_h, self.brush_px, self.region
            )

            if not positions:
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

            for idx, (sx, sy) in enumerate(positions):
                if self.stop_flag.is_set():
                    break
                try:
                    pyautogui.moveTo(sx, sy, duration=0.02)
                    pyautogui.click()
                    if idx % 50 == 0:
                        time.sleep(0.05)
                except pyautogui.FailSafeException:
                    self.stop_flag.set()
                    break
                except Exception as e:
                    print(f"Error during click at {sx}, {sy}: {e}")
                    continue

        except Exception as e:
            print(f"Error while drawing: {e}")
        finally:
            if hasattr(self.parent_widget, "cancel_draw_btn"):
                self.parent_widget.cancel_draw_btn.setEnabled(False)
