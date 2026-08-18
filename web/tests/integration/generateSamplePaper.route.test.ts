import { PrismaClient } from "@prisma/client";
import { seedTiers } from "../../prisma/seed";

vi.mock("@clerk/nextjs/server", () => ({
  auth: () => ({ userId: null }),
}));

vi.mock("../../src/lib/pipelineClient", () => ({
  callPipelineService: vi.fn().mockResolvedValue({
    questionPaperUrl: "https://x/qp.pdf",
    answerSheetUrl: "https://x/as.pdf",
  }),
}));

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
  await prisma.tier.deleteMany();
  await seedTiers(prisma);
  vi.stubEnv("GUEST_IP_SALT", "salt");
  vi.stubEnv("PIPELINE_SERVICE_URL", "https://pipeline.internal");
  vi.stubEnv("PIPELINE_SERVICE_TOKEN", "token");
});
afterAll(() => prisma.$disconnect());

test("a guest within quota gets both PDF URLs back", async () => {
  const { POST } = await import("../../src/app/api/generate-sample-paper/route");
  const req = new Request("https://app.test/api/generate-sample-paper", {
    method: "POST",
    headers: { "x-forwarded-for": "203.0.113.5" },
    body: JSON.stringify({ imageUrls: ["https://x/img1.jpg"] }),
  });

  const res = await POST(req as any);
  const body = await res.json();

  expect(res.status).toBe(200);
  expect(body).toEqual({ questionPaperUrl: "https://x/qp.pdf", answerSheetUrl: "https://x/as.pdf" });
});

test("a guest over quota gets a 402 with the reason, never calling the pipeline", async () => {
  const { POST } = await import("../../src/app/api/generate-sample-paper/route");
  const { callPipelineService } = await import("../../src/lib/pipelineClient");

  const makeReq = () =>
    new Request("https://app.test/api/generate-sample-paper", {
      method: "POST",
      headers: { "x-forwarded-for": "203.0.113.9" },
      body: JSON.stringify({ imageUrls: ["https://x/img1.jpg", "https://x/img2.jpg", "https://x/img3.jpg"] }),
    });

  const res = await POST(makeReq() as any); // 3 images exceeds guest's 2-scan limit
  const body = await res.json();

  expect(res.status).toBe(402);
  expect(body).toMatchObject({ reason: "scans", tier: "guest" });
  expect(callPipelineService).not.toHaveBeenCalled();
});
