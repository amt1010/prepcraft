import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { prisma } from "../../../../../lib/prismaClient";
import { recordAuditLog } from "../../../../../lib/auditLog";

const EDITABLE_FIELDS = [
  "scansPerPeriod",
  "pdfsPerPeriod",
  "priceAmount",
  "currency",
  "billingInterval",
  "isActive",
] as const;

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const { userId } = auth();
  const before = await prisma.tier.findUniqueOrThrow({ where: { id: params.id as any } });
  const patch = await req.json();

  const data: Record<string, unknown> = {};
  for (const field of EDITABLE_FIELDS) {
    if (field in patch) data[field] = patch[field];
  }

  const after = await prisma.tier.update({
    where: { id: params.id as any },
    data: { ...data, updatedBy: userId },
  });

  for (const field of EDITABLE_FIELDS) {
    if (field in patch && String((before as any)[field]) !== String((after as any)[field])) {
      await recordAuditLog(prisma, {
        adminUserId: userId!,
        action: "tier.update",
        target: `${params.id}.${field}`,
        oldValue: String((before as any)[field]),
        newValue: String((after as any)[field]),
      });
    }
  }

  return NextResponse.json(after);
}
