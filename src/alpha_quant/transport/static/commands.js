import { post, get } from "./api.js";

export async function submitCommand(type, payload = {}, options = {}) {
  return post("/v1/commands", { type, payload, ...options });
}

export async function pollCommand(commandId) {
  return get(`/v1/commands/${commandId}`);
}

export function generateKey() {
  return crypto.randomUUID();
}

/* Refresh the currently active view after a mutation completes.
   All view renderers listen for this custom event. */
export function refreshView() {
  window.dispatchEvent(new CustomEvent("bookchange"));
}

/* ── Typed helpers for the redesign's new command types (see API plan §2). ──
   Each returns the submit response { command_id, status }. The caller drives
   the toast via runWithToast() in components/toast.js. */
export const cmd = {
  submit: (type, payload, bookId = null, reason = null) => submitCommand(type, payload, { idempotency_key: generateKey(), book_id: bookId, reason }),
  runCycle:       (bookId, asOf = null) => submitCommand("decision_run.create", { decision_as_of: asOf, snapshot_id: null }, { idempotency_key: generateKey(), book_id: bookId, reason: "Manual run from Desk" }),
  haltCreate:     (bookId, reason) => submitCommand("halt.create", {}, { idempotency_key: generateKey(), book_id: bookId, reason }),
  haltResume:     (bookId, reason) => submitCommand("halt.resume", {}, { idempotency_key: generateKey(), book_id: bookId, reason }),
  orderSubmit:    (bookId, payload, reason) => submitCommand("order.submit", payload, { idempotency_key: generateKey(), book_id: bookId, reason }),
  orderCancel:    (bookId, orderId, reason) => submitCommand("order.cancel", { order_id: orderId }, { idempotency_key: generateKey(), book_id: bookId, reason }),
  approve:        (bookId, payload, reason) => submitCommand("candidate.approve", payload, { idempotency_key: generateKey(), book_id: bookId, reason }),
  reject:         (bookId, payload, reason) => submitCommand("candidate.reject", payload, { idempotency_key: generateKey(), book_id: bookId, reason }),
  flatten:        (bookId, positionId, reason) => submitCommand("position.flatten", { position_id: positionId }, { idempotency_key: generateKey(), book_id: bookId, reason }),
  setStop:        (bookId, positionId, stopPrice, reason) => submitCommand("position.set_stop", { position_id: positionId, stop_price: stopPrice }, { idempotency_key: generateKey(), book_id: bookId, reason }),
  modify:         (bookId, payload, reason) => submitCommand("candidate.modify", payload, { idempotency_key: generateKey(), book_id: bookId, reason }),
  backtest:       (bookId, payload, reason) => submitCommand("backtest.create", payload, { idempotency_key: generateKey(), book_id: bookId, reason }),
  setMockMode:    (mock, reason) => submitCommand("system.set_mock_mode", { mock }, { idempotency_key: generateKey(), reason }),
};
