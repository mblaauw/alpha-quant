/* Lightweight hover tooltip (parity with the original). Attach data-tip="…" to
   any element; the shared tooltip element is positioned on hover. */
let tip;
function ensure() {
  if (tip) return tip;
  tip = document.createElement("div");
  tip.id = "aq-tooltip";
  tip.style.cssText = "position:fixed;z-index:999;display:none;max-width:280px;padding:9px 11px;border-radius:5px;background:var(--aq-paper);border:1px solid var(--aq-rule2);box-shadow:0 10px 30px rgba(0,0,0,.25);font-size:12px;color:var(--aq-ink2);pointer-events:none;line-height:1.45;";
  document.body.appendChild(tip);
  return tip;
}
document.addEventListener("mouseover", (e) => {
  const t = e.target.closest("[data-tip]");
  if (!t) return;
  const el = ensure();
  el.textContent = t.getAttribute("data-tip");
  el.style.display = "block";
  const r = t.getBoundingClientRect();
  el.style.left = Math.min(r.left, window.innerWidth - 290) + "px";
  el.style.top = (r.bottom + 6) + "px";
});
document.addEventListener("mouseout", (e) => {
  if (e.target.closest("[data-tip]") && tip) tip.style.display = "none";
});

export {};
