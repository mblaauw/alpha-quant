import { initShell } from "./render/shell.js";
import { initRouter } from "./router.js";

document.addEventListener("DOMContentLoaded", async () => {
  await initShell();
  initRouter();
});
