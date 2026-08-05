"""三件套端到端：JD → 岗位洞察 → 匹配分析 → 定制简历。

用假模型适配器，不打真实付费 API。假模型故意返回两条违规内容
（引用不存在的事实、编造数字），验证引用校验闸门真的会拦下来。
"""

import re

import pytest

from resumefit.generate import GenerationService
from resumefit.routers.workflow import generation_service

JD = """岗位：AI 产品经理
职责：负责智能客服产品规划，搭建大模型效果评测体系，推动算法效果持续优化。
要求：5 年以上产品经验；熟悉 RAG 与 Agent；有评测体系搭建经验者优先。"""


class FakeModelClient:
    """按任务名返回预设结构化响应；resume_rewrite 会引用 prompt 里真实出现的事实 ID。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete_json(self, task, messages, schema):
        self.calls.append(task)
        prompt = "\n".join(message["content"] for message in messages)
        return schema.model_validate(getattr(self, f"_{task}")(prompt))

    def _job_insight(self, prompt):
        return {
            "positioning": "面向客服场景的大模型应用产品经理",
            "why_open": "已有客服产品需要引入大模型并建立效果闭环",
            "archetypes": [
                {"archetype": "业务应用型", "share": 60},
                {"archetype": "模型与评测型", "share": 40},
            ],
            "frequent_tasks": ["梳理客服场景", "定义评测集与指标", "跟进算法迭代"],
            "deliverables": ["产品需求文档", "评测方案"],
            "collaborators": ["算法", "研发", "客服业务"],
            "success_metrics": ["首次解决率", "人工转接率"],
            "explicit_requirements": ["产品规划", "评测体系"],
            "implicit_requirements": ["能与算法团队对齐效果口径"],
            "hard_gates": ["5 年以上产品经验"],
            "boundaries_and_risks": ["可能不负责模型训练本身"],
            "interview_focus": ["如何定义大模型效果"],
            "claims": [
                {
                    "conclusion": "岗位需要建立大模型功能的评测与迭代闭环",
                    "kind": "inference",
                    "confidence": "较高",
                    "basis": ["JD 要求搭建效果评测体系", "JD 要求推动算法效果持续优化"],
                    "open_questions": ["是否已有固定评测集"],
                }
            ],
            "open_questions": ["岗位是否亲自负责数据标注"],
        }

    def _requirement_extract(self, prompt):
        return {
            "requirements": [
                {
                    "text": "5 年以上产品经验",
                    "dimension": "行业与岗位特定经验",
                    "importance": "hard_gate",
                    "source_quote": "5 年以上产品经验",
                },
                {
                    "text": "搭建大模型效果评测体系",
                    "dimension": "数据、评测与效果迭代",
                    "importance": "core",
                    "source_quote": "搭建大模型效果评测体系",
                },
                {
                    "text": "熟悉 RAG 与 Agent",
                    "dimension": "模型/RAG/Agent 技术理解",
                    "importance": "important",
                    "source_quote": "熟悉 RAG 与 Agent",
                },
            ]
        }

    def _evidence_match(self, prompt):
        return {
            "judgements": [
                {"requirement_id": "r1", "status": "unknown", "fact_ids": [], "rationale": "简历未说明总年限"},
                {
                    "requirement_id": "r2",
                    "status": "unexpressed",
                    "fact_ids": [_fact_id_containing(prompt, "测试集")],
                    "rationale": "事实库有评测集证据，当前简历没写",
                    "over_claim_risk": "不要写成主导整个评测平台",
                },
                {"requirement_id": "r3", "status": "gap", "fact_ids": [], "rationale": "确认没有相关经历"},
            ]
        }

    def _resume_advice(self, prompt):
        return {
            "summary": "有一条能力已经具备但简历没写出来，改写就能补上。",
            "suggestions": [
                {
                    "requirement_id": "r2",
                    "action": "rewrite",
                    "advice": "把评测集建设写进项目要点",
                    "suggested_text": "建立 200 条测试集，覆盖 12 个场景",
                    "fact_ids": [_fact_id_containing(prompt, "测试集")],
                },
                {
                    "requirement_id": "r3",
                    "action": "do_not_claim",
                    "advice": "没有 Agent 经历，不要声称；可以说明学习计划",
                },
                {
                    # 引用了不存在的事实 → suggested_text 必须被作废。
                    "requirement_id": "r1",
                    "action": "rewrite",
                    "advice": "补充总年限",
                    "suggested_text": "拥有 8 年产品经验",
                    "fact_ids": ["fact-does-not-exist"],
                },
            ],
        }

    def _project_selection(self, prompt):
        project_ids = re.findall(r"([0-9a-f-]{36}): ", prompt)
        return {
            "positioning": "客服场景大模型产品经理",
            "selected_projects": [
                {"project_id": project_ids[0], "reason": "覆盖评测体系要求", "proves": ["评测能力"]}
            ]
            if project_ids
            else [],
            "strengthen": ["评测集建设"],
            "weaken": [],
            "prohibited_claims": ["不要声称熟悉 Agent"],
        }

    def _resume_rewrite(self, prompt):
        testset_fact = _fact_id_containing(prompt, "测试集")
        return {
            "id": "draft",
            "sections": [
                {
                    "title": "重点项目经历",
                    "claims": [
                        # 合法：引用真实已确认事实，数字与原文一致。
                        {"text": "建立 200 条测试集，覆盖 12 个场景", "fact_ids": [testset_fact]},
                        # 违规一：引用不存在的事实 ID。
                        {"text": "主导模型训练并上线三个大模型", "fact_ids": ["fact-does-not-exist"]},
                        # 违规二：引用真实事实，但把数字改大了。
                        {"text": "建立 900 条测试集", "fact_ids": [testset_fact]},
                    ],
                }
            ],
        }


def _facts_in(prompt: str) -> list[tuple[str, str]]:
    block = prompt.split("已确认事实")[-1]
    return re.findall(r"([0-9a-f]{8}-[0-9a-f-]{27}): (.+)", block)


def _all_facts(prompt: str) -> list[tuple[str, str]]:
    return re.findall(r"([0-9a-f]{8}-[0-9a-f-]{27})[:｜] ?(.+)", prompt)


def _fact_ids(prompt: str) -> list[str]:
    return [fact_id for fact_id, _ in _facts_in(prompt)]


def _fact_id_containing(prompt: str, needle: str) -> str:
    return next(fact_id for fact_id, text in _all_facts(prompt) if needle in text)


@pytest.fixture
def workflow(client):
    fake = FakeModelClient()
    client.app.dependency_overrides[generation_service] = lambda: GenerationService(
        client.app.state.db, fake
    )
    return client, fake


def _seed_confirmed_facts(client) -> str:
    client.put("/api/profile", json={"full_name": "张三", "target": "AI 产品经理"})
    imported = client.post(
        "/api/projects/import",
        json={
            "name": "智能客服大模型改造",
            "text": "负责智能客服产品规划。建立 200 条测试集，覆盖 12 个场景。首次解决率提升至 71%。",
            "original_name": "复盘.txt",
        },
    ).json()
    for fact in imported["facts"]:
        client.post(f"/api/facts/{fact['id']}/confirm")
    return imported["project"]["id"]


def _confirmed_record(client) -> str:
    record_id = client.post("/api/records", json={"title": "AI 产品经理"}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": JD})
    client.post(f"/api/records/{record_id}/jd/confirm")
    return record_id


def test_insight_explains_the_role_and_labels_inference(workflow):
    client, _ = workflow
    record_id = _confirmed_record(client)

    insight = client.post(f"/api/records/{record_id}/insight").json()

    assert sum(item["share"] for item in insight["archetypes"]) == 100
    assert insight["claims"][0]["kind"] == "inference"
    assert insight["claims"][0]["basis"]  # 每条结论都有依据
    assert insight["open_questions"]


def test_analysis_is_blocked_until_the_jd_is_confirmed(workflow):
    client, _ = workflow
    record_id = client.post("/api/records", json={}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": JD})

    assert client.post(f"/api/records/{record_id}/insight").status_code == 409


def test_match_separates_capability_from_presentation(workflow):
    client, _ = workflow
    _seed_confirmed_facts(client)
    record_id = _confirmed_record(client)

    body = client.post(f"/api/records/{record_id}/match").json()
    report = body["report"]

    # r2 是「有经历但简历未表达」：能力算得上，呈现度接近 0。
    assert "r2" in report["unexpressed"]
    assert report["capability_high"] > report["presentation_high"]
    # r1 资料不足 → unknown，不能算成缺口；r3 才是用户确认的缺口。
    assert report["unknowns"] == ["r1"]
    assert report["confirmed_gaps"] == ["r3"]
    # 硬性门槛单独提示，不被平均掉。
    assert report["hard_gate_risks"] == []
    assert body["questions"][0]["requirement_id"] == "r1"


def test_resume_generation_blocks_uncited_and_fabricated_claims(workflow):
    client, _ = workflow
    _seed_confirmed_facts(client)
    record_id = _confirmed_record(client)
    client.post(f"/api/records/{record_id}/match")

    body = client.post(f"/api/records/{record_id}/resumes").json()

    codes = sorted(violation["code"] for violation in body["violations"])
    assert codes == ["unconfirmed_fact", "unsupported_metric"]

    kept = [claim["text"] for section in body["document"]["sections"] for claim in section["claims"]]
    assert kept == ["建立 200 条测试集，覆盖 12 个场景"]
    assert "主导模型训练并上线三个大模型" not in kept
    assert "建立 900 条测试集" not in kept


def test_resume_requires_a_fresh_match_for_the_current_jd(workflow):
    client, _ = workflow
    _seed_confirmed_facts(client)
    record_id = _confirmed_record(client)
    client.post(f"/api/records/{record_id}/match")

    # 改 JD 之后旧匹配报告过期，必须重新分析才能生成简历。
    client.put(f"/api/records/{record_id}/jd", json={"text": JD + "\n新增：负责商业化"})
    client.post(f"/api/records/{record_id}/jd/confirm")

    assert client.get(f"/api/records/{record_id}/match").json()["stale"] is True
    assert client.post(f"/api/records/{record_id}/resumes").status_code == 409


def test_each_generation_creates_a_new_immutable_version(workflow):
    client, _ = workflow
    _seed_confirmed_facts(client)
    record_id = _confirmed_record(client)
    client.post(f"/api/records/{record_id}/match")

    client.post(f"/api/records/{record_id}/resumes")
    client.post(f"/api/records/{record_id}/resumes")

    versions = client.get(f"/api/records/{record_id}/resumes").json()
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[0]["version_id"] != versions[1]["version_id"]


def test_history_carries_both_scores_and_flags(workflow):
    client, _ = workflow
    _seed_confirmed_facts(client)
    resume_id = client.post("/api/resumes", json={"text": "简历正文", "label": "AI 产品版"}).json()["id"]
    record_id = _confirmed_record(client)
    client.put(f"/api/records/{record_id}/resume", json={"resume_source_id": resume_id})
    client.post(f"/api/records/{record_id}/insight")
    client.post(f"/api/records/{record_id}/match")

    entry = client.get("/api/records/history").json()[0]

    assert entry["has_insight"] is True
    assert entry["scores"]["capability_high"] > entry["scores"]["presentation_high"]
    assert entry["resume_label"] == "AI 产品版"


def test_match_returns_actionable_advice_and_drops_fabricated_citations(workflow):
    client, _ = workflow
    _seed_confirmed_facts(client)
    record_id = _confirmed_record(client)

    advice = client.post(f"/api/records/{record_id}/match").json()["advice"]
    by_requirement = {item["requirement_id"]: item for item in advice["suggestions"]}

    # 有能力没写 → 给出可直接用的文案，并引用真实事实。
    assert by_requirement["r2"]["action"] == "rewrite"
    assert by_requirement["r2"]["suggested_text"] == "建立 200 条测试集，覆盖 12 个场景"
    assert by_requirement["r2"]["fact_ids"]
    # 确认没有 → 明确不要声称。
    assert by_requirement["r3"]["action"] == "do_not_claim"
    # 引用了不存在的事实 → 文案作废，动作降级，标签不会与说明自相矛盾。
    assert by_requirement["r1"]["suggested_text"] == ""
    assert by_requirement["r1"]["fact_ids"] == []
    assert by_requirement["r1"]["action"] == "add_evidence"


def test_insight_only_record_is_not_shown_as_a_failed_match(workflow):
    client, _ = workflow
    record_id = client.post("/api/records", json={}).json()["id"]
    client.put(f"/api/records/{record_id}/jd", json={"text": JD})
    client.post(f"/api/records/{record_id}/jd/confirm")
    client.post(f"/api/records/{record_id}/insight")

    entry = client.get("/api/records/history").json()[0]

    assert entry["kind"] == "insight"
    assert entry["scores"] is None
    assert entry["title"] == "AI 产品经理"
