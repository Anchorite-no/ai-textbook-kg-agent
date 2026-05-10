import type { JobRecord, JobRetryResponse } from "@/types/api";
import { request } from "./client";

export async function getJob(jobId: string): Promise<JobRecord> {
  return request<JobRecord>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export async function retryJob(jobId: string): Promise<JobRetryResponse> {
  return request<JobRetryResponse>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST"
  });
}

export async function waitForJob(jobId: string, timeoutMs = 180_000): Promise<JobRecord> {
  const startedAt = Date.now();
  let delay = 800;
  while (Date.now() - startedAt < timeoutMs) {
    const job = await getJob(jobId);
    if (job.status === "completed" || job.status === "failed") return job;
    await new Promise((resolve) => setTimeout(resolve, delay));
    delay = Math.min(2_500, delay + 300);
  }
  throw new Error(`任务超时：${jobId}`);
}

export const jobsApi = {
  getJob,
  retryJob,
  waitForJob
};
