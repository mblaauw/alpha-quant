import { chip } from "../formatters.js";

/* Renders a status chip with a leading dot. `state` selects the tone. */
export function statusChip(label, state) {
  return `<span class="${chip(state)}"><span class="d"></span>${label}</span>`;
}

/* Chip without a dot (for inline table cells). */
export function tagChip(label, state) {
  return `<span class="${chip(state)}">${label}</span>`;
}
