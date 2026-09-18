import { DEFAULT_PREPROCESS, type PreprocessConf } from "../theme";

interface Props {
  conf: PreprocessConf;
  onChange: (patch: Partial<PreprocessConf>) => void;
  onReset: () => void;
}

function Num({
  label, value, min, max, step, disabled, onChange, title,
}: {
  label: string; value: number; min?: number; max?: number; step?: number;
  disabled?: boolean; onChange: (v: number) => void; title?: string;
}) {
  return (
    <div className="field">
      <label title={title}>{label}</label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step ?? 1}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}

export default function PreprocessPanel({ conf, onChange, onReset }: Props) {
  return (
    <div className="panel-body">
      <div className="form-block">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <label className="switch">
            <input
              type="checkbox"
              checked={conf.baseline}
              onChange={(e) => onChange({ baseline: e.target.checked })}
            />
            基线校正（非对称最小二乘）
          </label>
        </div>
        <Num
          label="多项式阶数" value={conf.baseline_order} min={1} max={7} step={1}
          disabled={!conf.baseline} onChange={(v) => onChange({ baseline_order: v })}
          title="拟合基线的多项式阶数，越大越贴合弯曲基线"
        />
        <Num
          label="迭代次数" value={conf.baseline_iters} min={1} max={50} step={1}
          disabled={!conf.baseline} onChange={(v) => onChange({ baseline_iters: v })}
        />
        <Num
          label="收敛容差" value={conf.baseline_tol} min={1e-6} max={1e-2} step={1e-5}
          disabled={!conf.baseline} onChange={(v) => onChange({ baseline_tol: v })}
        />
      </div>

      <div className="section-label">平滑</div>
      <div className="form-block">
        <label className="switch">
          <input
            type="checkbox"
            checked={conf.smooth}
            onChange={(e) => onChange({ smooth: e.target.checked })}
          />
          Savitzky-Golay 平滑
        </label>
        <Num
          label="窗口长度" value={conf.smooth_window} min={3} max={101} step={2}
          disabled={!conf.smooth} onChange={(v) => onChange({ smooth_window: v })}
          title="窗口越长越平滑，但会损失窄峰分辨率（须为奇数）"
        />
        <Num
          label="多项式阶数" value={conf.smooth_polyorder} min={1} max={7} step={1}
          disabled={!conf.smooth} onChange={(v) => onChange({ smooth_polyorder: v })}
        />
        <div className="row" style={{ marginTop: 4 }}>
          <button onClick={onReset}>恢复默认</button>
        </div>
      </div>

      <div className="doc">
        <b>提示：</b>基线校正采用非对称最小二乘（airPLS 变体），只惩罚位于基线以下的偏离，
        因此不会把真实峰削掉。平滑在基线校正之后进行，改动参数会立即重算。
        离线演示模式下浏览器会用等价的窗口极小值包络 + 移动平均实现。
      </div>
    </div>
  );
}
