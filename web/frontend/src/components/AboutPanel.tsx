import { ALG_VISUALS } from "../theme";

interface Props {
  backendOk: boolean | null;
  version?: string;
}

export default function AboutPanel({ backendOk, version = "1.0.0" }: Props) {
  return (
    <div className="panel-body">
      <div className="doc" style={{ paddingBottom: 0 }}>
        <b style={{ fontSize: 13 }}>ChromaPeak Studio</b>
        <div style={{ marginTop: 2 }}>气相色谱峰识别算法测试平台 · v{version}</div>
        <div style={{ marginTop: 8 }}>
          同一套算法内核（Python 包 <code>chrompeak-core</code>）同时驱动桌面端（PyQt6 GUI /
          命令行 CLI）与 Web 端（React + FastAPI），保证两端结果一致。
        </div>
      </div>

      <div className="section-label">算法清单</div>
      <div className="doc" style={{ paddingTop: 0 }}>
        {Object.values(ALG_VISUALS).map((v) => (
          <div key={v.code} style={{ display: "flex", gap: 8, marginBottom: 7 }}>
            <span
              style={{
                width: 3, borderRadius: 2, background: v.color, flex: "0 0 auto",
              }}
            />
            <span>
              <b>{v.label}</b>{" "}
              <span style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{v.code}</span>
              <div>{v.desc}</div>
            </span>
          </div>
        ))}
      </div>

      <div className="section-label">运行模式</div>
      <div className="doc" style={{ paddingTop: 0 }}>
        {backendOk === true
          ? "已连接 FastAPI 后端：参数改动走 WebSocket 流式重算，项目可保存到云端。"
          : backendOk === false
            ? "未连接后端（纯静态托管）：全部计算在浏览器本地完成，项目保存在本机 localStorage。"
            : "正在探测后端…"}
      </div>

      <div className="section-label">快捷操作</div>
      <div className="doc" style={{ paddingTop: 0 }}>
        <div>· 图表上拖动可框选放大，双击图表重置缩放</div>
        <div>· 鼠标在图上移动时右上角显示 <code>t = 时间 / 响应</code> 读数</div>
        <div>· 点击图表左上角图例可显隐对应曲线</div>
        <div>· 算法列表点「执行」可单独运行某个算法并查看耗时</div>
      </div>
    </div>
  );
}
