from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np


def pil_to_qpixmap(pil_img):
    if pil_img.mode == "RGBA":
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
    else:
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        data = pil_img.tobytes("raw", "RGB")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


def process_image_for_drawing(
    img: Image.Image, region_w: int, region_h: int, threshold: int, brush_px: int
):
    try:
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255)[0])
            background.paste(
                img, mask=img.split()[3] if len(img.split()) == 4 else None
            )
            img_gray = background.convert("L")
        else:
            img_gray = img.convert("L")

        img_w, img_h = img_gray.size
        if img_w == 0 or img_h == 0:
            return None, None, 0, 0

        scale = min(region_w / img_w, region_h / img_h)
        target_w = max(1, int(img_w * scale))
        target_h = max(1, int(img_h * scale))

        img_resized = img_gray.resize((target_w, target_h), resample=Image.LANCZOS)
        print(f"Resized image shape: {img_resized.size}")
        arr = np.array(img_resized)
        if arr.size == 0:
            return None, None, 0, 0
        mask = arr < threshold
        return img_resized, mask, target_w, target_h
    except Exception as e:
        print(f"Error in process_image_for_drawing: {e}")
        return None, None, 0, 0


def generate_dot_positions(mask, target_w, target_h, brush_px, region):
    try:
        if mask is None or mask.size == 0:
            return []

        step = max(1, brush_px)
        positions = []

        for y in range(0, target_h, step):
            for x in range(0, target_w, step):
                if (
                    y < mask.shape[0]
                    and x < mask.shape[1]
                    and mask[min(y, mask.shape[0] - 1), min(x, mask.shape[1] - 1)]
                ):
                    offset_x = region.x + (region.w - target_w) // 2
                    offset_y = region.y + (region.h - target_h) // 2
                    sx = offset_x + x
                    sy = offset_y + y
                    positions.append((sx, sy))
        return positions
    except Exception as e:
        print(f"Error in generate_dot_positions: {e}")
        return []
