import { useEffect, useState } from "react";

import { ApiError, type Api } from "../api";
import { FACT_STATUS_LABEL, type AtomicFact, type Project, type ResumeSummary } from "../types";

interface ProjectDetail extends Project {
  facts: AtomicFact[];
}

export function MaterialsPage({ api }: { api: Api }) {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function guard(action: () => Promise<void>) {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void guard(async () => {
      setResumes(await api.get<ResumeSummary[]>("/resumes"));
      setProjects(await api.get<Project[]>("/projects"));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const open = (id: string) =>
    guard(async () => {
      setOpenId(openId === id ? null : id);
      setDetail(openId === id ? null : await api.get<ProjectDetail>(`/projects/${id}`));
    });

  const importMaterial = () =>
    guard(async () => {
      const result = await api.post<{ project: Project }>("/projects/import", {
        name,
        text,
        original_name: "粘贴素材",
      });
      setName("");
      setText("");
      setProjects(await api.get<Project[]>("/projects"));
      setOpenId(result.project.id);
      setDetail(await api.get<ProjectDetail>(`/projects/${result.project.id}`));
    });

  const setStatus = (factId: string, status: string) =>
    guard(async () => {
      await (status === "confirmed"
        ? api.post(`/facts/${factId}/confirm`)
        : api.post(`/facts/${factId}/status`, { status }));
      if (openId) setDetail(await api.get<ProjectDetail>(`/projects/${openId}`));
    });

  const confirmedCount = detail?.facts.filter((fact) => fact.status === "confirmed").length ?? 0;

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">我的材料</p>
        <h1>简历库与经历事实</h1>
        <p className="lede">
          经历库存的是你确认过的具体事实，不是润色后的简历段落。只有已确认的事实能用来支撑简历表达。
        </p>
      </header>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <section className="step">
        <div className="step-body" style={{ gridColumn: "1 / -1" }}>
          <h2>简历库</h2>
          {resumes.length === 0 ? (
            <p className="hint">还没有简历。到「匹配分析」上传或粘贴一份。</p>
          ) : (
            <ul className="plain rows">
              {resumes.map((item) => (
                <li key={item.id}>
                  <div className="step-head">
                    <strong>{item.label}</strong>
                    <span className="hint data">
                      {item.char_count} 字 · {item.created_at.slice(0, 10)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="step">
        <div className="step-body" style={{ gridColumn: "1 / -1" }}>
          <h2>从素材拆出候选事实</h2>
          <label htmlFor="project-name">项目名称</label>
          <input
            id="project-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="智能客服大模型改造"
          />
          <label htmlFor="material">项目复盘、工作笔记或简历片段</label>
          <textarea
            id="material"
            rows={7}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <p className="hint">只做切分，不会归纳素材里没有的东西。拆出的每条都要你确认。</p>
          <div className="row">
            <button
              type="button"
              className="go"
              onClick={importMaterial}
              disabled={!name.trim() || !text.trim() || busy}
            >
              拆分为候选事实
            </button>
          </div>
        </div>
      </section>

      <section className="step">
        <div className="step-body" style={{ gridColumn: "1 / -1" }}>
          <h2>项目经历</h2>
          {projects.length === 0 ? (
            <p className="hint">还没有项目。</p>
          ) : (
            <ul className="plain rows">
              {projects.map((project) => (
                <li key={project.id}>
                  <div className="step-head">
                    <button
                      type="button"
                      onClick={() => open(project.id)}
                      aria-expanded={openId === project.id}
                    >
                      {openId === project.id ? "收起" : "查看事实"}
                    </button>
                    <strong>{project.name}</strong>
                    {project.company && <span className="hint">{project.company}</span>}
                  </div>

                  {openId === project.id && detail && (
                    <>
                      <p className="hint" style={{ marginTop: "0.625rem" }}>
                        {detail.facts.length} 条，其中 {confirmedCount} 条已确认可用
                      </p>
                      <ul className="plain rows">
                        {detail.facts.map((fact) => (
                          <li key={fact.id}>
                            <div className="step-head">
                              <span className="tag" data-t={fact.status}>
                                {FACT_STATUS_LABEL[fact.status]}
                              </span>
                              <span>{fact.text}</span>
                            </div>
                            {fact.status === "conflict" && (
                              <p className="hint">
                                和已有事实的数字对不上。先编辑或拒绝，冲突的事实不能直接确认。
                              </p>
                            )}
                            <div className="row" style={{ marginTop: "0.375rem" }}>
                              {fact.status !== "confirmed" && fact.status !== "conflict" && (
                                <button
                                  type="button"
                                  onClick={() => setStatus(fact.id, "confirmed")}
                                  disabled={busy}
                                >
                                  确认
                                </button>
                              )}
                              {fact.status !== "rejected" && (
                                <button
                                  type="button"
                                  onClick={() => setStatus(fact.id, "rejected")}
                                  disabled={busy}
                                >
                                  拒绝
                                </button>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}
