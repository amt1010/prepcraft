import type { PrismaClient } from "@prisma/client";
import { resolveIdentity, type Identity } from "./identity";
import { resolveTier } from "./tier";
import { getOrCreateAndIncrementInTx } from "./usageCounter";
import { recordAuditLog } from "./auditLog";

export interface QuotaCheckInput {
  clerkUserId: string | null;
  ipAddress: string;
  ipSalt: string;
  scanCount: number;
}

export type QuotaCheckResult =
  | { allowed: true; identity: Identity }
  | { allowed: false; reason: "scans" | "pdfs"; tier: string; limit: number; used: number };

class QuotaRollback extends Error {
  constructor(public result: Extract<QuotaCheckResult, { allowed: false }>) {
    super("quota check failed — transaction rolled back");
  }
}

export async function checkAndConsumeQuota(
  prisma: PrismaClient,
  input: QuotaCheckInput
): Promise<QuotaCheckResult> {
  const identity = resolveIdentity(input.clerkUserId, input.ipAddress, input.ipSalt);
  const { tierId, isBypass } = await resolveTier(identity, prisma);
  const tier = await prisma.tier.findUniqueOrThrow({ where: { id: tierId } });

  // Runs the quota check in its own transaction so a rejection rolls back
  // BOTH counters (all-or-nothing). The audit-log write below deliberately
  // happens outside this transaction, using the top-level `prisma` client
  // (not `tx`) — a bypass account's usage must stay traceable even when
  // the quota check itself is rejected and rolled back.
  const result = await prisma
    .$transaction(async (tx) => {
      const scanResult = await getOrCreateAndIncrementInTx(
        tx,
        identity.type,
        identity.key,
        "scansUsed",
        input.scanCount,
        tier.scansPerPeriod
      );
      if (!scanResult.allowed) {
        throw new QuotaRollback({
          allowed: false,
          reason: "scans",
          tier: tierId,
          limit: scanResult.limit,
          used: scanResult.used,
        });
      }

      const pdfResult = await getOrCreateAndIncrementInTx(
        tx,
        identity.type,
        identity.key,
        "pdfsUsed",
        1,
        tier.pdfsPerPeriod
      );
      if (!pdfResult.allowed) {
        throw new QuotaRollback({
          allowed: false,
          reason: "pdfs",
          tier: tierId,
          limit: pdfResult.limit,
          used: pdfResult.used,
        });
      }

      return { allowed: true, identity } as const;
    })
    .catch((err) => {
      if (err instanceof QuotaRollback) return err.result;
      throw err;
    });

  if (isBypass) {
    await recordAuditLog(prisma, {
      adminUserId: identity.key,
      action: "test_bypass.quota_check",
      target: identity.key,
      newValue: result.allowed ? "allowed" : `rejected:${result.reason}`,
    });
  }

  return result;
}
