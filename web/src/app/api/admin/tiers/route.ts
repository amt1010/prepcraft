import { NextResponse } from "next/server";
import { prisma } from "../../../../lib/prismaClient";

export async function GET() {
  const tiers = await prisma.tier.findMany({ orderBy: { id: "asc" } });
  return NextResponse.json(tiers);
}
