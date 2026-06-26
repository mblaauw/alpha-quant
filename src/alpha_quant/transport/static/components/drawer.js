const drawer = document.getElementById("drawer");

export function openDrawer(title, bodyHtml) {
  if (!drawer) return;
  drawer.innerHTML = `
    <div class="drawer-header">
      <h3>${title}</h3>
      <button class="drawer-close" onclick="window.__closeDrawer()">×</button>
    </div>
    <div class="drawer-body">${bodyHtml}</div>
  `;
  drawer.classList.remove("hidden");
  window.__closeDrawer = closeDrawer;
}

export function closeDrawer() {
  if (!drawer) return;
  drawer.classList.add("hidden");
  drawer.innerHTML = "";
}
