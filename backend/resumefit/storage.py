"""本地文件存储：UUID 命名落盘，界面显示原始文件名。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import BinaryIO

from resumefit.config import AppConfig

CHUNK = 64 * 1024


class UnsupportedUpload(Exception):
    """文件类型或大小不被接受。"""


@dataclass(frozen=True)
class StoredFile:
    id: str
    path: Path
    original_name: str
    byte_size: int


class LocalStorage:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _category(self, category: str) -> tuple[Path, set[str], int]:
        if category == "imports":
            return self.config.imports_dir, {".txt", ".md", ".docx", ".pdf"}, self.config.max_import_bytes
        if category == "jd-images":
            return self.config.images_dir, {".png", ".jpg", ".jpeg", ".webp"}, self.config.max_image_bytes
        raise UnsupportedUpload(f"未知的存储分类：{category}")

    def save_upload(self, stream: BinaryIO, original_name: str, category: str) -> StoredFile:
        directory, allowed, max_bytes = self._category(category)

        # 只取原名的后缀，绝不把用户提供的文件名当作路径使用。
        suffix = Path(original_name).suffix.lower()
        if suffix not in allowed:
            raise UnsupportedUpload(f"不支持的文件类型：{suffix or original_name}")

        file_id = str(uuid.uuid4())
        path = directory / f"{file_id}{suffix}"
        size = 0
        try:
            with path.open("wb") as target:
                while chunk := stream.read(CHUNK):
                    size += len(chunk)
                    if size > max_bytes:
                        raise UnsupportedUpload(
                            f"文件超过 {max_bytes // (1024 * 1024)} MB 限制"
                        )
                    target.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise

        return StoredFile(id=file_id, path=path, original_name=original_name, byte_size=size)

    @staticmethod
    def safe_export_name(*parts: str, suffix: str) -> str:
        cleaned = [re.sub(r"\W+", "", part) for part in parts]
        stem = "_".join(part for part in cleaned if part) or "resume"
        return f"{stem}_{date.today():%Y%m%d}{suffix}"
