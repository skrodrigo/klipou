const BACKEND_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_BASE_URL ?? "http://localhost:8000";

let cachedCsrfToken: string | null = null;

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() || null;
  return null;
}

async function fetchCsrfToken(): Promise<string | null> {
  if (cachedCsrfToken) return cachedCsrfToken;

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/csrf-token/`, {
      credentials: "include",
    });

    if (response.ok) {
      const data = await response.json();
      cachedCsrfToken = data.csrfToken;
      return cachedCsrfToken;
    }
  } catch (error) {
    console.error("Failed to fetch CSRF token:", error);
  }

  return null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BACKEND_BASE_URL}${path}`;

  // Tenta obter CSRF token de múltiplas fontes
  let csrfToken = getCookie("csrftoken");

  // Se não encontrou no cookie, tenta buscar do meta tag
  if (!csrfToken && typeof document !== "undefined") {
    const csrfElement = document.querySelector('meta[name="csrf-token"]');
    csrfToken = csrfElement?.getAttribute("content") || null;
  }

  // Se ainda não tem token e é POST/PUT, tenta buscar do endpoint
  if (!csrfToken && (options.method === "POST" || options.method === "PUT")) {
    csrfToken = await fetchCsrfToken();
  }

  const response = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.headers ?? {}),
      ...(!(options.body instanceof FormData) && { "Content-Type": "application/json" }),
      ...(csrfToken && { "X-CSRFToken": csrfToken }),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(`Request to ${url} failed with status ${response.status}: ${JSON.stringify(errorData)}`);
  }

  return (await response.json()) as T;
}

function requestSSE(path: string): EventSource {
  const url = `${BACKEND_BASE_URL}${path}`;
  return new EventSource(url, { withCredentials: true });
}

export { BACKEND_BASE_URL, request, requestSSE };
