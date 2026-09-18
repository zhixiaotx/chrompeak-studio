import type { Peak } from "../api";
import { algVisual, type AlgRunStat } from "../theme";

interface Props {
  names: string[];
  peaks: Record<string, Peak[]>;
  stats: Record<string, AlgRunStat>;
  onRunAll: () => void;
}

interface Row {
  name: string;
  code: string;
  label: string;
  color: string;
  n: number;
  ms: number | null;
  avgH: number;
  avgSym: number;
  avgScore: number;
}

export default function ComparePanel({ names, peaks, stats, onRunAll }: Props) {
  const rows: Row[] = names.map((n) => {
    const v = algVisual(n);
    const ps = peaks[n] || [];
    const st = stats[n];
    const avg = (f: (p: Peak) => number) =>
      ps.length ? ps.reduce((s, p) => s + f(p), 0) / ps.length : 0;
    return {
      name: n,
      code: v.code,
      label: v.label,
      color: v.color,
      n: ps.length,
      ms: st ? st.ms : null,
      avgH: avg((p) => p.height),
      avgSym: avg((p) => p.asymmetry),
      avgScore: avg((p) => p.score),
    };
  });

  const maxN = Math.max(1, ...rows.map((r) => r.n));
  const maxMs = Math.max(1, ...rows.map((r) => r.ms ?? 0));

  return (
    <div className="panel-body">
      <div className="panel-sub" style={{ paddingTop: 8 }}>
        <span>按算法横向对比检出结果与耗时</span>
        <span className="links">
          <button onClick={onRunAll}>重新运行</button>
        </span>
      </div>
      <table className="cmp-table">
        <thead>
          <tr>
            <th>算法</th>
            <th>峰数</th>
            <th>耗时</th>
            <th>平均峰高</th>
            <th>不对称</th>
            <th>置信度</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <td>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 8, height: 8, borderRadius: "50%", background: r.color,
                      flex: "0 0 auto",
                    }}
                  />
                  <span style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>{r.code}</span>
                </div>
              </td>
              <td className="num">
                {r.n}
                <div className="cmp-bar" style={{ marginTop: 3 }}>
                  <i style={{ width: `${(r.n / maxN) * 100}%`, background: r.color }} />
                </div>
              </td>
              <td className="num">
                {r.ms == null ? "—" : `${r.ms} ms`}
                <div className="cmp-bar" style={{ marginTop: 3 }}>
                  <i
                    style={{
                      width: `${((r.ms ?? 0) / maxMs) * 100}%`,
                      background: "var(--dim)",
                    }}
                  />
                </div>
              </td>
              <td className="num">{r.avgH ? r.avgH.toFixed(4) : "—"}</td>
              <td className="num">{r.avgSym ? r.avgSym.toFixed(3) : "—"}</td>
              <td className="num">{r.avgScore ? r.avgScore.toFixed(2) : "—"}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={6} className="empty">尚未运行任何算法</td></tr>
          )}
        </tbody>
      </table>
      <div className="doc">
        <b>怎么看：</b>峰数差异说明算法灵敏度不同——导数法偏保守，CWT 与 GNN 解卷积更容易
        拆出重叠峰；耗时反映计算代价，EMG / GNN 明显更贵。不对称因子接近 1 说明峰形对称，
        明显大于 1 表示拖尾。
      </div>
    </div>
  );
}
