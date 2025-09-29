from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy import ndimage
import pyautogui
import time
from skimage import feature


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


def detect_edges(img_array, threshold, brush_px):
    smoothed = gaussian_filter(img_array.astype(float), sigma=max(0.5, brush_px / 8))

    edges = feature.canny(
        smoothed,
        low_threshold=threshold * 0.3,
        high_threshold=threshold,
        sigma=max(0.8, brush_px / 6),
    )

    return edges.astype(bool)


def trace_edge_lines(edge_mask, min_line_length=5):
    lines = []
    visited = np.zeros_like(edge_mask, dtype=bool)

    def get_neighbors(y, x):
        neighbors = []
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if (
                    0 <= ny < edge_mask.shape[0]
                    and 0 <= nx < edge_mask.shape[1]
                    and edge_mask[ny, nx]
                    and not visited[ny, nx]
                ):
                    neighbors.append((ny, nx))
        return neighbors

    def trace_line(start_y, start_x):
        line = [(start_x, start_y)]
        visited[start_y, start_x] = True
        current_y, current_x = start_y, start_x

        while True:
            neighbors = get_neighbors(current_y, current_x)
            if not neighbors:
                break

            next_y, next_x = neighbors[0]
            line.append((next_x, next_y))
            visited[next_y, next_x] = True
            current_y, current_x = next_y, next_x

        return line

    for y in range(edge_mask.shape[0]):
        for x in range(edge_mask.shape[1]):
            if edge_mask[y, x] and not visited[y, x]:
                line = trace_line(y, x)
                if len(line) >= min_line_length:
                    lines.append(line)

    return lines


def generate_fill_scribbles(mask, brush_px, density_factor=0.7):
    scribbles = []
    spacing = max(2, int(brush_px * density_factor))

    for y in range(0, mask.shape[0], spacing):
        row_points = []
        for x in range(mask.shape[1]):
            if mask[y, x]:
                row_points.append((x, y))

        if len(row_points) >= 2:
            i = 0
            while i < len(row_points):
                scribble_start = i
                while (
                    i < len(row_points) - 1
                    and row_points[i + 1][0] - row_points[i][0] <= spacing * 2
                ):
                    i += 1

                if i > scribble_start:
                    scribble_line = row_points[scribble_start : i + 1]
                    if len(scribble_line) >= 3:
                        scribbles.append(scribble_line)
                i += 1

    return scribbles


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


def break_line_into_segments(line, max_segment_length):
    if len(line) < 2:
        return [line] if line else []

    segments = []
    current_start = line[0]

    for i in range(1, len(line)):
        current_point = line[i]

        dx = current_point[0] - current_start[0]
        dy = current_point[1] - current_start[1]
        distance = (dx * dx + dy * dy) ** 0.5

        if distance >= max_segment_length:
            segments.append([current_start, current_point])
            current_start = current_point

    if len(segments) == 0:
        segments.append([line[0], line[-1]])
    elif current_start != segments[-1][-1]:
        segments.append([segments[-1][-1], line[-1]])

    valid_segments = [seg for seg in segments if len(seg) >= 2]

    print(
        f"Original line with {len(line)} points broken into {len(valid_segments)} straight segments"
    )

    return valid_segments if valid_segments else [[line[0], line[-1]]]


def process_image_for_edge_drawing(
    img: Image.Image,
    region_w: int,
    region_h: int,
    threshold: int,
    brush_px: int,
    color_locations: dict = None,
    sampled_colors: dict = None,
    brightness_offset: int = 0,
    enable_fill: bool = False,
    straight_lines_only: bool = False,
    curve_resolution: int = 10,
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

        drawing_data = {}

        for color_name, mask in masks.items():
            color_drawing_data = {"edge_lines": [], "fill_lines": []}

            edges = detect_edges(arr * mask.astype(float), threshold, brush_px)
            lines = trace_edge_lines(edges, min_line_length=max(3, brush_px // 2))

            print(f"Original {color_name}: {len(lines)} lines")

            if straight_lines_only:
                print(
                    f"Breaking lines into segments with max length: {curve_resolution}"
                )
                segmented_lines = []
                for line_idx, line in enumerate(lines):
                    segments = break_line_into_segments(line, curve_resolution)
                    segmented_lines.extend(segments)
                    if line_idx == 0:
                        print(
                            f"First line: {len(line)} points -> {len(segments)} segments"
                        )
                lines = segmented_lines
                print(f"After segmentation {color_name}: {len(lines)} line segments")

            color_drawing_data["edge_lines"] = lines

            if enable_fill:
                scribbles = generate_fill_scribbles(mask, brush_px)
                print(f"Original {color_name} fill: {len(scribbles)} scribbles")

                if straight_lines_only:
                    segmented_scribbles = []
                    for scribble in scribbles:
                        segments = break_line_into_segments(scribble, curve_resolution)
                        segmented_scribbles.extend(segments)
                    scribbles = segmented_scribbles
                    print(
                        f"After segmentation {color_name} fill: {len(scribbles)} scribble segments"
                    )

                color_drawing_data["fill_lines"] = scribbles

            drawing_data[color_name] = color_drawing_data

        return img_resized_color, drawing_data, active_colors

    except Exception as e:
        print(f"Error in process_image_for_edge_drawing: {e}")
        return None


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
