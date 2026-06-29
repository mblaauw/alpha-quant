import store from "./state.js";
import { renderAdvice } from "./render/advice.js";
import { renderPortfolio } from "./render/portfolio.js";
import { renderDecisions } from "./render/decisions.js";
import { renderOrders } from "./render/orders.js";
import { renderRisk } from "./render/risk.js";
import { renderSystem } from "./render/system.js";

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
  store.route = route;
  const navRoute = (route === "runs" || route === "journal") ? "system" : route;
  document.querySelectorAll("#tabs a").forEach((a) =>
    a.classList.toggle("active", a.getAttribute("href") === `#${navRoute}`));
  const render = routes[route];
  if (render) render();
}

export function initRouter() {
  window.addEventListener("hashchange", () => navigate(location.hash));
  navigate(location.hash || "#advice");
}
