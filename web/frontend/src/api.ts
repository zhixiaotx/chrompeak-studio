// 与 FastAPI 后端通信的封装层。生产环境通过 VITE_API_BASE 指向后端地址；
// 本地开发由 vite.config.ts 的 /api 代理转发到 http://localhost:8000。

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) || "/api";

export interface ParamSpec {
  key: string;
  label: string;
  type: "float" | "int" | "bool" | "choice";
  default: any;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  choices?: any[] | null;
  help?: string;
}

export interface AlgMeta {
  name: string;
  description: string;
  params: ParamSpec[];
}

export interface Peak {
  index: number;
  rt: number;
  height: number;
  area: number;
  left: number;
  right: number;
  fwhm: number;
  asymmetry: number;
  score: number;
  algorithm: string;
}

export interface AnalyzeResult {
  x: number[];
  y: number[];
  y_proc: number[];
  baseline: number[];
  results: Record<string, Peak[]>;
}

function authHeader(token: string | null | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** 后端不存在 / 不可达（静态托管下访问 /api 会得到 404/405 或 HTML 兜底页）。 */
export class BackendUnavailableError extends Error {
  status: number;
  constructor(status: number, message?: string) {
    super(message || `后端不可用（HTTP ${status}）`);
    this.name = "BackendUnavailableError";
    this.status = status;
  }
}

/** 把各种失败响应翻译成人话，避免把整段 HTML 直接甩给用户。 */
async function readableError(res: Response): Promise<string> {
  const raw = await res.text().catch(() => "");
  const text = raw.trim();
  if (text.startsWith("<")) {
    return `后端不可用（HTTP ${res.status}）：当前为纯静态部署，没有 FastAPI 服务`;
  }
  try {
    const j = JSON.parse(text);
    const d = j?.detail ?? j?.message;
    if (d) return typeof d === "string" ? d : JSON.stringify(d);
  } catch {
    /* 非 JSON，按纯文本处理 */
  }
  return text || res.statusText || `HTTP ${res.status}`;
}

async function jsonFetch<T>(
  path: string,
  init?: RequestInit,
  token?: string | null
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...(init?.headers || {}), ...authHeader(token) },
    });
  } catch (e: any) {
    // 网络层失败（DNS/跨域/离线）同样视为后端不可用
    throw new BackendUnavailableError(0, "无法连接后端服务");
  }
  if (!res.ok) {
    const msg = await readableError(res);
    if (res.status === 404 || res.status === 405) {
      throw new BackendUnavailableError(res.status, msg);
    }
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("json")) {
    // 静态兜底页冒充成功响应的情况，一并归为后端不可用
    throw new BackendUnavailableError(res.status, "后端返回了非 JSON 响应");
  }
  return res.json() as Promise<T>;
}

export const api = {
  async register(username: string, password: string) {
    return jsonFetch<{ id: number; username: string }>("/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  },

  async login(username: string, password: string): Promise<string> {
    const data = await jsonFetch<{ access_token: string }>("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    return data.access_token;
  },

  async algorithms(): Promise<AlgMeta[]> {
    return jsonFetch<AlgMeta[]>("/algorithms");
  },

  async analyze(
    file: File,
    algorithms: string[],
    params: Record<string, Record<string, any>>,
    token?: string | null
  ): Promise<AnalyzeResult> {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("algorithms", JSON.stringify(algorithms));
    fd.append("params", JSON.stringify(params));
    return jsonFetch<AnalyzeResult>("/analyze", { method: "POST", body: fd }, token);
  },

  async analyzeBatch(
    zip: File,
    algorithms: string[],
    token?: string | null
  ): Promise<{ download_url: string; n_peaks: number }> {
    const fd = new FormData();
    fd.append("file", zip);
    fd.append("algorithms", JSON.stringify(algorithms));
    return jsonFetch<{ download_url: string; n_peaks: number }>(
      "/analyze_batch",
      { method: "POST", body: fd },
      token
    );
  },

  async listProjects(token: string) {
    return jsonFetch<{ id: number; name: string; created_at: number }[]>(
      "/projects",
      { method: "GET" },
      token
    );
  },

  async createProject(
    payload: {
      name: string;
      algorithms: string[];
      algo_params: Record<string, any>;
      x: number[];
      y: number[];
    },
    token: string
  ) {
    return jsonFetch<{ id: number; name: string }>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, token);
  },

  async getProject(id: number, token: string) {
    return jsonFetch<any>(`/projects/${id}`, { method: "GET" }, token);
  },
};

// WebSocket 流式推理地址（把 http(s) 换成 ws(s)，并走 /api 前缀以复用代理）
export function wsUrl(): string {
  const base = API_BASE.replace(/\/$/, "");
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}/ws/analyze`;
}
