import type { AlgMeta, ParamSpec } from "../api";

interface Props {
  algos: AlgMeta[];
  enabled: Record<string, boolean>;
  params: Record<string, Record<string, any>>;
  onToggle: (name: string, checked: boolean) => void;
  onParamChange: (name: string, key: string, value: any) => void;
}

function ParamInput({
  spec,
  value,
  onChange,
}: {
  spec: ParamSpec;
  value: any;
  onChange: (v: any) => void;
}) {
  if (spec.type === "bool") {
    return (
      <input
        type="checkbox"
        checked={!!value}
        onChange={(e) => onChange(e.target.checked)}
        style={{ width: "auto" }}
      />
    );
  }
  if (spec.type === "choice" && spec.choices) {
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {spec.choices.map((c) => (
          <option key={String(c)} value={String(c)}>
            {String(c)}
          </option>
        ))}
      </select>
    );
  }
  const isFloat = spec.type === "float";
  return (
    <input
      type={isFloat ? "number" : "number"}
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
  algos,
  enabled,
  params,
  onToggle,
  onParamChange,
}: Props) {
  return (
    <div>
      {algos.map((alg) => (
        <div className="alg-item" key={alg.name}>
          <div className="alg-head">
            <input
              type="checkbox"
              checked={!!enabled[alg.name]}
              onChange={(e) => onToggle(alg.name, e.target.checked)}
              style={{ width: "auto" }}
            />
            <span className="name">{alg.name}</span>
            <span className="badge">{alg.params.length} 参数</span>
          </div>
          <div className="desc">{alg.description}</div>
          {enabled[alg.name] &&
            alg.params.map((spec) => (
              <div className="param" key={spec.key}>
                <label title={spec.help}>{spec.label}</label>
                <ParamInput
                  spec={spec}
                  value={(params[alg.name] || {})[spec.key] ?? spec.default}
                  onChange={(v) => onParamChange(alg.name, spec.key, v)}
                />
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
