import { useState } from "react";
import { api } from "../api";

interface Props {
  onAuth: (token: string, username: string) => void;
  /** 后端不可用时禁用表单，避免把 POST 打到静态主机上（会返回 405） */
  disabled?: boolean;
  onClose?: () => void;
}

export default function Auth({ onAuth, disabled = false, onClose }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (disabled) {
      setErr("离线模式下无法登录：当前站点没有后端服务。");
      return;
    }
    setErr("");
    setBusy(true);
    try {
      if (mode === "register") {
        await api.register(username, password);
      }
      const token = await api.login(username, password);
      onAuth(token, username);
    } catch (e: any) {
      setErr(e.message || "认证失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card auth-card">
      <div className="row" style={{ alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{mode === "login" ? "登录" : "注册"} ChromaPeak Studio</h3>
        <div className="spacer" />
        {onClose && (
          <button className="ghost" onClick={onClose} title="收起">
            ✕
          </button>
        )}
      </div>

      <div className="param">
        <label>用户名</label>
        <input
          value={username}
          disabled={disabled || busy}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
      </div>
      <div className="param">
        <label>密码</label>
        <input
          type="password"
          value={password}
          disabled={disabled || busy}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
      </div>

      {err && <div className="status error">{err}</div>}

      <div className="row" style={{ marginTop: 10 }}>
        <button onClick={submit} disabled={disabled || busy}>
          {busy ? "提交中…" : "提交"}
        </button>
        <button
          className="ghost"
          disabled={disabled || busy}
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "去注册" : "去登录"}
        </button>
      </div>

      <div className="hint" style={{ marginTop: 10 }}>
        {disabled
          ? "离线演示模式下无需登录；上传 CSV、算法对比、参数调优、导出 JSON 均可直接使用。"
          : "注册/登录用于保存分析项目（需要后端已开启用户系统）。"}
      </div>
    </div>
  );
}
