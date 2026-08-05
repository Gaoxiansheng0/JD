from io import BytesIO

import pytest

from resumefit.config import AppConfig
from resumefit.storage import LocalStorage, UnsupportedUpload


def test_upload_is_uuid_named_and_cannot_escape_its_category(tmp_path):
    storage = LocalStorage(AppConfig.for_root(tmp_path))

    stored = storage.save_upload(BytesIO(b"JD"), "../../岗位 JD.png", "jd-images")

    assert stored.path.parent == storage.config.images_dir
    assert stored.path.name != "../../岗位 JD.png"
    assert stored.path.read_bytes() == b"JD"


def test_upload_keeps_original_name_for_display_but_not_on_disk(tmp_path):
    storage = LocalStorage(AppConfig.for_root(tmp_path))

    stored = storage.save_upload(BytesIO(b"resume"), "我的简历.docx", "imports")

    assert stored.original_name == "我的简历.docx"
    assert stored.path.suffix == ".docx"
    assert "我的简历" not in stored.path.name
    assert stored.byte_size == len(b"resume")


def test_upload_rejects_a_suffix_outside_the_allowed_set(tmp_path):
    storage = LocalStorage(AppConfig.for_root(tmp_path))

    with pytest.raises(UnsupportedUpload):
        storage.save_upload(BytesIO(b"#!/bin/sh"), "run.sh", "imports")


def test_upload_rejects_content_over_the_configured_limit(tmp_path):
    config = AppConfig.for_root(tmp_path)
    storage = LocalStorage(config)
    oversized = BytesIO(b"x" * (config.max_import_bytes + 1))

    with pytest.raises(UnsupportedUpload):
        storage.save_upload(oversized, "big.txt", "imports")


def test_export_file_name_is_safe_and_readable(tmp_path):
    storage = LocalStorage(AppConfig.for_root(tmp_path))

    name = storage.safe_export_name("张/三", "AI 产品经理", "示例公司", suffix=".docx")

    assert "/" not in name
    assert name.endswith(".docx")
    assert "张" in name
