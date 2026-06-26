import { getState, setState } from "./state.js";
import { renderCommandCenter } from "./render/command_center.js";
import { renderDecisions } from "./render/decisions.js";
import { renderPortfolio } from "./render/portfolio.js";
import { renderOrders } from "./render/orders.js";
import { renderRisk } from "./render/risk.js";
import { renderRuns } from "./render/runs.js";
import { renderJournal } from "./render/journal.js";
import { renderReports } from "./render/reports.js";
import { renderSystem } from "./render/system.js";
import { renderNotFound } from "./render/shell.js";
import { showLoading } from "./components/loading_state.js";

const RENDERERS = {
  "command-center": renderCommandCenter,
  "decisions": renderDecisions,
  "portfolio": renderPortfolio,
  "orders": renderOrders,
  "risk": renderRisk,
  "runs": renderRuns,
  "journal": renderJournal,
  "reports": renderReports,
  "system": renderSystem,
};

export function initRouter() {
  window.addEventListener("hashchange", handleRoute);
  const saved = localStorage.getItem("aq-last-route");
  const route = saved || "command-center";
  navigate(route);
}

export function navigate(route) {
  window.location.hash = `#${route}`;
}

async function handleRoute() {
  const hash = window.location.hash.slice(1) || "command-center";
  setState({ route: hash });
  localStorage.setItem("aq-last-route", hash);
  updateSidebar(hash);
  const view = document.getElementById("view");
  showLoading(view);
  const renderer = RENDERERS[hash] || renderNotFound;
  try {
    await renderer(view);
  } catch (err) {
    view.innerHTML = `<div class="error-state"><h3>Failed to load</h3><p>${err.message}</p></div>`;
  }
}

function updateSidebar(route) {
  document.querySelectorAll("#sidebar li").forEach(li => {
    li.classList.toggle("active", li.dataset.route === route);
  });
}
