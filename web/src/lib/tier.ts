import type { PrismaClient, TierId } from "@prisma/client";
import type { Identity } from "./identity";

export const TEST_BYPASS_TIER: TierId = "subscribed_annual";

export interface TierResolution {
  tierId: TierId;
  isBypass: boolean;
}

export async function resolveTier(identity: Identity, prisma: PrismaClient): Promise<TierResolution> {
  if (identity.type === "guest_ip") {
    return { tierId: "guest", isBypass: false };
  }

  const user = await prisma.user.findUnique({ where: { id: identity.key } });
  if (user?.isTestBypassAccount) {
    return { tierId: TEST_BYPASS_TIER, isBypass: true };
  }

  const activeSubscription = await prisma.subscription.findFirst({
    where: { userId: identity.key, status: "active" },
    orderBy: { currentPeriodEnd: "desc" },
  });

  return { tierId: activeSubscription?.tierId ?? "registered_free", isBypass: false };
}
