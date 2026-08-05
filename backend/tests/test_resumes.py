from resumefit.resumes import (
    IMMUTABLE_FIELDS,
    ResumeClaim,
    ResumeSection,
    ResumeVersion,
    validate_resume_claims,
    validate_immutable_fields,
)


def version_with(*claims: ResumeClaim) -> ResumeVersion:
    return ResumeVersion(
        id="v1", sections=[ResumeSection(title="重点项目经历", claims=list(claims))]
    )


def test_resume_claim_without_confirmed_fact_is_blocked():
    version = version_with(ResumeClaim(text="主导模型训练", fact_ids=["missing"]))

    violations = validate_resume_claims(version, confirmed_fact_ids={"fact-1"})

    assert violations[0].code == "unconfirmed_fact"
    assert violations[0].claim_text == "主导模型训练"


def test_claim_citing_a_confirmed_fact_passes():
    version = version_with(ResumeClaim(text="搭建评测体系", fact_ids=["fact-1"]))

    assert validate_resume_claims(
        version, confirmed_fact_ids={"fact-1"}, fact_texts={"fact-1": "搭建评测体系"}
    ) == []


def test_substantive_claim_must_cite_something():
    version = version_with(ResumeClaim(text="主导了从 0 到 1 的产品落地", fact_ids=[]))

    assert validate_resume_claims(version, confirmed_fact_ids=set())[0].code == "missing_citation"


def test_number_absent_from_the_cited_fact_is_rejected():
    version = version_with(ResumeClaim(text="首次解决率提升至 91%", fact_ids=["fact-1"]))

    violations = validate_resume_claims(
        version,
        confirmed_fact_ids={"fact-1"},
        fact_texts={"fact-1": "首次解决率提升至 71%"},
    )

    assert violations[0].code == "unsupported_metric"


def test_number_present_in_the_cited_fact_is_allowed():
    version = version_with(ResumeClaim(text="首次解决率提升至 71%", fact_ids=["fact-1"]))

    assert validate_resume_claims(
        version,
        confirmed_fact_ids={"fact-1"},
        fact_texts={"fact-1": "把首次解决率从 52% 提升至 71%"},
    ) == []


def test_model_cannot_change_protected_profile_fields():
    original = {"full_name": "张三", "company": "示例公司", "graduation_date": "2019-06"}
    generated = {"full_name": "张三丰", "company": "示例公司", "graduation_date": "2019-06"}

    violations = validate_immutable_fields(original, generated)

    assert [v.code for v in violations] == ["immutable_field_changed"]
    assert "full_name" in violations[0].claim_text


def test_immutable_field_list_covers_the_spec():
    assert {"full_name", "company", "job_title", "graduation_date"} <= set(IMMUTABLE_FIELDS)
