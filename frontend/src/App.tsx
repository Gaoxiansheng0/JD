import { useState } from "react";

import { api as defaultApi, type Api } from "./api";
import { AnalyzePage } from "./pages/AnalyzePage";
import { HistoryPage } from "./pages/HistoryPage";
import { InsightPage } from "./pages/InsightPage";
import { MaterialsPage } from "./pages/MaterialsPage";
import { SettingsPage } from "./pages/SettingsPage";

type Where = "匹配分析" | "岗位解读" | "分析记录" | "我的材料" | "设置";

export function App({ api = defaultApi }: { api?: Api } = {}) {
  const [where, setWhere] = useState<Where>("匹配分析");
  // 分析完成后让记录页重新拉取，不用手动刷新。
  const [historyKey, setHistoryKey] = useState(0);

  const item = (label: Where) => (
    <button
      key={label}
      type="button"
      aria-current={label === where ? "page" : undefined}
      onClick={() => setWhere(label)}
    >
      {label}
    </button>
  );

  return (
    <div className="shell">
      <aside className="rail">
        <div>
          <p className="mark">Resume Fit</p>
          <p className="mark-sub">本地运行 · 证据优先</p>
        </div>

        <nav aria-label="主导航">
          <p className="rail-group">主流程</p>
          {item("匹配分析")}
          {item("分析记录")}

          <p className="rail-group">按需使用</p>
          {item("岗位解读")}
          {item("我的材料")}
          {item("设置")}
        </nav>

        <p className="rail-foot">
          资料和分析结果都存在这台机器上。只有你点击分析时，选中的内容才会发给你配置的模型。
        </p>
      </aside>

      <main>
        {where === "匹配分析" && (
          <AnalyzePage api={api} onFinish={() => setHistoryKey((key) => key + 1)} />
        )}
        {where === "分析记录" && <HistoryPage api={api} reloadKey={historyKey} />}
        {where === "岗位解读" && <InsightPage api={api} />}
        {where === "我的材料" && <MaterialsPage api={api} />}
        {where === "设置" && <SettingsPage api={api} />}
      </main>
    </div>
  );
}
