import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { App } from "./App";
import type { Api } from "./api";

const REPORT = {
  capability_low: 88,
  capability_high: 96,
  presentation_low: 30,
  presentation_high: 41,
  confidence: "较高",
  dimensions: [
    {
      dimension: "数据、评测与效果迭代",
      capability_low: 88,
      capability_high: 96,
      presentation_low: 30,
      presentation_high: 41,
    },
  ],
  hard_gate_risks: ["r9"],
  strongest: [],
  unexpressed: ["r1"],
  unknowns: [],
  confirmed_gaps: [],
  conflicts: [],
  requirements: [
    { id: "r1", text: "搭建评测体系", dimension: "评测", weight: 5, hard_gate: false },
    { id: "r9", text: "5 年以上产品经验", dimension: "门槛", weight: 5, hard_gate: true },
  ],
  evidence: [{ requirement_id: "r1", status: "unexpressed", fact_ids: ["f1"], rationale: "事实库有证据" }],
};

const MATCH = {
  report: REPORT,
  questions: [],
  advice: {
    summary: "有一条能力已经具备但简历没写出来。",
    suggestions: [
      {
        requirement_id: "r1",
        action: "rewrite",
        advice: "把评测集建设写进项目要点",
        suggested_text: "建立 200 条测试集，覆盖 12 个场景",
        fact_ids: ["f1"],
      },
    ],
  },
};

function fakeApi(routes: Record<string, unknown> = {}): Api {
  const resolve = (path: string) => routes[path] ?? {};
  return {
    get: vi.fn(async (path: string) => routes[path] ?? []),
    post: vi.fn(async (path: string) => resolve(path)),
    put: vi.fn(async (path: string) => resolve(path)),
    upload: vi.fn(async (path: string) => resolve(path)),
  } as unknown as Api;
}

const FLOW = {
  "/resumes": [
    { id: "res-1", label: "AI 产品版", original_name: "r.txt", pages: 1, status: "success", created_at: "2026-08-01T09:00:00", char_count: 1200 },
  ],
  "/records": { id: "rec-1", workflow_state: "DRAFT", jd_version: 0, resume_source_id: null },
  "/records/rec-1/jd/confirm": { id: "rec-1", workflow_state: "JD_CONFIRMED", jd_version: 1, resume_source_id: null },
  "/records/rec-1/resume": { id: "rec-1", workflow_state: "JD_CONFIRMED", jd_version: 1, resume_source_id: "res-1" },
  "/records/rec-1/match": MATCH,
};

test("rail separates the main flow from optional modules and tracks nothing", () => {
  render(<App api={fakeApi()} />);

  const nav = screen.getByRole("navigation", { name: "主导航" });
  expect(within(nav).getByText("主流程")).toBeInTheDocument();
  expect(within(nav).getByText("按需使用")).toBeInTheDocument();
  for (const label of ["匹配分析", "分析记录", "岗位解读", "我的材料", "设置"]) {
    expect(within(nav).getByRole("button", { name: label })).toBeInTheDocument();
  }
  expect(screen.queryByText("已投递")).not.toBeInTheDocument();
});

test("job insight is reachable without touching a resume", async () => {
  render(<App api={fakeApi()} />);

  await userEvent.click(screen.getByRole("button", { name: "岗位解读" }));

  expect(screen.getByRole("heading", { name: "这个岗位实际上在做什么" })).toBeInTheDocument();
  expect(screen.getByText(/不涉及你的简历/)).toBeInTheDocument();
  expect(screen.queryByText("简历库")).not.toBeInTheDocument();
});

test("the flow gates each step: JD, then resume, then analysis", async () => {
  render(<App api={fakeApi(FLOW)} />);

  expect(screen.getByRole("button", { name: "开始分析" })).toBeDisabled();
  // 简历库是异步拉来的，等它出现再断言它此刻不可选。
  expect(await screen.findByRole("button", { name: "用这份" })).toBeDisabled();

  await userEvent.type(screen.getByLabelText("岗位描述全文"), "搭建评测体系");
  await userEvent.click(screen.getByRole("button", { name: "确认 JD" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "用这份" })).toBeEnabled());

  // JD 确认了但还没选简历，分析仍然锁着。
  expect(screen.getByRole("button", { name: "开始分析" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "用这份" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "开始分析" })).toBeEnabled());
});

test("the gauge shows the recoverable gap and keeps hard gates off the score", async () => {
  render(<App api={fakeApi(FLOW)} />);

  await userEvent.type(screen.getByLabelText("岗位描述全文"), "搭建评测体系");
  await userEvent.click(screen.getByRole("button", { name: "确认 JD" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "用这份" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "用这份" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "开始分析" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "开始分析" }));

  const capability = await screen.findByRole("group", { name: "岗位能力适配度" });
  const presentation = screen.getByRole("group", { name: "当前简历呈现度" });
  expect(capability).toHaveTextContent("88–96");
  expect(presentation).toHaveTextContent("30–41");

  // 88 − 41 = 47：这就是改写能补回来的部分，标注在同一条轨道上。
  const delta = screen.getByRole("group", { name: "改写可补" });
  expect(delta).toHaveTextContent("47 分");

  // 硬门槛单独成戳，不进上面的分数。
  expect(screen.getByText("硬性门槛 · 不计入上面的分数")).toBeInTheDocument();
  expect(screen.getByText("5 年以上产品经验")).toBeInTheDocument();
});

test("suggestions arrive with usable copy, not just a score", async () => {
  render(<App api={fakeApi(FLOW)} />);

  await userEvent.type(screen.getByLabelText("岗位描述全文"), "搭建评测体系");
  await userEvent.click(screen.getByRole("button", { name: "确认 JD" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "用这份" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "用这份" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "开始分析" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "开始分析" }));

  expect(await screen.findByRole("heading", { name: "简历修改建议" })).toBeInTheDocument();
  expect(screen.getByText("改写就能补")).toBeInTheDocument();
  expect(screen.getByText("建立 200 条测试集，覆盖 12 个场景")).toBeInTheDocument();
});

test("history lists past analyses with both scores and no delivery status", async () => {
  const api = fakeApi({
    "/records/history": [
      {
        id: "rec-1",
        kind: "match",
        title: "AI 产品经理",
        company: "示例公司",
        jd_version: 1,
        workflow_state: "JD_CONFIRMED",
        created_at: "2026-08-04T10:30:00",
        jd_excerpt: "负责智能客服产品规划",
        resume_label: "AI 产品版",
        has_insight: true,
        resume_count: 2,
        scores: {
          capability_low: 88,
          capability_high: 96,
          presentation_low: 30,
          presentation_high: 41,
          hard_gate_count: 1,
        },
      },
    ],
  });
  render(<App api={api} />);

  await userEvent.click(screen.getByRole("button", { name: "分析记录" }));

  expect(await screen.findByRole("heading", { name: "AI 产品经理" })).toBeInTheDocument();
  expect(screen.getByText("能力 88–96")).toBeInTheDocument();
  expect(screen.getByText("呈现 30–41")).toBeInTheDocument();
  expect(screen.getByText("改写可补 47 分")).toBeInTheDocument();
  expect(screen.getByText("1 项硬门槛风险")).toBeInTheDocument();
  expect(screen.getByText("含岗位解读")).toBeInTheDocument();
  expect(screen.getByText(/使用的简历：AI 产品版/)).toBeInTheDocument();
});

test("history invites action when empty", async () => {
  render(<App api={fakeApi({ "/records/history": [] })} />);

  await userEvent.click(screen.getByRole("button", { name: "分析记录" }));

  expect(await screen.findByText(/还没有分析记录/)).toBeInTheDocument();
});
