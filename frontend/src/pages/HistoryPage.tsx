import { useEffect, useState } from "react";

import { ApiError, type Api } from "../api";
import { GapGauge } from "../components/GapGauge";
import { MatchResult } from "../components/MatchResult";
import type { Artifact, HistoryEntry, MatchPayload } from "../types";

export function HistoryPage({ api, reloadKey }: { api: Api; reloadKey: number }) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Artifact<MatchPayload> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void api
      .get<HistoryEntry[]>("/records/history")
      .then(setEntries)
      .catch((cause) => setError(cause instanceof ApiError ? cause.message : String(cause)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  const open = async (id: string) => {
    setError("");
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    try {
      setDetail(await api.get<Artifact<MatchPayload>>(`/records/${id}/match`));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    }
  };

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">分析记录</p>
        <h1>你分析过的岗位</h1>
        <p className="lede">
          这里只记录你分析过什么、结果是什么。不记录投递状态，也不做求职进度管理。
        </p>
      </header>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {entries.length === 0 ? (
        <p className="empty">还没有分析记录。到「匹配分析」贴一份 JD 开始。</p>
      ) : (
        <ul className="plain">
          {entries.map((entry) => (
            <li key={entry.id} className="step" style={{ display: "block" }}>
              <div className="step-head">
                <h2>{entry.title || "未命名岗位"}</h2>
                {entry.kind === "insight" && <span className="tag">仅岗位解读</span>}
                {entry.company && <span className="hint">{entry.company}</span>}
                <span className="hint data">{entry.created_at.slice(0, 16).replace("T", " ")}</span>
              </div>

              <p className="hint" style={{ marginTop: "0.25rem" }}>
                {entry.jd_excerpt}
                {entry.jd_excerpt.length >= 120 && "…"}
              </p>

              <div className="row" style={{ marginTop: "0.625rem" }}>
                {entry.scores ? (
                  <>
                    <span className="tag" data-t="strong">
                      能力 {entry.scores.capability_low}–{entry.scores.capability_high}
                    </span>
                    <span className="tag">
                      呈现 {entry.scores.presentation_low}–{entry.scores.presentation_high}
                    </span>
                    {entry.scores.capability_low > entry.scores.presentation_high && (
                      <span className="tag" data-t="unexpressed">
                        改写可补 {entry.scores.capability_low - entry.scores.presentation_high} 分
                      </span>
                    )}
                    {entry.scores.hard_gate_count > 0 && (
                      <span className="tag" data-t="risk">
                        {entry.scores.hard_gate_count} 项硬门槛风险
                      </span>
                    )}
                  </>
                ) : entry.kind === "match" ? (
                  <span className="tag">尚未分析匹配度</span>
                ) : null}
                {entry.has_insight && entry.kind === "match" && (
                  <span className="tag">含岗位解读</span>
                )}
                {entry.resume_count > 0 && (
                  <span className="tag data">{entry.resume_count} 版定制简历</span>
                )}
              </div>

              <p className="hint">
                {entry.kind === "insight"
                  ? "这条只解读了岗位，没有做简历匹配。"
                  : `使用的简历：${entry.resume_label || "未指定"} · JD 第 ${entry.jd_version} 版`}
              </p>

              {entry.scores && (
                <div className="row">
                  <button type="button" onClick={() => open(entry.id)} aria-expanded={openId === entry.id}>
                    {openId === entry.id ? "收起" : "查看结果"}
                  </button>
                </div>
              )}

              {openId === entry.id && detail && (
                <div style={{ marginTop: "1.25rem" }}>
                  {detail.stale && (
                    <p className="alert">
                      这份结果基于 JD 的旧版本（第 {detail.jd_version} 版），JD 之后被改过。
                      重新分析才能得到当前 JD 的结果。
                    </p>
                  )}
                  <GapGauge
                    report={detail.payload.report}
                    requirementText={(id) =>
                      detail.payload.report.requirements.find((item) => item.id === id)?.text ?? id
                    }
                  />
                  <MatchResult payload={detail.payload} recordId={entry.id} api={api} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
