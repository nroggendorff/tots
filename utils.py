from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter


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


def create_dot_mask(img_array, threshold, brush_px):

    smoothed = gaussian_filter(img_array.astype(float), sigma=0.5)

    kernel_size = max(3, brush_px // 2)
    if kernel_size % 2 == 0:
        kernel_size += 1

    from scipy.ndimage import uniform_filter

    local_mean = uniform_filter(smoothed, size=kernel_size)

    global_mask = smoothed < threshold
    adaptive_mask = smoothed < (local_mean - 10)

    combined_mask = global_mask | (adaptive_mask & (smoothed < threshold + 30))

    return combined_mask


def clean_dot_positions(mask, brush_px, target_w, target_h):
    positions = []

    spacing = max(brush_px // 2, 2)

    jitter_range = max(1, spacing // 4)

    for y in range(spacing // 2, target_h - spacing // 2, spacing):
        for x in range(spacing // 2, target_w - spacing // 2, spacing):

            if y < mask.shape[0] and x < mask.shape[1] and mask[y, x]:

                if jitter_range > 0:
                    jx = np.random.randint(-jitter_range, jitter_range + 1)
                    jy = np.random.randint(-jitter_range, jitter_range + 1)

                    final_x = np.clip(x + jx, 0, target_w - 1)
                    final_y = np.clip(y + jy, 0, target_h - 1)
                else:
                    final_x, final_y = x, y

                if (
                    final_y < mask.shape[0]
                    and final_x < mask.shape[1]
                    and mask[final_y, final_x]
                ):
                    positions.append((final_x, final_y))

    return positions


def process_image_for_drawing(
    img: Image.Image, region_w: int, region_h: int, threshold: int, brush_px: int
):
    try:
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
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

        mask = create_dot_mask(arr, threshold, brush_px)

        return img_resized, mask, target_w, target_h

    except Exception as e:
        print(f"Error in process_image_for_drawing: {e}")
        return None, None, 0, 0


def generate_dot_positions(
    mask, target_w, target_h, brush_px, region, edge_strength=None
):
    try:
        if mask is None or mask.size == 0:
            return []

        np.random.seed(42)

        positions = clean_dot_positions(mask, brush_px, target_w, target_h)

        screen_positions = []
        for x, y in positions:
            offset_x = region.x + (region.w - target_w) // 2
            offset_y = region.y + (region.h - target_h) // 2
            sx = offset_x + x
            sy = offset_y + y
            screen_positions.append((sx, sy))

        print(f"Generated {len(screen_positions)} dot positions")
        return screen_positions

    except Exception as e:
        print(f"Error in generate_dot_positions: {e}")
        return []
