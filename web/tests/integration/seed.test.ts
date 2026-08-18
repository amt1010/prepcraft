import { PrismaClient } from "@prisma/client";
import { seedTiers } from "../../prisma/seed";

const prisma = new PrismaClient({
  datasources: { db: { url: process.env.DATABASE_URL_TEST } },
});

beforeEach(async () => {
  await prisma.tier.deleteMany();
});

afterAll(async () => {
  await prisma.$disconnect();
});

test("seedTiers creates all four tiers with scans=2 and pdfs=2", async () => {
  await seedTiers(prisma);

  const tiers = await prisma.tier.findMany({ orderBy: { id: "asc" } });

  expect(tiers).toHaveLength(4);
  for (const tier of tiers) {
    expect(tier.scansPerPeriod).toBe(2);
    expect(tier.pdfsPerPeriod).toBe(2);
  }
});

test("seedTiers is idempotent and never overwrites an admin's edited values", async () => {
  await seedTiers(prisma);
  await prisma.tier.update({ where: { id: "guest" }, data: { scansPerPeriod: 5 } });

  await seedTiers(prisma);

  const guest = await prisma.tier.findUniqueOrThrow({ where: { id: "guest" } });
  expect(guest.scansPerPeriod).toBe(5);
  expect(await prisma.tier.count()).toBe(4);
});
