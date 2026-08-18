import { PrismaClient } from "@prisma/client";
import { checkAndConsumeQuota } from "../../src/lib/quotaOrchestrator";
import { seedTiers } from "../../prisma/seed";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
  await prisma.adminAuditLog.deleteMany(); // must clear before user.deleteMany() (FK)
  await prisma.subscription.deleteMany();
  await prisma.user.deleteMany();
  await prisma.tier.deleteMany();
  await seedTiers(prisma);
});
afterAll(() => prisma.$disconnect());

test("a guest within both limits is allowed", async () => {
  const result = await checkAndConsumeQuota(prisma, {
    clerkUserId: null,
    ipAddress: "203.0.113.5",
    ipSalt: "salt",
    scanCount: 1,
  });
  expect(result.allowed).toBe(true);
});

test("a guest who already used both scan units for the period is rejected on the scan check", async () => {
  const input = { clerkUserId: null, ipAddress: "203.0.113.9", ipSalt: "salt", scanCount: 2 };
  await checkAndConsumeQuota(prisma, input); // consumes guest's 2/2 scans and pdfs

  const result = await checkAndConsumeQuota(prisma, { ...input, scanCount: 1 });
  expect(result).toMatchObject({ allowed: false, reason: "scans" });
});

test("rejecting on the scan check never touches the pdf counter (all-or-nothing)", async () => {
  const input = { clerkUserId: null, ipAddress: "203.0.113.30", ipSalt: "salt", scanCount: 3 }; // exceeds guest's 2-scan limit immediately

  const result = await checkAndConsumeQuota(prisma, input);

  expect(result).toMatchObject({ allowed: false, reason: "scans" });
  const counter = await prisma.usageCounter.findFirst({ where: { identityType: "guest_ip" } });
  expect(counter).toBeNull(); // transaction rolled back — no counter row was ever committed
});

test("a test-bypass account's quota check writes an AdminAuditLog row, regardless of outcome", async () => {
  await prisma.user.create({
    data: { id: "bypass_user", email: "bypass@example.com", isTestBypassAccount: true },
  });

  await checkAndConsumeQuota(prisma, {
    clerkUserId: "bypass_user",
    ipAddress: "203.0.113.50",
    ipSalt: "salt",
    scanCount: 1,
  });

  const logs = await prisma.adminAuditLog.findMany({ where: { adminUserId: "bypass_user" } });
  expect(logs).toHaveLength(1);
  expect(logs[0].action).toBe("test_bypass.quota_check");
});
