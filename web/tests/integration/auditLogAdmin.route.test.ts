import { PrismaClient } from "@prisma/client";
import { recordAuditLog } from "../../src/lib/auditLog";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.user.create({ data: { id: "admin_1", email: "admin@example.com", role: "admin" } });
  await recordAuditLog(prisma, { adminUserId: "admin_1", action: "tier.update", target: "guest.scansPerPeriod", oldValue: "2", newValue: "5" });
  await recordAuditLog(prisma, { adminUserId: "admin_1", action: "tier.update", target: "guest.pdfsPerPeriod", oldValue: "2", newValue: "5" });
});
afterAll(() => prisma.$disconnect());

test("returns audit log entries newest first", async () => {
  const { GET } = await import("../../src/app/api/admin/audit-log/route");
  const res = await GET();
  const body = await res.json();

  expect(body).toHaveLength(2);
  expect(body[0].target).toBe("guest.pdfsPerPeriod");
  expect(body[1].target).toBe("guest.scansPerPeriod");
});
