# Resume Fit

Resume Fit 是一款面向中文 AI 产品经理的本地简历定制工具。它根据岗位 JD 还原岗位的实际工作内容，把岗位要求与用户的主简历、个人档案和项目经历库建立可追溯的证据匹配，再基于用户确认过的真实事实生成岗位定制简历和轻量面试准备材料。

项目正在实现中。当前实现范围是设计规格的核心闭环：岗位理解、匹配度分析、简历调整。OCR 多图导入、交互式追问、面试材料、DOCX/PDF 导出、脱敏之外的联网调研和 macOS `.app` 打包尚未开始，实施计划见 [MVP 实施计划](docs/superpowers/plans/2026-08-05-resume-fit-mvp.md)。

## 本地开发

```bash
./scripts/dev.sh
```

脚本会创建后端虚拟环境、同步依赖、在 `127.0.0.1:8000` 启动 FastAPI，并在 `127.0.0.1:5173` 启动 Vite（`/api` 已配置代理到后端）。

构建前端后，后端会用同一个端口托管界面和 API（只监听 `127.0.0.1`，不对局域网开放）：

```bash
npm --prefix frontend run build
cd backend && .venv/bin/uvicorn resumefit.app:create_app --factory --host 127.0.0.1 --port 8000
```

单独运行测试：

```bash
backend/.venv/bin/pytest          # 后端，需先 cd backend
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

**工具链说明**：实施计划里的命令写的是 `uv` 和 `pnpm`，本仓库实际使用 `venv + pip` 和 `npm`（`uv run pytest` → `backend/.venv/bin/pytest`，`pnpm --dir frontend` → `npm --prefix frontend`）。

核心原则：

- 不把招聘话术复述成岗位分析；
- 不把“简历没有表达”误判为“用户没有能力”；
- 不为提高匹配度编造项目、职责、方法或结果；
- 每条高风险简历表达都能追溯到用户确认过的事实；
- 原始资料和结构化职业数据默认保存在本地；
- 第一版聚焦 macOS、中文 AI 产品经理和按需生成，不做求职进度管理。

完整设计规格：

- [Resume Fit 设计规格](docs/superpowers/specs/2026-08-04-resume-fit-design.md)
