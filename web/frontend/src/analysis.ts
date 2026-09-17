// 前端离线分析引擎（无需后端即可运行）。
// 当 Web 端部署到 GitHub Pages / Cloudflare / Vercel / Netlify 等纯静态平台、
// 且未连接 FastAPI 后端时，前端会回退到本模块，用 TypeScript 实现的核心算法
// 在浏览器里直接做峰识别，做到「页面打开即用、不报 404/405」。

import type { AlgMeta, ParamSpec, Peak } from "./api";

// ---------------- 数值工具 ----------------
function maxOf(a: number[]): number {
  let m = -Infinity;
  for (const v of a) if (v > m) m = v;
  return m === -Infinity ? 1e-9 : m;
}

function movingAverage(y: number[], win: number): number[] {
  const w = Math.max(1, Math.floor(win));
  const half = Math.floor(w / 2);
  const out = new Array<number>(y.length);
  for (let i = 0; i < y.length; i++) {
    let s = 0;
    let c = 0;
    const lo = Math.max(0, i - half);
    const hi = Math.min(y.length - 1, i + half);
    for (let j = lo; j <= hi; j++) {
      s += y[j];
      c++;
    }
    out[i] = s / c;
  }
  return out;
}

function movingMin(y: number[], win: number): number[] {
  const w = Math.max(1, Math.floor(win));
  const half = Math.floor(w / 2);
  const out = new Array<number>(y.length);
  for (let i = 0; i < y.length; i++) {
    let m = Infinity;
    const lo = Math.max(0, i - half);
    const hi = Math.min(y.length - 1, i + half);
    for (let j = lo; j <= hi; j++) m = Math.min(m, y[j]);
    out[i] = m;
  }
  return out;
}

function gradient(y: number[]): number[] {
  const out = new Array<number>(y.length).fill(0);
  for (let i = 1; i < y.length; i++) out[i] = y[i] - y[i - 1];
  return out;
}

// 高斯平滑（sigma 为索引单位）
function gaussianSmooth(y: number[], sigma: number): number[] {
  const s = Math.max(0.5, sigma);
  const r = Math.ceil(s * 3);
  const out = new Array<number>(y.length).fill(0);
  for (let i = 0; i < y.length; i++) {
    let wsum = 0;
    let vsum = 0;
    for (let j = -r; j <= r; j++) {
      const idx = i + j;
      if (idx < 0 || idx >= y.length) continue;
      const wgt = Math.exp(-(j * j) / (2 * s * s));
      wsum += wgt;
      vsum += wgt * y[idx];
    }
    out[i] = wsum > 0 ? vsum / wsum : y[i];
  }
  return out;
}

// 差分高斯（近似墨西哥帽小波脊线）
function differenceOfGaussian(y: number[], sigma: number): number[] {
  const a = gaussianSmooth(y, sigma);
  const b = gaussianSmooth(y, sigma * 1.6);
  return a.map((v, i) => v - b[i]);
}

// 非对称基线：窗口极小值上包络，再轻度平滑
function baseline(y: number[], win = 64): number[] {
  const half = Math.max(1, Math.floor(win / 2));
  const base = new Array<number>(y.length);
  for (let i = 0; i < y.length; i++) {
    let mn = Infinity;
    const lo = Math.max(0, i - half);
    const hi = Math.min(y.length - 1, i + half);
    for (let j = lo; j <= hi; j++) mn = Math.min(mn, y[j]);
    base[i] = mn;
  }
  return movingAverage(base, 8);
}

// 峰指标：半峰宽 FWHM、面积、不对称因子
function peakMetrics(
  x: number[],
  yRaw: number[],
  base: number[],
  apex: number
): { height: number; area: number; fwhm: number; asymmetry: number; left: number; right: number } | null {
  const h = yRaw[apex] - base[apex];
  if (h <= 0) return null;
  const half = h / 2;
  let left = apex;
  let right = apex;
  while (left > 0 && yRaw[left] - base[left] > half) left--;
  while (right < yRaw.length - 1 && yRaw[right] - base[right] > half) right++;
  const fwhm = Math.abs(x[right] - x[left]);
  let area = 0;
  for (let i = left; i < right; i++) {
    const a = Math.max(0, yRaw[i] - base[i]);
    const b = Math.max(0, yRaw[i + 1] - base[i + 1]);
    area += ((a + b) * (x[i + 1] - x[i])) / 2;
  }
  const leftH = Math.abs(x[apex] - x[left]);
  const rightH = Math.abs(x[right] - x[apex]);
  const asymmetry = rightH > 1e-9 ? leftH / rightH : 1;
  return { height: h, area, fwhm, asymmetry, left, right };
}

type Strategy = "deriv" | "curv" | "tophat" | "wavelet" | "emg" | "gnn";

interface DetectOpts {
  smooth: number;
  threshold: number; // 0..1 相对最大响应
  minDistance: number; // 索引间距
  strategy: Strategy;
}

function findPeaks(x: number[], yRaw: number[], opts: DetectOpts): Peak[] {
  const base = baseline(yRaw, Math.max(32, opts.smooth * 4));
  let y = yRaw.map((v, i) => v - base[i]);
  y = movingAverage(y, opts.smooth);
  const ymax = maxOf(y);

  const cand = new Set<number>();
  if (opts.strategy === "curv") {
    const d2 = gradient(gradient(y));
    const dmax = maxOf(d2.map(Math.abs));
    for (let i = 2; i < y.length - 2; i++) {
      if (y[i] > opts.threshold * ymax && d2[i] < -0.2 * dmax) cand.add(i);
    }
  } else if (opts.strategy === "tophat") {
    const mm = movingMin(y, opts.smooth * 3);
    const tophat = y.map((v, i) => v - mm[i]);
    const tmax = maxOf(tophat);
    for (let i = 1; i < y.length - 1; i++) {
      if (y[i] >= y[i - 1] && y[i] >= y[i + 1] && tophat[i] > 0.3 * tmax) cand.add(i);
    }
  } else if (opts.strategy === "wavelet") {
    const dog = differenceOfGaussian(y, opts.smooth);
    const dmax = maxOf(dog.map(Math.abs));
    for (let i = 2; i < y.length - 2; i++) {
      if (y[i] > opts.threshold * ymax && dog[i] < -0.2 * dmax) cand.add(i);
    }
  } else {
    // deriv（ALG-D / emg / gnn 默认）
    const dy = gradient(y);
    for (let i = 1; i < y.length - 1; i++) {
      if (dy[i - 1] < 0 && dy[i] >= 0 && y[i] > opts.threshold * ymax) cand.add(i);
    }
    for (let i = 1; i < y.length - 1; i++) {
      if (y[i] >= y[i - 1] && y[i] >= y[i + 1] && y[i] > opts.threshold * ymax) cand.add(i);
    }
  }

  const list = Array.from(cand).sort((a, b) => y[b] - y[a]);
  const used = new Array<boolean>(y.length).fill(false);
  const peaks: Peak[] = [];
  for (const i of list) {
    if (used[i]) continue;
    let conflict = false;
    for (const p of peaks) {
      if (Math.abs(p.index - i) < opts.minDistance) {
        conflict = true;
        break;
      }
    }
    if (conflict) continue;
    const m = peakMetrics(x, yRaw, base, i);
    if (!m) continue;
    for (let k = Math.max(0, i - opts.minDistance); k <= Math.min(y.length - 1, i + opts.minDistance); k++) used[k] = true;
    const score = Math.min(1, m.height / ymax + 0.2);
    peaks.push({
      index: i,
      rt: x[i],
      height: m.height,
      area: m.area,
      left: m.left,
      right: m.right,
      fwhm: m.fwhm,
      asymmetry: m.asymmetry,
      score,
      algorithm: "",
    });
  }
  peaks.sort((a, b) => a.rt - b.rt);
  return peaks;
}

function strategyFor(name: string, p: Record<string, any>): DetectOpts {
  const smooth = Number(p.smooth ?? 5);
  const threshold = Number(p.threshold ?? 0.05);
  const minDistance = Number(p.minDistance ?? 8);
  const base: DetectOpts = { smooth, threshold, minDistance, strategy: "deriv" };
  switch (name) {
    case "ALG-D":
      return { ...base, strategy: "deriv" };
    case "ALG-C":
      return { ...base, strategy: "curv" };
    case "ALG-M":
      return { ...base, strategy: "tophat", smooth: Math.max(smooth, 7) };
    case "ALG-W":
      return { ...base, strategy: "wavelet", smooth: Math.max(smooth, 9) };
    case "ALG-E":
      return { ...base, strategy: "emg", smooth: Math.max(smooth, 7) };
    case "ALG-GNN":
      return { ...base, strategy: "gnn", smooth: Math.max(smooth, 6) };
    default:
      return base;
  }
}

// ---------------- 对外 API ----------------
export function analyzeLocal(
  x: number[],
  yRaw: number[],
  algorithms: string[],
  params: Record<string, Record<string, any>>
): { x: number[]; y: number[]; y_proc: number[]; results: Record<string, Peak[]> } {
  const results: Record<string, Peak[]> = {};
  for (const name of algorithms) {
    const peaks = findPeaks(x, yRaw, strategyFor(name, params[name] || {})).map((pk) => ({
      ...pk,
      algorithm: name,
    }));
    results[name] = peaks;
  }
  return { x, y: yRaw, y_proc: preprocessForDisplay(x, yRaw), results };
}

export function preprocessForDisplay(x: number[], y: number[]): number[] {
  const base = baseline(y, 64);
  let ys = y.map((v, i) => v - base[i]);
  ys = movingAverage(ys, 5);
  return ys;
}

// 解析上传的 CSV/TXT（两列：x, y），自动跳过表头与非数字行
export async function parseCsvFile(file: File): Promise<{ x: number[]; y: number[] }> {
  const text = await file.text();
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
  const x: number[] = [];
  const y: number[] = [];
  for (const l of lines) {
    const parts = l.split(/[,;\t\s]+/);
    if (parts.length < 2) continue;
    const a = parseFloat(parts[0]);
    const b = parseFloat(parts[1]);
    if (isFinite(a) && isFinite(b)) {
      x.push(a);
      y.push(b);
    }
  }
  return { x, y };
}

// 前端生成示例色谱（无后端时的默认数据）
export function syntheticChromatogram(n = 600): { x: number[]; y: number[] } {
  const x: number[] = [];
  for (let i = 0; i < n; i++) x.push(Number((i * 0.1).toFixed(3)));
  const gauss = (mu: number, sigma: number, amp: number) =>
    x.map((t) => amp * Math.exp(-((t - mu) ** 2) / (2 * sigma * sigma)));
  const peaks = [
    gauss(12, 0.9, 1.0),
    gauss(25, 1.4, 0.7),
    gauss(38, 0.7, 0.45),
    gauss(46, 1.1, 0.85),
  ];
  const baseline = x.map((t) => 0.05 + 0.0008 * t + 0.02 * Math.sin(t * 0.3));
  const y: number[] = [];
  let seed = 12345;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return (seed / 0x7fffffff - 0.5) * 0.06;
  };
  for (let i = 0; i < n; i++) {
    let v = baseline[i] + rand();
    for (const p of peaks) v += p[i];
    y.push(Number(v.toFixed(4)));
  }
  return { x, y };
}

// ---------------- 算法元信息（与后端一致的 UI） ----------------
function pSmooth(def: number): ParamSpec {
  return { key: "smooth", label: "平滑窗口", type: "int", default: def, min: 1, max: 31, step: 2, help: "越大越平滑、越抗噪" };
}
function pThr(def: number): ParamSpec {
  return { key: "threshold", label: "阈值(相对)", type: "float", default: def, min: 0.01, max: 0.5, step: 0.01, help: "峰高相对最大响应的比例" };
}
function pDist(def: number): ParamSpec {
  return { key: "minDistance", label: "最小峰距", type: "int", default: def, min: 2, max: 60, step: 1, help: "两峰间最小索引距离" };
}

export const LOCAL_ALGORITHMS: AlgMeta[] = [
  { name: "ALG-D", description: "导数法（一阶导过零）", params: [pSmooth(5), pThr(0.05), pDist(8)] },
  { name: "ALG-W", description: "小波变换（脊线）", params: [pSmooth(9), pThr(0.05), pDist(8)] },
  { name: "ALG-M", description: "形态学顶帽", params: [pSmooth(7), pThr(0.05), pDist(8)] },
  { name: "ALG-C", description: "曲率法（二阶导）", params: [pSmooth(5), pThr(0.05), pDist(8)] },
  { name: "ALG-E", description: "EMG 拟合（离线近似）", params: [pSmooth(7), pThr(0.05), pDist(8)] },
  { name: "ALG-GNN", description: "图神经网络（离线回退）", params: [pSmooth(6), pThr(0.05), pDist(8)] },
];
