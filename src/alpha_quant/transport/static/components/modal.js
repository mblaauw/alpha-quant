export function showModal(title, body, actions) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = body;
  const el = document.getElementById("modal-actions");
  el.innerHTML = "";
  actions.forEach(a => { const b = document.createElement("button"); b.className = a.class || "btn"; b.textContent = a.label; b.onclick = a.onclick; el.appendChild(b); });
  document.getElementById("modal").showModal();
}

export function closeModal() {
  document.getElementById("modal").close();
}

document.addEventListener("click", (e) => { if (e.target.closest("#modal-close-btn")) closeModal(); });
document.getElementById("modal").addEventListener("close", closeModal);
