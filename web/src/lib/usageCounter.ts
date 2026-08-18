import type { Prisma, PrismaClient, IdentityType } from "@prisma/client";
import { evaluateQuota, type UsageCounterState } from "./quota";

export interface ConsumeResult {
  allowed: boolean;
  used: number;
  limit: number;
}

/**
 * Core logic, assumed to already be running inside a transaction — used
 * directly by callers (like the quota orchestrator) that need this
 * increment to participate in a larger all-or-nothing transaction.
 */
export async function getOrCreateAndIncrementInTx(
  tx: Prisma.TransactionClient,
  identityType: IdentityType,
  identityKey: string,
  metric: "scansUsed" | "pdfsUsed",
  requested: number,
  limit: number,
  now: Date = new Date()
): Promise<ConsumeResult> {
  const rows = await tx.$queryRaw<UsageCounterState[]>`
    SELECT period_start as "periodStart", period_end as "periodEnd",
           scans_used as "scansUsed", pdfs_used as "pdfsUsed"
    FROM usage_counters
    WHERE identity_type = ${identityType}::"IdentityType" AND identity_key = ${identityKey}
    ORDER BY period_end DESC
    LIMIT 1
    FOR UPDATE
  `;
  const existing = rows[0] ?? null;

  const evaluation = evaluateQuota(existing, now, limit, requested, metric);

  if (!evaluation.allowed) {
    return { allowed: false, used: existing?.[metric] ?? 0, limit };
  }

  if (evaluation.needsNewPeriod) {
    await tx.usageCounter.create({
      data: {
        identityType,
        identityKey,
        periodStart: evaluation.periodStart,
        periodEnd: evaluation.periodEnd,
        scansUsed: metric === "scansUsed" ? requested : 0,
        pdfsUsed: metric === "pdfsUsed" ? requested : 0,
      },
    });
    return { allowed: true, used: requested, limit };
  }

  const updated = await tx.usageCounter.update({
    where: {
      identityType_identityKey_periodStart: {
        identityType,
        identityKey,
        periodStart: evaluation.periodStart,
      },
    },
    data: { [metric]: { increment: requested } },
  });

  return { allowed: true, used: updated[metric], limit };
}

/**
 * Public entry point for a standalone increment — opens its own
 * transaction. Callers already inside a transaction (e.g. the quota
 * orchestrator) should use getOrCreateAndIncrementInTx directly instead;
 * Prisma's TransactionClient has no $transaction of its own to nest into.
 */
export async function getOrCreateAndIncrement(
  prisma: PrismaClient,
  identityType: IdentityType,
  identityKey: string,
  metric: "scansUsed" | "pdfsUsed",
  requested: number,
  limit: number,
  now: Date = new Date()
): Promise<ConsumeResult> {
  return prisma.$transaction((tx) =>
    getOrCreateAndIncrementInTx(tx, identityType, identityKey, metric, requested, limit, now)
  );
}
