// 浏览器端 ZIP 批量处理（离线模式可用）。
// 用 JSZip 在前端解压上传的 ZIP，逐个 CSV 走本地算法出峰，再把结果打包成一个新的 ZIP 下载。
// 这样即使部署在纯静态托管（无 FastAPI 后端），批量功能依然可用。

import JSZip from "jszip";
import { analyzeLocal, parseCsvText } from "../analysis";
import type { Peak } from "../api";

const CSV_EXT = /\.(csv|txt|tsv)$/i;

const HEADER = "file,algorithm,index,rt,height,area,fwhm,asymmetry,score";

export interface BatchOutcome {
  nFiles: number;
  nPeaks: number;
  fileName: string;
  blob: Blob;
}

function peakRow(file: string, p: Peak): string {
  return [
    file,
    p.algorithm,
    p.index,
    p.rt,
    p.height.toFixed(6),
    p.area.toFixed(6),
    p.fwhm.toFixed(6),
    p.asymmetry.toFixed(4),
    p.score.toFixed(4),
  ].join(",");
}

function baseName(name: string): string {
  const parts = name.split("/");
  return (parts[parts.length - 1] || name).replace(/\.[^.]+$/, "");
}

/** 触发浏览器下载 */
export function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/**
 * 处理上传的 ZIP：返回可直接下载的结果 Blob。
 * @param onProgress 每处理完一个文件回调一次，用于更新进度文案
 */
export async function batchProcessLocalZip(
  zipFile: File,
  algorithms: string[],
  params: Record<string, Record<string, any>>,
  onProgress?: (done: number, total: number, current: string) => void
): Promise<BatchOutcome> {
  const zip = await JSZip.loadAsync(zipFile);

  const entries: { name: string; getText: () => Promise<string> }[] = [];
  zip.forEach((path, handle) => {
    if (handle.dir) return;
    if (!CSV_EXT.test(path)) return;
    entries.push({ name: path, getText: () => handle.async("string") });
  });

  if (!entries.length) throw new Error("ZIP 内没有找到 CSV/TXT 数据文件");
  if (!algorithms.length) throw new Error("请至少选择一个算法");

  const summary: string[] = [HEADER];
  const out = new JSZip();
  const peaksDir = out.folder("peaks") || out;
  let nPeaks = 0;
  let nFiles = 0;

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    onProgress?.(i, entries.length, entry.name);
    await new Promise((r) => setTimeout(r, 0)); // 让出主线程，避免大批量时页面卡死

    let text: string;
    try {
      text = await entry.getText();
    } catch {
      continue;
    }
    const { x, y } = parseCsvText(text);
    if (x.length < 3) continue;
    nFiles++;

    const res = analyzeLocal(x, y, algorithms, params);
    const rows: string[] = [];
    for (const alg of algorithms) {
      for (const p of res.results[alg] || []) {
        const line = peakRow(entry.name, p);
        summary.push(line);
        rows.push(line);
        nPeaks++;
      }
    }
    peaksDir.file(`${baseName(entry.name)}_peaks.csv`, [HEADER, ...rows].join("\n"));
  }

  out.file("summary.csv", summary.join("\n"));
  out.file(
    "README.txt",
    [
      "ChromaPeak Studio - 离线批量结果",
      `源文件：${zipFile.name}`,
      `数据文件数：${nFiles}`,
      `算法：${algorithms.join(", ")}`,
      `总峰数：${nPeaks}`,
      "说明：结果由浏览器本地算法计算，与 Python 后端结果可能有细微差异。",
    ].join("\n")
  );

  const blob = await out.generateAsync({ type: "blob" });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  return { nFiles, nPeaks, fileName: `chromapeak-batch-${stamp}.zip`, blob };
}
