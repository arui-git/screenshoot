from __future__ import annotations

from pathlib import Path
from typing import List


class HistoryManager:
    def __init__(self, save_dir: Path, max_items: int = 10) -> None:
        self._save_dir = Path(save_dir)
        self._max_items = max_items

    def set_save_dir(self, save_dir: Path) -> None:
        self._save_dir = Path(save_dir)

    def list_recent(self) -> List[Path]:
        if not self._save_dir.exists():
            return []
        png_files = sorted(
            self._save_dir.glob("*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return png_files[: self._max_items]

