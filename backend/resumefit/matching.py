"""确定性匹配评分。

规格 §9.4 的分工在这里是硬边界：**模型不出分**。
模型只判断每条要求落在哪个证据状态、引用了哪些事实；本模块负责
状态→区间映射、重要性加权、维度汇总、硬性门槛抽离和区间宽度。
纯函数，无 I/O，可单测。
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

EvidenceStatus = Literal["strong", "partial", "unexpressed", "pending", "unknown", "gap", "conflict"]

# 声称具备能力的状态必须引用事实，否则无从追溯。
CITING_STATUSES = ("strong", "partial", "unexpressed")

# 状态 → (能力区间, 呈现区间)。双指标就在这一步分叉。
#
# 关键：unexpressed 的能力区间与 strong 完全相同——底下是同一批已确认事实，
# 差别只在简历有没有写出来。所以没有新事实时，润色只能抬高呈现度。
# unknown 给宽区间且上界高，因为「资料不足」不等于「不匹配」（§9.3）。
INTERVALS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "strong": ((85, 100), (85, 100)),
    "unexpressed": ((85, 100), (0, 15)),
    "partial": ((45, 70), (45, 70)),
    "pending": ((30, 85), (0, 15)),
    "unknown": ((20, 80), (20, 80)),
    "conflict": ((10, 70), (10, 70)),
    "gap": ((0, 10), (0, 10)),
}


class Requirement(BaseModel):
    id: str
    text: str
    dimension: str = ""
    weight: int = Field(default=3, ge=1, le=5)
    hard_gate: bool = False


class Evidence(BaseModel):
    requirement_id: str
    status: EvidenceStatus
    fact_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class DimensionScore(BaseModel):
    dimension: str
    capability_low: int
    capability_high: int
    presentation_low: int
    presentation_high: int


class ClarifyingQuestion(BaseModel):
    requirement_id: str
    question: str
    reason: str
    priority: int


class MatchReport(BaseModel):
    capability_low: int
    capability_high: int
    presentation_low: int
    presentation_high: int
    confidence: str
    dimensions: list[DimensionScore]
    hard_gate_risks: list[str]
    strongest: list[str]
    unexpressed: list[str]
    unknowns: list[str]
    confirmed_gaps: list[str]
    conflicts: list[str]
    requirements: list[Requirement]
    evidence: list[Evidence]


def _weighted(pairs: list[tuple[int, int, int]]) -> tuple[int, int]:
    """pairs = [(weight, low, high)] → 向外取整的加权区间。"""
    if not pairs:
        return 0, 0
    total = sum(weight for weight, _, _ in pairs)
    low = sum(weight * value for weight, value, _ in pairs) / total
    high = sum(weight * value for weight, _, value in pairs) / total
    return math.floor(low), math.ceil(high)


def calculate_match(
    requirements: list[Requirement], evidence: list[Evidence]
) -> MatchReport:
    by_requirement = {item.requirement_id: item for item in evidence}

    for item in evidence:
        if item.status in CITING_STATUSES and not item.fact_ids:
            raise ValueError(f"证据状态 {item.status} 必须引用至少一条事实：{item.requirement_id}")

    capability: list[tuple[int, int, int]] = []
    presentation: list[tuple[int, int, int]] = []
    per_dimension: dict[str, tuple[list, list]] = {}
    hard_gate_risks, strongest, unexpressed, unknowns, gaps, conflicts = [], [], [], [], [], []

    for requirement in requirements:
        # 没有给出证据判断的要求按「信息未知」处理，不能默认算作不匹配。
        item = by_requirement.get(requirement.id) or Evidence(
            requirement_id=requirement.id, status="unknown"
        )
        (cap_lo, cap_hi), (pres_lo, pres_hi) = INTERVALS[item.status]

        {
            "strong": strongest,
            "unexpressed": unexpressed,
            "unknown": unknowns,
            "gap": gaps,
            "conflict": conflicts,
        }.get(item.status, []).append(requirement.id)

        if requirement.hard_gate:
            # 硬性门槛单独提示，不进综合分，避免被高分维度平均掉（§9.4）。
            if item.status in ("gap", "partial", "conflict"):
                hard_gate_risks.append(requirement.id)
            continue

        capability.append((requirement.weight, cap_lo, cap_hi))
        presentation.append((requirement.weight, pres_lo, pres_hi))
        caps, press = per_dimension.setdefault(requirement.dimension, ([], []))
        caps.append((requirement.weight, cap_lo, cap_hi))
        press.append((requirement.weight, pres_lo, pres_hi))

    cap_low, cap_high = _weighted(capability)
    pres_low, pres_high = _weighted(presentation)
    width = cap_high - cap_low

    return MatchReport(
        capability_low=cap_low,
        capability_high=cap_high,
        presentation_low=pres_low,
        presentation_high=pres_high,
        confidence="较高" if width <= 15 else "中等" if width <= 30 else "偏低",
        dimensions=[
            DimensionScore(
                dimension=dimension,
                capability_low=_weighted(caps)[0],
                capability_high=_weighted(caps)[1],
                presentation_low=_weighted(press)[0],
                presentation_high=_weighted(press)[1],
            )
            for dimension, (caps, press) in per_dimension.items()
        ],
        hard_gate_risks=hard_gate_risks,
        strongest=strongest,
        unexpressed=unexpressed,
        unknowns=unknowns,
        confirmed_gaps=gaps,
        conflicts=conflicts,
        requirements=requirements,
        evidence=evidence,
    )


# 只有这些状态能靠追问收窄；strong / gap 已经有确定答案，再问是浪费。
_ASKABLE = {"unknown": "信息不足", "pending": "候选证据待确认", "partial": "范围或结果不够清晰"}


def rank_questions(report: MatchReport, max_questions: int = 10) -> list[ClarifyingQuestion]:
    """按 重要性 × 区间可收窄幅度 排序（§9.5）。

    问题必须是事实型的：先问有没有做过，不在题面里暗示用户具备某段经历或某个数字。
    """
    by_requirement = {item.requirement_id: item for item in report.evidence}
    ranked = []

    for requirement in report.requirements:
        item = by_requirement.get(requirement.id) or Evidence(
            requirement_id=requirement.id, status="unknown"
        )
        if item.status not in _ASKABLE:
            continue
        (low, high), _ = INTERVALS[item.status]
        ranked.append(
            (
                requirement.weight * (high - low),
                ClarifyingQuestion(
                    requirement_id=requirement.id,
                    question=f"是否做过与「{requirement.text}」直接相关的工作？",
                    reason=_ASKABLE[item.status],
                    priority=requirement.weight * (high - low),
                ),
            )
        )

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [question for _, question in ranked[:max_questions]]
