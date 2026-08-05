from resumefit.projects import ProjectService


def test_only_confirmed_facts_appear_in_reusable_search(db):
    service = ProjectService(db)
    project = service.create_project({"name": "智能客服", "company": "示例公司"})
    pending = service.add_fact(project.id, {"text": "建立 200 条测试集", "source": "用户输入"})

    assert service.search_confirmed_facts("测试集") == []

    service.confirm_fact(pending.id)

    assert [fact.id for fact in service.search_confirmed_facts("测试集")] == [pending.id]


def test_conflicting_fact_is_not_marked_confirmed(db):
    service = ProjectService(db)
    project = service.create_project({"name": "智能客服", "company": "示例公司"})
    service.add_fact(
        project.id,
        {"text": "首次解决率提升至 71%", "source": "用户输入", "status": "confirmed"},
    )

    duplicate = service.add_fact(
        project.id, {"text": "首次解决率提升至 61%", "source": "简历导入"}
    )

    assert duplicate.status == "conflict"


def test_restating_the_same_number_is_not_a_conflict(db):
    service = ProjectService(db)
    project = service.create_project({"name": "智能客服"})
    service.add_fact(
        project.id,
        {"text": "首次解决率提升至 71%", "source": "用户输入", "status": "confirmed"},
    )

    same = service.add_fact(project.id, {"text": "首次解决率提升至 71%", "source": "简历导入"})

    assert same.status == "pending"


def test_a_conflicting_fact_cannot_be_confirmed(db):
    import pytest

    from resumefit.projects import FactNotConfirmable

    service = ProjectService(db)
    project = service.create_project({"name": "智能客服"})
    service.add_fact(
        project.id,
        {"text": "首次解决率提升至 71%", "source": "用户输入", "status": "confirmed"},
    )
    conflicting = service.add_fact(project.id, {"text": "首次解决率提升至 61%", "source": "简历导入"})

    with pytest.raises(FactNotConfirmable):
        service.confirm_fact(conflicting.id)


def test_rejected_fact_leaves_the_reusable_index(db):
    service = ProjectService(db)
    project = service.create_project({"name": "智能客服"})
    fact = service.add_fact(project.id, {"text": "建立 200 条测试集", "source": "用户输入"})
    service.confirm_fact(fact.id)

    service.set_fact_status(fact.id, "rejected")

    assert service.search_confirmed_facts("测试集") == []


def test_pending_fact_is_listed_on_its_project_but_not_searchable(client):
    project_id = client.post("/api/projects", json={"name": "智能客服"}).json()["id"]
    client.post(
        f"/api/projects/{project_id}/facts",
        json={"text": "建立 200 条测试集", "source": "用户输入"},
    )

    listed = client.get(f"/api/projects/{project_id}").json()
    assert [fact["text"] for fact in listed["facts"]] == ["建立 200 条测试集"]
    assert client.get("/api/projects/search", params={"q": "测试集"}).json() == []


def test_profile_round_trips(client):
    client.put("/api/profile", json={"full_name": "张三", "target": "AI 产品经理"})

    assert client.get("/api/profile").json()["full_name"] == "张三"
