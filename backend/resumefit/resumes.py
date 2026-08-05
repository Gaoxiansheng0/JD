"""简历文档模型与事实引用校验。

规格 §10.7 / §17：模型引用不存在或未确认的事实时，**阻止该段进入正式简历**，
不是给个警告了事。全部是纯函数，模型的输出必须先过这道闸门。
"""

from __future__ import annotations

import re
from typing import Iterable

from pydantic import BaseModel, Field

# 规格 §10.2：模型默认不能修改的字段。
IMMUTABLE_FIELDS = (
    "full_name",
    "contact",
    "phone",
    "email",
    "company",
    "employment_start",
    "employment_end",
    "job_title",
    "school",
    "degree",
    "graduation_date",
    "certificates",
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# 短句（技能词、栏目标题）不要求引用；成句的成果陈述必须有出处。
_SUBSTANTIVE_CHARS = 10


class ResumeClaim(BaseModel):
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class ResumeSection(BaseModel):
    title: str
    claims: list[ResumeClaim] = Field(default_factory=list)


class ResumeVersion(BaseModel):
    id: str
    label: str = ""
    sections: list[ResumeSection] = Field(default_factory=list)


class ClaimViolation(BaseModel):
    code: str
    claim_text: str
    detail: str


def validate_resume_claims(
    version: ResumeVersion,
    confirmed_fact_ids: Iterable[str],
    fact_texts: dict[str, str] | None = None,
) -> list[ClaimViolation]:
    confirmed = set(confirmed_fact_ids)
    fact_texts = fact_texts or {}
    violations: list[ClaimViolation] = []

    for section in version.sections:
        for claim in section.claims:
            if not claim.fact_ids:
                if len(claim.text.strip()) >= _SUBSTANTIVE_CHARS:
                    violations.append(
                        ClaimViolation(
                            code="missing_citation",
                            claim_text=claim.text,
                            detail="成果陈述必须引用已确认事实",
                        )
                    )
                continue

            unknown = [fact_id for fact_id in claim.fact_ids if fact_id not in confirmed]
            if unknown:
                violations.append(
                    ClaimViolation(
                        code="unconfirmed_fact",
                        claim_text=claim.text,
                        detail=f"引用了不存在或未确认的事实：{'、'.join(unknown)}",
                    )
                )
                continue

            # 数字口径不能改：简历里出现的每个数字都要在被引用事实的原文里出现过。
            cited = " ".join(fact_texts.get(fact_id, "") for fact_id in claim.fact_ids)
            invented = [n for n in _NUMBER.findall(claim.text) if n not in _NUMBER.findall(cited)]
            if invented:
                violations.append(
                    ClaimViolation(
                        code="unsupported_metric",
                        claim_text=claim.text,
                        detail=f"数字未出现在被引用事实中：{'、'.join(invented)}",
                    )
                )

    return violations


def validate_immutable_fields(
    original: dict[str, object], generated: dict[str, object]
) -> list[ClaimViolation]:
    """模型可以提示问题，但不能自行改写这些字段（规格 §10.2）。"""
    return [
        ClaimViolation(
            code="immutable_field_changed",
            claim_text=field,
            detail=f"{field} 不允许由模型修改：{original[field]!r} → {generated[field]!r}",
        )
        for field in IMMUTABLE_FIELDS
        if field in original and field in generated and original[field] != generated[field]
    ]
