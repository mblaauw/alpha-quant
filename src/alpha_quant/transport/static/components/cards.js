export function metricCard(label, value, modifier = "") {
  return `<div class="card metric-card">
    <div class="metric-label">${label}</div>
    <div class="metric-value ${modifier}">${value}</div>
  </div>`;
}

export function card(header, body) {
  return `<div class="card">
    ${header ? `<div class="card-header">${header}</div>` : ""}
    <div class="card-body">${body}</div>
  </div>`;
}
