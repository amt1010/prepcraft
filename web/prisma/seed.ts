import { PrismaClient, type TierId } from "@prisma/client";

const prisma = new PrismaClient();

const DEFAULT_TIERS: Array<{ id: TierId; name: string }> = [
  { id: "guest", name: "Guest" },
  { id: "registered_free", name: "Registered (Free)" },
  { id: "subscribed_monthly", name: "Subscribed (Monthly)" },
  { id: "subscribed_annual", name: "Subscribed (Annual)" },
];

export async function seedTiers(client: PrismaClient = prisma): Promise<void> {
  for (const tier of DEFAULT_TIERS) {
    await client.tier.upsert({
      where: { id: tier.id },
      update: {},
      create: {
        id: tier.id,
        name: tier.name,
        scansPerPeriod: 2,
        pdfsPerPeriod: 2,
      },
    });
  }
}

if (require.main === module) {
  seedTiers().finally(() => prisma.$disconnect());
}
