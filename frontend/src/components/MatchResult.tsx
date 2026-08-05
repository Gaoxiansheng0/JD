import { useState } from "react";

import { ApiError, type Api } from "../api";
import {
  ACTION_LABEL,
  EVIDENCE_LABEL,
  VIOLATION_LABEL,
  type MatchPayload,
  type ResumeResult,
} from "../types";

const TAG_TONE: Record<string, string> = {
  strong: "strong",
  unexpressed: "unexpressed",
  gap: "gap",
  conflict: "conflict",
};

export function MatchResult({
  payload,
  recordId,
  api,
}: {
  payload: MatchPayload;
  recordId: string;
  api: Api;
}) {
  const { report, advice, questions } = payload;
  const [resume, setResume] = useState<ResumeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const text = (id: string) => report.requirements.find((item) => item.id === id)?.text ?? id;

  const generate = async () => {
    setBusy(true);
    setError("");
    try {
      setResume(await api.post<ResumeResult>(`/records/${recordId}/resumes`));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="step">
        <span className="step-n" aria-hidden="true">4</span>
        <div className="step-body">
          <h2>简历修改建议</h2>
          <p>{advice.summary}</p>

          {advice.suggestions.length === 0 ? (
            <p className="hint">没有需要修改的地方。</p>
          ) : (
            <ul className="plain rows">
              {advice.suggestions.map((item) => (
                <li key={item.requirement_id + item.action}>
                  <div className="step-head">
                    <span className="tag" data-t={item.action === "do_not_claim" ? "gap" : item.action === "rewrite" ? "unexpressed" : undefined}>
                      {ACTION_LABEL[item.action]}
                    </span>
                    <strong>{text(item.requirement_id)}</strong>
                  </div>
                  <p className="hint">{item.advice}</p>
                  {item.suggested_text && (
                    <div className="recover">
                      <p style={{ margin: 0 }}>{item.suggested_text}</p>
                      <p className="hint" style={{ marginBottom: 0 }}>
                        引用 {item.fact_ids.length} 条已确认事实 · 可直接用
                      </p>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="step">
        <span className="step-n" aria-hidden="true">5</span>
        <div className="step-body">
          <h2>生成整份定制简历</h2>
          <p className="hint">
            可选。会按互补原则挑 2–4 个重点项目重组，每条成果都必须能追溯到已确认事实。
          </p>
          {error && (
            <p role="alert" className="alert">
              {error}
            </p>
          )}
          <div className="row">
            <button type="button" onClick={generate} disabled={busy}>
              {busy ? "生成中…" : resume ? "再生成一版" : "生成定制简历"}
            </button>
          </div>
          {resume && <ResumeView result={resume} />}
        </div>
      </section>

      <details className="note">
        <summary>逐条证据（{report.evidence.length} 条要求）</summary>
        <ul className="plain rows" style={{ marginTop: "0.75rem" }}>
          {report.evidence.map((item) => (
            <li key={item.requirement_id}>
              <div className="step-head">
                <span className="tag" data-t={TAG_TONE[item.status]}>
                  {EVIDENCE_LABEL[item.status]}
                </span>
                <span>{text(item.requirement_id)}</span>
              </div>
              {item.rationale && <p className="hint">{item.rationale}</p>}
            </li>
          ))}
        </ul>

        <h4>分维度</h4>
        <table>
          <thead>
            <tr>
              <th scope="col">维度</th>
              <th scope="col">能力</th>
              <th scope="col">呈现</th>
            </tr>
          </thead>
          <tbody>
            {report.dimensions.map((item) => (
              <tr key={item.dimension}>
                <th scope="row">{item.dimension}</th>
                <td className="num">
                  {item.capability_low}–{item.capability_high}
                </td>
                <td className="num">
                  {item.presentation_low}–{item.presentation_high}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {questions.length > 0 && (
          <>
            <h4>补充这些事实能让区间更准</h4>
            <ol>
              {questions.map((question) => (
                <li key={question.requirement_id}>
                  {question.question}
                  <span className="hint"> （{question.reason}）</span>
                </li>
              ))}
            </ol>
            <p className="hint">到「我的材料」补充并确认事实后重新分析。</p>
          </>
        )}
      </details>
    </>
  );
}

function ResumeView({ result }: { result: ResumeResult }) {
  return (
    <div style={{ marginTop: "1.25rem" }}>
      <p className="eyebrow data">第 {result.version_number} 版 · 不可覆盖</p>
      <p>{result.strategy.positioning}</p>

      {result.document.sections.map((section) => (
        <div key={section.title}>
          <h4>{section.title}</h4>
          <ul>
            {section.claims.map((claim) => (
              <li key={claim.text}>
                {claim.text}
                <span className="hint data"> · {claim.fact_ids.length} 条事实</span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {result.strategy.prohibited_claims.length > 0 && (
        <>
          <h4>不建议声称</h4>
          <ul>
            {result.strategy.prohibited_claims.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}

      {result.violations.length > 0 && (
        <div className="alert">
          <p className="eyebrow" style={{ color: "inherit" }}>
            已拦下 {result.violations.length} 条表达
          </p>
          <ul className="plain">
            {result.violations.map((violation) => (
              <li key={violation.claim_text + violation.code}>
                <span className="tag" data-t="risk">
                  {VIOLATION_LABEL[violation.code]}
                </span>{" "}
                {violation.claim_text}
                <p className="hint">{violation.detail}</p>
              </li>
            ))}
          </ul>
          <p className="hint">这些没有进入简历。补充事实、改写表述或直接删掉。</p>
        </div>
      )}
    </div>
  );
}
