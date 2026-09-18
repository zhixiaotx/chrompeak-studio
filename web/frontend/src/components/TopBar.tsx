import { useEffect, useRef, useState } from "react";
import type { AlgMeta } from "../api";
import { algVisual } from "../theme";

export type Cmd =
  | "open-file" | "sample" | "import-json" | "export-csv" | "export-json"
  | "save-project" | "batch" | "clear-log"
  | "toggle-raw" | "toggle-proc" | "toggle-markers" | "toggle-measure"
  | "view-algo" | "view-preprocess" | "view-compare" | "view-log" | "view-about"
  | "select-all" | "select-none" | "run-all" | "toggle-auth"
  | `toggle-alg:${string}`;

interface Props {
  algos: AlgMeta[];
  enabled: Record<string, boolean>;
  showRaw: boolean;
  showProc: boolean;
  showMarkers: boolean;
  measuring: boolean;
  backendOk: boolean | null;
  token: string | null;
  username: string;
  showAuth: boolean;
  onCmd: (cmd: Cmd) => void;
  onLogout: () => void;
}

interface Item {
  label: string;
  cmd?: Cmd;
  kbd?: string;
  checked?: boolean;
  sep?: boolean;
  disabled?: boolean;
}

export default function TopBar({
  algos, enabled, showRaw, showProc, showMarkers,
  backendOk, token, username, showAuth, onCmd, onLogout,
}: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!barRef.current?.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const menus: { key: string; label: string; items: Item[] }[] = [
    {
      key: "file", label: "文件",
      items: [
        { label: "打开数据文件…", cmd: "open-file", kbd: "Ctrl+O" },
        { label: "载入示例数据", cmd: "sample" },
        { label: "导入项目 JSON…", cmd: "import-json" },
        { sep: true, label: "" },
        { label: "导出峰表 CSV", cmd: "export-csv", kbd: "Ctrl+S" },
        { label: "导出项目 JSON", cmd: "export-json" },
        { sep: true, label: "" },
        { label: "保存项目", cmd: "save-project", kbd: "Ctrl+Shift+S" },
        { label: "ZIP 批量处理…", cmd: "batch" },
      ],
    },
    {
      key: "view", label: "视图",
      items: [
        { label: "原始数据曲线", cmd: "toggle-raw", checked: showRaw },
        { label: "处理后曲线", cmd: "toggle-proc", checked: showProc },
        { label: "峰位标记", cmd: "toggle-markers", checked: showMarkers },
        { sep: true, label: "" },
        { label: "算法面板", cmd: "view-algo" },
        { label: "预处理面板", cmd: "view-preprocess" },
        { label: "对比面板", cmd: "view-compare" },
        { label: "运行日志", cmd: "view-log" },
      ],
    },
    {
      key: "alg", label: "算法",
      items: [
        { label: "全选", cmd: "select-all" },
        { label: "全不选", cmd: "select-none" },
        { sep: true, label: "" },
        { label: "运行全部已选算法", cmd: "run-all" },
        { sep: true, label: "" },
        ...algos.map((a) => ({
          label: `${algVisual(a.name).code}  ${algVisual(a.name).label}`,
          cmd: `toggle-alg:${a.name}` as Cmd,
          checked: !!enabled[a.name],
        })),
      ],
    },
    {
      key: "tools", label: "工具",
      items: [
        { label: "ZIP 批量处理…", cmd: "batch" },
        { label: "清空运行日志", cmd: "clear-log" },
        { sep: true, label: "" },
        {
          label: backendOk === false
            ? "后端：未连接（浏览器本地计算）"
            : backendOk === true ? "后端：已连接" : "后端：检测中…",
          disabled: true,
        },
      ],
    },
    {
      key: "help", label: "帮助",
      items: [
        { label: "关于 ChromaPeak Studio", cmd: "view-about" },
        { label: "面板说明…", cmd: "view-log" },
      ],
    },
  ];

  const click = (it: Item) => {
    if (it.disabled || !it.cmd) return;
    setOpen(null);
    onCmd(it.cmd);
  };

  return (
    <div className="topbar" ref={barRef}>
      <span className="logo">CP</span>
      <div className="brand">
        <h1>ChromaPeak Studio</h1>
        <span className="sub">— 气相色谱峰识别算法测试平台</span>
      </div>

      <div className="menubar">
        {menus.map((m) => (
          <div className="menu-wrap" key={m.key}>
            <button
              className={`menu-btn${open === m.key ? " on" : ""}`}
              onClick={() => setOpen(open === m.key ? null : m.key)}
            >
              {m.label}
            </button>
            {open === m.key && (
              <div className="menu-pop">
                {m.items.map((it, i) =>
                  it.sep ? (
                    <div className="sep" key={i} />
                  ) : (
                    <button
                      key={i}
                      onClick={() => click(it)}
                      disabled={it.disabled}
                      style={it.disabled ? { opacity: 0.5, cursor: "default" } : undefined}
                    >
                      <span>
                        {it.checked !== undefined && (
                          <span style={{ color: "var(--accent)", marginRight: 6 }}>
                            {it.checked ? "✓" : "\u00a0"}
                          </span>
                        )}
                        {it.label}
                      </span>
                      {it.kbd && <kbd>{it.kbd}</kbd>}
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="spacer" />

      <div className="topbar-actions">
        <button className="tbtn" onClick={() => onCmd("view-compare")} title="算法对比">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <line x1="4" y1="20" x2="20" y2="20" />
            <rect x="5" y="11" width="3.5" height="7" rx="1" />
            <rect x="10.2" y="6" width="3.5" height="12" rx="1" />
            <rect x="15.4" y="13.5" width="3.5" height="4.5" rx="1" />
          </svg>
          <span>对比</span>
        </button>
        <button className="tbtn" onClick={() => onCmd("batch")} title="批量处理 ZIP">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3.5 7.5 12 3.5l8.5 4v9L12 20.5l-8.5-4z" />
            <path d="M3.5 7.5 12 11.5l8.5-4M12 11.5v9" />
          </svg>
          <span>批量</span>
        </button>
        <button className="tbtn" onClick={() => onCmd("toggle-markers")} title="峰位标记">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="12" cy="12" r="8" />
            <line x1="12" y1="2.5" x2="12" y2="21.5" />
            <line x1="2.5" y1="12" x2="21.5" y2="12" />
          </svg>
          <span>测量</span>
        </button>
        <button className="tbtn" onClick={() => onCmd("export-csv")} title="导出峰表">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3.5v11" /><path d="M7.5 10.5 12 15l4.5-4.5" /><path d="M4.5 19.5h15" />
          </svg>
          <span>导出</span>
        </button>
        <span className="badge-count">{algos.length} 算法</span>
        {token ? (
          <span className="user-chip">
            {username}
            <button className="ghost" onClick={onLogout}>退出</button>
          </span>
        ) : backendOk === false ? (
          <span className="user-chip">离线</span>
        ) : (
          <button
            className={`tbtn${showAuth ? " on" : ""}`}
            onClick={() => onCmd("view-algo")}
            style={{ display: "none" }}
          />
        )}
      </div>
    </div>
  );
}
