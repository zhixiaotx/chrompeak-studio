// 统一视觉层：算法编号徽标 / 中文展示名 / 曲线配色 / 说明文案。
// 桌面端 desktop/theme.py 使用同一套取值，改色时两端一起改。

export interface AlgVisual {
  /** 编号徽标，例如 ALG-D */
  code: string;
  /** 中文展示名 */
  label: string;
  /** 曲线与散点颜色 */
  color: string;
  /** 一句话说明（显示在右侧面板底部） */
  desc: string;
}

export const ALG_VISUALS: Record<string, AlgVisual> = {
  "ALG-D": {
    code: "ALG-D",
    label: "导数法（一阶导数过零）",
    color: "#3b82f6",
    desc: "Savitzky-Golay 平滑后求一阶导数，以零交叉点配合二阶导数负判决定位峰顶；对缓变基线漂移稳健。",
  },
  "ALG-E": {
    code: "ALG-E",
    label: "指数修正高斯拟合",
    color: "#ef4444",
    desc: "以上游检出的峰位为初值，用指数修正高斯（EMG）做非线性精修，修正拖尾峰的峰高与面积；重叠峰走双 EMG 解卷积。",
  },
  "ALG-W": {
    code: "ALG-W",
    label: "CWT 小波变换",
    color: "#a855f7",
    desc: "多尺度 Ricker 小波连续变换取脊线最大响应，抗噪能力强，适合分离肩峰与重叠峰。",
  },
  "ALG-M": {
    code: "ALG-M",
    label: "形态学 Top-Hat",
    color: "#22c55e",
    desc: "原信号减去开运算结果（Top-Hat 变换），只保留比结构元素更窄的局部波峰，对宽基线漂移天然免疫。",
  },
  "ALG-C": {
    code: "ALG-C",
    label: "曲率法（二阶导数）",
    color: "#f59e0b",
    desc: "取平滑信号的二阶导数，以负极大值（曲率最大处）定位峰顶，对宽峰与低矮峰同样敏感。",
  },
  "ALG-GNN": {
    code: "ALG-GNN",
    label: "图神经网络解卷积",
    color: "#06b6d4",
    desc: "把色谱序列构图后由 ONNX 模型输出逐点峰概率热力，再经 EMG 精修；未加载模型时自动回退二阶导数判据。",
  },
};

const FALLBACK: AlgVisual = {
  code: "ALG-?",
  label: "未登记算法",
  color: "#8b949e",
  desc: "",
};

export function algVisual(name: string): AlgVisual {
  return ALG_VISUALS[name] ?? { ...FALLBACK, code: name, label: name };
}

/** 去掉括号补充说明后的短名，用于列表与表格等窄栏位 */
export function algShortLabel(name: string): string {
  return algVisual(name).label.replace(/（.*?）/g, "").trim();
}

/** 图表配色（与桌面端 theme.py 中 PLOT 保持一致） */
export const PLOT = {
  bg: "#191d23",
  grid: "#252a32",
  axis: "#8b949e",
  raw: "#98a2b3",
  proc: "#e8eaed",
  /** 处理后曲线的面积填充（半透明） */
  procFill: "rgba(232, 234, 237, 0.08)",
  region: "rgba(47, 127, 244, 0.10)",
};

/** 图标栏面板标识 */
export type PanelKey = "algo" | "preprocess" | "compare" | "log" | "about";

export const PANEL_TITLES: Record<PanelKey, string> = {
  algo: "算法",
  preprocess: "预处理",
  compare: "对比",
  log: "日志",
  about: "关于",
};

/** 预处理默认值（与 core/preprocess.py 的 PreprocessOptions 一致） */
export interface PreprocessConf {
  baseline: boolean;
  baseline_order: number;
  baseline_iters: number;
  baseline_tol: number;
  smooth: boolean;
  smooth_window: number;
  smooth_polyorder: number;
}

export const DEFAULT_PREPROCESS: PreprocessConf = {
  baseline: true,
  baseline_order: 3,
  baseline_iters: 10,
  baseline_tol: 1e-4,
  smooth: true,
  smooth_window: 11,
  smooth_polyorder: 3,
};

/** 一次算法执行的统计，用于右侧列表「状态 / 耗时」列与对比面板 */
export interface AlgRunStat {
  peaks: number;
  /** 毫秒；null 表示本次未单独计时（例如批量 REST 分析） */
  ms: number | null;
  status: "ok" | "error";
  message?: string;
}
