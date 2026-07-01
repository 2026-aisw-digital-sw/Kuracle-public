export async function apiFetch<T = unknown>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => String(res.status));
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json() as Promise<T>;
}

export interface JobPollResult {
  final: { response: string; delivery?: unknown } | null;
  worker_results: WorkerResult[];
}

export interface WorkerResult {
  node_id: string;
  handler_result: KnowledgeHandlerResult;
}

export interface CitedArticle {
  node_id: string;
  label: string;
  regulation_name: string;
  content_preview: string;
}

export interface CitedContentSource {
  title: string;
  url: string | null;
  category: string | null;
  issuing_office: string | null;
}

export interface KnowledgeHandlerResult {
  answer: string;
  confidence: number;
  requires_human_review: boolean;
  risk_class: string;
  cited_rule_ids: string[];
  cited_articles: CitedArticle[];
  cited_content_sources: CitedContentSource[];
  profile_gaps: string[];
  regulation_gaps: string[];
  regulation_rag_trace_id: string | null;
}

export async function pollJob(
  jobId: string,
  { interval = 1500, maxAttempts = 80 }: { interval?: number; maxAttempts?: number } = {},
): Promise<JobPollResult> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise<void>((r) => setTimeout(r, interval));
    const job = await apiFetch<{
      status: string;
      result?: JobPollResult;
      error?: string;
    }>(`/api/jobs/${encodeURIComponent(jobId)}`);
    if (job.status === "COMPLETED") return job.result as JobPollResult;
    if (job.status === "FAILED" || job.status === "CANCELLED") {
      throw new Error(job.error ?? `Job ${jobId} ${job.status}`);
    }
  }
  throw new Error(`Job ${jobId} timed out`);
}
