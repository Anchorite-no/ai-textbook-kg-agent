import type {
  SampleDatasetPrepareRequest,
  SampleDatasetPrepareResponse,
  SampleDatasetResponse
} from "@/types/api";
import { request } from "./client";

export async function getSevenBooksDataset(): Promise<SampleDatasetResponse> {
  return request<SampleDatasetResponse>("/api/datasets/seven-books");
}

export async function prepareSevenBooks(
  body: Partial<SampleDatasetPrepareRequest> = {}
): Promise<SampleDatasetPrepareResponse> {
  return request<SampleDatasetPrepareResponse>("/api/datasets/seven-books/prepare", {
    method: "POST",
    body
  });
}

export const datasetsApi = {
  getSevenBooksDataset,
  prepareSevenBooks
};
