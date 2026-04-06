import { initDashboard } from "./views/dashboard.js";

initDashboard().catch((error) => {
  console.error(error);
  document.getElementById("detailPanel").innerHTML = '<div class="empty-state">Unable to load case data right now.</div>';
  document.getElementById("dataModeBadge").textContent = "Load failed";
  document.getElementById("feedTimestamp").textContent = error.message;
});
