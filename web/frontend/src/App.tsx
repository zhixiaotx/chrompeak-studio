import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl, API_BASE } from "./api";
import type { AlgMeta, ParamSpec, Peak } from "./api";
import { lttb } from "./utils/lttb";
import {
  analyzeLocal,
  LOCAL_ALGORITHMS,
  syntheticChromatogram,
  parseCsvFile,
  preprocessForDisplay,
} from "./analysis";
import {
  batchProcessLocalZip,
  downloadBlob,
} from "./utils/localBatch";
import {
  listLocalProjects,
  saveLocalProject,
  deleteLocalProject,
  getLocalProject,
  type LocalProject,
} from "./utils/localProjects";
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
  const [localProjs, setLocalProjs] = useState<LocalProject[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null); // null=检测中, true=连上, false=离线
  const [showAuth, setShowAuth] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const debounceRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const zipInputRef = useRef<HTMLInputElement | null>(null);
  const jsonInputRef = useRef<HTMLInputElement | null>(null);

  // 载入浏览器本地保存的项目列表
  useEffect(() => {
    setLocalProjs(listLocalProjects());
  }, []);

  const enabledNames = () => algos.map((a) => a.name).filter((n) => enabled[n]);

  // 登录态变化写回 localStorage
  useEffect(() => {
    if (token) {
      localStorage.setItem("cp_token", token);
      localStorage.setItem("cp_user", username);
    }
  }, [token, username]);

  // 拉取算法元信息；后端不可用时切换离线演示模式
  useEffect(() => {
    api
      .algorithms()
      .then((list) => {
        setAlgos(list);
        const en: Record<string, boolean> = {};
        for (const a of list) en[a.name] = true;
        setEnabled(en);
        setParams(defaultParams(list));
        setBackendOk(true);
      })
      .catch(() => {
        setAlgos(LOCAL_ALGORITHMS);
        const en: Record<string, boolean> = {};
        for (const a of LOCAL_ALGORITHMS) en[a.name] = true;
        setEnabled(en);
        const localParams = defaultParams(LOCAL_ALGORITHMS);
        setParams(localParams);
        const s = syntheticChromatogram();
        const init = analyzeLocal(
          s.x,
          s.y,
          LOCAL_ALGORITHMS.map((a) => a.name),
          localParams
        );
        setX(s.x);
        setY(s.y);
        setYProc(init.y_proc);
        setPeaks(init.results);
        setFileName("示例数据（离线）");
        setBackendOk(false);
        setStatus({ msg: "未连接后端，已切换离线演示模式（前端算法）", kind: "" });
      });
  }, []);

  const onAuth = (t: string, u: string) => {
    setToken(t);
    setUsername(u);
    setShowAuth(false);
    setStatus({ msg: `欢迎，${u}`, kind: "ok" });
  };

  const logout = () => {
    setToken(null);
    setUsername("");
    localStorage.removeItem("cp_token");
    localStorage.removeItem("cp_user");
  };

  // ---- 离线分析（无后端时在浏览器内直接算） ----
  const runLocal = (lx: number[], ly: number[]) => {
    const names = enabledNames();
    if (!names.length) {
      setStatus({ msg: "请至少选择一个算法", kind: "error" });
      return;
    }
    const res = analyzeLocal(lx, ly, names, params);
    setX(res.x);
    setY(res.y);
    setYProc(res.y_proc);
    setPeaks(res.results);
    const total = Object.values(res.results).reduce((s, p) => s + p.length, 0);
    setStatus({ msg: `离线分析完成，共 ${total} 个峰`, kind: "ok" });
  };

  // ---- 单文件分析（有后端走 REST；无后端走本地） ----
  const analyzeFile = useCallback(
    async (file: File) => {
      setStatus({ msg: "分析中…", kind: "" });
      try {
        if (backendOk) {
          const res = await api.analyze(file, enabledNames(), params, token);
          setX(res.x);
          setY(res.y);
          setYProc(res.y_proc);
          setPeaks(res.results);
          setFileName(file.name);
          setStatus({ msg: `已完成，共 ${Object.values(res.results).reduce((s, p) => s + p.length, 0)} 个峰`, kind: "ok" });
        } else {
          const { x: lx, y: ly } = await parseCsvFile(file);
          if (!lx.length) {
            setStatus({ msg: "CSV 解析失败：需要两列数值（x,y）", kind: "error" });
            return;
          }
          setFileName(file.name);
          runLocal(lx, ly);
        }
      } catch (e: any) {
        // 后端中途失联：自动降级为离线本地分析
        if (e?.name === "BackendUnavailableError") {
          setBackendOk(false);
          try {
            const { x: lx, y: ly } = await parseCsvFile(file);
            setFileName(file.name);
            runLocal(lx, ly);
            return;
          } catch {
            setStatus({ msg: "后端不可用，且 CSV 解析失败", kind: "error" });
            return;
          }
        }
        setStatus({ msg: e.message || "分析失败", kind: "error" });
      }
    },
    [backendOk, enabled, params, token]
  );

  // ---- WebSocket 流式实时预览（参数变动时边滑边出峰） ----
  const runLive = useCallback(() => {
    if (!x.length) return;
    if (!backendOk) {
      runLocal(x, y); // 离线模式：本地重算
      return;
    }
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
  }, [x, y, enabled, params, backendOk]);

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

  // ZIP 批处理（在线走后端；离线在浏览器本地算）
  const onZipPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;

    if (backendOk !== true) {
      setStatus({ msg: "本地批量处理中…", kind: "" });
      try {
        const res = await batchProcessLocalZip(
          f,
          enabledNames(),
          params,
          (done, total, cur) =>
            setStatus({ msg: `批量进度 ${done}/${total} · ${cur}`, kind: "" })
        );
        downloadBlob(res.blob, res.fileName);
        setStatus({
          msg: `批量完成：${res.nFiles} 个文件 / ${res.nPeaks} 个峰，已下载 ${res.fileName}`,
          kind: "ok",
        });
      } catch (err: any) {
        setStatus({ msg: err.message || "批量失败", kind: "error" });
      } finally {
        e.target.value = "";
      }
      return;
    }

    setStatus({ msg: "批量处理中…", kind: "" });
    try {
      const res = await api.analyzeBatch(f, enabledNames(), token);
      setBatchUrl(`${API_BASE}${res.download_url}`);
      setStatus({ msg: `批量完成，共 ${res.n_peaks} 个峰`, kind: "ok" });
    } catch (err: any) {
      setStatus({ msg: err.message || "批量失败", kind: "error" });
    } finally {
      e.target.value = "";
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

  // 保存项目：已登录且后端在线 -> 云端；否则保存到浏览器 localStorage
  const saveProject = async () => {
    const name = fileName || "project";
    if (!x.length) {
      setStatus({ msg: "尚无数据可保存", kind: "error" });
      return;
    }
    const payload = {
      name,
      algorithms: enabledNames(),
      algo_params: params,
      x,
      y,
      results: peaks,
    };

    if (backendOk === true && token) {
      try {
        const res = await api.createProject(
          { name, algorithms: enabledNames(), algo_params: params, x, y },
          token
        );
        setProjectId(res.id);
        setStatus({ msg: `项目已保存到云端 #${res.id}`, kind: "ok" });
        return;
      } catch (err: any) {
        // 云端失败时仍可落到本地
        setStatus({ msg: `云端保存失败（${err.message}），已改为保存到本地`, kind: "" });
      }
    }

    try {
      const p = saveLocalProject(payload);
      setLocalProjs(listLocalProjects());
      setStatus({ msg: `项目已保存到本浏览器：${p.name}`, kind: "ok" });
    } catch {
      setStatus({ msg: "本地保存失败（localStorage 空间不足？）", kind: "error" });
    }
  };

  const loadLocalProject = (id: number) => {
    const p = getLocalProject(id);
    if (!p) return;
    setX(p.x || []);
    setY(p.y || []);
    setYProc(p.y || []);
    setPeaks((p.results as PeaksMap) || {});
    setFileName(p.name);
    if (p.algo_params) setParams(p.algo_params);
    setStatus({ msg: `已载入本地项目：${p.name}`, kind: "ok" });
  };

  const removeLocalProject = (id: number) => {
    deleteLocalProject(id);
    setLocalProjs(listLocalProjects());
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
        ) : backendOk === false ? (
          <span className="hint">离线模式 · 无需登录</span>
        ) : (
          <button className="ghost" onClick={() => setShowAuth((v) => !v)}>
            {showAuth ? "收起登录" : "登录 / 注册"}
          </button>
        )}
      </div>

      {backendOk === false && (
        <div className="offline-banner">
          ⚠ 未连接后端，已切换「离线演示模式」：分析、保存项目、ZIP 批量都在浏览器本地完成。
          登录（云端）需自备 FastAPI 后端。
        </div>
      )}

      <div className="layout">
        <div className="sidebar">
          {!token && showAuth && (
            <Auth
              onAuth={onAuth}
              disabled={backendOk === false}
              onClose={() => setShowAuth(false)}
            />
          )}

          <div className="card">
              <h3>数据</h3>
              <div className="row">
                <input type="file" accept=".csv,.txt" onChange={onFilePick} />
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <label className="ghost" style={{ flex: 1 }} title={backendOk === true ? "" : "离线模式：在浏览器本地解压并计算"}>
                  ZIP 批量{backendOk === true ? "（后端）" : "（本地）"}
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
                <button
                  className="secondary"
                  onClick={saveProject}
                  title={backendOk === true ? "" : "离线模式：保存到本浏览器 localStorage"}
                >
                  保存项目
                </button>
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
                {backendOk === true
                  ? "调整参数会在 250ms 后触发 WebSocket 流式重算（边滑边出峰）。"
                  : "调整参数会在 250ms 后在浏览器本地重算（离线模式）。"}
              </div>
            </div>

            <div className="card" style={{ marginTop: 12 }}>
              <h3>本地项目（{localProjs.length}）</h3>
              {localProjs.length === 0 ? (
                <div className="hint">暂无。点「保存项目」把当前数据存到本浏览器。</div>
              ) : (
                <ul className="proj-list">
                  {localProjs.map((p) => (
                    <li key={p.id}>
                      <div className="proj-main">
                        <span className="proj-name" title={p.name}>{p.name}</span>
                        <span className="hint">
                          {new Date(p.created_at).toLocaleString()} · {(p.results ? Object.values(p.results).flat().length : 0)} 峰
                        </span>
                      </div>
                      <div className="row">
                        <button className="ghost" onClick={() => loadLocalProject(p.id)}>载入</button>
                        <button className="ghost" onClick={() => removeLocalProject(p.id)}>删除</button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
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
    </div>
  );
}
