import { chip } from "../formatters.js";

export function statusChip(label, state) {
  return `<span class="${chip(state)}">${label}</span>`;
}
