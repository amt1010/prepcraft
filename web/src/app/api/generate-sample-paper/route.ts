import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { prisma } from "../../../lib/prismaClient";
import { checkAndConsumeQuota } from "../../../lib/quotaOrchestrator";
import { callPipelineService } from "../../../lib/pipelineClient";

export async function POST(req: Request) {
  const { userId } = await auth();
  const body = await req.json();
  const imageUrls: string[] = body.imageUrls;
  const ip = req.headers.get("x-forwarded-for") ?? "0.0.0.0";

  const quota = await checkAndConsumeQuota(prisma, {
    clerkUserId: userId,
    ipAddress: ip,
    ipSalt: process.env.GUEST_IP_SALT!,
    scanCount: imageUrls.length,
  });

  if (!quota.allowed) {
    return NextResponse.json(
      { reason: quota.reason, tier: quota.tier, limit: quota.limit, used: quota.used },
      { status: 402 }
    );
  }

  const result = await callPipelineService(
    imageUrls,
    process.env.PIPELINE_SERVICE_URL!,
    process.env.PIPELINE_SERVICE_TOKEN!
  );

  return NextResponse.json(result, { status: 200 });
}
