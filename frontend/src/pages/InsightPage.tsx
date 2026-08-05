import { useState } from "react";

import { ApiError, type Api } from "../api";
import { CLAIM_KIND_LABEL, type GenerationRecord, type JobInsight } from "../types";

/** 独立可选模块：只读 JD，不需要简历，也不产出匹配结果。 */
export function InsightPage({ api }: { api: Api }) {
  const [jd, setJd] = useState("");
  const [insight, setInsight] = useState<JobInsight | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const analyse = async () => {
    setBusy(true);
    setError("");
    try {
      const record = await api.post<GenerationRecord>("/records", { title: "岗位解读" });
      await api.put(`/records/${record.id}/jd`, { text: jd });
      await api.post(`/records/${record.id}/jd/confirm`);
      setInsight(await api.post<JobInsight>(`/records/${record.id}/insight`));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">岗位解读 · 独立模块</p>
        <h1>这个岗位实际上在做什么</h1>
        <p className="lede">
          只看 JD，不涉及你的简历，也不算匹配度。用来判断一个岗位值不值得投，
          或者面试前搞清楚对方到底要人干什么。
        </p>
      </header>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <section className="step">
        <div className="step-body" style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="insight-jd">岗位描述全文</label>
          <textarea
            id="insight-jd"
            rows={9}
            value={jd}
            onChange={(event) => setJd(event.target.value)}
            placeholder="把招聘页面上的岗位描述整段贴进来"
          />
          <div className="row">
            <button type="button" className="go" onClick={analyse} disabled={!jd.trim() || busy}>
              {busy ? "解读中…" : "解读岗位"}
            </button>
          </div>
        </div>
      </section>

      {insight && <InsightView insight={insight} />}
    </>
  );
}

function InsightView({ insight }: { insight: JobInsight }) {
  return (
    <>
      <section className="gauge">
        <p className="eyebrow">一句话定位</p>
        <h2>{insight.positioning}</h2>
        <p style={{ marginTop: "0.75rem" }}>{insight.why_open}</p>

        <h4>岗位重心</h4>
        <div className="gauge-track">
          {insight.archetypes.map((item) => (
            <div className="gauge-row" key={item.archetype} role="group" aria-label={item.archetype}>
              <span className="gauge-name">{item.archetype}</span>
              <span className="gauge-bar">
                <span
                  className="gauge-fill"
                  data-metric="share"
                  style={{ left: 0, width: `${item.share}%` }}
                />
              </span>
              <span className="gauge-value">{item.share}%</span>
            </div>
          ))}
        </div>
        <p className="hint">比例只用于解释重心，不是科学测量。</p>
      </section>

      <section className="step">
        <div className="step-body" style={{ gridColumn: "1 / -1" }}>
          <Block title="高频实际任务" items={insight.frequent_tasks} />
          <Block title="主要交付物" items={insight.deliverables} />
          <Block title="真实协作关系" items={insight.collaborators} />
          <Block title="可能背的指标" items={insight.success_metrics} />
          <Block title="JD 没写但需要的" items={insight.implicit_requirements} />
          <Block title="硬性门槛" items={insight.hard_gates} />
          <Block title="岗位边界与风险" items={insight.boundaries_and_risks} />
          <Block title="面试重点" items={insight.interview_focus} />
        </div>
      </section>

      <section className="step">
        <div className="step-body" style={{ gridColumn: "1 / -1" }}>
          <h2>结论与依据</h2>
          <p className="hint">每条都标了这是 JD 明确写的，还是根据岗位模式推出来的。</p>
          <ul className="plain rows">
            {insight.claims.map((claim) => (
              <li key={claim.conclusion}>
                <div className="step-head">
                  <span className="tag" data-t={claim.kind}>
                    {CLAIM_KIND_LABEL[claim.kind]}
                  </span>
                  <span className="hint data">置信度 {claim.confidence}</span>
                </div>
                <p style={{ margin: "0.375rem 0" }}>
                  <strong>{claim.conclusion}</strong>
                </p>
                {claim.basis.length > 0 && (
                  <ul className="hint" style={{ margin: 0 }}>
                    {claim.basis.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
          <Block title="仍需向面试官确认" items={insight.open_questions} />
        </div>
      </section>
    </>
  );
}

function Block({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </>
  );
}
