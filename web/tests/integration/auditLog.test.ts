import { PrismaClient } from "@prisma/client";
import { recordAuditLog } from "../../src/lib/auditLog";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.adminAuditLog.deleteMany();
  await prisma.user.deleteMany();
  await prisma.user.create({ data: { id: "admin_1", email: "admin@example.com", role: "admin" } });
});
afterAll(() => prisma.$disconnect());

test("writes an audit log row with the given fields", async () => {
  await recordAuditLog(prisma, {
    adminUserId: "admin_1",
    action: "tier.update",
    target: "subscribed_monthly.scans_per_period",
    oldValue: "2",
    newValue: "30",
  });

  const rows = await prisma.adminAuditLog.findMany();
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({
    adminUserId: "admin_1",
    action: "tier.update",
    target: "subscribed_monthly.scans_per_period",
    oldValue: "2",
    newValue: "30",
  });
});
