import store from "./state.js";
import { renderDesk } from "./render/desk.js";
import { renderPortfolio } from "./render/portfolio.js";
import { renderDecisions } from "./render/decisions.js";
import { renderOrders } from "./render/orders.js";
import { renderRisk } from "./render/risk.js";
import { renderRuns } from "./render/runs.js";
import { renderJournal } from "./render/journal.js";
import { renderSystem } from "./render/system.js";

const routes = {
  desk: renderDesk,
  portfolio: renderPortfolio,
  decisions: renderDecisions,
  orders: renderOrders,
  risk: renderRisk,
  runs: renderRuns,
  journal: renderJournal,
  system: renderSystem,
};

export function navigate(hash) {
  const route = hash.replace(/^#\/?/, "").split("?")[0] || "desk";
  store.route = route;
  document.querySelectorAll("#tabs a").forEach(a => a.classList.toggle("active", a.getAttribute("href") === `#${route}`));
  const render = routes[route];
  if (render) render();
}

export function initRouter() {
  window.addEventListener("hashchange", () => navigate(location.hash));
  navigate(location.hash || "#desk");
}
