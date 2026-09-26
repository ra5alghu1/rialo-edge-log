import assert from "node:assert/strict";
import test from "node:test";
await import("../portal/csv.js");
const csv = globalThis.RialoCsv.serializeBatch;

test("exports negative temperatures, zero, false and missing schema-3 fields", () => {
  const batch = { batch_id: "batch", readings: [{ schema_version: 2,
    device_id: "edge", sequence: 0, uptime_ms: 0,
    temperature_milli_c: -1250, temperature_c: -1.25, simulated: false }] };
  const before = JSON.stringify(batch);
  const result = csv(batch);
  assert.ok(result.startsWith('\uFEFF"batch_id","schema_version"'));
  assert.ok(result.includes('"batch","2","edge","0","0","-1250","-1.25","false","","","",""\r\n'));
  assert.equal(JSON.stringify(batch), before);
});

test("escapes separators and formulas without dropping schema-3 data", () => {
  const result = csv({batch_id: '=SUM(1,2)', readings: [{
    device_id: 'sensor,"one"\nnext', boot_id: 123,
    reset_reason: ' @SUM(1)', tamper_open: true, received_at_utc: "2026-09-26T00:00:00Z",
  }]});
  assert.ok(result.includes('"\'=SUM(1,2)"'));
  assert.ok(result.includes('"sensor,""one""\nnext"'));
  assert.ok(result.includes('"123","\' @SUM(1)","true","2026-09-26T00:00:00Z"'));
});

test("empty batch exports headers only", () => {
  assert.equal(csv({batch_id: "empty", readings: []}).split("\r\n").length, 2);
});
