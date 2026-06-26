const CSRF_METHODS = new Set(["POST"]);

export async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, {
    headers: { "Accept": "application/json" },
  });
  if (!res.ok) {
    const body = await safeJson(res);
    throw new ApiError(res.status, body?.detail || body?.message || res.statusText, body);
  }
  return res.json();
}

export async function apiPostCommand(type, payload = {}, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Idempotency-Key": options.idempotencyKey || crypto.randomUUID(),
  };
  if (options.expectedVersion !== undefined) {
    headers["X-Expected-Version"] = String(options.expectedVersion);
  }

  const body = {
    type,
    idempotency_key: headers["X-Idempotency-Key"],
    book_id: options.bookId || null,
    reason: options.reason || "",
    payload,
  };

  const res = await fetch("/v1/commands", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const b = await safeJson(res);
    throw new ApiError(res.status, b?.detail || b?.message || res.statusText, b);
  }
  return res.json();
}

export async function apiGetCommand(commandId) {
  return apiGet(`/v1/commands/${commandId}`);
}

export async function apiPollCommand(commandId, interval = 1000, timeout = 60000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const cmd = await apiGetCommand(commandId);
    if (cmd && cmd.status !== "queued" && cmd.status !== "running") return cmd;
    await sleep(interval);
  }
  throw new Error("Command polling timed out");
}

class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body;
    this.name = "ApiError";
  }
}

function safeJson(res) {
  return res.json().catch(() => null);
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
