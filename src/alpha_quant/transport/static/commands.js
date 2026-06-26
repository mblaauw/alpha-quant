import { post, get } from "./api.js";

export async function submitCommand(type, payload = {}, options = {}) {
  return post("/v1/commands", { type, payload, ...options });
}

export async function pollCommand(commandId) {
  return get(`/v1/commands/${commandId}`);
}

export async function cancelCommand(commandId) {
  return post(`/v1/commands/${commandId}/cancel`, {});
}

export function generateKey() {
  return crypto.randomUUID();
}
