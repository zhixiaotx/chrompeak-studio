import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, wsUrl, API_BASE } from "./api";
import type { AlgMeta, ParamSpec, Peak } from "./api";
import {
  DEFAULT_PREPROCESS,
  PANEL_TITLES,
  algVisual,
  type AlgRunStat,
  type PanelKey,
  type PreprocessConf,
} from "./theme";
import {
  analyzeLocalOne,
  LOCAL_ALGORITHMS,
  syntheticChromatogram,
  parseCsvFile,
  preprocessForDisplay,
} from "./analysis";
import { batchProcessLocalZip, downloadBlob } from "./utils/localBatch";
import {
  listLocalProjects,
  saveLocalProject,
  deleteLocalProject,
  getLocalProject,
  type LocalProject,
} from "./utils/localProjects";

import TopBar, { type Cmd } from "./components/TopBar";
import IconRail from "./components/IconRail";
import Chromatogram from "./components/Chromatogram";
import AlgorithmPanel from "./components/AlgorithmPanel";
import PreprocessPanel from "./components/PreprocessPanel";
import ComparePanel from "./components/ComparePanel";
import LogPanel, { type LogEntry } from "./components/LogPanel";
import AboutPanel from "./components/AboutPanel";
import BottomPanel, { type FileInfo, type TabKey } from "./components/BottomPanel";
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

/** 把当前 x/y 序列化成 CSV File（在线模式下重新分析时用） */
function toCsvFile(x: number[], y: number[], name: string): File {
  const parts: string[] = ["x,y"];
  for (let i = 0; i < x.length; i++) parts.push(`${x[i]},${y[i]}`);
  return new File([parts.join("\n")], name || "current.csv", { type: "text/csv" });
}

export default function App() {
  // ---------------- 账号 ----------------
  const [token, setToken] = useState<string | null>(localStorage.getItem("cp_token"));
  const [username, setUsername] = useState(localStorage.getItem("cp_user") || "");
  const [showAuth, setShowAuth] = useState(false);

  // ---------------- 算法 ----------------
  const [algos, setAlgos] = useState<AlgMeta[]>([]);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [params, setParams] = useState<Record<string, Record<string, any>>>({});
  const [stats, setStats] = useState<Record<string, AlgRunStat>>({});
  const [active, setActive] = useState("");
  const [pre, setPre] = useState<PreprocessConf>(DEFAULT_PREPROCESS);

  // ---------------- 数据 ----------------
  const [x, setX] = useState<number[]>([]);
  const [y, setY] = useState<number[]>([]);
  const [yProc, setYProc] = useState<number[]>([]);
  const [peaks, setPeaks] = useState<PeaksMap>({});
  const [fileName, setFileName] = useState("");
  const [lastMs, setLastMs] = useState<number | null>(null);

  // ---------------- 视图 ----------------
  const [panel, setPanel] = useState<PanelKey>("algo");
  const [tab, setTab] = useState<TabKey>("peaks");
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [measuring, setMeasuring] = useState(true);
  const [algQuery, setAlgQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("__all__");
  const [peakQuery, setPeakQuery] = useState("");
  const [selRow, setSelRow] = useState(-1);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // ---------------- 杂项 ----------------
  const [status, setStatus] = useState<{ msg: string; kind: "ok" | "error" | "" }>({ msg: "", kind: "" });
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [localProjs, setLocalProjs] = useState<LocalProject[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [batchUrl, setBatchUrl] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);
  const cursorEl = useRef<HTMLSpanElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const zipRef = useRef<HTMLInputElement>(null);
  const jsonRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLocalProjs(listLocalProjects());
    // 支持 #algo / #preprocess / #compare / #log / #about 深链
    const h = window.location.hash.replace(/^#/, "");
    if (["algo", "preprocess", "compare", "log", "about"].includes(h)) {
      setPanel(h as PanelKey);
    }
  }, []);

  // 面板切换写回 URL hash，便于分享与刷新保持
  useEffect(() => {
    if (window.location.hash.replace(/^#/, "") !== panel) {
      history.replaceState(null, "", `#${panel}`);
    }
  }, [panel]);

  useEffect(() => {
    if (token) {
      localStorage.setItem("cp_token", token);
      localStorage.setItem("cp_user", username);
    }
  }, [token, username]);

  const pushLog = useCallback((msg: string, kind: LogEntry["kind"] = "") => {
    const t = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    setLogs((prev) => [...prev.slice(-299), { t, msg, kind }]);
  }, []);

  const enabledNames = useCallback(
    () => algos.map((a) => a.name).filter((n) => enabled[n]),
    [algos, enabled]
  );

  // ==================== 离线（浏览器本地）计算 ====================
  const runLocal = useCallback(
    (lx: number[], ly: number[], conf: PreprocessConf, only?: string[]) => {
      const names = only && only.length ? only : enabledNames();
      if (!names.length) {
        setStatus({ msg: "请至少选择一个算法", kind: "error" });
        return;
      }
      const t0 = performance.now();
      const results: PeaksMap = {};
      const st: Record<string, AlgRunStat> = {};
      for (const n of names) {
        const s0 = performance.now();
        try {
          const ps = analyzeLocalOne(lx, ly, n, params[n] || {});
          results[n] = ps;
          st[n] = { peaks: ps.length, ms: Math.max(1, Math.round(performance.now() - s0)), status: "ok" };
        } catch (e: any) {
          results[n] = [];
          st[n] = {
            peaks: 0,
            ms: Math.max(1, Math.round(performance.now() - s0)),
            status: "error",
            message: String(e?.message || e),
          };
        }
      }
      const total = Object.values(results).reduce((s, p) => s + p.length, 0);
      const ms = Math.round(performance.now() - t0);
      setX(lx);
      setY(ly);
      setYProc(preprocessForDisplay(lx, ly, conf));
      setPeaks((prev) => (only && only.length ? { ...prev, ...results } : results));
      setStats((prev) => (only && only.length ? { ...prev, ...st } : st));
      setLastMs(ms);
      setStatus({ msg: `本地计算完成：${total} 个峰 · ${ms} ms`, kind: "ok" });
      pushLog(`本地计算 ${names.length} 个算法 → ${total} 个峰（${ms} ms）`, "ok");
    },
    [enabledNames, params, pushLog]
  );

  // ==================== 载入文件（在线 REST / 离线本地） ====================
  const analyzeFileWith = useCallback(
    async (file: File, conf: PreprocessConf) => {
      setStatus({ msg: "分析中…", kind: "" });
      pushLog(`载入 ${file.name}（${Math.round(file.size / 1024)} KB）`);
      try {
        if (backendOk === true) {
          const t0 = performance.now();
          const res = await api.analyze(file, enabledNames(), params, token, conf);
          const ms = Math.round(performance.now() - t0);
          setX(res.x);
          setY(res.y);
          setYProc(res.y_proc);
          setPeaks(res.results);
          const st: Record<string, AlgRunStat> = {};
          for (const [k, v] of Object.entries(res.results)) {
            st[k] = { peaks: v.length, ms: null, status: "ok" };
          }
          setStats(st);
          setFileName(file.name);
          setLastMs(ms);
          const total = Object.values(res.results).reduce((s, p) => s + p.length, 0);
          setStatus({ msg: `分析完成：${total} 个峰 · ${ms} ms`, kind: "ok" });
          pushLog(`后端分析完成 → ${total} 个峰（${ms} ms）`, "ok");
        } else {
          const parsed = await parseCsvFile(file);
          if (!parsed.x.length) {
            setStatus({ msg: "CSV 解析失败：需要两列数值（x, y）", kind: "error" });
            pushLog("CSV 解析失败：未找到两列数值", "err");
            return;
          }
          setFileName(file.name);
          runLocal(parsed.x, parsed.y, conf);
        }
      } catch (e: any) {
        if (e?.name === "BackendUnavailableError") {
          setBackendOk(false);
          pushLog("后端不可达，已自动切换离线模式", "warn");
          try {
            const parsed = await parseCsvFile(file);
            setFileName(file.name);
            runLocal(parsed.x, parsed.y, conf);
            return;
          } catch {
            setStatus({ msg: "后端不可用，且 CSV 解析失败", kind: "error" });
            return;
          }
        }
        setStatus({ msg: e.message || "分析失败", kind: "error" });
        pushLog(`分析失败：${e.message || e}`, "err");
      }
    },
    [backendOk, enabledNames, params, token, runLocal, pushLog]
  );

  const analyzeFile = useCallback(
    (file: File) => analyzeFileWith(file, pre),
    [analyzeFileWith, pre]
  );

  // ==================== 算法列表 ====================
  const applyAlgos = useCallback((list: AlgMeta[]) => {
    setAlgos(list);
    const en: Record<string, boolean> = {};
    for (const a of list) en[a.name] = true;
    setEnabled(en);
    setParams(defaultParams(list));
    setActive(list[0]?.name || "");
  }, []);

  useEffect(() => {
    api
      .algorithms()
      .then((list) => {
        applyAlgos(list);
        setBackendOk(true);
        pushLog(`已连接后端，载入 ${list.length} 个算法`, "ok");
      })
      .catch(() => {
        applyAlgos(LOCAL_ALGORITHMS);
        const localParams = defaultParams(LOCAL_ALGORITHMS);
        const s = syntheticChromatogram();
        const t0 = performance.now();
        const results: PeaksMap = {};
        const st: Record<string, AlgRunStat> = {};
        for (const a of LOCAL_ALGORITHMS) {
          const s0 = performance.now();
          const ps = analyzeLocalOne(s.x, s.y, a.name, localParams[a.name] || {});
          results[a.name] = ps;
          st[a.name] = { peaks: ps.length, ms: Math.max(1, Math.round(performance.now() - s0)), status: "ok" };
        }
        setX(s.x);
        setY(s.y);
        setYProc(preprocessForDisplay(s.x, s.y, DEFAULT_PREPROCESS));
        setPeaks(results);
        setStats(st);
        setFileName("示例数据（合成色谱）");
        setLastMs(Math.round(performance.now() - t0));
        setBackendOk(false);
        setStatus({ msg: "未连接后端，已切换离线模式（浏览器本地算法）", kind: "" });
        pushLog("未检测到 FastAPI 后端，切换为浏览器本地算法", "warn");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ==================== 流式实时重算（参数改动） ====================
  const runLive = useCallback(() => {
    if (!x.length) return;
    const names = enabledNames();
    if (!names.length) return;

    if (backendOk !== true) {
      runLocal(x, y, pre);
      return;
    }
    if (typeof WebSocket === "undefined") return;
    try {
      wsRef.current?.close();
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;
      let t0 = performance.now();
      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            x,
            y,
            algorithms: names,
            params: Object.fromEntries(names.map((n) => [n, params[n] || {}])),
            preprocess: pre,
          })
        );
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "algorithm") {
          const ms = Math.max(1, Math.round(performance.now() - t0));
          t0 = performance.now();
          setPeaks((prev) => ({ ...prev, [msg.algorithm]: msg.peaks }));
          setStats((prev) => ({
            ...prev,
            [msg.algorithm]: { peaks: msg.peaks.length, ms, status: "ok" },
          }));
        } else if (msg.type === "done") {
          setStatus({ msg: "流式重算完成", kind: "ok" });
        } else if (msg.type === "error") {
          setStatus({ msg: msg.msg, kind: "error" });
        }
      };
      ws.onerror = () => {
        setBackendOk(false);
        pushLog("WebSocket 不可用，已回退离线计算", "warn");
        runLocal(x, y, pre);
      };
    } catch {
      runLocal(x, y, pre);
    }
  }, [x, y, enabledNames, params, pre, backendOk, runLocal, pushLog]);

  const scheduleLive = useCallback(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => runLive(), 250);
  }, [runLive]);

  const onParamChange = (name: string, key: string, value: any) => {
    setParams((prev) => ({ ...prev, [name]: { ...prev[name], [key]: value } }));
    scheduleLive();
  };

  const onToggle = (name: string, checked: boolean) => {
    setEnabled((prev) => ({ ...prev, [name]: checked }));
    scheduleLive();
  };

  const setAllEnabled = (v: boolean) => {
    const en: Record<string, boolean> = {};
    for (const a of algos) en[a.name] = v;
    setEnabled(en);
    scheduleLive();
  };

  // 预处理改动：需要重算 y_proc，因此走完整分析（离线本地 / 在线 REST）
  const onPreChange = (patch: Partial<PreprocessConf>) => {
    const next = { ...pre, ...patch };
    setPre(next);
    if (!x.length) return;
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      if (backendOk === true) analyzeFileWith(toCsvFile(x, y, fileName), next);
      else runLocal(x, y, next);
    }, 250);
  };

  // 单独运行某个算法（带真实耗时）
  const runOne = useCallback(
    async (name: string) => {
      setActive(name);
      if (!x.length) {
        setStatus({ msg: "请先载入数据", kind: "error" });
        return;
      }
      const s0 = performance.now();
      if (backendOk === true) {
        try {
          const res = await api.analyze(
            toCsvFile(x, y, fileName),
            [name],
            { [name]: params[name] || {} },
            token,
            pre
          );
          const ms = Math.max(1, Math.round(performance.now() - s0));
          const ps = res.results[name] || [];
          setPeaks((prev) => ({ ...prev, [name]: ps }));
          setStats((prev) => ({ ...prev, [name]: { peaks: ps.length, ms, status: "ok" } }));
          setYProc(res.y_proc);
          setLastMs(ms);
          setStatus({ msg: `${algVisual(name).code} 完成：${ps.length} 个峰 · ${ms} ms`, kind: "ok" });
        } catch (e: any) {
          if (e?.name === "BackendUnavailableError") setBackendOk(false);
          setStats((prev) => ({
            ...prev,
            [name]: { peaks: 0, ms: Math.round(performance.now() - s0), status: "error", message: e.message },
          }));
          setStatus({ msg: e.message || "执行失败", kind: "error" });
        }
        return;
      }
      try {
        const ps = analyzeLocalOne(x, y, name, params[name] || {});
        const ms = Math.max(1, Math.round(performance.now() - s0));
        setPeaks((prev) => ({ ...prev, [name]: ps }));
        setStats((prev) => ({ ...prev, [name]: { peaks: ps.length, ms, status: "ok" } }));
        setStatus({ msg: `${algVisual(name).code} 完成：${ps.length} 个峰 · ${ms} ms`, kind: "ok" });
        pushLog(`${algVisual(name).code} 单独执行 → ${ps.length} 个峰（${ms} ms）`, "ok");
      } catch (e: any) {
        setStats((prev) => ({
          ...prev,
          [name]: { peaks: 0, ms: 0, status: "error", message: String(e?.message || e) },
        }));
        setStatus({ msg: "执行失败", kind: "error" });
      }
    },
    [x, y, fileName, params, pre, backendOk, token, pushLog]
  );

  // 全部重跑
  const rerunAll = useCallback(() => {
    if (!x.length) {
      setStatus({ msg: "请先载入数据", kind: "error" });
      return;
    }
    if (backendOk === true) analyzeFileWith(toCsvFile(x, y, fileName), pre);
    else runLocal(x, y, pre);
  }, [x, y, fileName, pre, backendOk, analyzeFileWith, runLocal]);

  // ==================== 数据载入 ====================
  const loadSample = () => {
    const s = syntheticChromatogram();
    setFileName("示例数据（合成色谱）");
    setSelRow(-1);
    if (backendOk === true) {
      analyzeFile(toCsvFile(s.x, s.y, "sample.csv"));
    } else {
      runLocal(s.x, s.y, pre);
    }
  };

  const onFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setSelRow(-1);
      analyzeFile(f);
    }
    e.target.value = "";
  };

  // ==================== 导出 ====================
  const allPeaks = useMemo(() => Object.values(peaks).flat(), [peaks]);

  const exportCsv = () => {
    if (!allPeaks.length) {
      setStatus({ msg: "没有可导出的峰", kind: "error" });
      return;
    }
    const head = ["algorithm", "rt", "height", "area", "fwhm", "asymmetry", "score", "index"];
    const lines = [head.join(",")];
    for (const p of allPeaks) {
      lines.push(
        [p.algorithm, p.rt, p.height, p.area, p.fwhm, p.asymmetry, p.score, p.index].join(",")
      );
    }
    downloadBlob(
      new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" }),
      `${(fileName || "peaks").replace(/\.[^.]+$/, "")}_peaks.csv`
    );
    setStatus({ msg: `已导出 ${allPeaks.length} 个峰到 CSV`, kind: "ok" });
    pushLog(`导出峰表 CSV（${allPeaks.length} 行）`, "ok");
  };

  const exportJSON = () => {
    const payload = {
      name: fileName || "project",
      algorithms: enabledNames(),
      algo_params: params,
      preprocess: pre,
      x,
      y,
      y_proc: yProc,
      results: peaks,
    };
    downloadBlob(
      new Blob([JSON.stringify(payload)], { type: "application/json" }),
      `${fileName || "project"}.json`
    );
    pushLog("导出项目 JSON", "ok");
  };

  const importJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const d = JSON.parse(String(reader.result));
        setX(d.x || []);
        setY(d.y || []);
        setYProc(d.y_proc || d.y || []);
        setPeaks(d.results || {});
        setFileName(d.name || f.name);
        if (d.algo_params) setParams(d.algo_params);
        if (d.preprocess) setPre({ ...DEFAULT_PREPROCESS, ...d.preprocess });
        if (Array.isArray(d.algorithms)) {
          const en: Record<string, boolean> = {};
          for (const a of algos) en[a.name] = d.algorithms.includes(a.name);
          setEnabled(en);
        }
        setStatus({ msg: "已导入项目 JSON", kind: "ok" });
        pushLog(`导入项目 ${d.name || f.name}`, "ok");
      } catch {
        setStatus({ msg: "JSON 解析失败", kind: "error" });
      }
    };
    reader.readAsText(f);
  };

  // ==================== 保存 / 载入项目 ====================
  const saveProject = async () => {
    const name = fileName || "project";
    if (!x.length) {
      setStatus({ msg: "尚无数据可保存", kind: "error" });
      return;
    }
    if (backendOk === true && token) {
      try {
        const res = await api.createProject(
          { name, algorithms: enabledNames(), algo_params: params, x, y },
          token
        );
        setProjectId(res.id);
        setStatus({ msg: `项目已保存到云端 #${res.id}`, kind: "ok" });
        pushLog(`项目保存到云端 #${res.id}`, "ok");
        return;
      } catch (err: any) {
        setStatus({ msg: `云端保存失败（${err.message}），已改为保存到本地`, kind: "" });
      }
    }
    try {
      const p = saveLocalProject({
        name,
        algorithms: enabledNames(),
        algo_params: params,
        x,
        y,
        results: peaks,
      } as any);
      setLocalProjs(listLocalProjects());
      setStatus({ msg: `项目已保存到本浏览器：${p.name}`, kind: "ok" });
      pushLog(`项目保存到本机 localStorage：${p.name}`, "ok");
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
    pushLog(`载入本地项目 ${p.name}`, "ok");
  };

  const removeLocalProject = (id: number) => {
    deleteLocalProject(id);
    setLocalProjs(listLocalProjects());
  };

  // ==================== ZIP 批量 ====================
  const onZipPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (backendOk === true) {
      setStatus({ msg: "批量处理中…", kind: "" });
      try {
        const res = await api.analyzeBatch(f, enabledNames(), token, pre);
        setBatchUrl(`${API_BASE}${res.download_url}`);
        setStatus({ msg: `批量完成，共 ${res.n_peaks} 个峰`, kind: "ok" });
        pushLog(`后端批量完成 → ${res.n_peaks} 个峰`, "ok");
      } catch (err: any) {
        setStatus({ msg: err.message || "批量失败", kind: "error" });
      }
      return;
    }
    setStatus({ msg: "本地批量处理中…", kind: "" });
    try {
      const res = await batchProcessLocalZip(f, enabledNames(), params, (done, total, cur) =>
        setStatus({ msg: `批量进度 ${done}/${total} · ${cur}`, kind: "" })
      );
      downloadBlob(res.blob, res.fileName);
      setStatus({
        msg: `批量完成：${res.nFiles} 个文件 / ${res.nPeaks} 个峰，已下载 ${res.fileName}`,
        kind: "ok",
      });
      pushLog(`本地批量完成 → ${res.nFiles} 个文件 / ${res.nPeaks} 个峰`, "ok");
    } catch (err: any) {
      setStatus({ msg: err.message || "批量失败", kind: "error" });
    }
  };

  // ==================== 派生数据 ====================
  const filteredAlgos = useMemo(() => {
    const q = algQuery.trim().toLowerCase();
    if (!q) return algos;
    return algos.filter((a) => {
      const v = algVisual(a.name);
      return (
        a.name.toLowerCase().includes(q) ||
        v.label.toLowerCase().includes(q) ||
        v.code.toLowerCase().includes(q)
      );
    });
  }, [algos, algQuery]);

  const sources = useMemo(
    () => Object.keys(peaks).filter((k) => (peaks[k] || []).length > 0),
    [peaks]
  );

  const tablePeaks = useMemo(() => {
    let ps = allPeaks;
    if (sourceFilter !== "__all__") ps = ps.filter((p) => p.algorithm === sourceFilter);
    const q = peakQuery.trim().toLowerCase();
    if (q) {
      ps = ps.filter((p) => {
        const v = algVisual(p.algorithm);
        return (
          p.rt.toFixed(4).includes(q) ||
          v.code.toLowerCase().includes(q) ||
          v.label.toLowerCase().includes(q)
        );
      });
    }
    return ps;
  }, [allPeaks, sourceFilter, peakQuery]);

  const fileInfo: FileInfo = useMemo(
    () => ({
      name: fileName,
      points: x.length,
      dt: x.length > 1 ? Math.abs(x[1] - x[0]) : 0,
      xmin: x.length ? x[0] : 0,
      xmax: x.length ? x[x.length - 1] : 0,
      nAlg: enabledNames().length,
      nPeaks: allPeaks.length,
      lastMs,
      mode:
        backendOk === false
          ? "离线 · 浏览器本地算法"
          : backendOk === true
            ? "在线 · FastAPI 后端"
            : "检测中…",
      endpoint: API_BASE,
    }),
    [fileName, x, allPeaks, lastMs, backendOk, enabledNames]
  );

  // ==================== 命令派发 ====================
  const onCmd = (cmd: Cmd) => {
    if (cmd === "open-file") return void fileRef.current?.click();
    if (cmd === "sample") return void loadSample();
    if (cmd === "import-json") return void jsonRef.current?.click();
    if (cmd === "export-csv") return void exportCsv();
    if (cmd === "export-json") return void exportJSON();
    if (cmd === "save-project") return void saveProject();
    if (cmd === "batch") return void zipRef.current?.click();
    if (cmd === "clear-log") return void setLogs([]);
    if (cmd === "toggle-raw") return void setHidden((h) => ({ ...h, raw: !h.raw }));
    if (cmd === "toggle-proc") return void setHidden((h) => ({ ...h, proc: !h.proc }));
    if (cmd === "toggle-markers") {
      const anyVisible = Object.keys(peaks).some((k) => !hidden[k]);
      const next: Record<string, boolean> = { ...hidden };
      for (const k of Object.keys(peaks)) next[k] = anyVisible;
      return void setHidden(next);
    }
    if (cmd === "toggle-measure") return void setMeasuring((v) => !v);
    if (cmd === "toggle-auth") return void setShowAuth((v) => !v);
    if (cmd === "view-algo") return void setPanel("algo");
    if (cmd === "view-preprocess") return void setPanel("preprocess");
    if (cmd === "view-compare") return void setPanel("compare");
    if (cmd === "view-log") return void setPanel("log");
    if (cmd === "view-about") return void setPanel("about");
    if (cmd === "select-all") return void setAllEnabled(true);
    if (cmd === "select-none") return void setAllEnabled(false);
    if (cmd === "run-all") return void rerunAll();
    if (cmd.startsWith("toggle-alg:")) {
      const n = cmd.slice("toggle-alg:".length);
      return void onToggle(n, !enabled[n]);
    }
  };

  const onCursorText = useCallback((text: string) => {
    const el = cursorEl.current;
    if (el) el.textContent = text || "—";
  }, []);

  const toggleSeries = (key: string) =>
    setHidden((h) => ({ ...h, [key]: !h[key] }));

  const markersVisible = Object.keys(peaks).some((k) => !hidden[k]);

  return (
    <div className="app">
      <header className="app-header">
        <TopBar
          algos={algos}
          enabled={enabled}
          showRaw={!hidden.raw}
          showProc={!hidden.proc}
          showMarkers={markersVisible}
          measuring={measuring}
          backendOk={backendOk}
          token={token}
          username={username}
          showAuth={showAuth}
          onCmd={onCmd}
          onLogout={() => {
            setToken(null);
            setUsername("");
            localStorage.removeItem("cp_token");
            localStorage.removeItem("cp_user");
            pushLog("已退出登录");
          }}
        />
        {backendOk === false && (
          <div className="offline-banner">
            ⚠ 未连接后端（纯静态托管）：全部计算在浏览器本地完成，项目保存在本机 localStorage；
            参数改动实时重算。云端登录与云端项目需自备 FastAPI 后端。
          </div>
        )}
      </header>

      <div className="body">
        <IconRail active={panel} onChange={setPanel} />

        <div className="center">
          <Chromatogram
            x={x}
            y={y}
            yProc={yProc}
            peaks={peaks}
            hidden={hidden}
            onToggle={toggleSeries}
            measuring={measuring}
            onCursorText={onCursorText}
            emptyHint={
              backendOk === false
                ? "尚未载入数据：点「文件 → 打开数据文件」导入 CSV，或「载入示例数据」。"
                : "尚未载入数据：点「文件 → 打开数据文件」导入 CSV，或「载入示例数据」。"
            }
          />
          <BottomPanel
            tab={tab}
            onTab={setTab}
            peaks={tablePeaks}
            allPeaks={allPeaks}
            x={x}
            sources={sources}
            sourceFilter={sourceFilter}
            onSourceFilter={setSourceFilter}
            query={peakQuery}
            onQuery={setPeakQuery}
            info={fileInfo}
            selected={selRow}
            onSelect={setSelRow}
            localProjs={localProjs}
            onLoadProject={loadLocalProject}
            onDeleteProject={removeLocalProject}
            batchUrl={batchUrl}
          />
        </div>

        <aside className="panel">
          <div className="panel-head">
            <h3>{PANEL_TITLES[panel]}</h3>
            {panel === "algo" && (
              <button className="ghost" title="运行全部已选算法" onClick={() => rerunAll()}>
                运行
              </button>
            )}
          </div>

          {showAuth && !token && (
            <div style={{ padding: 10, borderBottom: "1px solid var(--border)" }}>
              <Auth
                onAuth={(t, u) => {
                  setToken(t);
                  setUsername(u);
                  setShowAuth(false);
                  setStatus({ msg: `欢迎，${u}`, kind: "ok" });
                  pushLog(`登录成功：${u}`, "ok");
                }}
                disabled={backendOk === false}
                onClose={() => setShowAuth(false)}
              />
            </div>
          )}

          {panel === "algo" && (
            <AlgorithmPanel
              algos={filteredAlgos}
              total={algos.length}
              enabled={enabled}
              params={params}
              stats={stats}
              active={active}
              search={algQuery}
              onSearch={setAlgQuery}
              onToggle={onToggle}
              onSelect={setActive}
              onRunOne={runOne}
              onParamChange={onParamChange}
              onSelectAll={() => setAllEnabled(true)}
              onSelectNone={() => setAllEnabled(false)}
            />
          )}

          {panel === "preprocess" && (
            <PreprocessPanel
              conf={pre}
              onChange={onPreChange}
              onReset={() => onPreChange(DEFAULT_PREPROCESS)}
            />
          )}

          {panel === "compare" && (
            <ComparePanel
              names={algos.map((a) => a.name).filter((n) => enabled[n])}
              peaks={peaks}
              stats={stats}
              onRunAll={rerunAll}
            />
          )}

          {panel === "log" && <LogPanel entries={logs} onClear={() => setLogs([])} />}

          {panel === "about" && <AboutPanel backendOk={backendOk} />}
        </aside>
      </div>

      <footer className="statusbar">
        <span>文件：<b>{fileName || "—"}</b></span>
        <span className="sep">│</span>
        <span className="hide-sm">点数：<b>{x.length}</b></span>
        <span className="sep hide-sm">│</span>
        <span className="hide-sm">
          采样间隔：<b>{x.length > 1 ? Math.abs(x[1] - x[0]).toFixed(4) : "—"}</b>
        </span>
        <span className="sep hide-sm">│</span>
        <span>算法：<b>{enabledNames().length}</b></span>
        <span className="sep">│</span>
        <span>峰数：<b>{allPeaks.length}</b></span>
        <span className="sep">│</span>
        <span>耗时：<b>{lastMs == null ? "—" : `${lastMs} ms`}</b></span>
        <span className="sep hide-sm">│</span>
        <span className="hide-sm">
          光标：<b ref={cursorEl}>—</b>
        </span>
        {status.msg && (
          <>
            <span className="sep">│</span>
            <span className={`msg ${status.kind === "error" ? "err" : status.kind === "ok" ? "ok" : ""}`}>
              {status.msg}
            </span>
          </>
        )}
        <span className="right">{backendOk === false ? "离线模式" : backendOk === true ? "在线模式" : "检测中"}</span>
      </footer>

      <input ref={fileRef} type="file" accept=".csv,.txt,.xlsx" style={{ display: "none" }} onChange={onFilePick} />
      <input ref={zipRef} type="file" accept=".zip" style={{ display: "none" }} onChange={onZipPick} />
      <input ref={jsonRef} type="file" accept=".json" style={{ display: "none" }} onChange={importJSON} />
    </div>
  );
}
