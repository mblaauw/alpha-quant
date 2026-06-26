export function renderTable(headers, rows) {
  if (!rows || rows.length === 0) return "";
  const thead = headers.map((h) => `<th>${h}</th>`).join("");
  const tbody = rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table>`;
}
