"""Pinned local-only CLIP vision inference; model acquisition is admin-initiated."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from src.config import get_storage_paths
from src.services.tcg_card_crop import CROP_VERSION, frame_card
from src.utils.file_lock import exclusive_file_lock

MODEL_REVISION = "6b7c523703ae26e39be4b03774966f8571c7f523"
MODEL_SHA256 = "fd6e1402a588279d1723c7534d4bcba5bc0b14b47dfab0e46f8c47b8270d7d40"
MODEL_BYTES = 351685709
MODEL_URL = f"https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/{MODEL_REVISION}/onnx/vision_model.onnx"
ENCODER_VERSION = f"clip-vit-b32-onnx-{MODEL_SHA256[:12]}-{CROP_VERSION}"
VECTOR_SIZE = 512
logger = logging.getLogger(__name__)


class ClipEncoder:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._session = None
        self._lock = threading.RLock()

    def _verify_model(self) -> None:
        if not self.model_path.is_file():
            raise FileNotFoundError("CLIP model is missing. Generate CLIP embeddings in Settings first.")
        with self.model_path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != MODEL_SHA256:
            raise ValueError("CLIP model checksum mismatch; remove the corrupt model and generate again.")

    def prepare(self) -> None:
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.model_path.parent.parent / ".tcg-embedding-job-clip-model.lock"):
            if not self.model_path.is_file():
                logger.info("Downloading CLIP model from %s to %s", MODEL_URL, self.model_path)
                descriptor, temporary = tempfile.mkstemp(prefix="clip-model-", dir=self.model_path.parent)
                try:
                    digest = hashlib.sha256()
                    size = 0
                    with os.fdopen(descriptor, "wb") as output, requests.get(
                        MODEL_URL, stream=True, timeout=(15, 120),
                    ) as response:
                        response.raise_for_status()
                        for chunk in response.iter_content(1024 * 1024):
                            size += len(chunk)
                            if size > MODEL_BYTES:
                                raise ValueError("CLIP model download exceeded its expected size")
                            output.write(chunk)
                            digest.update(chunk)
                    if size != MODEL_BYTES or digest.hexdigest() != MODEL_SHA256:
                        raise ValueError("CLIP model download failed size/checksum verification")
                    os.replace(temporary, self.model_path)
                finally:
                    Path(temporary).unlink(missing_ok=True)
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            self._verify_model()
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(
                str(self.model_path), sess_options=options, providers=["CPUExecutionProvider"],
            )
            if "pixel_values" not in [item.name for item in session.get_inputs()]:
                raise ValueError("CLIP model has an unexpected input contract")
            if "image_embeds" not in [item.name for item in session.get_outputs()]:
                raise ValueError("CLIP model has an unexpected output contract")
            self._session = session

    def encode(self, images: list[Image.Image]) -> np.ndarray:
        self._load()
        values = np.stack([np.asarray(frame_card(image), dtype=np.float32) / 255 for image in images])
        values = (values - np.asarray((0.48145466, 0.4578275, 0.40821073), dtype=np.float32)) / np.asarray(
            (0.26862954, 0.26130258, 0.27577711), dtype=np.float32,
        )
        with self._lock:
            output = np.asarray(self._session.run(
                ["image_embeds"], {"pixel_values": values.transpose(0, 3, 1, 2)},
            )[0], dtype=np.float32)
        if output.shape != (len(images), VECTOR_SIZE) or not np.isfinite(output).all():
            raise ValueError("CLIP produced an invalid embedding matrix")
        norms = np.linalg.norm(output, axis=1, keepdims=True)
        if (norms <= 0).any():
            raise ValueError("CLIP produced an empty embedding")
        return output / norms


_ENCODER: ClipEncoder | None = None


def get_clip_encoder() -> ClipEncoder:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = ClipEncoder(get_storage_paths().clip_model)
    return _ENCODER
