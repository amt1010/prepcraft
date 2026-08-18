import { PrismaClient } from "@prisma/client";

// Global safety net: every integration test file constructs its own
// PrismaClient and does its own beforeEach cleanup, but each only clears
// the tables IT touches. A row left behind by one file (e.g. a bypass
// user + its audit log row from quotaOrchestrator.test.ts) can then
// violate a foreign key constraint in a completely different file's
// cleanup. Wiping every shared table before every test, in FK-safe
// order, closes that regardless of which files run before which.
const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.adminAuditLog.deleteMany();
  await prisma.usageCounter.deleteMany();
  await prisma.subscription.deleteMany();
  await prisma.user.deleteMany();
  await prisma.tier.deleteMany();
});

afterAll(async () => {
  await prisma.$disconnect();
});
