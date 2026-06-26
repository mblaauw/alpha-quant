export function dataTable(headers, rows, options = {}) {
  const thead = headers.map(h => `<th>${h}</th>`).join("");
  const tbody = rows.map(row =>
    `<tr${options.clickable ? ' class="clickable"' : ""}>${row.map(c => `<td>${c}</td>`).join("")}</tr>`
  ).join("");
  return `<table class="data-table"><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table>`;
}
