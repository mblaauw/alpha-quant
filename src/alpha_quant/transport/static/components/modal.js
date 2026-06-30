/* Modal shell. showModal(title, bodyHTML, actions[]) where each action is
   { label, class, onclick }. Body is raw HTML built by the caller — use the
   field() helper to compose forms in the Lake Watch style. */

export function showModal(title, body, actions) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = body;
  const el = document.getElementById("modal-actions");
  el.innerHTML = "";
  actions.forEach((a, i) => {
    const b = document.createElement("button");
    b.className = a.class || "btn";
    b.textContent = a.label;
    b.onclick = a.onclick;
    el.appendChild(b);
    // Focus the first action button when modal opens
    if (i === 0) setTimeout(() => b.focus(), 100);
  });
  document.getElementById("modal").showModal();
}

export function closeModal() {
  document.getElementById("modal").close();
}

/* Form-field helpers for modal bodies. */
export function intro(text, danger = false) {
  return `<p class="intro${danger ? " danger" : ""}">${text}</p>`;
}
export function fieldStatic(label, value) {
  return `<div><label>${label}</label><div class="static">${value}</div></div>`;
}
export function fieldText(id, label, placeholder = "", value = "") {
  return `<div><label>${label}</label><input id="${id}" value="${value}" placeholder="${placeholder}"></div>`;
}
export function fieldNumber(id, label, value = "") {
  return `<div><label>${label}</label><input id="${id}" type="number" value="${value}"></div>`;
}
export function fieldSelect(id, label, options, value = "") {
  const opts = options.map((o) => `<option value="${o}"${o === value ? " selected" : ""}>${o}</option>`).join("");
  return `<div><label>${label}</label><select id="${id}">${opts}</select></div>`;
}
export function fieldDateTime(id, label) {
  return `<div><label>${label}</label><input id="${id}" type="datetime-local"></div>`;
}
export function val(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}

document.addEventListener("click", (e) => { if (e.target.closest("#modal-close-btn")) closeModal(); });
document.getElementById("modal").addEventListener("close", () => {});
