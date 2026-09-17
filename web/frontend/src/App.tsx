import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl, API_BASE } from "./api";
import type { AlgMeta, ParamSpec, Peak } from "./api";
import { lttb } from "./utils/lttb";
import AlgorithmPanel from "./components/AlgorithmPanel";
import Chromatogram from "./components/Chromatogram";
import ResultTable from "./components/ResultTable";
import Auth from "./components/Auth";

type PeaksMap = Record<string, Peak[]>;

function defaultParams(algos: AlgMeta[]): Record<string, Record<string, any>> {
  const out: Record<string, Record<string, any>> = {};
  for (const a of algos) {
    out[a.name] = {};
    for (const p of a.params as ParamSpec[]) out[a.name][p.key] = p.default;
  }
  return out;
}

export default function App() {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("cp_token")
  );
  const [username, setUsername] = useState(localStorage.getItem("cp_user") || "");

  const [algos, setAlgos] = useState<AlgMeta[]>([]);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [params, setParams] = useState<Record<string, Record<string, any>>>({});

  const [x, setX] = useState<number[]>([]);
  const [y, setY] = useState<number[]>([]);
  const [yProc, setYProc] = useState<number[]>([]);
  const [peaks, setPeaks] = useState<PeaksMap>({});
  const [fileName, setFileName] = useState("");

  const [status, setStatus] = useState<{ msg: string; kind: "ok" | "error" | "" }>(
    { msg: "", kind: "" }
  );
  const [wsStatus, setWsStatus] = useState("");
  const [batchUrl, setBatchUrl] = useState("");
  const [projectId, setProjectId] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const debounceRef = useRef<number | null>(null);

  const enabledNames = () => algos.map((a) => a.name).filter((n) => enabled[n]);

  // 登录态变化写回 localStorage
  useEffect(() => {
    if (token) {
      localStorage.setItem("cp_token", token);
      localStorage.setItem("cp_user", username);
    }
  }, [token, username]);

  // 拉取算法元信息
  useEffect(() => {
    api
      .algorithms()
      .then((list) => {
        setAlgos(list);
        const en: Record<string, boolean> = {};
        for (const a of list) en[a.name] = true;
        setEnabled(en);
        setParams(defaultParams(list));
      })
      .catch((e) =>
        setStatus({ msg: `无法获取算法列表：${e.message}`, kind: "error" })
      );
  }, []);

  const onAuth = (t: string, u: string) => {
    setToken(t);
    setUsername(u);
    setStatus({ msg: `欢迎，${u}`, kind: "ok" });
  };

  const logout = () => {
    setToken(null);
    setUsername("");
    localStorage.removeItem("cp_token");
    localStorage.removeItem("cp_user");
  };

  // ---- 单文件分析（REST，用于首次载入完整 x/y/y_proc） ----
  const analyzeFile = useCallback(
    async (file: File) => {
      setStatus({ msg: "分析中…", kind: "" });
      try {
        const res = await api.analyze(file, enabledNames(), params, token);
        setX(res.x);
        setY(res.y);
        setYProc(res.y_proc);
        setPeaks(res.results);
        setFileName(file.name);
        setStatus({ msg: `已完成，共 ${Object.values(res.results).reduce((s, p) => s + p.length, 0)} 个峰`, kind: "ok" });
      } catch (e: any) {
        setStatus({ msg: e.message || "分析失败", kind: "error" });
      }
    },
    [enabled, params, token]
  );

  // ---- WebSocket 流式实时预览（参数变动时边滑边出峰） ----
  const runLive = useCallback(() => {
    if (!x.length) return;
    if (typeof WebSocket === "undefined") return;
    try {
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;
      setWsStatus("连接中…");
      ws.onopen = () => {
        setWsStatus("流式推理中…");
        ws.send(
          JSON.stringify({
            x,
            y,
            algorithms: enabledNames(),
            params: Object.fromEntries(
              enabledNames().map((n) => [n, params[n]])
            ),
          })
        );
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "algorithm") {
          setPeaks((prev) => ({ ...prev, [msg.algorithm]: msg.peaks }));
        } else if (msg.type === "done") {
          setWsStatus("");
        } else if (msg.type === "error") {
          setStatus({ msg: msg.msg, kind: "error" });
        }
      };
      ws.onerror = () => setWsStatus("WS 不可用，已回退 REST");
      ws.onclose = () => setWsStatus("");
    } catch {
      setWsStatus("WS 不可用");
    }
  }, [x, y, enabled, params]);

  // 参数变动 -> 250ms 防抖后流式重算
  const onParamChange = (name: string, key: string, value: any) => {
    setParams((prev) => ({ ...prev, [name]: { ...prev[name], [key]: value } }));
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => runLive(), 250);
  };

  const onToggle = (name: string, checked: boolean) => {
    setEnabled((prev) => ({ ...prev, [name]: checked }));
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => runLive(), 250);
  };

  // 文件选择
  const onFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) analyzeFile(f);
  };

  // ZIP 批处理
  const onZipPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setStatus({ msg: "批量处理中…", kind: "" });
    try {
      const res = await api.analyzeBatch(f, enabledNames(), token);
      setBatchUrl(`${API_BASE}${res.download_url}`);
      setStatus({ msg: `批量完成，共 ${res.n_peaks} 个峰`, kind: "ok" });
    } catch (err: any) {
      setStatus({ msg: err.message || "批量失败", kind: "error" });
    }
  };

  // 导出 JSON
  const exportJSON = () => {
    const payload = {
      name: fileName || "project",
      algorithms: enabledNames(),
      algo_params: params,
      x,
      y,
      results: peaks,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${fileName || "project"}.json`;
    a.click();
  };

  // 导入 JSON
  const importJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(String(reader.result));
        setX(data.x || []);
        setY(data.y || []);
        setYProc(data.y_proc || data.y || []);
        setPeaks(data.results || {});
        setFileName(data.name || f.name);
        if (data.algorithms) {
          const en: Record<string, boolean> = {};
          for (const a of algos) en[a.name] = data.algorithms.includes(a.name);
          setEnabled(en);
        }
        if (data.algo_params) setParams(data.algo_params);
        setStatus({ msg: "已导入项目 JSON", kind: "ok" });
      } catch (err: any) {
        setStatus({ msg: "JSON 解析失败", kind: "error" });
      }
    };
    reader.readAsText(f);
  };

  // 保存项目（需登录）
  const saveProject = async () => {
    if (!token) {
      setStatus({ msg: "请先登录再保存项目", kind: "error" });
      return;
    }
    try {
      const res = await api.createProject(
        { name: fileName || "project", algorithms: enabledNames(), algo_params: params, x, y },
        token
      );
      setProjectId(res.id);
      setStatus({ msg: `项目已保存 #${res.id}`, kind: "ok" });
    } catch (err: any) {
      setStatus({ msg: err.message, kind: "error" });
    }
  };

  const flatPeaks: Peak[] = Object.values(peaks).flat();

  return (
    <div className="app">
      <div className="topbar">
        <h1>ChromaPeak Studio</h1>
        <span className="badge">{algos.length} 算法</span>
        <div className="spacer" />
        {wsStatus && <span className="status">{wsStatus}</span>}
        {token ? (
          <>
            <span className="user">{username}</span>
            <button className="ghost" onClick={logout}>退出</button>
          </>
        ) : (
          <span className="hint">未登录（无法保存项目）</span>
        )}
      </div>

      {!token && (
        <Auth onAuth={onAuth} />
      )}

      {token && (
        <div className="layout">
          <div className="sidebar">
            <div className="card">
              <h3>数据</h3>
              <div className="row">
                <input type="file" accept=".csv,.txt" onChange={onFilePick} />
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <label className="ghost" style={{ flex: 1 }}>
                  ZIP 批量
                  <input type="file" accept=".zip" onChange={onZipPick} style={{ marginTop: 4 }} />
                </label>
              </div>
              {batchUrl && (
                <a href={batchUrl} className="badge" style={{ marginTop: 6, display: "inline-block" }}>
                  下载批量结果
                </a>
              )}
              <div className="row" style={{ marginTop: 8 }}>
                <button className="secondary" onClick={exportJSON}>导出 JSON</button>
                <label className="ghost">
                  导入 JSON
                  <input type="file" accept=".json" onChange={importJSON} style={{ display: "none" }} />
                </label>
                <button className="secondary" onClick={saveProject}>保存项目</button>
              </div>
              {fileName && <div className="hint" style={{ marginTop: 6 }}>当前：{fileName}{projectId ? ` · #${projectId}` : ""}</div>}
            </div>

            <div className="card" style={{ marginTop: 12 }}>
              <h3>算法与参数</h3>
              <AlgorithmPanel
                algos={algos}
                enabled={enabled}
                params={params}
                onToggle={onToggle}
                onParamChange={onParamChange}
              />
              <div className="hint" style={{ marginTop: 8 }}>
                调整参数会在 250ms 后触发 WebSocket 流式重算（边滑边出峰）。
              </div>
            </div>
          </div>

          <div className="main">
            <div className="card">
              <h3>色谱图与峰识别</h3>
              {status.msg && (
                <div className={`status ${status.kind}`}>{status.msg}</div>
              )}
              <Chromatogram x={x} y={y} yProc={yProc} peaks={peaks} height={380} />
            </div>
            <div className="card">
              <h3>结果表（{flatPeaks.length} 个峰）</h3>
              <ResultTable peaks={flatPeaks} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
