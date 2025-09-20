from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter
import pyautogui
import time


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


def sample_color_at_location(location):
    try:
        screenshot = pyautogui.screenshot()
        color = screenshot.getpixel((location.x, location.y))
        return color
    except Exception as e:
        print(f"Error sampling color at {location.x}, {location.y}: {e}")
        return None


def rgb_to_luminance(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def create_luminance_based_masks(img_array, color_sources, brush_px, threshold):
    smoothed = gaussian_filter(img_array.astype(float), sigma=0.5)

    active_colors = {}

    if not color_sources:
        black_mask = smoothed < threshold
        return {"black": black_mask}, {"black": {"rgb": (0, 0, 0), "luminance": 0}}

    for color_type, src in color_sources.items():
        if src is None:
            continue

        sampled_color = None

        if hasattr(src, "x") and hasattr(src, "y"):
            sampled_color = sample_color_at_location(src)
        elif isinstance(src, (tuple, list)) and len(src) == 3:
            try:
                sampled_color = tuple(int(c) for c in src)
            except Exception:
                sampled_color = None
        else:
            try:
                vals = tuple(int(c) for c in src)
                if len(vals) == 3:
                    sampled_color = vals
            except Exception:
                sampled_color = None

        if sampled_color:
            luminance = rgb_to_luminance(sampled_color)
            active_colors[color_type] = {"rgb": sampled_color, "luminance": luminance}

    if not active_colors:
        black_mask = smoothed < threshold
        return {"black": black_mask}, {"black": {"rgb": (0, 0, 0), "luminance": 0}}

    sorted_colors = sorted(active_colors.items(), key=lambda x: x[1]["luminance"])
    masks = {}

    if len(sorted_colors) == 1:
        color_name, color_data = sorted_colors[0]
        masks[color_name] = smoothed < threshold
    elif len(sorted_colors) == 2:
        dark_name, dark_data = sorted_colors[0]
        light_name, light_data = sorted_colors[1]

        luminance_range = light_data["luminance"] - dark_data["luminance"]
        if luminance_range < 20:
            base_threshold = threshold
        else:
            luminance_center = (dark_data["luminance"] + light_data["luminance"]) / 2
            threshold_offset = (threshold - 128) * 0.5
            base_threshold = luminance_center + threshold_offset

        masks[dark_name] = smoothed < base_threshold
        masks[light_name] = smoothed >= base_threshold
    else:
        dark_name, dark_data = sorted_colors[0]
        medium_name, medium_data = sorted_colors[1]
        light_name, light_data = sorted_colors[2]

        total_range = light_data["luminance"] - dark_data["luminance"]
        threshold_offset = (threshold - 128) * 0.3

        if total_range < 30:
            dark_threshold = threshold - 20
            light_threshold = threshold + 20
        else:
            dark_threshold = (
                dark_data["luminance"]
                + (medium_data["luminance"] - dark_data["luminance"]) * 0.7
                + threshold_offset
            )
            light_threshold = (
                medium_data["luminance"]
                + (light_data["luminance"] - medium_data["luminance"]) * 0.3
                + threshold_offset
            )

        masks[dark_name] = smoothed < dark_threshold
        masks[medium_name] = (smoothed >= dark_threshold) & (smoothed < light_threshold)
        masks[light_name] = smoothed >= light_threshold

    return masks, active_colors


def process_image_for_multicolor_drawing(
    img: Image.Image,
    region_w: int,
    region_h: int,
    threshold: int,
    brush_px: int,
    color_locations: dict = None,
    sampled_colors: dict = None,
    brightness_offset: int = 0,
):
    try:
        original_img = img.copy()

        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(
                img, mask=img.split()[3] if len(img.split()) == 4 else None
            )
            img_gray = background.convert("L")
            color_img = background
        else:
            if img.mode != "RGB":
                color_img = img.convert("RGB")
            else:
                color_img = img
            img_gray = img.convert("L")

        img_w, img_h = img_gray.size
        if img_w == 0 or img_h == 0:
            return None

        scale = min(region_w / img_w, region_h / img_h)
        target_w = max(1, int(img_w * scale))
        target_h = max(1, int(img_h * scale))

        img_resized_gray = img_gray.resize((target_w, target_h), resample=Image.LANCZOS)
        img_resized_color = color_img.resize(
            (target_w, target_h), resample=Image.LANCZOS
        )

        arr = np.array(img_resized_gray, dtype=np.int16)
        arr = np.clip(arr + brightness_offset, 0, 255).astype(np.uint8)

        if arr.size == 0:
            return None

        np.random.seed(42)

        source_for_masking = None
        if sampled_colors and any(v is not None for v in sampled_colors.values()):
            source_for_masking = sampled_colors
        elif color_locations and any(v is not None for v in color_locations.values()):
            source_for_masking = color_locations

        if source_for_masking:
            masks, active_colors = create_luminance_based_masks(
                arr, source_for_masking, brush_px, threshold
            )
        else:
            masks = {"black": arr < threshold}
            active_colors = {"black": {"rgb": (0, 0, 0), "luminance": 0}}

        color_dots = {}
        for color_name, mask in masks.items():
            positions = []
            spacing = max(brush_px // 2, 2)
            for y in range(0, target_h, spacing):
                for x in range(0, target_w, spacing):
                    if mask[y, x]:
                        positions.append((x, y))
            color_dots[color_name] = positions

        return img_resized_color, color_dots, active_colors

    except Exception as e:
        print(f"Error in process_image_for_multicolor_drawing: {e}")
        return None
