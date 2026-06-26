import store from "./state.js";

export async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function get(path) { return api(path); }

export async function post(path, body) {
  return api(path, {
    method: "POST",
    body: JSON.stringify({ idempotency_key: crypto.randomUUID(), ...body }),
  });
}
