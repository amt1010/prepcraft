export interface PipelineResult {
  questionPaperUrl: string;
  answerSheetUrl: string;
}

export async function callPipelineService(
  imageUrls: string[],
  serviceUrl: string,
  serviceToken: string,
  fetchImpl: typeof fetch = fetch
): Promise<PipelineResult> {
  const res = await fetchImpl(`${serviceUrl}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${serviceToken}`,
    },
    body: JSON.stringify({ image_urls: imageUrls }),
  });

  if (!res.ok) {
    throw new Error(`pipeline service returned ${res.status}`);
  }

  return res.json();
}
