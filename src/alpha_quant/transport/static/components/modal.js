const modal = document.getElementById("modal");

export function openModal(html) {
  if (!modal) return;
  modal.innerHTML = `<div class="modal-body">${html}</div>`;
  modal.showModal();
}

export function closeModal() {
  if (!modal) return;
  modal.close();
  modal.innerHTML = "";
}
