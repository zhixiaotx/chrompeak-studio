import { useEffect, useRef } from "react";
import uPlot from "uplot";
import { lttb } from "../utils/lttb";
import type { Peak } from "../api";

export const ALG_COLORS: Record<string, string> = {
  "ALG-D": "#e6194B",
  "ALG-W": "#3cb44b",
  "ALG-M": "#4363d8",
  "ALG-C": "#f58231",
  "ALG-E": "#911eb4",
  "ALG-GNN": "#46f0f0",
};

interface Props {
  x: number[];
  y: number[];
  yProc?: number[];
  peaks: Record<string, Peak[]>;
  height?: number;
}

export default function Chromatogram({ x, y, yProc, peaks, height = 360 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const sizeRef = useRef({ w: 800, h: height });

  // 根据当前数据构建 uPlot options 与 aligned data
  const build = (): uPlot | null => {
    const wrap = wrapRef.current;
    if (!wrap || x.length === 0) return null;
    const w = wrap.clientWidth || 800;
    sizeRef.current = { w, h: height };

    const target = Math.max(800, Math.min(x.length, Math.floor(w * 2)));
    const raw = lttb(x, y, target);
    const series: uPlot.AlignedData = [raw.x, raw.y];

    const uSeries: uPlot.Series[] = [
      {},
      { label: "原始信号", stroke: "#7f8c9b", width: 1, points: { show: false } },
    ];

    if (yProc && yProc.length === x.length) {
      const proc = lttb(x, yProc, target);
      series.push(proc.y);
      uSeries.push({
        label: "处理后",
        stroke: "#e6edf3",
        width: 1.5,
        points: { show: false },
      });
    }

    const algNames = Object.keys(peaks);
    for (const alg of algNames) {
      const ys = new Array(x.length).fill(null);
      for (const p of peaks[alg]) {
        const i = x.findIndex((v) => v >= p.rt);
        if (i >= 0) ys[i] = y[i];
      }
      series.push(ys);
      uSeries.push({
        label: alg,
        stroke: ALG_COLORS[alg] || "#ff00ff",
        width: 1,
        points: { show: true, size: 7, fill: ALG_COLORS[alg] || "#ff00ff" },
      });
    }

    const opts: uPlot.Options = {
      width: w,
      height,
      title: "",
      scales: { x: { time: false }, y: { auto: true } },
      axes: [
        { stroke: "#8b98a5", grid: { stroke: "#2c3744" }, ticks: { stroke: "#2c3744" } },
        { stroke: "#8b98a5", grid: { stroke: "#2c3744" }, ticks: { stroke: "#2c3744" } },
      ],
      series: uSeries,
      legend: { show: algNames.length > 0 },
    };

    return new uPlot(opts, series, wrap);
  };

  // 仅更新数据（序列数量不变时）
  const updateData = (): boolean => {
    const p = plotRef.current;
    if (!p) return false;
    const w = wrapRef.current?.clientWidth || 800;
    const target = Math.max(800, Math.min(x.length, Math.floor(w * 2)));
    const raw = lttb(x, y, target);
    const data: uPlot.AlignedData = [raw.x, raw.y];
    if (yProc && yProc.length === x.length) data.push(lttb(x, yProc, target).y);
    for (const alg of Object.keys(peaks)) {
      const ys = new Array(x.length).fill(null);
      for (const pk of peaks[alg]) {
        const i = x.findIndex((v) => v >= pk.rt);
        if (i >= 0) ys[i] = y[i];
      }
      data.push(ys);
    }
    p.setData(data);
    p.setSize({ width: w, height });
    return true;
  };

  // 数据更新：序列数量变化则重建，否则只刷新数据
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || x.length === 0) return;

    const expectedLen =
      2 + (yProc && yProc.length === x.length ? 1 : 0) + Object.keys(peaks).length;
    const have = plotRef.current;

    if (have && have.series.length === expectedLen) {
      updateData();
    } else {
      plotRef.current?.destroy();
      plotRef.current = build();
    }
  }, [x, y, yProc, peaks, height]);

  // 响应式：容器宽度变化时跟随
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const ro = new ResizeObserver(() => {
      const p = plotRef.current;
      if (p && wrap.clientWidth > 0) {
        p.setSize({ width: wrap.clientWidth, height: sizeRef.current.h });
      }
    });
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // 卸载时销毁
  useEffect(() => {
    return () => {
      plotRef.current?.destroy();
      plotRef.current = null;
    };
  }, []);

  return <div className="chart-wrap" ref={wrapRef} style={{ height }} />;
}
