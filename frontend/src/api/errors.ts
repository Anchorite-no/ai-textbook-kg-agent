/** 错误归一化。后端按 plan 17 §7 返回 { message, code, detail }，
 * 这里转成前端统一的 ApiError 类。所有 fetch 出口必须经过本层。 */

export interface ApiErrorShape {
  message: string;
  code: string;
  detail?: string;
  status: number;
}

export class ApiError extends Error implements ApiErrorShape {
  readonly code: string;
  readonly detail?: string;
  readonly status: number;

  constructor(shape: ApiErrorShape) {
    super(shape.message);
    this.name = "ApiError";
    this.code = shape.code;
    this.detail = shape.detail;
    this.status = shape.status;
  }
}

export async function normalizeErrorResponse(response: Response): Promise<ApiError> {
  const status = response.status;
  let message = `请求失败 (${status})`;
  let code = `HTTP_${status}`;
  let detail: string | undefined;

  try {
    const json = (await response.json()) as Record<string, unknown>;
    if (typeof json.message === "string") message = json.message;
    else if (typeof json.detail === "string") message = json.detail;
    if (typeof json.code === "string") code = json.code;
    if (typeof json.detail === "string") detail = json.detail;
  } catch {
    // 后端返回非 JSON，保留默认 message
  }

  return new ApiError({ message, code, detail, status });
}

/** 把任何抛出的错误标准化成 ApiError，方便上层统一处理。 */
export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof Error) {
    return new ApiError({
      message: err.message || "未知错误",
      code: "CLIENT_ERROR",
      status: 0
    });
  }
  return new ApiError({ message: "未知错误", code: "UNKNOWN", status: 0 });
}
