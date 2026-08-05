export type FactStatus = "pending" | "confirmed" | "rejected" | "conflict" | "archived";

export const FACT_STATUS_LABEL: Record<FactStatus, string> = {
  pending: "待确认",
  confirmed: "已确认",
  rejected: "已拒绝",
  conflict: "存在冲突",
  archived: "已归档",
};

export type EvidenceStatus =
  | "strong"
  | "partial"
  | "unexpressed"
  | "pending"
  | "unknown"
  | "gap"
  | "conflict";

/** 措辞直接对应规格 §9.3，尤其要让「有能力但没写」和「确认没有」在界面上分得开。 */
export const EVIDENCE_LABEL: Record<EvidenceStatus, string> = {
  strong: "强证据",
  partial: "部分证据",
  unexpressed: "有经历但简历未表达",
  pending: "候选证据待确认",
  unknown: "信息未知",
  gap: "确认缺口",
  conflict: "存在冲突",
};

export interface AtomicFact {
  id: string;
  project_id: string | null;
  text: string;
  source: string;
  status: FactStatus;
  offset_start: number | null;
  offset_end: number | null;
}

export interface Project {
  id: string;
  name: string;
  company: string;
}

export interface GenerationRecord {
  id: string;
  title: string;
  company: string;
  jd_text: string;
  jd_version: number;
  workflow_state: "DRAFT" | "JD_CONFIRMED";
  resume_source_id: string | null;
}

export interface Requirement {
  id: string;
  text: string;
  dimension: string;
  weight: number;
  hard_gate: boolean;
}

export interface Evidence {
  requirement_id: string;
  status: EvidenceStatus;
  fact_ids: string[];
  rationale: string;
}

export interface DimensionScore {
  dimension: string;
  capability_low: number;
  capability_high: number;
  presentation_low: number;
  presentation_high: number;
}

export interface MatchReport {
  capability_low: number;
  capability_high: number;
  presentation_low: number;
  presentation_high: number;
  confidence: string;
  dimensions: DimensionScore[];
  hard_gate_risks: string[];
  strongest: string[];
  unexpressed: string[];
  unknowns: string[];
  confirmed_gaps: string[];
  conflicts: string[];
  requirements: Requirement[];
  evidence: Evidence[];
}

export interface ClarifyingQuestion {
  requirement_id: string;
  question: string;
  reason: string;
  priority: number;
}

export interface InsightClaim {
  conclusion: string;
  kind: "jd_fact" | "user_fact" | "inference" | "unknown";
  confidence: string;
  basis: string[];
  open_questions: string[];
}

export const CLAIM_KIND_LABEL: Record<InsightClaim["kind"], string> = {
  jd_fact: "JD 明确事实",
  user_fact: "用户补充事实",
  inference: "推断",
  unknown: "信息不足",
};

export interface JobInsight {
  positioning: string;
  why_open: string;
  archetypes: { archetype: string; share: number }[];
  frequent_tasks: string[];
  deliverables: string[];
  collaborators: string[];
  success_metrics: string[];
  explicit_requirements: string[];
  implicit_requirements: string[];
  hard_gates: string[];
  boundaries_and_risks: string[];
  interview_focus: string[];
  claims: InsightClaim[];
  open_questions: string[];
}

export interface ClaimViolation {
  code: "missing_citation" | "unconfirmed_fact" | "unsupported_metric" | "immutable_field_changed";
  claim_text: string;
  detail: string;
}

export const VIOLATION_LABEL: Record<ClaimViolation["code"], string> = {
  missing_citation: "缺少事实引用",
  unconfirmed_fact: "引用了未确认的事实",
  unsupported_metric: "数字没有事实支撑",
  immutable_field_changed: "改动了不允许修改的字段",
};

export interface ResumeClaim {
  text: string;
  fact_ids: string[];
  requirement_ids: string[];
}

export interface ResumeDocument {
  id: string;
  label: string;
  sections: { title: string; claims: ResumeClaim[] }[];
}

export interface ResumeResult {
  version_id: string;
  version_number: number;
  strategy: {
    positioning: string;
    strengthen: string[];
    weaken: string[];
    prohibited_claims: string[];
  };
  document: ResumeDocument;
  violations: ClaimViolation[];
}

export interface Artifact<T> {
  payload: T;
  jd_version: number;
  stale: boolean;
}

export interface ResumeSummary {
  id: string;
  label: string;
  original_name: string;
  pages: number;
  status: string;
  created_at: string;
  char_count: number;
}

export type SuggestionAction = "rewrite" | "add_evidence" | "do_not_claim" | "acknowledge";

export const ACTION_LABEL: Record<SuggestionAction, string> = {
  rewrite: "改写就能补",
  add_evidence: "需要补充事实",
  do_not_claim: "不要声称",
  acknowledge: "正面说明",
};

export interface Suggestion {
  requirement_id: string;
  action: SuggestionAction;
  advice: string;
  suggested_text: string;
  fact_ids: string[];
}

export interface MatchPayload {
  report: MatchReport;
  questions: ClarifyingQuestion[];
  advice: { summary: string; suggestions: Suggestion[] };
}

export interface HistoryEntry {
  id: string;
  kind: "match" | "insight";
  title: string;
  company: string;
  jd_version: number;
  workflow_state: string;
  created_at: string;
  jd_excerpt: string;
  resume_label: string | null;
  has_insight: boolean;
  resume_count: number;
  scores: {
    capability_low: number;
    capability_high: number;
    presentation_low: number;
    presentation_high: number;
    hard_gate_count: number;
  } | null;
}
