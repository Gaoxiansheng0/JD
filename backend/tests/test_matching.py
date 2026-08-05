import pytest

from resumefit.matching import Evidence, Requirement, calculate_match, rank_questions


def req(id_, **kwargs):
    return Requirement(
        id=id_,
        text=kwargs.get("text", id_),
        dimension=kwargs.get("dimension", "产品"),
        weight=kwargs.get("weight", 3),
        hard_gate=kwargs.get("hard_gate", False),
    )


def test_rewriting_evidence_can_raise_presentation_but_not_capability():
    requirement = req("eval", weight=5, dimension="评测", text="搭建评测体系")

    before = calculate_match(
        [requirement], [Evidence(requirement_id="eval", status="unexpressed", fact_ids=["fact-1"])]
    )
    after = calculate_match(
        [requirement], [Evidence(requirement_id="eval", status="strong", fact_ids=["fact-1"])]
    )

    # 同一批已确认事实，能力不因为改写而变化，只有呈现度变了。
    assert before.capability_low == after.capability_low
    assert before.capability_high == after.capability_high
    assert after.presentation_low > before.presentation_low


def test_unmet_hard_gate_is_visible_even_when_other_dimensions_score_high():
    report = calculate_match(
        [
            req("years", weight=5, hard_gate=True, dimension="门槛", text="5 年经验"),
            req("product", weight=5, dimension="产品", text="产品规划"),
        ],
        [
            Evidence(requirement_id="years", status="gap", fact_ids=[]),
            Evidence(requirement_id="product", status="strong", fact_ids=["f"]),
        ],
    )

    assert report.hard_gate_risks == ["years"]
    # 硬性门槛不进综合分，不会被高分维度平均掉。
    assert report.capability_low >= 85


def test_unknown_widens_the_interval_and_is_not_counted_as_a_gap():
    unknown = calculate_match([req("a")], [Evidence(requirement_id="a", status="unknown", fact_ids=[])])
    gap = calculate_match([req("a")], [Evidence(requirement_id="a", status="gap", fact_ids=[])])

    assert unknown.capability_high - unknown.capability_low > gap.capability_high - gap.capability_low
    assert unknown.capability_high > gap.capability_high
    assert "a" not in unknown.confirmed_gaps
    assert "a" in gap.confirmed_gaps


def test_scores_are_integers_and_ordered():
    report = calculate_match(
        [req("a", weight=5), req("b", weight=1)],
        [
            Evidence(requirement_id="a", status="partial", fact_ids=["f"]),
            Evidence(requirement_id="b", status="unknown", fact_ids=[]),
        ],
    )

    for value in (report.capability_low, report.capability_high, report.presentation_low, report.presentation_high):
        assert isinstance(value, int)
    assert report.capability_low <= report.capability_high


def test_weight_actually_shifts_the_aggregate():
    heavy_gap = calculate_match(
        [req("a", weight=5), req("b", weight=1)],
        [
            Evidence(requirement_id="a", status="gap", fact_ids=[]),
            Evidence(requirement_id="b", status="strong", fact_ids=["f"]),
        ],
    )
    light_gap = calculate_match(
        [req("a", weight=1), req("b", weight=5)],
        [
            Evidence(requirement_id="a", status="gap", fact_ids=[]),
            Evidence(requirement_id="b", status="strong", fact_ids=["f"]),
        ],
    )

    assert light_gap.capability_low > heavy_gap.capability_low


def test_evidence_claiming_capability_must_cite_facts():
    for status in ("strong", "partial", "unexpressed"):
        with pytest.raises(ValueError):
            calculate_match([req("a")], [Evidence(requirement_id="a", status=status, fact_ids=[])])


def test_missing_evidence_for_a_requirement_is_treated_as_unknown():
    report = calculate_match([req("a")], [])

    assert "a" in report.unknowns
    assert "a" not in report.confirmed_gaps


def test_dimension_breakdown_separates_the_two_metrics():
    report = calculate_match(
        [req("a", dimension="评测"), req("b", dimension="产品")],
        [
            Evidence(requirement_id="a", status="unexpressed", fact_ids=["f"]),
            Evidence(requirement_id="b", status="strong", fact_ids=["f"]),
        ],
    )

    by_dimension = {d.dimension: d for d in report.dimensions}
    assert by_dimension["评测"].capability_low == by_dimension["产品"].capability_low
    assert by_dimension["评测"].presentation_high < by_dimension["产品"].presentation_low


def test_questions_target_the_widest_high_weight_gaps_first():
    report = calculate_match(
        [
            req("heavy", weight=5, text="搭建评测体系"),
            req("light", weight=1, text="熟悉标注流程"),
            req("known", weight=5, text="产品规划"),
        ],
        [
            Evidence(requirement_id="heavy", status="unknown", fact_ids=[]),
            Evidence(requirement_id="light", status="unknown", fact_ids=[]),
            Evidence(requirement_id="known", status="strong", fact_ids=["f"]),
        ],
    )

    questions = rank_questions(report, max_questions=10)

    assert [q.requirement_id for q in questions] == ["heavy", "light"]
    # 先问「有没有做过」，不在问题里暗示用户具备某段经历或某个数字。
    assert questions[0].question.startswith("是否")


def test_question_list_respects_the_cap():
    requirements = [req(f"r{i}", weight=5) for i in range(20)]
    evidence = [Evidence(requirement_id=f"r{i}", status="unknown", fact_ids=[]) for i in range(20)]

    report = calculate_match(requirements, evidence)

    assert len(rank_questions(report, max_questions=8)) == 8
