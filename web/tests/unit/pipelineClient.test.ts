import { callPipelineService } from "../../src/lib/pipelineClient";

test("posts image URLs to the pipeline service with the bearer token and returns the result", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ questionPaperUrl: "https://x/qp.pdf", answerSheetUrl: "https://x/as.pdf" }),
  });

  const result = await callPipelineService(
    ["https://x/img1.jpg"],
    "https://pipeline.internal",
    "secret-token",
    fetchMock as unknown as typeof fetch
  );

  expect(result).toEqual({ questionPaperUrl: "https://x/qp.pdf", answerSheetUrl: "https://x/as.pdf" });
  expect(fetchMock).toHaveBeenCalledWith(
    "https://pipeline.internal/generate",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer secret-token" }),
    })
  );
});

test("throws when the pipeline service responds with a non-OK status", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 });
  await expect(
    callPipelineService(["x"], "https://pipeline.internal", "t", fetchMock as unknown as typeof fetch)
  ).rejects.toThrow("500");
});
