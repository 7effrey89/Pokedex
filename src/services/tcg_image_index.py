"""Shared encoding and exact NumPy search for the TCG image catalog."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

CARD_ASPECT_RATIO = 63 / 88
ENCODER_VERSION = "pillow-standardized-grayscale-histogram-v2"
GRAYSCALE_SIZE = (32, 44)
HISTOGRAM_BINS = 8
HISTOGRAM_WEIGHT = 8.0
QUERY_CONTENT_SCALES = (1.0, 0.90, 0.86, 0.82)
VECTOR_SIZE = (GRAYSCALE_SIZE[0] * GRAYSCALE_SIZE[1]) + (HISTOGRAM_BINS * 3)


def crop_to_card_aspect(image: Image.Image) -> Image.Image:
    """Center-crop an image to the standard Pokemon card aspect ratio."""
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    current_ratio = width / height
    if current_ratio > CARD_ASPECT_RATIO:
        crop_width = int(height * CARD_ASPECT_RATIO)
        left = max(0, (width - crop_width) // 2)
        return image.crop((left, 0, left + crop_width, height))

    crop_height = int(width / CARD_ASPECT_RATIO)
    top = max(0, (height - crop_height) // 2)
    return image.crop((0, top, width, top + crop_height))


def encode_card_image(image: Image.Image) -> np.ndarray:
    """Create a deterministic, L2-normalized visual vector for a card image."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = crop_to_card_aspect(image)
    resized = ImageOps.fit(image, GRAYSCALE_SIZE, method=Image.Resampling.LANCZOS)
    color_array = np.asarray(resized, dtype=np.float32) / 255.0
    grayscale_values = (
        (color_array[:, :, 0] * 0.299)
        + (color_array[:, :, 1] * 0.587)
        + (color_array[:, :, 2] * 0.114)
    ).reshape(-1)
    grayscale_std = float(grayscale_values.std())
    grayscale_values = (grayscale_values - float(grayscale_values.mean())) / (grayscale_std or 1.0)
    histograms = []
    for channel in range(3):
        histogram, _ = np.histogram(color_array[:, :, channel], bins=HISTOGRAM_BINS, range=(0.0, 1.0))
        histogram = histogram.astype(np.float32)
        histogram /= max(float(histogram.sum()), 1.0)
        histograms.append(histogram)

    vector = np.concatenate((
        grayscale_values,
        np.concatenate(histograms) * HISTOGRAM_WEIGHT,
    )).astype(np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise ValueError("image produced an empty feature vector")
    return vector / norm


def query_scale_variants(image: Image.Image) -> list[Image.Image]:
    """Pad tightly framed captures so their card content can align with catalog images."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    background = image.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    variants = [image]
    for scale in QUERY_CONTENT_SCALES[1:]:
        scaled_size = (
            max(1, round(image.width * scale)),
            max(1, round(image.height * scale)),
        )
        scaled = image.resize(scaled_size, Image.Resampling.LANCZOS)
        padded = Image.new("RGB", image.size, background)
        padded.paste(scaled, ((image.width - scaled.width) // 2, (image.height - scaled.height) // 2))
        variants.append(padded)
    return variants


class TcgImageIndex:
    """Lazy-loading exact cosine index backed by generated NumPy artifacts."""

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self._vectors = None
        self._cards = None
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._vectors is not None and self._cards is not None:
            return
        with self._lock:
            if self._vectors is not None and self._cards is not None:
                return
            manifest_path = self.index_dir / "manifest.json"
            vectors_path = self.index_dir / "vectors.npy"
            cards_path = self.index_dir / "cards.json"
            if not manifest_path.exists() or not vectors_path.exists() or not cards_path.exists():
                raise FileNotFoundError("TCG NumPy image index is missing; run scripts/04-cache_tcg_images.py")

            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            if manifest.get("encoder_version") != ENCODER_VERSION:
                raise ValueError("TCG image index encoder version does not match the application")
            if manifest.get("vector_size") != VECTOR_SIZE:
                raise ValueError("TCG image index manifest has an unexpected vector size")
            if manifest.get("dtype") != "float32" or manifest.get("normalized") is not True:
                raise ValueError("TCG image index manifest has an unsupported storage format")
            with cards_path.open("r", encoding="utf-8") as handle:
                cards = json.load(handle)
            vectors = np.load(vectors_path, mmap_mode="r")
            if vectors.ndim != 2 or vectors.shape[1] != VECTOR_SIZE:
                raise ValueError("TCG image index has an unexpected vector shape")
            if vectors.shape[0] != len(cards):
                raise ValueError("TCG image index card mapping is not aligned with its vectors")
            self._vectors = vectors
            self._cards = cards

    def search(self, image: Image.Image, limit: int = 6) -> list[dict]:
        self._load()
        query_vectors = np.stack([encode_card_image(variant) for variant in query_scale_variants(image)])
        scores = np.max(np.asarray(self._vectors @ query_vectors.T, dtype=np.float32), axis=1)
        limit = max(1, min(int(limit), len(scores), 24))
        candidate_rows = np.argpartition(scores, -limit)[-limit:]
        ranked_rows = candidate_rows[np.argsort(scores[candidate_rows])[::-1]]
        return [
            {
                "id": self._cards[row].get("id"),
                "score": round(float(scores[row]), 6),
                "card": self._cards[row],
            }
            for row in ranked_rows
        ]