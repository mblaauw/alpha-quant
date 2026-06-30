export function openDrawer(title, content, subtitle) {
  document.getElementById("drawer-title").innerHTML = title;
  document.getElementById("drawer-body").innerHTML = content;
  const sub = document.getElementById("drawer-sub");
  if (sub) {
    sub.textContent = subtitle ?? "";
    sub.style.display = subtitle ? "" : "none";
  }
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-overlay").classList.add("open");
  // Focus management: move focus to drawer close button
  setTimeout(() => document.getElementById("drawer-close-btn")?.focus(), 100);
}

export function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-overlay").classList.remove("open");
  // Restore focus to the trigger element
  if (document.activeElement) document.activeElement.blur();
}

document.addEventListener("click", (e) => {
  if (e.target.closest("#drawer-overlay")) closeDrawer();
  if (e.target.closest("#drawer-close-btn")) closeDrawer();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
