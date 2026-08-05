import { useEffect, useState } from "react";

import { ApiError, type Api } from "../api";
import { GapGauge } from "../components/GapGauge";
import { MatchResult } from "../components/MatchResult";
import type { GenerationRecord, MatchPayload, ResumeSummary } from "../types";

export function AnalyzePage({ api, onFinish }: { api: Api; onFinish?: () => void }) {
  const [jd, setJd] = useState("");
  const [record, setRecord] = useState<GenerationRecord | null>(null);
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [chosen, setChosen] = useState("");
  const [pasted, setPasted] = useState("");
  const [match, setMatch] = useState<MatchPayload | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const jdReady = record?.workflow_state === "JD_CONFIRMED";
  const resumeReady = jdReady && !!record?.resume_source_id;

  useEffect(() => {
    void api.get<ResumeSummary[]>("/resumes").then(setResumes).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setBusy("");
    }
  }

  const confirmJd = () =>
    run("确认 JD", async () => {
      const current = record ?? (await api.post<GenerationRecord>("/records", {}));
      await api.put(`/records/${current.id}/jd`, { text: jd });
      setRecord(await api.post<GenerationRecord>(`/records/${current.id}/jd/confirm`));
      setMatch(null);
    });

  const useResume = (sourceId: string) =>
    run("选择简历", async () => {
      setChosen(sourceId);
      setRecord(await api.put<GenerationRecord>(`/records/${record!.id}/resume`, {
        resume_source_id: sourceId,
      }));
      setMatch(null);
    });

  const savePasted = () =>
    run("保存简历", async () => {
      const saved = await api.post<ResumeSummary>("/resumes", {
        text: pasted,
        label: `粘贴于 ${new Date().toLocaleDateString("zh-CN")}`,
      });
      setResumes(await api.get<ResumeSummary[]>("/resumes"));
      setPasted("");
      await useResume(saved.id);
    });

  const upload = (file: File) =>
    run("上传简历", async () => {
      const form = new FormData();
      form.append("file", file);
      const saved = await api.upload<ResumeSummary>("/resumes/upload", form);
      setResumes(await api.get<ResumeSummary[]>("/resumes"));
      await useResume(saved.id);
    });

  const analyse = () =>
    run("分析", async () => {
      setMatch(await api.post<MatchPayload>(`/records/${record!.id}/match`));
      onFinish?.();
    });

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">匹配分析</p>
        <h1>把一份 JD 和一份简历放到一起</h1>
        <p className="lede">
          先确认岗位 JD，再指定这次用哪份简历。分析会分别算出你的经历撑得起多少、
          简历眼下讲出来了多少，然后告诉你差在哪、怎么改。
        </p>
      </header>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <section className="step" data-done={jdReady}>
        <span className="step-n" aria-hidden="true">1</span>
        <div className="step-body">
          <div className="step-head">
            <h2>粘贴岗位 JD</h2>
            {jdReady && (
              <span className="tag" data-t="confirmed">
                已确认 · 第 {record!.jd_version} 版
              </span>
            )}
          </div>
          <label htmlFor="jd">岗位描述全文</label>
          <textarea
            id="jd"
            rows={9}
            value={jd}
            onChange={(event) => setJd(event.target.value)}
            placeholder="把招聘页面上的岗位描述整段贴进来"
          />
          <p className="hint">
            确认后才能开始分析。之后再改 JD，这条记录会退回草稿，已有结果标记为过期。
          </p>
          <div className="row">
            <button type="button" className="go" onClick={confirmJd} disabled={!jd.trim() || !!busy}>
              {jdReady ? "重新确认 JD" : "确认 JD"}
            </button>
          </div>
        </div>
      </section>

      <section className="step" data-locked={!jdReady} data-done={resumeReady}>
        <span className="step-n" aria-hidden="true">2</span>
        <div className="step-body">
          <div className="step-head">
            <h2>选择这次用哪份简历</h2>
            {resumeReady && (
              <span className="tag" data-t="confirmed">
                {resumes.find((item) => item.id === record?.resume_source_id)?.label ?? "已选择"}
              </span>
            )}
          </div>

          {resumes.length > 0 && (
            <>
              <h4>简历库</h4>
              <ul className="plain rows">
                {resumes.map((item) => (
                  <li key={item.id}>
                    <div className="step-head">
                      <button
                        type="button"
                        onClick={() => useResume(item.id)}
                        disabled={!jdReady || !!busy}
                        aria-pressed={record?.resume_source_id === item.id}
                      >
                        {record?.resume_source_id === item.id ? "正在使用" : "用这份"}
                      </button>
                      <strong>{item.label}</strong>
                      <span className="hint data">
                        {item.char_count} 字 · {item.created_at.slice(0, 10)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          <h4>或者新加一份</h4>
          <label htmlFor="upload">上传文件（TXT、DOCX、文本型 PDF）</label>
          <input
            id="upload"
            type="file"
            accept=".txt,.md,.docx,.pdf"
            disabled={!jdReady || !!busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
              event.target.value = "";
            }}
          />
          <p className="hint">扫描版 PDF 提取不到文字，会明确告诉你，不会当成空简历。</p>

          <label htmlFor="paste">或直接粘贴简历正文</label>
          <textarea
            id="paste"
            rows={6}
            value={pasted}
            onChange={(event) => setPasted(event.target.value)}
            disabled={!jdReady || !!busy}
          />
          <div className="row">
            <button type="button" onClick={savePasted} disabled={!jdReady || !pasted.trim() || !!busy}>
              保存并使用
            </button>
          </div>
        </div>
      </section>

      <section className="step" data-locked={!resumeReady} data-done={!!match}>
        <span className="step-n" aria-hidden="true">3</span>
        <div className="step-body">
          <h2>分析匹配度</h2>
          <p className="hint">
            会调用你配置的模型。判断由模型给出，分数由本地规则算，两件事分开。
          </p>
          <div className="row">
            <button type="button" className="go" onClick={analyse} disabled={!resumeReady || !!busy}>
              {busy === "分析" ? "分析中…" : match ? "重新分析" : "开始分析"}
            </button>
            {chosen && !resumeReady && <span className="hint">先确认 JD</span>}
          </div>
        </div>
      </section>

      {match && (
        <>
          <GapGauge
            report={match.report}
            requirementText={(id) =>
              match.report.requirements.find((item) => item.id === id)?.text ?? id
            }
          />
          <MatchResult payload={match} recordId={record!.id} api={api} />
        </>
      )}
    </>
  );
}
