export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await response.text();
  const parsed = text ? JSON.parse(text) : null;

  if (!response.ok) {
    // FastAPI 的错误体是 {detail: ...}，422 时 detail 是数组。
    const detail = parsed?.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg?: string }) => item.msg ?? String(item)).join("；")
          : `请求失败（${response.status}）`,
    );
  }
  return parsed as T;
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  // 不设 content-type，让浏览器带上 multipart 边界。
  const response = await fetch(`/api${path}`, { method: "POST", body: form });
  const text = await response.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = parsed?.detail;
    throw new ApiError(typeof detail === "string" ? detail : `上传失败（${response.status}）`);
  }
  return parsed as T;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T,>(path: string, body?: unknown) => request<T>("PUT", path, body),
  upload,
};

export type Api = typeof api;
