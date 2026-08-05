"""本地数据根目录与运行限制。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "Resume Fit"


@dataclass(frozen=True)
class AppConfig:
    root: Path
    max_import_bytes: int = 20 * 1024 * 1024  # 规格 §12.4
    max_image_bytes: int = 15 * 1024 * 1024
    max_pdf_pages: int = 20

    @property
    def database_path(self) -> Path:
        return self.root / "resumefit.sqlite3"

    @property
    def imports_dir(self) -> Path:
        return self.root / "imports"

    @property
    def images_dir(self) -> Path:
        return self.root / "jd-images"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def directories(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.imports_dir,
            self.images_dir,
            self.exports_dir,
            self.backups_dir,
            self.logs_dir,
        )

    @classmethod
    def for_root(cls, root: Path | str) -> AppConfig:
        config = cls(root=Path(root).expanduser().resolve())
        for directory in config.directories:
            directory.mkdir(parents=True, exist_ok=True)
        return config

    @classmethod
    def default(cls) -> AppConfig:
        """生产默认：macOS 用户应用数据目录，可用 RESUMEFIT_DATA_ROOT 覆盖。"""
        root = os.environ.get("RESUMEFIT_DATA_ROOT") or (
            Path.home() / "Library" / "Application Support" / APP_DIR_NAME
        )
        return cls.for_root(root)
