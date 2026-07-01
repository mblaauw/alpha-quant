import store from "./state.js";
import { renderAdvice } from "./render/advice.js";
import { renderPortfolio } from "./render/portfolio.js";
import { renderDecisions } from "./render/decisions.js";
import { renderOrders } from "./render/orders.js";
import { renderRisk } from "./render/risk.js";
import { renderSystem } from "./render/system.js";
import { closeDrawer } from "./components/drawer.js";

const routes = {
  advice: renderAdvice,
  portfolio: renderPortfolio,
  decisions: renderDecisions,
  orders: renderOrders,
  risk: renderRisk,
  runs:    () => renderSystem("runs"),
  journal: () => renderSystem("journal"),
  system:  () => renderSystem("overview"),
};

export function navigate(hash) {
  const route = hash.replace(/^#\/?/, "").split("?")[0] || "advice";

  closeDrawer();
  const tk = document.getElementById("tk-overlay");
  if (tk) {
    tk.dataset.open = "false";
    tk.remove();
  }

  store.route = route;
  const navRoute = (route === "runs" || route === "journal") ? "system" : route;
  document.querySelectorAll("#tabs a").forEach((a) => {
    const isActive = a.getAttribute("href") === `#${navRoute}`;
    a.classList.toggle("active", isActive);
    if (isActive) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const render = routes[route];
  if (render) render();
}

export function initRouter() {
  window.addEventListener("hashchange", () => navigate(location.hash));
  navigate(location.hash || "#advice");
}
