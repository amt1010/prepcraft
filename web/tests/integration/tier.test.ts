import { PrismaClient } from "@prisma/client";
import { resolveTier, TEST_BYPASS_TIER } from "../../src/lib/tier";
import { seedTiers } from "../../prisma/seed";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.subscription.deleteMany();
  await prisma.user.deleteMany();
  await seedTiers(prisma); // Subscription.tierId is a real FK to Tier
});
afterAll(() => prisma.$disconnect());

test("guest_ip identity always resolves to the guest tier", async () => {
  const result = await resolveTier({ type: "guest_ip", key: "hash123" }, prisma);
  expect(result).toEqual({ tierId: "guest", isBypass: false });
});

test("a registered user with no subscription resolves to registered_free", async () => {
  await prisma.user.create({ data: { id: "user_1", email: "a@example.com" } });
  const result = await resolveTier({ type: "user", key: "user_1" }, prisma);
  expect(result).toEqual({ tierId: "registered_free", isBypass: false });
});

test("a user with an active subscription resolves to that subscription's tier", async () => {
  await prisma.user.create({ data: { id: "user_2", email: "b@example.com" } });
  await prisma.subscription.create({
    data: {
      userId: "user_2",
      tierId: "subscribed_monthly",
      status: "active",
      startedAt: new Date(),
      currentPeriodEnd: new Date(Date.now() + 86_400_000),
    },
  });
  const result = await resolveTier({ type: "user", key: "user_2" }, prisma);
  expect(result).toEqual({ tierId: "subscribed_monthly", isBypass: false });
});

test("a test-bypass account resolves to the bypass tier and flags isBypass, without needing a Subscription row", async () => {
  await prisma.user.create({
    data: { id: "user_3", email: "bypass@example.com", isTestBypassAccount: true },
  });
  const result = await resolveTier({ type: "user", key: "user_3" }, prisma);
  expect(result).toEqual({ tierId: TEST_BYPASS_TIER, isBypass: true });
});
