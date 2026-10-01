"""Face detection / ArcFace embeddings via InsightFace (buffalo_l).

InsightFace/OpenCV are imported lazily so the API (and tests) start without the heavy ML stack.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings

log = logging.getLogger(__name__)


class FaceError(Exception):
    """Carries a short machine-readable reason (stored as reject_reason)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class FrameFeature:
    embedding: np.ndarray  # L2-normalised ArcFace vector
    ear: float             # mean eye-aspect-ratio
    yaw: float             # degrees
    bbox: tuple            # x1, y1, x2, y2
    det_score: float
    image: np.ndarray      # BGR frame (kept for passive anti-spoof)


_app = None


def _get_app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=-1, det_size=(640, 640))
        log.info("InsightFace model loaded")
    return _app


def decode_image(data: bytes) -> np.ndarray:
    import cv2
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FaceError("invalid_image")
    return img


def _ear(pts: np.ndarray, idx: list[int]) -> float:
    p = pts[idx][:, :2]
    v = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    h = np.linalg.norm(p[0] - p[3])
    return float(v / (2.0 * h + 1e-6))


def extract_features(images: list[np.ndarray], min_valid: int = 3) -> list[FrameFeature]:
    app = _get_app()
    feats: list[FrameFeature] = []
    for img in images:
        faces = app.get(img)
        if len(faces) > 1:
            raise FaceError("multiple_faces")
        if not faces:
            continue
        f = faces[0]
        if float(f.det_score) < settings.FACE_MIN_DET_SCORE:
            continue
        lm = f.landmark_3d_68  # iBUG-68 order: right eye 36-41, left eye 42-47
        ear = (_ear(lm, list(range(36, 42))) + _ear(lm, list(range(42, 48)))) / 2
        feats.append(FrameFeature(f.normed_embedding.astype(np.float32), ear, float(f.pose[1]),
                                  tuple(float(v) for v in f.bbox), float(f.det_score), img))
    if len(feats) < min_valid:
        raise FaceError("no_face_detected" if not feats else "insufficient_clear_frames")
    return feats


def mean_embedding(feats: list[FrameFeature]) -> np.ndarray:
    embs = np.stack([f.embedding for f in feats])
    m = embs.mean(axis=0)
    m /= np.linalg.norm(m) + 1e-9
    # every frame must be the same person (blocks swapping faces mid-capture)
    if float((embs @ m).min()) < settings.FACE_MATCH_THRESHOLD:
        raise FaceError("inconsistent_faces")
    return m.astype(np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def save_embedding(user_id: int, emb: np.ndarray) -> str:
    from app.services.storage import embeddings_dir
    path = embeddings_dir() / f"user_{user_id}.npy"
    np.save(path, emb)
    return str(path)


def load_embedding(path: str) -> np.ndarray:
    return np.load(Path(path))
