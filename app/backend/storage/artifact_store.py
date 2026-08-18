import json
from pathlib import Path

import numpy as np
from PIL import Image


class ArtifactStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.run_dir = Path(root) / run_id

    def _page_dir(self, page: int) -> Path:
        page_dir = self.run_dir / f"page_{page:02d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        return page_dir

    def save_image(self, page: int, stage_name: str, image: np.ndarray) -> Path:
        path = self._page_dir(page) / f"{stage_name}.png"
        Image.fromarray(image[:, :, ::-1] if image.ndim == 3 else image).save(path)
        return path

    def save_json(self, page: int, stage_name: str, data: dict) -> Path:
        path = self._page_dir(page) / f"{stage_name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    def save_run_json(self, stage_name: str, data: dict) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / f"{stage_name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    def load_run_json(self, stage_name: str) -> dict:
        path = self.run_dir / f"{stage_name}.json"
        return json.loads(path.read_text())

    def load_image(self, page: int, stage_name: str) -> np.ndarray:
        path = self._page_dir(page) / f"{stage_name}.png"
        pil_image = Image.open(path).convert("RGB")
        return np.array(pil_image)[:, :, ::-1]  # RGB -> BGR

    def list_pages(self) -> list[int]:
        if not self.run_dir.exists():
            return []
        pages = [
            int(child.name.removeprefix("page_"))
            for child in self.run_dir.iterdir()
            if child.is_dir() and child.name.startswith("page_")
        ]
        return sorted(pages)
