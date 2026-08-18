import { PrismaClient } from "@prisma/client";
import { seedTiers } from "../../prisma/seed";

vi.mock("@clerk/nextjs/server", () => ({
  auth: () => ({ userId: "admin_1" }),
}));

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.user.create({ data: { id: "admin_1", email: "admin@example.com", role: "admin" } });
  await seedTiers(prisma);
});
afterAll(() => prisma.$disconnect());

test("GET lists all four seeded tiers", async () => {
  const { GET } = await import("../../src/app/api/admin/tiers/route");
  const res = await GET();
  const body = await res.json();
  expect(body).toHaveLength(4);
});

test("PATCH updates scansPerPeriod and writes one audit log entry for the changed field", async () => {
  const { PATCH } = await import("../../src/app/api/admin/tiers/[id]/route");
  const req = new Request("https://app.test/api/admin/tiers/guest", {
    method: "PATCH",
    body: JSON.stringify({ scansPerPeriod: 5 }),
  });

  const res = await PATCH(req as any, { params: { id: "guest" } });
  const body = await res.json();

  expect(body.scansPerPeriod).toBe(5);

  const logs = await prisma.adminAuditLog.findMany();
  expect(logs).toHaveLength(1);
  expect(logs[0]).toMatchObject({
    action: "tier.update",
    target: "guest.scansPerPeriod",
    oldValue: "2",
    newValue: "5",
  });
});
