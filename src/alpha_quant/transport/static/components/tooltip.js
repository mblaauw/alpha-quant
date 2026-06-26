export function tooltip(text) {
  return ` data-tooltip="${text.replace(/"/g, "&quot;")}"`;
}
