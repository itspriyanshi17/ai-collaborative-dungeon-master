const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getErrorMessage(payload: unknown): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return String(item);
        })
        .join(" ");
    }
  }
  return "Something went wrong. Please try again.";
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { accessToken?: string | null }
): Promise<T> {
  const { accessToken, headers, ...requestInit } = init ?? {};
  const response = await fetch(`${API_URL}${path}`, {
    ...requestInit,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers
    }
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as unknown;
    throw new ApiError(getErrorMessage(payload), response.status, payload);
  }

  return response.json() as Promise<T>;
}
