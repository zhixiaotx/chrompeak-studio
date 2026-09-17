// Largest-Triangle-Three-Buckets 降采样：在保留波形形态的前提下大幅减少点数，
// 用于大文件在浏览器中的流畅渲染。返回 [x, y] 的索引抽样结果。
export function lttb(
  xs: number[],
  ys: number[],
  threshold: number
): { x: number[]; y: number[] } {
  const n = xs.length;
  if (threshold >= n || threshold <= 2) {
    return { x: xs, y: ys };
  }

  const sampledX: number[] = [xs[0]];
  const sampledY: number[] = [ys[0]];

  const bucketSize = (n - 2) / (threshold - 2);
  let a = 0; // 当前桶的起点索引

  for (let i = 0; i < threshold - 2; i++) {
    // 下一个桶的平均点（用于计算面积）
    const avgRangeStart = Math.floor((i + 1) * bucketSize) + 1;
    const avgRangeEnd = Math.min(Math.floor((i + 2) * bucketSize) + 1, n);
    let avgX = 0;
    let avgY = 0;
    const avgRangeLen = avgRangeEnd - avgRangeStart;
    for (let j = avgRangeStart; j < avgRangeEnd; j++) {
      avgX += xs[j];
      avgY += ys[j];
    }
    avgX /= avgRangeLen || 1;
    avgY /= avgRangeLen || 1;

    // 当前桶的范围
    const rangeOffs = Math.floor(i * bucketSize) + 1;
    const rangeTo = Math.floor((i + 1) * bucketSize) + 1;

    const pointAX = xs[a];
    const pointAY = ys[a];

    let maxArea = -1;
    let maxAreaIdx = rangeOffs;
    for (let j = rangeOffs; j < rangeTo; j++) {
      const area =
        Math.abs(
          (pointAX - avgX) * (ys[j] - pointAY) -
            (pointAX - xs[j]) * (avgY - pointAY)
        ) * 0.5;
      if (area > maxArea) {
        maxArea = area;
        maxAreaIdx = j;
      }
    }

    sampledX.push(xs[maxAreaIdx]);
    sampledY.push(ys[maxAreaIdx]);
    a = maxAreaIdx;
  }

  sampledX.push(xs[n - 1]);
  sampledY.push(ys[n - 1]);
  return { x: sampledX, y: sampledY };
}
