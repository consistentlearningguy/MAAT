import { escapeHtml, formatDate, formatElapsed } from "../lib/formatters.js";

function priorityLabel(rank) {
  return `P${rank ?? 1}`;
}

export function renderCaseList(container, records, selectedCaseId, viewMode, onSelect) {
  container.className = `case-list ${viewMode}-view`;
  if (!records.length) {
    container.innerHTML = '<div class="empty-state">No cases match the current filters.</div>';
    return;
  }

  container.innerHTML = records.map((record) => `
    <article class="case-card ${record.id === selectedCaseId ? "active" : ""}" data-case-id="${record.id}">
      <div class="case-card-media">
        <img src="${record.photos[0]?.thumb_url || "./assets/case-a.svg"}" alt="${escapeHtml(record.name)}" loading="lazy">
        <div class="case-card-overlay">
          <span class="case-card-index">#${record.id}</span>
          <span class="case-card-priority priority-${record.riskRank ?? 1}">${priorityLabel(record.riskRank)}</span>
        </div>
      </div>
      <div class="case-card-copy">
        <div class="case-card-top">
          <div>
            <p class="case-card-label">${escapeHtml(record.slug)}</p>
            <h4>${escapeHtml(record.name)}</h4>
            <p>${escapeHtml(record.city || "Unknown city")}, ${escapeHtml(record.province)}</p>
          </div>
          <span class="status-tag status-${record.status}">${escapeHtml(record.statusLabel)}</span>
        </div>
        <p class="case-card-meta">Age ${record.age ?? "Unknown"} • Missing ${formatDate(record.missingSince)}</p>
        <p class="case-card-context">${escapeHtml(record.geoContext?.[0]?.label || "No nearby public context layer")}</p>
        <div class="source-row">
          ${(record.riskFlags || []).slice(0, 2).map((flag) => `<span class="flag-chip">${escapeHtml(flag)}</span>`).join("") || '<span class="flag-chip">No derived flags</span>'}
          <span class="source-badge">${escapeHtml(record.sources[0]?.label || "Official source")}</span>
          <span class="source-badge">Elapsed ${formatElapsed(record.elapsedDays)}</span>
        </div>
      </div>
    </article>
  `).join("");

  container.querySelectorAll(".case-card").forEach((card) => {
    card.addEventListener("click", () => onSelect(Number(card.dataset.caseId), true));
  });
}
