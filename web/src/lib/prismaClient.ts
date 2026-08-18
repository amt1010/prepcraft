import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

// Vitest sets process.env.VITEST automatically — route to DATABASE_URL_TEST
// under test so route-handler code under test hits the same database its
// test seeded, instead of the dev database.
const databaseUrl = process.env.VITEST ? process.env.DATABASE_URL_TEST : process.env.DATABASE_URL;

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient(databaseUrl ? { datasources: { db: { url: databaseUrl } } } : undefined);

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
