import { NextResponse } from "next/server";
import { prisma } from "../../../../lib/prismaClient";

export async function GET() {
  const entries = await prisma.adminAuditLog.findMany({ orderBy: { createdAt: "desc" } });
  return NextResponse.json(entries);
}
