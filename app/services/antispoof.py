"""Liveness checks.

Layer 1 (active):  blink + head-turn detected across the submitted frame sequence.
Layer 2 (passive): MiniFASNet (Silent-Face-Anti-Spoofing) ONNX models -> photo / screen-replay detection.

Active checks alone can be beaten by a video replay, so passive is required by default and the
service FAILS CLOSED if it is required but no model is configured.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.core.config import settings
from app.services.face import FaceError, FrameFeature

log = logging.getLogger(__name__)


@dataclass
class Liveness:
    blink: bool
    head_movement: bool
    passive_score: float | None


def check_active(feats: list[FrameFeature]) -> tuple[bool, bool]:
    ears = np.array([f.ear for f in feats])
    yaws = np.array([f.yaw for f in feats])
    blink = bool(ears.min() <= settings.LIVENESS_BLINK_DROP_RATIO * np.median(ears))
    head = bool((yaws.max() - yaws.min()) >= settings.LIVENESS_MIN_YAW_RANGE_DEG)
    return blink, head


@lru_cache
def _load_models():
    import onnxruntime as ort
    models = []
    for item in filter(None, (s.strip() for s in settings.ANTISPOOF_MODEL_PATHS.split(","))):
        path, scale = item.rsplit(":", 1)
        models.append((ort.InferenceSession(path, providers=["CPUExecutionProvider"]), float(scale)))
    return models


def _crop(img: np.ndarray, bbox: tuple, scale: float, out: int = 80) -> np.ndarray:
    import cv2
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    scale = min((h - 1) / bh, (w - 1) / bw, scale)
    nw, nh = bw * scale, bh * scale
    cx, cy = x1 + bw / 2, y1 + bh / 2
    l, t = max(0, cx - nw / 2), max(0, cy - nh / 2)
    r, b = min(w - 1, cx + nw / 2), min(h - 1, cy + nh / 2)
    return cv2.resize(img[int(t):int(b) + 1, int(l):int(r) + 1], (out, out))


def passive_score(feats: list[FrameFeature]) -> float | None:
    models = _load_models()
    if not models:
        return None
    picks = [feats[i] for i in np.linspace(0, len(feats) - 1, num=min(3, len(feats)), dtype=int)]
    scores = []
    for f in picks:
        for sess, scale in models:
            x = _crop(f.image, f.bbox, scale).transpose(2, 0, 1)[None].astype(np.float32)  # BGR, 0-255, NCHW
            logits = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
            e = np.exp(logits - logits.max())
            scores.append(float((e / e.sum())[1]))  # class 1 == real face in Silent-Face
    return float(np.mean(scores))


def verify_liveness(feats: list[FrameFeature]) -> Liveness:
    blink, head = check_active(feats)
    if settings.LIVENESS_REQUIRE_BLINK and not blink:
        raise FaceError("no_blink_detected")
    if settings.LIVENESS_REQUIRE_HEAD_MOVEMENT and not head:
        raise FaceError("no_head_movement")
    score = passive_score(feats)
    if score is None:
        if settings.ANTISPOOF_REQUIRE_PASSIVE:
            log.error("Passive anti-spoof required but ANTISPOOF_MODEL_PATHS is empty")
            raise FaceError("antispoof_unavailable")
    elif score < settings.ANTISPOOF_THRESHOLD:
        raise FaceError("spoof_suspected")
    return Liveness(blink, head, score)
