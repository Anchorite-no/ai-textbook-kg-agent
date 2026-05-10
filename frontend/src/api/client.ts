/** 共享 fetch 封装。所有 adapter 通过本文件出请求；
 *  错误统一走 normalizeErrorResponse → ApiError；
 *  base URL 走 vite proxy（/api → 8010）或环境变量。 */

import { ApiError, normalizeErrorResponse, toApiError } from "./errors";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | Record<string, unknown> | null;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  let url = `${API_BASE}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue;
      params.append(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }
  return url;
}

function prepareBody(body: RequestOptions["body"], headers: Headers): BodyInit | null | undefined {
  if (body === undefined || body === null) return undefined;
  if (body instanceof FormData) return body;
  if (body instanceof Blob || body instanceof ArrayBuffer || typeof body === "string") return body;
  if (body instanceof URLSearchParams) {
    headers.set("Content-Type", "application/x-www-form-urlencoded");
    return body;
  }
  if (typeof body === "object") {
    headers.set("Content-Type", "application/json");
    return JSON.stringify(body);
  }
  return undefined;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, query, headers: rawHeaders, ...rest } = options;
  const headers = new Headers(rawHeaders);
  const preparedBody = prepareBody(body, headers);

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      ...rest,
      headers,
      body: preparedBody
    });
  } catch (err) {
    throw toApiError(err);
  }

  if (!response.ok) throw await normalizeErrorResponse(response);
  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  // 非 JSON 调用方自行处理
  return (await response.text()) as unknown as T;
}

export async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const { body, query, headers: rawHeaders, ...rest } = options;
  const headers = new Headers(rawHeaders);
  const preparedBody = prepareBody(body, headers);
  const response = await fetch(buildUrl(path, query), {
    ...rest,
    headers,
    body: preparedBody
  });
  if (!response.ok) throw await normalizeErrorResponse(response);
  return response.blob();
}

export { ApiError };
