export function chartPoints(values, width = 900, height = 260, pad = 20) {
  if (!values.length) return { path: "", min: 0, max: 1 };
  let min = Math.min(...values),
    max = Math.max(...values);
  const spread = Math.max((max - min) * 0.15, Math.abs(max) * 0.0001, 0.00001);
  min -= spread;
  max += spread;
  return {
    path: values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${pad + (i / Math.max(values.length - 1, 1)) * (width - 2 * pad)},${pad + ((max - v) / (max - min)) * (height - 2 * pad)}`,
      )
      .join(" "),
    min,
    max,
  };
}
export function relativeReturn(first, last) {
  return first > 0 ? (last / first - 1) * 100 : null;
}
export function completeRatio(accepted, expected) {
  return expected > 0 ? (accepted / expected) * 100 : null;
}
