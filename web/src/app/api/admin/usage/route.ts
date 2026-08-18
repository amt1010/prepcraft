import { NextResponse } from "next/server";
import { prisma } from "../../../../lib/prismaClient";

export async function GET(req: Request) {
  const email = new URL(req.url).searchParams.get("email");
  const user = email ? await prisma.user.findUnique({ where: { email } }) : null;

  if (!user) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const counter = await prisma.usageCounter.findFirst({
    where: { identityType: "user", identityKey: user.id },
    orderBy: { periodEnd: "desc" },
  });

  return NextResponse.json({
    email: user.email,
    scansUsed: counter?.scansUsed ?? 0,
    pdfsUsed: counter?.pdfsUsed ?? 0,
    periodStart: counter?.periodStart ?? null,
    periodEnd: counter?.periodEnd ?? null,
  });
}
