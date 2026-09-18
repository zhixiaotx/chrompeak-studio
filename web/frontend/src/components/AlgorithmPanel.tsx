import { Fragment } from "react";
import type { AlgMeta, ParamSpec } from "../api";
import { algShortLabel, algVisual, type AlgRunStat } from "../theme";

interface Props {
  algos: AlgMeta[];
  total: number;
  enabled: Record<string, boolean>;
  params: Record<string, Record<string, any>>;
  stats: Record<string, AlgRunStat>;
  active: string;
  search: string;
  onSearch: (v: string) => void;
  onToggle: (name: string, checked: boolean) => void;
  onSelect: (name: string) => void;
  onRunOne: (name: string) => void;
  onParamChange: (name: string, key: string, value: any) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
}

function ParamInput({
  spec, value, onChange,
}: { spec: ParamSpec; value: any; onChange: (v: any) => void }) {
  if (spec.type === "bool") {
    return (
      <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
    );
  }
  if (spec.type === "choice" && spec.choices) {
    return (
      <select value={String(value)} onChange={(e) => onChange(e.target.value)}>
        {spec.choices.map((c) => (
          <option key={String(c)} value={String(c)}>{String(c)}</option>
        ))}
      </select>
    );
  }
  const isFloat = spec.type === "float";
  return (
    <input
      type="number"
      step={spec.step ?? (isFloat ? 0.01 : 1)}
      min={spec.min ?? undefined}
      max={spec.max ?? undefined}
      value={value}
      onChange={(e) =>
        onChange(isFloat ? parseFloat(e.target.value) : parseInt(e.target.value, 10))
      }
    />
  );
}

export default function AlgorithmPanel({
  algos, total, enabled, params, stats, active, search, onSearch,
  onToggle, onSelect, onRunOne, onParamChange, onSelectAll, onSelectNone,
}: Props) {
  const nSel = algos.filter((a) => enabled[a.name]).length;
  const activeMeta = algos.find((a) => a.name === active);
  const v = activeMeta ? algVisual(activeMeta.name) : null;

  return (
    <>
      <div className="panel-search">
        <input
          placeholder="搜索算法名称 / 编号…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </div>
      <div className="panel-sub">
        <span>共 {total} 个 · 已选 {nSel}</span>
        <span className="links">
          <button onClick={onSelectAll}>全选</button>
          <button onClick={onSelectNone}>全不选</button>
        </span>
      </div>

      <div className="panel-body">
        {algos.length === 0 && <div className="empty">没有匹配的算法</div>}
        {algos.map((a) => {
          const vis = algVisual(a.name);
          const st = stats[a.name];
          const on = !!enabled[a.name];
          return (
            <Fragment key={a.name}>
              <div
                className={`alg-row${active === a.name ? " active" : ""}`}
                onClick={() => onSelect(a.name)}
              >
                <input
                  type="checkbox"
                  checked={on}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => onToggle(a.name, e.target.checked)}
                />
                <div className="name">
                  <span className="swatch" style={{ background: vis.color }} />
                  <span title={vis.label}>{algShortLabel(a.name)}</span>
                  <span className="code">{vis.code}</span>
                </div>
                <div className="stat">
                  <button
                    className="ghost"
                    title="只运行该算法"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRunOne(a.name);
                    }}
                  >
                    执行
                  </button>
                </div>
                <div className="stat">
                  <span
                    className={`res${st ? (st.status === "ok" ? " ok" : " err") : ""}`}
                    title={st?.message || ""}
                  >
                    {st
                      ? st.status === "ok"
                        ? `${st.peaks} 峰${st.ms != null ? ` | ${st.ms} ms` : ""}`
                        : `失败 | ${st.ms ?? 0} ms`
                      : on ? "待执行" : "未启用"}
                  </span>
                </div>
              </div>

              {active === a.name && on && a.params.length > 0 && (
                <div className="params">
                  {a.params.map((spec) => (
                    <div className="param" key={spec.key}>
                      <label title={spec.help}>{spec.label}</label>
                      <ParamInput
                        spec={spec}
                        value={(params[a.name] || {})[spec.key] ?? spec.default}
                        onChange={(val) => onParamChange(a.name, spec.key, val)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </Fragment>
          );
        })}
      </div>

      <div className="panel-foot">
        {v ? (
          <>
            <b style={{ color: "var(--text)" }}>{v.code}</b>
            <span style={{ marginLeft: 6 }}>{v.label}</span>
            <div style={{ marginTop: 4 }}>{v.desc || activeMeta?.description}</div>
          </>
        ) : (
          "选择左侧任一算法查看参数与说明。"
        )}
      </div>
    </>
  );
}
