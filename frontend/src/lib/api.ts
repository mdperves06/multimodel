export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { loc?: unknown[]; msg?: string };
      const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "";
      return field && field !== "body" ? `${field}: ${first.msg}` : (first.msg ?? fallback);
    }
  }
  return fallback;
}

const AUTH_PATHS = ["/login", "/register", "/"];

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      credentials: "same-origin",
      headers: {
        ...(init.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection.", 0);
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    if (
      res.status === 401 &&
      typeof window !== "undefined" &&
      !path.startsWith("/auth/login") &&
      !AUTH_PATHS.includes(window.location.pathname)
    ) {
      // Full reload on purpose: it discards every cached SWR entry for the dead session.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign(
        `/login?expired=1&next=${encodeURIComponent(window.location.pathname)}`,
      );
    }
    throw new ApiError(messageFrom(body, `Request failed (${res.status})`), res.status);
  }
  return res;
}

export async function apiGet<T>(path: string): Promise<T> {
  return (await send(path)).json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await send(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export async function apiDelete(path: string): Promise<void> {
  await send(path, { method: "DELETE" });
}

export async function apiPostBlob(path: string, body: unknown): Promise<Blob> {
  const res = await send(path, { method: "POST", body: JSON.stringify(body) });
  return res.blob();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
