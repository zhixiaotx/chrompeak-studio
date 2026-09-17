import { useState } from "react";
import { api } from "../api";

interface Props {
  onAuth: (token: string, username: string) => void;
}

export default function Auth({ onAuth }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function submit() {
    setErr("");
    try {
      if (mode === "register") {
        await api.register(username, password);
      }
      const token = await api.login(username, password);
      onAuth(token, username);
    } catch (e: any) {
      setErr(e.message || "认证失败");
    }
  }

  return (
    <div className="card" style={{ maxWidth: 360, margin: "40px auto" }}>
      <h3>{mode === "login" ? "登录" : "注册"} ChromaPeak Studio</h3>
      <div className="param">
        <label>用户名</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} />
      </div>
      <div className="param">
        <label>密码</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      {err && <div className="status error">{err}</div>}
      <div className="row" style={{ marginTop: 10 }}>
        <button onClick={submit}>提交</button>
        <button
          className="ghost"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "去注册" : "去登录"}
        </button>
      </div>
      <div className="hint" style={{ marginTop: 10 }}>
        注册/登录用于保存分析项目（需要后端已开启用户系统）。
      </div>
    </div>
  );
}
