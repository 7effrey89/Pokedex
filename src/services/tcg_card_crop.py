"""Card-boundary detection and consistent framing for learned embeddings."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageOps

from src.services.tcg_image_index import CARD_ASPECT_RATIO, crop_to_card_aspect

CROP_VERSION = "perspective-full-card-inset2-square-v1"
MIN_LANDSCAPE_AREA_IN_PORTRAIT_FRAME = 0.27


def rectify_card(image: Image.Image, *, reference: bool = False) -> tuple[Image.Image, dict]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if reference:
        return crop_to_card_aspect(image), {"method": "catalog_card", "detected": True}
    scaled = image.copy()
    scaled.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
    pixels = np.asarray(scaled)
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    height, width = gray.shape
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour) / (width * height)
        if not 0.18 <= area <= 0.99:
            continue
        perimeter = cv2.arcLength(contour, True)
        for epsilon in (0.02, 0.03, 0.04):
            polygon = cv2.approxPolyDP(contour, epsilon * perimeter, True)
            if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                continue
            points = polygon[:, 0, :].astype(np.float32)
            center = points.mean(axis=0)
            angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
            points = points[np.argsort(angles)]
            points = np.roll(points, -int(np.argmin(points.sum(axis=1))), axis=0)
            lengths = np.linalg.norm(points - np.roll(points, -1, axis=0), axis=1)
            card_width = (lengths[0] + lengths[2]) / 2
            card_height = (lengths[1] + lengths[3]) / 2
            if card_width > card_height:
                if height > width and area < MIN_LANDSCAPE_AREA_IN_PORTRAIT_FRAME:
                    continue
                points = np.roll(points, -1, axis=0)
                card_width, card_height = card_height, card_width
            ratio = card_width / card_height
            if not 0.53 <= ratio <= 0.91 or lengths.min() < 30:
                continue
            rectangularity = cv2.contourArea(polygon) / (card_width * card_height)
            if rectangularity < 0.65:
                continue
            distance = np.linalg.norm(center / (width, height) - 0.5)
            score = area - abs(ratio - CARD_ASPECT_RATIO) * 0.2 - distance * 0.1
            candidates.append((score, points, "perspective"))
            break
    if not candidates:
        hsv = cv2.cvtColor(pixels, cv2.COLOR_RGB2HSV)
        kernel_size = max(5, round(min(width, height) * 0.014) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        for hue_center in range(0, 180, 15):
            low, high = (hue_center - 30) % 180, (hue_center + 30) % 180
            lower, upper = (low, 35, 25), (high, 255, 255)
            mask = cv2.inRange(hsv, lower, upper) if low <= high else cv2.bitwise_or(
                cv2.inRange(hsv, (0, 35, 25), upper),
                cv2.inRange(hsv, lower, (179, 255, 255)),
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            color_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in color_contours:
                mask_area = cv2.contourArea(contour) / (width * height)
                if mask_area < 0.12:
                    continue
                rectangle = cv2.minAreaRect(contour)
                (center_x, center_y), (rect_width, rect_height), _ = rectangle
                if min(rect_width, rect_height) < 1:
                    continue
                ratio = min(rect_width, rect_height) / max(rect_width, rect_height)
                rect_area = rect_width * rect_height
                rectangularity = cv2.contourArea(contour) / rect_area
                if not 0.53 <= ratio <= 0.91 or rectangularity < 0.25:
                    continue
                if not 0.12 <= rect_area / (width * height) <= 0.95:
                    continue
                points = cv2.boxPoints(rectangle).astype(np.float32)
                if (points[:, 0].min() < 0 or points[:, 1].min() < 0
                        or points[:, 0].max() >= width or points[:, 1].max() >= height):
                    continue
                span = np.ptp(points, axis=0)
                if (height > width and span[0] > span[1]
                        and rect_area / (width * height) < MIN_LANDSCAPE_AREA_IN_PORTRAIT_FRAME):
                    continue
                center = points.mean(axis=0)
                angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
                points = points[np.argsort(angles)]
                points = np.roll(points, -int(np.argmin(points.sum(axis=1))), axis=0)
                distance = np.linalg.norm(np.asarray((center_x / width, center_y / height)) - 0.5)
                score = (
                    rect_area / (width * height)
                    + rectangularity * 0.1
                    - abs(ratio - CARD_ASPECT_RATIO) * 4.0
                    - distance * 0.05
                )
                candidates.append((score, points, "color_segmentation"))
        if not candidates:
            return crop_to_card_aspect(image), {
                "method": "guide_fallback", "detected": False,
                "warning": "No reliable card boundary found. Fill the guide with the card and avoid glare.",
            }
    _, points, method = max(candidates, key=lambda candidate: candidate[0])
    points *= np.asarray(image.size, dtype=np.float32) / np.asarray(scaled.size, dtype=np.float32)
    target = np.asarray(((0, 0), (629, 0), (629, 879), (0, 879)), dtype=np.float32)
    transform = cv2.getPerspectiveTransform(points, target)
    warped = cv2.warpPerspective(np.asarray(image), transform, (630, 880), flags=cv2.INTER_CUBIC)
    return Image.fromarray(warped), {
        "method": method, "detected": True, "corners": points.round(1).tolist(),
    }


def frame_card(image: Image.Image) -> Image.Image:
    """Retain the complete card on a square canvas instead of CLIP's center cut."""
    width, height = image.size
    inset_x, inset_y = round(width * 0.02), round(height * 0.02)
    image = image.crop((inset_x, inset_y, width - inset_x, height - inset_y))
    return ImageOps.pad(
        image, (224, 224), method=Image.Resampling.BICUBIC, color=(127, 127, 127),
    )
