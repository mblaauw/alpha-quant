export function openDrawer(title, content) {
  document.getElementById("drawer-title").textContent = title;
  document.getElementById("drawer-body").innerHTML = content;
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-overlay").classList.add("open");
}

export function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-overlay").classList.remove("open");
}

document.addEventListener("click", (e) => {
  if (e.target.closest("#drawer-overlay")) closeDrawer();
  if (e.target.closest("#drawer-close-btn")) closeDrawer();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
