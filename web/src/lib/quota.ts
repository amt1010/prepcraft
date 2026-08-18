export interface UsageCounterState {
  periodStart: Date;
  periodEnd: Date;
  scansUsed: number;
  pdfsUsed: number;
}

export interface QuotaEvaluation {
  allowed: boolean;
  needsNewPeriod: boolean;
  periodStart: Date;
  periodEnd: Date;
}

const PERIOD_LENGTH_MS = 30 * 24 * 60 * 60 * 1000;

export function evaluateQuota(
  counter: UsageCounterState | null,
  now: Date,
  limit: number,
  requested: number,
  metric: "scansUsed" | "pdfsUsed"
): QuotaEvaluation {
  const needsNewPeriod = counter === null || now.getTime() >= counter.periodEnd.getTime();

  const periodStart = needsNewPeriod ? now : counter!.periodStart;
  const periodEnd = needsNewPeriod
    ? new Date(now.getTime() + PERIOD_LENGTH_MS)
    : counter!.periodEnd;
  const used = needsNewPeriod ? 0 : counter![metric];

  return {
    allowed: used + requested <= limit,
    needsNewPeriod,
    periodStart,
    periodEnd,
  };
}
