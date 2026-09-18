import { useMemo, useState } from "react";
import type { Peak } from "../api";
import { algVisual } from "../theme";
import type { LocalProject } from "../utils/localProjects";
import PeakTable from "./PeakTable";

export type TabKey = "peaks" | "result" | "file";

export interface FileInfo {
  name: string;
  points: number;
  dt: number;
  xmin: number;
  xmax: number;
  nAlg: number;
  nPeaks: number;
  lastMs: number | null;
  mode: string;
  endpoint: string;
}

interface Props {
  tab: TabKey;
  onTab: (t: TabKey) => void;
  peaks: Peak[];
  allPeaks: Peak[];
  x: number[];
  sources: string[];
  sourceFilter: string;
  onSourceFilter: (v: string) => void;
  query: string;
  onQuery: (v: string) => void;
  info: FileInfo;
  selected: number;
  onSelect: (i: number) => void;
  localProjs: LocalProject[];
  onLoadProject: (id: number) => void;
  onDeleteProject: (id: number) => void;
  batchUrl: string;
}

interface Cluster {
  rt: number;
  nAlg: number;
  algs: string[];
  avgH: number;
  avgScore: number;
  spread: number;
  keys: string[];
}

export function peakKey(p: Peak): string {
  return `${p.algorithm}|${p.index}`;
}

function buildClusters(peaks: Peak[], xmin: number, xmax: number): Cluster[] {
  const tol = Math.max((xmax - xmin) * 0.004, 1e-6);
  const sorted = [...peaks].sort((a, b) => a.rt - b.rt);
  const groups: Peak[][] = [];
  for (const p of sorted) {
    const last = groups[groups.length - 1];
    if (last && Math.abs(p.rt - last[last.length - 1].rt) <= tol) last.push(p);
    else groups.push([p]);
  }
  return groups.map((g) => {
    const algs = Array.from(new Set(g.map((p) => p.algorithm))).sort();
    const rts = g.map((p) => p.rt);
    return {
      rt: rts.reduce((a, b) => a + b, 0) / rts.length,
      nAlg: algs.length,
      algs,
      avgH: g.reduce((a, p) => a + p.height, 0) / g.length,
      avgScore: g.reduce((a, p) => a + p.score, 0) / g.length,
      spread: Math.max(...rts) - Math.min(...rts),
      keys: g.map(peakKey),
    };
  });
}

export default function BottomPanel({
  tab, onTab, peaks, allPeaks, x, sources, sourceFilter, onSourceFilter,
  query, onQuery, info, selected, onSelect,
  localProjs, onLoadProject, onDeleteProject, batchUrl,
}: Props) {
  const clusters = useMemo(
    () => buildClusters(allPeaks, info.xmin, info.xmax),
    [allPeaks, info.xmin, info.xmax]
  );
  const consensus = clusters.filter((c) => c.nAlg >= 2).length;
  // (alg|index) → 该保留时间簇上共同检出的算法数；峰表用它标「共识度」
  const consMap = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of clusters) for (const k of c.keys) m[k] = c.nAlg;
    return m;
  }, [clusters]);
  const nAlg = useMemo(
    () => new Set(allPeaks.map((p) => p.algorithm)).size,
    [allPeaks]
  );
  const [onlyCons, setOnlyCons] = useState(false);
  const shown = useMemo(
    () => (onlyCons ? peaks.filter((p) => (consMap[peakKey(p)] ?? 1) >= 2) : peaks),
    [peaks, onlyCons, consMap]
  );

  return (
    <section className="bottom">
      <div className="tabs">
        <button className={`tab${tab === "peaks" ? " on" : ""}`} onClick={() => onTab("peaks")}>
          峰表
        </button>
        <button className={`tab${tab === "result" ? " on" : ""}`} onClick={() => onTab("result")}>
          结果
        </button>
        <button className={`tab${tab === "file" ? " on" : ""}`} onClick={() => onTab("file")}>
          文件信息
        </button>
        {tab === "peaks" && (
          <span className="right">
            <span style={{ color: "var(--dim)", fontSize: 11 }}>来源</span>
            <select value={sourceFilter} onChange={(e) => onSourceFilter(e.target.value)}>
              <option value="__all__">全部来源</option>
              {sources.map((s) => (
                <option key={s} value={s}>{algVisual(s).code} {algVisual(s).label}</option>
              ))}
            </select>
          </span>
        )}
      </div>

      {tab === "peaks" && (
        <>
          <div className="bottom-toolbar">
            <span>保留时间筛选</span>
            <input
              placeholder="输入保留时间或算法编号…"
              value={query}
              onChange={(e) => onQuery(e.target.value)}
            />
            <label
              style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer" }}
              title="只显示被 ≥2 个算法共同检出的峰 —— 用来快速判断是否过检"
            >
              <input
                type="checkbox"
                checked={onlyCons}
                onChange={(e) => setOnlyCons(e.target.checked)}
                style={{ width: "auto", margin: 0 }}
              />
              仅共识峰
            </label>
            <span style={{ marginLeft: "auto" }}>
              共 <b style={{ color: "var(--text)" }}>{shown.length}</b> / {allPeaks.length} 个峰
              　·　共识 {consensus}
            </span>
          </div>
          <div className="table-scroll">
            <PeakTable
              peaks={shown}
              x={x}
              cons={consMap}
              nAlg={nAlg}
              selected={selected}
              onSelect={onSelect}
            />
          </div>
        </>
      )}

      {tab === "result" && (
        <>
          <div className="bottom-toolbar">
            <span>
              共识峰（≥2 个算法共同检出）：<b style={{ color: "var(--ok)" }}>{consensus}</b>
            </span>
            <span>·</span>
            <span>保留时间簇总数：<b style={{ color: "var(--text)" }}>{clusters.length}</b></span>
          </div>
          <div className="table-scroll">
            {clusters.length === 0 ? (
              <div className="empty">暂无结果。运行算法后这里会按保留时间把各算法的峰对齐成簇。</div>
            ) : (
              <table className="data">
                <thead>
                  <tr>
                    <th>序号</th>
                    <th>保留时间/min</th>
                    <th>检出算法数</th>
                    <th>离散度/min</th>
                    <th>平均峰高</th>
                    <th>平均置信度</th>
                    <th>检出算法</th>
                  </tr>
                </thead>
                <tbody>
                  {clusters.map((c, i) => (
                    <tr key={i}>
                      <td className="idx">{i + 1}</td>
                      <td className="num">{c.rt.toFixed(4)}</td>
                      <td className="num">
                        <span style={{ color: c.nAlg >= 2 ? "var(--ok)" : "var(--dim)" }}>
                          {c.nAlg}
                        </span>
                      </td>
                      <td className="num">{c.spread.toFixed(4)}</td>
                      <td className="num">{c.avgH.toFixed(4)}</td>
                      <td className="num">{c.avgScore.toFixed(2)}</td>
                      <td>
                        <span style={{ display: "flex", gap: 8 }}>
                          {c.algs.map((a) => {
                            const v = algVisual(a);
                            return (
                              <span key={a} className="algo-cell">
                                <span className="dot" style={{ background: v.color }} />
                                <span style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>{v.code}</span>
                              </span>
                            );
                          })}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {tab === "file" && (
        <div className="table-scroll">
          <div className="info-grid">
            <div className="info-cell"><div className="k">文件名</div><div className="v">{info.name || "—"}</div></div>
            <div className="info-cell"><div className="k">数据点数</div><div className="v">{info.points || 0}</div></div>
            <div className="info-cell"><div className="k">采样间隔</div><div className="v">{info.dt ? info.dt.toFixed(4) : "—"}</div></div>
            <div className="info-cell"><div className="k">时间范围 / min</div><div className="v">{info.points ? `${info.xmin.toFixed(3)} ~ ${info.xmax.toFixed(3)}` : "—"}</div></div>
            <div className="info-cell"><div className="k">参与算法</div><div className="v">{info.nAlg}</div></div>
            <div className="info-cell"><div className="k">检出峰总数</div><div className="v">{info.nPeaks}</div></div>
            <div className="info-cell"><div className="k">最近一次耗时</div><div className="v">{info.lastMs == null ? "—" : `${info.lastMs} ms`}</div></div>
            <div className="info-cell"><div className="k">运行模式</div><div className="v">{info.mode}</div></div>
            <div className="info-cell" style={{ gridColumn: "1 / -1" }}>
              <div className="k">后端地址</div><div className="v">{info.endpoint}</div>
            </div>
          </div>
          <div className="doc">
            <b>说明：</b>桌面端（PyQt6）与 Web 端共用同一份算法内核，
            同样的数据与参数应得到一致的峰位。若两端结果不同，先检查预处理参数是否一致。
          </div>
          {batchUrl && (
            <div className="doc" style={{ paddingTop: 0 }}>
              批量结果已生成：{" "}
              <a href={batchUrl} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                下载 CSV
              </a>
            </div>
          )}
          <div className="section-label" style={{ paddingLeft: 12 }}>
            本机保存的项目（localStorage）
          </div>
          {localProjs.length === 0 ? (
            <div className="doc" style={{ paddingTop: 0 }}>
              暂无。点「文件 → 保存项目」可把当前数据存到本机浏览器。
            </div>
          ) : (
            <ul className="proj-list">
              {localProjs.map((p) => (
                <li key={p.id}>
                  <div className="proj-main">
                    <span className="proj-name" title={p.name}>{p.name}</span>
                    <span className="hint">
                      {new Date(p.created_at).toLocaleString()} ·{" "}
                      {p.results
                        ? Object.values(p.results as Record<string, unknown[]>).flat().length
                        : 0}{" "}
                      峰
                    </span>
                  </div>
                  <div className="row">
                    <button className="ghost" onClick={() => onLoadProject(p.id)}>载入</button>
                    <button className="ghost" onClick={() => onDeleteProject(p.id)}>删除</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
