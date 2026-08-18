from pathlib import Path

import cv2
import numpy as np
import pymupdf as fitz

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_pages(path: Path) -> list[np.ndarray]:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in _IMAGE_SUFFIXES:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"could not read image: {path}")
        return [image]
    raise ValueError(f"unsupported file type: {suffix}")


def _load_pdf(path: Path, dpi: int = 200) -> list[np.ndarray]:
    pages: list[np.ndarray] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            pages.append(img)

    return pages
