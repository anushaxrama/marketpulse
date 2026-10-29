import { test } from "node:test";
import assert from "node:assert/strict";
import { chartPoints, relativeReturn, completeRatio } from "../lib/chart.mjs";
test("flat and empty series have finite drawable bounds", () => {
  assert.equal(chartPoints([]).path, "");
  const chart = chartPoints([100, 100]);
  assert(chart.max > chart.min);
  assert(!chart.path.includes("NaN"));
  assert(!chart.path.includes("Infinity"));
});
test("historical change and completeness preserve their denominators", () => {
  assert.equal(relativeReturn(100, 110)?.toFixed(2), "10.00");
  assert.equal(relativeReturn(0, 10), null);
  assert.equal(completeRatio(4317, 4320)?.toFixed(2), "99.93");
  assert.equal(completeRatio(0, 0), null);
});
