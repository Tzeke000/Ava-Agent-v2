const API_BASE = import.meta.env.VITE_OPERATOR_API || "http://127.0.0.1:5876";

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export async function getText(path: string): Promise<string> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.text();
}

export { API_BASE };
