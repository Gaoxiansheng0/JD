def test_new_record_starts_as_draft(client):
    record = client.post("/api/records", json={"title": "AI 产品经理"}).json()

    assert record["workflow_state"] == "DRAFT"
    assert record["jd_version"] == 0


def test_confirming_jd_advances_the_workflow_state(client):
    record_id = client.post("/api/records", json={}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": "负责 AI 产品规划，建立评测体系"})

    response = client.post(f"/api/records/{record_id}/jd/confirm")

    assert response.json()["workflow_state"] == "JD_CONFIRMED"
    assert response.json()["jd_version"] == 1


def test_empty_jd_cannot_be_confirmed(client):
    record_id = client.post("/api/records", json={}).json()["id"]

    assert client.post(f"/api/records/{record_id}/jd/confirm").status_code == 409


def test_editing_a_confirmed_jd_reopens_the_record_and_bumps_the_version(client):
    record_id = client.post("/api/records", json={}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": "负责 AI 产品规划"})
    client.post(f"/api/records/{record_id}/jd/confirm")

    client.put(f"/api/records/{record_id}/jd", json={"text": "负责 AI 产品规划，并搭建评测体系"})
    record = client.get(f"/api/records/{record_id}").json()

    # 下游产物记录自己所依据的 jd_version，版本对不上即视为过期。
    assert record["workflow_state"] == "DRAFT"
    assert record["jd_version"] == 1

    confirmed = client.post(f"/api/records/{record_id}/jd/confirm").json()
    assert confirmed["jd_version"] == 2


def test_records_are_listed_newest_first(client):
    client.post("/api/records", json={"title": "岗位一"})
    client.post("/api/records", json={"title": "岗位二"})

    titles = [record["title"] for record in client.get("/api/records").json()]

    assert titles == ["岗位二", "岗位一"]
