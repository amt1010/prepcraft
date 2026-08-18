import type { PrismaClient } from "@prisma/client";

export interface AuditLogEntry {
  adminUserId: string;
  action: string;
  target: string;
  oldValue?: string;
  newValue?: string;
}

export async function recordAuditLog(prisma: PrismaClient, entry: AuditLogEntry): Promise<void> {
  await prisma.adminAuditLog.create({
    data: {
      adminUserId: entry.adminUserId,
      action: entry.action,
      target: entry.target,
      oldValue: entry.oldValue ?? null,
      newValue: entry.newValue ?? null,
    },
  });
}
