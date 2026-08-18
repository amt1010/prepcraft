import { evaluateQuota } from "../../src/lib/quota";

const now = new Date("2026-08-18T00:00:00Z");

test("no existing counter starts a fresh 30-day period and allows a request within the limit", () => {
  const result = evaluateQuota(null, now, 2, 1, "scansUsed");
  expect(result.allowed).toBe(true);
  expect(result.needsNewPeriod).toBe(true);
  expect(result.periodStart).toEqual(now);
  expect(result.periodEnd).toEqual(new Date("2026-09-17T00:00:00Z"));
});

test("a request that would exceed the limit within an active period is rejected", () => {
  const counter = {
    periodStart: new Date("2026-08-01T00:00:00Z"),
    periodEnd: new Date("2026-08-31T00:00:00Z"),
    scansUsed: 2,
    pdfsUsed: 0,
  };
  const result = evaluateQuota(counter, now, 2, 1, "scansUsed");
  expect(result.allowed).toBe(false);
  expect(result.needsNewPeriod).toBe(false);
});

test("a request exactly at the remaining headroom is allowed", () => {
  const counter = {
    periodStart: new Date("2026-08-01T00:00:00Z"),
    periodEnd: new Date("2026-08-31T00:00:00Z"),
    scansUsed: 1,
    pdfsUsed: 0,
  };
  const result = evaluateQuota(counter, now, 2, 1, "scansUsed");
  expect(result.allowed).toBe(true);
});

test("a counter whose period already ended resets to a fresh period regardless of prior usage", () => {
  const counter = {
    periodStart: new Date("2026-06-01T00:00:00Z"),
    periodEnd: new Date("2026-07-01T00:00:00Z"),
    scansUsed: 2,
    pdfsUsed: 0,
  };
  const result = evaluateQuota(counter, now, 2, 2, "scansUsed");
  expect(result.allowed).toBe(true);
  expect(result.needsNewPeriod).toBe(true);
});

test("a multi-unit request (e.g. a multi-page scan) is checked against the full requested amount", () => {
  const result = evaluateQuota(null, now, 2, 3, "scansUsed");
  expect(result.allowed).toBe(false);
});
