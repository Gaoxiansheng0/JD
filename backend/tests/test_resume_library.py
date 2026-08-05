import io


def test_pasted_resume_lands_in_the_library_newest_first(client):
    client.post("/api/resumes", json={"text": "第一版简历", "label": "通用版"})
    client.post("/api/resumes", json={"text": "第二版简历", "label": "AI 产品版"})

    labels = [item["label"] for item in client.get("/api/resumes").json()]

    assert labels == ["AI 产品版", "通用版"]


def test_uploaded_txt_resume_is_parsed_and_labelled(client):
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("我的简历.txt", io.BytesIO("AI 产品经理\n建立评测体系".encode()), "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["label"] == "我的简历.txt"
    assert "评测体系" in client.get(f"/api/resumes/{response.json()['id']}").json()["text"]


def test_upload_rejects_an_unsupported_file_type(client):
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("run.sh", io.BytesIO(b"#!/bin/sh"), "application/x-sh")},
    )

    assert response.status_code == 422
    assert "不支持" in response.json()["detail"]


def test_scanned_pdf_upload_reports_a_scan_instead_of_an_empty_resume(client, tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)

    response = client.post(
        "/api/resumes/upload",
        files={"file": ("scan.pdf", io.BytesIO(buffer.getvalue()), "application/pdf")},
    )

    assert response.status_code == 422
    assert "扫描" in response.json()["detail"]


def test_resume_library_does_not_leak_project_material(client):
    client.post(
        "/api/projects/import",
        json={"name": "智能客服", "text": "建立 200 条测试集，覆盖 12 个场景。", "original_name": "复盘.txt"},
    )

    assert client.get("/api/resumes").json() == []


def test_record_remembers_which_resume_the_analysis_used(client):
    resume_id = client.post("/api/resumes", json={"text": "AI 产品版简历", "label": "AI 产品版"}).json()["id"]
    record_id = client.post("/api/records", json={"title": "AI 产品经理"}).json()["id"]

    updated = client.put(f"/api/records/{record_id}/resume", json={"resume_source_id": resume_id}).json()

    assert updated["resume_source_id"] == resume_id


def test_history_shows_what_each_record_produced(client):
    resume_id = client.post("/api/resumes", json={"text": "简历正文", "label": "AI 产品版"}).json()["id"]
    record_id = client.post("/api/records", json={"title": "AI 产品经理"}).json()["id"]
    client.put(f"/api/records/{record_id}/resume", json={"resume_source_id": resume_id})
    client.put(f"/api/records/{record_id}/jd", json={"text": "负责 AI 产品规划"})
    client.post(f"/api/records/{record_id}/jd/confirm")

    entry = client.get("/api/records/history").json()[0]

    assert entry["title"] == "AI 产品经理"
    assert entry["resume_label"] == "AI 产品版"
    assert entry["jd_excerpt"] == "负责 AI 产品规划"
    # 还没分析过，所以没有分数，也没有岗位解读。
    assert entry["scores"] is None
    assert entry["has_insight"] is False
    assert entry["resume_count"] == 0


def test_title_is_derived_from_the_jd_when_not_given(client):
    record_id = client.post("/api/records", json={}).json()["id"]
    client.put(
        f"/api/records/{record_id}/jd",
        json={"text": "岗位：AI 产品经理（智能客服方向）\n职责：负责产品规划"},
    )

    assert client.post(f"/api/records/{record_id}/jd/confirm").json()["title"] == (
        "AI 产品经理（智能客服方向）"
    )


def test_title_falls_back_to_the_first_line(client):
    record_id = client.post("/api/records", json={}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": "大模型应用产品负责人\n要求若干"})

    assert client.post(f"/api/records/{record_id}/jd/confirm").json()["title"] == "大模型应用产品负责人"


def test_an_explicit_title_is_never_overwritten(client):
    record_id = client.post("/api/records", json={"title": "我自己起的名字"}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": "岗位：AI 产品经理"})

    assert client.post(f"/api/records/{record_id}/jd/confirm").json()["title"] == "我自己起的名字"
