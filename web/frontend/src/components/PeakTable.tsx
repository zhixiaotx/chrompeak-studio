import { useMemo } from "react";
import type { Peak } from "../api";
import { algShortLabel, algVisual } from "../theme";

interface Props {
  peaks: Peak[];
  x: number[];
  selected?: number;
  onSelect?: (i: number) => void;
}

interface Row {
  no: number;
  algNo: number;
  peak: Peak;
  xLeft: number;
  width: number;
  res: number | null;
}

export default function PeakTable({ peaks, x, selected, onSelect }: Props) {
  const rows = useMemo<Row[]>(() => {
    const groups: Record<string, Peak[]> = {};
    for (const p of peaks) (groups[p.algorithm] ||= []).push(p);

    const out: Row[] = [];
    // 先按算法分组排序，算出算法内序号与相邻峰分离度；再合并成全局行
    const prepared: { alg: string; algNo: number; p: Peak; res: number | null }[] = [];
    for (const [alg, ps] of Object.entries(groups)) {
      ps.sort((a, b) => a.rt - b.rt);
      ps.forEach((p, i) => {
        let res: number | null = null;
        if (i > 0) {
          const prev = ps[i - 1];
          const denom = (p.fwhm || 0) + (prev.fwhm || 0);
          if (denom > 0) res = (1.18 * (p.rt - prev.rt)) / denom;
        }
        prepared.push({ alg, algNo: i + 1, p, res });
      });
    }
    prepared.sort((a, b) => a.p.rt - b.p.rt || a.alg.localeCompare(b.alg));
    prepared.forEach((r, i) => {
      const li = r.p.left >= 0 && r.p.left < x.length ? r.p.left : r.p.index;
      const ri = r.p.right >= 0 && r.p.right < x.length ? r.p.right : r.p.index;
      out.push({
        no: i + 1,
        algNo: r.algNo,
        peak: r.p,
        xLeft: x[li] ?? r.p.rt,
        width: x[ri] !== undefined && x[li] !== undefined ? x[ri] - x[li] : 0,
        res: r.res,
      });
    });
    return out;
  }, [peaks, x]);

  if (rows.length === 0) {
    return (
      <div className="empty">
        暂无峰结果。载入数据并运行算法后，这里会按保留时间列出每个峰的完整指标。
      </div>
    );
  }

  return (
    <table className="data">
      <thead>
        <tr>
          <th>序号</th>
          <th>保留时间/min</th>
          <th>最小值/min</th>
          <th>峰高</th>
          <th>峰面积</th>
          <th>峰宽</th>
          <th>分离度 w/s</th>
          <th>不对称因子</th>
          <th>置信度</th>
          <th>来源算法</th>
          <th>标记</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const v = algVisual(r.peak.algorithm);
          return (
            <tr
              key={`${r.no}-${r.peak.algorithm}-${r.peak.index}`}
              className={selected === r.no - 1 ? "sel" : ""}
              onClick={() => onSelect?.(r.no - 1)}
            >
              <td className="idx">{r.no}</td>
              <td className="num">{r.peak.rt.toFixed(4)}</td>
              <td className="num">{r.xLeft.toFixed(4)}</td>
              <td className="num">{r.peak.height.toFixed(4)}</td>
              <td className="num">{r.peak.area.toFixed(4)}</td>
              <td className="num">{r.width.toFixed(4)}</td>
              <td className="num">{r.res == null ? "—" : r.res.toFixed(3)}</td>
              <td className="num">{r.peak.asymmetry.toFixed(3)}</td>
              <td>
                <span className="conf-bar">
                  <span className="bar">
                    <i
                      style={{
                        width: `${Math.max(0, Math.min(1, r.peak.score)) * 100}%`,
                        background: v.color,
                      }}
                    />
                  </span>
                  <span style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>
                    {r.peak.score.toFixed(2)}
                  </span>
                </span>
              </td>
              <td>
                <span className="algo-cell">
                  <span className="dot" style={{ background: v.color }} />
                  <span style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>{v.code}</span>
                </span>
              </td>
              <td style={{ color: "var(--dim)" }}>
                {v.label.replace(/（.*?）/g, "")} #{r.algNo}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
