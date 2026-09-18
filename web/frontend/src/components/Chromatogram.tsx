import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { lttb } from "../utils/lttb";
import { algVisual, PLOT } from "../theme";
import type { Peak } from "../api";

interface Props {
  x: number[];
  y: number[];
  yProc: number[];
  peaks: Record<string, Peak[]>;
  /** 被隐藏的序列 key：raw / proc / 算法名 */
  hidden: Record<string, boolean>;
  onToggle: (key: string) => void;
  /** 是否显示十字光标读数 */
  measuring: boolean;
  /** 光标读数回调（直接写 DOM，避免高频 setState 引起重渲染） */
  onCursorText: (text: string) => void;
  emptyHint?: string;
}

interface SeriesDef {
  key: string;
  label: string;
  color: string;
  kind: "line" | "points";
}

/** uPlot 画布高度：留出底部 x 轴刻度与标签的空间，避免被容器裁切 */
const AXIS_ROOM = 10;

function fmt(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "-";
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(3);
  return v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

/** 在升序数组里找最接近 v 的下标（二分） */
function nearest(arr: number[], v: number): number {
  let lo = 0;
  let hi = arr.length - 1;
  if (hi < 0) return -1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] < v) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(arr[lo - 1] - v) <= Math.abs(arr[lo] - v)) return lo - 1;
  return lo;
}

export default function Chromatogram({
  x, y, yProc, peaks, hidden, onToggle, measuring, onCursorText, emptyHint,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const sigRef = useRef<string>("");
  const lenRef = useRef<number>(-1);
  const measureRef = useRef(measuring);
  measureRef.current = measuring;
  const cbRef = useRef(onCursorText);
  cbRef.current = onCursorText;

  const defs: SeriesDef[] = [
    { key: "raw", label: "原始数据", color: PLOT.raw, kind: "line" },
    { key: "proc", label: "处理后（基线校正 + 平滑）", color: PLOT.proc, kind: "line" },
    ...Object.keys(peaks).map((n) => ({
      key: n,
      label: `${algVisual(n).code} · ${algVisual(n).label}`,
      color: algVisual(n).color,
      kind: "points" as const,
    })),
  ];
  const visible = defs.filter((d) => !hidden[d.key]);

  // ---------- 数据构建 ----------
  const buildData = (): uPlot.AlignedData => {
    const wrap = wrapRef.current;
    const w = Math.max(240, wrap?.clientWidth || 800);
    const target = Math.max(600, Math.min(x.length, Math.floor(w * 2)));
    const raw = lttb(x, y, target);
    const data: uPlot.AlignedData = [raw.x, raw.y];
    if (yProc.length === x.length) data.push(lttb(x, yProc, target).y);
    else data.push(new Array(raw.x.length).fill(null));

    if (lenRef.current !== x.length) lenRef.current = x.length;

    for (const d of defs) {
      if (d.kind !== "points") continue;
      const arr = new Array(raw.x.length).fill(null);
      for (const p of peaks[d.key] || []) {
        const j = nearest(raw.x, p.rt);
        if (j >= 0) arr[j] = raw.y[j];
      }
      data.push(arr);
    }
    return data;
  };

  const innerH = () =>
    Math.max(150, Math.round((wrapRef.current?.clientHeight || 320) - AXIS_ROOM));
  const buildPlot = (): uPlot | null => {
    const wrap = wrapRef.current;
    if (!wrap || !x.length) return null;
    const w = Math.max(240, wrap.clientWidth);
    const h = innerH();

    const uSeries: uPlot.Series[] = [
      {},
      {
        label: "原始数据",
        stroke: PLOT.raw,
        width: 1,
        points: { show: false },
        show: !hidden.raw,
      },
      {
        label: "处理后",
        stroke: PLOT.proc,
        width: 1.4,
        fill: PLOT.procFill,
        points: { show: false },
        show: !hidden.proc,
      },
      ...defs
        .filter((d) => d.kind === "points")
        .map((d) => ({
          label: d.label,
          stroke: d.color,
          width: 1,
          paths: () => null,
          points: { show: true, size: 7, width: 1.4, stroke: d.color, fill: d.color },
          show: !hidden[d.key],
        })) as uPlot.Series[],
    ];

    const opts: uPlot.Options = {
      width: w,
      height: h,
      padding: [8, 10, 0, 0],
      scales: { x: { time: false }, y: { auto: true } },
      cursor: {
        show: true,
        x: true,
        y: true,
        points: { show: true, size: 5 },
        drag: { x: true, y: false, setScale: true },
      },
      axes: [
        {
          stroke: PLOT.axis,
          grid: { stroke: PLOT.grid, width: 1 },
          ticks: { stroke: PLOT.grid, width: 1 },
          font: "10px ui-monospace, Consolas, monospace",
          label: "时间 / min",
          labelFont: "10px sans-serif",
          labelSize: 16,
          size: 26,
        },
        {
          stroke: PLOT.axis,
          grid: { stroke: PLOT.grid, width: 1 },
          ticks: { stroke: PLOT.grid, width: 1 },
          font: "10px ui-monospace, Consolas, monospace",
          label: "响应",
          labelFont: "10px sans-serif",
          labelSize: 16,
          size: 56,
        },
      ],
      series: uSeries,
      legend: { show: false },
      hooks: {
        setCursor: [
          (u: uPlot) => {
            const el = tipRef.current;
            const { idx, left, top } = u.cursor;
            const off = idx == null || left == null || top == null || left < 0 || top < 0;
            if (off) {
              if (el) el.style.display = "none";
              cbRef.current("");
              return;
            }
            const xv = u.data[0][idx as number];
            const yv = u.data[1][idx as number];
            const text = `t = ${fmt(xv)} min / ${fmt(yv)}`;
            cbRef.current(text);
            if (!el || !measureRef.current) {
              if (el) el.style.display = "none";
              return;
            }
            el.style.display = "block";
            el.textContent = text;
            el.style.left = `${(left as number) + 14}px`;
            el.style.top = `${Math.max(6, (top as number) - 30)}px`;
          },
        ],
      },
    };

    return new uPlot(opts, buildData(), wrap);
  };

  // ---------- 数据 / 结构变化 ----------
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    if (!x.length) {
      plotRef.current?.destroy();
      plotRef.current = null;
      sigRef.current = "";
      lenRef.current = -1;
      return;
    }
    const sig = visible.map((d) => d.key).join("|");
    const p = plotRef.current;
    if (p && sig === sigRef.current && lenRef.current === x.length) {
      p.setData(buildData());
    } else {
      p?.destroy();
      plotRef.current = buildPlot();
    }
    sigRef.current = sig;
    lenRef.current = x.length;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x, y, yProc, peaks, hidden]);

  // ---------- 容器尺寸变化 ----------
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const p = plotRef.current;
        const w = wrap.clientWidth;
        const h = innerH();
        if (p && w > 0 && h > 0 && (p.width !== w || p.height !== h)) {
          p.setSize({ width: w, height: h });
        }
      });
    });
    ro.observe(wrap);
    return () => {
      if (raf) cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  // ---------- 卸载清理 ----------
  useEffect(() => {
    return () => {
      plotRef.current?.destroy();
      plotRef.current = null;
    };
  }, []);

  return (
    <div className="plot-card">
      <div className="chart-wrap" ref={wrapRef} />
      {x.length > 0 && (
        <div className="legend">
          {defs.map((d) => (
            <button
              key={d.key}
              className={`legend-item${hidden[d.key] ? " off" : ""}`}
              onClick={() => onToggle(d.key)}
              title={hidden[d.key] ? "点击显示" : "点击隐藏"}
            >
              <span className="dot" style={{ background: d.color }} />
              <span className="txt">{d.label}</span>
            </button>
          ))}
        </div>
      )}
      <div className="readout" ref={tipRef} style={{ display: "none" }} />
      {x.length === 0 && (
        <div className="empty-hint">{emptyHint || "尚未载入数据：用「文件 → 打开数据文件」导入 CSV，或载入示例数据。"}</div>
      )}
    </div>
  );
}
