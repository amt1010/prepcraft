import { PrismaClient } from "@prisma/client";
import { getOrCreateAndIncrement } from "../../src/lib/usageCounter";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
});
afterAll(() => prisma.$disconnect());

test("increments scansUsed and allows a request within the limit", async () => {
  const result = await getOrCreateAndIncrement(prisma, "user", "user_1", "scansUsed", 1, 2);
  expect(result).toEqual({ allowed: true, used: 1, limit: 2 });
});

test("rejects a request that would exceed the limit", async () => {
  await getOrCreateAndIncrement(prisma, "user", "user_2", "scansUsed", 2, 2);
  const result = await getOrCreateAndIncrement(prisma, "user", "user_2", "scansUsed", 1, 2);
  expect(result.allowed).toBe(false);
});

test("two concurrent increments against a counter with 1 unit of headroom: exactly one succeeds", async () => {
  await getOrCreateAndIncrement(prisma, "user", "user_3", "scansUsed", 1, 2); // 1 used, 1 remaining

  const [a, b] = await Promise.all([
    getOrCreateAndIncrement(prisma, "user", "user_3", "scansUsed", 1, 2),
    getOrCreateAndIncrement(prisma, "user", "user_3", "scansUsed", 1, 2),
  ]);

  const allowedCount = [a, b].filter((r) => r.allowed).length;
  expect(allowedCount).toBe(1);
});
