import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.user.create({ data: { id: "user_1", email: "learner@example.com" } });
  await prisma.usageCounter.create({
    data: {
      identityType: "user",
      identityKey: "user_1",
      periodStart: new Date("2026-08-01T00:00:00Z"),
      periodEnd: new Date("2026-08-31T00:00:00Z"),
      scansUsed: 1,
      pdfsUsed: 0,
    },
  });
});
afterAll(() => prisma.$disconnect());

test("returns the matching user's usage counter by email", async () => {
  const { GET } = await import("../../src/app/api/admin/usage/route");
  const req = new Request("https://app.test/api/admin/usage?email=learner@example.com");

  const res = await GET(req as any);
  const body = await res.json();

  expect(res.status).toBe(200);
  expect(body).toMatchObject({ email: "learner@example.com", scansUsed: 1, pdfsUsed: 0 });
});

test("returns 404 when no user matches", async () => {
  const { GET } = await import("../../src/app/api/admin/usage/route");
  const req = new Request("https://app.test/api/admin/usage?email=nobody@example.com");

  const res = await GET(req as any);
  expect(res.status).toBe(404);
});
