import { escapeHtml, formatDate, formatElapsed } from "../lib/formatters.js";

function latestItem(records) {
  return [...records].sort((a, b) => new Date(b.updatedAt || b.missingSince || 0) - new Date(a.updatedAt || a.missingSince || 0))[0] || null;
}

export function renderMetrics(container, summary) {
  container.innerHTML = [
    { label: "Tracked cases", value: summary.total, note: "Visible in the current query scope.", tone: "neutral" },
    { label: "Priority statuses", value: summary.highRisk, note: "Amber, vulnerable, and child-search escalations.", tone: "alert" },
    { label: "Updated in 30 days", value: summary.recent, note: "Recently active records worth reviewing first.", tone: "live" },
    { label: "Latest sync", value: summary.latestUpdate ? formatDate(summary.latestUpdate) : "Unavailable", note: "Most recent public update timestamp in scope.", tone: "hot" },
  ].map((metric) => `
    <article class="metric-card metric-${metric.tone}">
      <span class="metric-kicker">${metric.label}</span>
      <strong class="metric-value">${metric.value}</strong>
      <p class="metric-note">${metric.note}</p>
    </article>
  `).join("");
}

export function renderSignalTicker(container, records, meta) {
  const latest = latestItem(records);
  const provinceCounts = {};
  records.forEach((record) => {
    provinceCounts[record.province] = (provinceCounts[record.province] || 0) + 1;
  });
  const topProvince = Object.entries(provinceCounts).sort((a, b) => b[1] - a[1])[0];
  const highRisk = records.filter((record) => record.riskRank >= 2).length;
  const items = [
    meta?.dataset_mode === "live-arcgis" ? "LIVE ARCGIS FEED ONLINE" : "BUNDLED STATIC EXPORT ACTIVE",
    `${records.length} CASES IN CURRENT FIELD OF VIEW`,
    `${highRisk} PRIORITY STATUS CASES IN SCOPE`,
    topProvince ? `${topProvince[0].toUpperCase()} HOLDS THE LARGEST CASE CLUSTER` : "PROVINCE DISTRIBUTION ONLINE",
    latest ? `LATEST PUBLIC UPDATE ${formatDate(latest.updatedAt || latest.missingSince).toUpperCase()}` : "AWAITING UPDATE SIGNAL",
    "OFFICIAL FACTS AND INFERRED CONTEXT REMAIN SEPARATE",
    "ROUTE ALL TIPS TO THE LISTED AUTHORITY OR MCSC",
    ...records.slice(0, 6).map((record) => `${record.statusLabel.toUpperCase()} // ${record.name.toUpperCase()} // ${(record.city || "UNKNOWN CITY").toUpperCase()}, ${record.province.toUpperCase()} // ELAPSED ${formatElapsed(record.elapsedDays).toUpperCase()}`),
  ];
  const stream = items.map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  container.innerHTML = `
    <div class="signal-marquee">
      <div class="signal-marquee-track">
        ${stream}
        ${stream}
      </div>
    </div>
  `;
}

export function renderSignalQueue(container, records) {
  const items = [...records]
    .sort((a, b) => ((b.riskRank ?? 0) - (a.riskRank ?? 0)) || (new Date(b.updatedAt || b.missingSince || 0) - new Date(a.updatedAt || a.missingSince || 0)))
    .slice(0, 5);

  if (!items.length) {
    container.innerHTML = '<div class="empty-state">No cases match the current filters, so no signal queue is visible.</div>';
    return;
  }

  container.innerHTML = items.map((record) => `
    <div class="signal-item priority-${record.riskRank ?? 1}">
      <div class="signal-item-head">
        <div>
          <strong>${escapeHtml(record.name)}</strong>
          <p>${escapeHtml(record.city || "Unknown city")}, ${escapeHtml(record.province)}</p>
        </div>
        <span class="signal-priority">P${record.riskRank ?? 1}</span>
      </div>
      <p>${escapeHtml(record.inferenceSummary)}</p>
      <div class="source-row">
        <span class="status-tag status-${record.status}">${escapeHtml(record.statusLabel)}</span>
        <span class="flag-chip">Elapsed ${formatElapsed(record.elapsedDays)}</span>
        <span class="geo-chip">${escapeHtml(record.geoContext?.[0]?.label || "No nearby public layer")}</span>
        <span class="source-badge">${record.sources.length} source${record.sources.length === 1 ? "" : "s"}</span>
      </div>
    </div>
  `).join("");
}

export function renderRecentUpdates(container, records) {
  const items = [...records].sort((a, b) => new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0)).slice(0, 5);
  container.innerHTML = items.map((record) => `
    <div class="update-item">
      <div>
        <strong>${escapeHtml(record.name)}</strong>
        <p>${escapeHtml(record.city || "Unknown city")}, ${escapeHtml(record.province)}</p>
      </div>
      <div class="update-meta">
        <span class="status-tag status-${record.status}">${escapeHtml(record.statusLabel)}</span>
        <span class="source-badge">${formatDate(record.updatedAt || record.missingSince)}</span>
      </div>
    </div>
  `).join("");
}

export function renderProvinceResources(container, records) {
  const byProvince = new Map();
  records.forEach((record) => {
    if (!byProvince.has(record.province)) byProvince.set(record.province, record.resources || []);
  });
  container.innerHTML = [...byProvince.entries()].map(([province, resources]) => `
    <div class="resource-item">
      <div>
        <strong>${escapeHtml(province)}</strong>
        <p>${resources.map((item) => `<a href="${item.url}" target="_blank" rel="noopener">${escapeHtml(item.label)}</a>`).join(" • ")}</p>
      </div>
      <span class="source-badge">${resources.length} route${resources.length === 1 ? "" : "s"}</span>
    </div>
  `).join("");
}
