import { useEffect, useState } from "react";

import { ApiError, type Api } from "../api";

interface ModelSettings {
  api_base_url: string;
  text_model: string;
  timeout_seconds: number;
  has_api_key: boolean;
}

export function SettingsPage({ api }: { api: Api }) {
  const [form, setForm] = useState({ api_base_url: "", text_model: "", api_key: "", timeout_seconds: 120 });
  const [saved, setSaved] = useState<ModelSettings | null>(null);
  const [probe, setProbe] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const settings = await api.get<ModelSettings>("/settings/model");
        setSaved(settings);
        setForm((current) => ({
          ...current,
          api_base_url: settings.api_base_url,
          text_model: settings.text_model,
          timeout_seconds: settings.timeout_seconds,
        }));
      } catch (cause) {
        setError(cause instanceof ApiError ? cause.message : String(cause));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function guard(action: () => Promise<void>) {
    setError("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    }
  }

  return (
    <section>
      <h2>设置</h2>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <fieldset>
        <legend>模型 API</legend>
        <p className="hint">
          任何 OpenAI 兼容接口都可以（DeepSeek、Kimi、通义、智谱、OpenAI 等）。API Key 保存在
          macOS 钥匙串，数据库和备份包里都不会出现它。
        </p>

        <label htmlFor="base">接口地址</label>
        <input
          id="base"
          value={form.api_base_url}
          onChange={(event) => setForm({ ...form, api_base_url: event.target.value })}
          placeholder="https://api.deepseek.com/v1"
        />

        <label htmlFor="model">模型名称</label>
        <input
          id="model"
          value={form.text_model}
          onChange={(event) => setForm({ ...form, text_model: event.target.value })}
          placeholder="deepseek-chat"
        />

        <label htmlFor="key">API Key</label>
        <input
          id="key"
          type="password"
          value={form.api_key}
          onChange={(event) => setForm({ ...form, api_key: event.target.value })}
          placeholder={saved?.has_api_key ? "已配置（留空则不改动）" : "sk-…"}
        />
        {saved?.has_api_key && <p className="hint">已保存的 Key 不会回显。</p>}

        <label htmlFor="timeout">超时（秒）</label>
        <input
          id="timeout"
          type="number"
          min={10}
          max={600}
          value={form.timeout_seconds}
          onChange={(event) => setForm({ ...form, timeout_seconds: Number(event.target.value) })}
        />

        <span className="actions">
          <button
            type="button"
            className="primary"
            onClick={() =>
              guard(async () => {
                const body = { ...form };
                if (!body.api_key) delete (body as Partial<typeof form>).api_key;
                setSaved(await api.put<ModelSettings>("/settings/model", body));
                setForm({ ...form, api_key: "" });
              })
            }
          >
            保存
          </button>
          <button
            type="button"
            onClick={() =>
              guard(async () => {
                setProbe("测试中…");
                const result = await api.post<{ structured_output: boolean; detail: string }>(
                  "/settings/model/test",
                );
                setProbe(result.detail);
              })
            }
          >
            测试连接
          </button>
        </span>
        <p className="hint">测试连接会真实调用一次模型，可能产生费用。</p>
        {probe && <p className="note">{probe}</p>}
      </fieldset>
    </section>
  );
}
