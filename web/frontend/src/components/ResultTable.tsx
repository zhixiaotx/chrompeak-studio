import type { Peak } from "../api";

interface Props {
  peaks: Peak[];
}

export default function ResultTable({ peaks }: Props) {
  if (peaks.length === 0) {
    return <div className="hint">暂无峰结果。上传数据并运行分析后，这里会列出每个峰的指标。</div>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>算法</th>
          <th>RT</th>
          <th>峰高</th>
          <th>面积</th>
          <th>半高宽</th>
          <th>不对称</th>
          <th>置信度</th>
        </tr>
      </thead>
      <tbody>
        {peaks.map((p, i) => (
          <tr key={`${p.algorithm}-${i}`}>
            <td>{p.algorithm}</td>
            <td>{p.rt.toFixed(3)}</td>
            <td>{p.height.toFixed(4)}</td>
            <td>{p.area.toFixed(4)}</td>
            <td>{p.fwhm.toFixed(3)}</td>
            <td>{p.asymmetry.toFixed(2)}</td>
            <td>{p.score.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
