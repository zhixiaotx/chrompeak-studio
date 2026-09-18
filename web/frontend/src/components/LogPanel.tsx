export interface LogEntry {
  t: string;
  msg: string;
  kind: "" | "ok" | "err" | "warn";
}

interface Props {
  entries: LogEntry[];
  onClear: () => void;
}

export default function LogPanel({ entries, onClear }: Props) {
  return (
    <>
      <div className="panel-sub" style={{ paddingTop: 8 }}>
        <span>本次会话共 {entries.length} 条记录</span>
        <span className="links">
          <button onClick={onClear}>清空</button>
        </span>
      </div>
      <div className="panel-body">
        {entries.length === 0 ? (
          <div className="empty">暂无日志。运行分析后会在这里留下记录。</div>
        ) : (
          <div className="log-list">
            {entries.map((e, i) => (
              <div className={`log-line ${e.kind}`} key={i}>
                <span className="t">{e.t}</span>
                <span className="m">{e.msg}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
