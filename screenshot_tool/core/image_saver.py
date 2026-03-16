from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtGui import QPixmap


class ImageSaver:
    def __init__(self, save_dir: Path) -> None:
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

    @property
    def save_dir(self) -> Path:
        return self._save_dir

    def set_save_dir(self, save_dir: Path) -> None:
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

    def save_pixmap(self, pixmap: QPixmap) -> Path:
        if pixmap.isNull():
            raise ValueError("Cannot save an empty screenshot.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        output = self._save_dir / filename
        suffix = 1
        while output.exists():
            output = self._save_dir / f"screenshot_{timestamp}_{suffix}.png"
            suffix += 1

        ok = pixmap.save(str(output), "PNG")
        if not ok:
            raise IOError(f"Failed to save screenshot: {output}")
        return output

