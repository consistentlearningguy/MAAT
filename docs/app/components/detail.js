import { escapeHtml, formatDate, formatElapsed, normalizePhone } from "../lib/formatters.js";

function renderEmpty() {
  return `
    <div class="empty-state">
      <p class="eyebrow">Select a case</p>
      <h3>Open a case file to inspect official facts, public context, reporting routes, and source trails.</h3>
    </div>
  `;
}

export function renderDetail(container, record) {
  if (!record) {
    container.innerHTML = renderEmpty();
    return;
  }

  container.innerHTML = `
    <div class="detail-stack">
      <div class="detail-top">
        <div>
          <p class="eyebrow">Selected Case</p>
          <h3>${escapeHtml(record.name)}</h3>
          <div class="case-label-row">
            <span class="status-tag status-${record.status}">${escapeHtml(record.statusLabel)}</span>
            <span class="source-badge">Case ${record.id}</span>
            <span class="source-badge">${escapeHtml(record.slug)}</span>
          </div>
        </div>
        <button class="primary-button" id="printCaseButton" type="button">Print packet</button>
      </div>

      <div class="detail-photo-grid">
        ${(record.photos || []).map((photo) => `<img src="${photo.url}" alt="${escapeHtml(record.name)}" loading="lazy">`).join("") || '<div class="empty-state">No photo provided</div>'}
      </div>

      <div class="detail-card">
        <div class="detail-section-head"><strong>Official facts</strong><span>Primary record</span></div>
        <div class="detail-grid">
          <div><strong>City</strong><p>${escapeHtml(record.city || "Not listed")}</p></div>
          <div><strong>Province</strong><p>${escapeHtml(record.province || "Not listed")}</p></div>
          <div><strong>Age</strong><p>${record.age ?? "Unknown"}</p></div>
          <div><strong>Missing since</strong><p>${formatDate(record.missingSince)}</p></div>
          <div><strong>Last update</strong><p>${formatDate(record.updatedAt)}</p></div>
          <div><strong>Authority</strong><p>${escapeHtml(record.authority.name || "Official authority")}</p></div>
        </div>
        <div class="detail-body">${record.summaryHtml || "<p>No official summary provided.</p>"}</div>
      </div>

      <div class="inference-card">
        <div class="detail-section-head"><strong>Unverified signal layer</strong><span>Derived context only</span></div>
        <p>${escapeHtml(record.inferenceSummary)}</p>
        <div class="geo-chip-row">
          ${(record.geoContext || []).map((item) => `<span class="geo-chip">${escapeHtml(item.context_type)} • ${escapeHtml(item.label)} • ${item.distance_km ?? "?"} km</span>`).join("") || '<span class="geo-chip">No bundled geospatial context</span>'}
        </div>
        <div class="geo-chip-row">
          ${(record.riskFlags || []).map((flag) => `<span class="flag-chip">${escapeHtml(flag)}</span>`).join("") || '<span class="flag-chip">No derived flags</span>'}
          <span class="flag-chip">Elapsed ${formatElapsed(record.elapsedDays)}</span>
          <span class="flag-chip">Estimated current age ${record.estimatedCurrentAge ?? "Unknown"}</span>
          <span class="flag-chip">${record.sources.length} source trail</span>
        </div>
      </div>

      <div class="detail-card">
        <div class="detail-section-head"><strong>Authority contacts</strong><span>Report, do not intervene</span></div>
        <div class="contact-grid">
          ${record.authority.url ? `<a class="link-button" href="${record.authority.url}" target="_blank" rel="noopener">Open authority page</a>` : ""}
          ${record.authority.phone ? `<a class="link-button" href="tel:${normalizePhone(record.authority.phone)}">Call ${escapeHtml(record.authority.phone)}</a>` : ""}
          ${record.mcsc.email ? `<a class="link-button" href="mailto:${record.mcsc.email}">Email MCSC</a>` : ""}
        </div>
      </div>

      <div class="detail-card">
        <div class="detail-section-head"><strong>What to report</strong><span>Checklist</span></div>
        <ul class="checklist">${record.whatToReport.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>

      <div class="detail-card">
        <div class="detail-section-head"><strong>How to help safely</strong><span>Guardrail</span></div>
        <ul class="checklist">${record.howToHelpSafely.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>

      <div class="detail-card">
        <div class="detail-section-head"><strong>Source attribution</strong><span>Transparency</span></div>
        <div class="stack-list">
          ${record.sources.map((source) => `
            <div class="resource-item">
              <div>
                <strong>${escapeHtml(source.label)}</strong>
                <p><a href="${source.source_url}" target="_blank" rel="noopener">${escapeHtml(source.source_url)}</a></p>
              </div>
              <span class="source-badge">${source.official ? "Official" : "Public"}</span>
            </div>
          `).join("")}
        </div>
      </div>

      <div class="detail-card">
        <div class="detail-section-head"><strong>Timeline</strong><span>${record.timelineEntries.length} entries</span></div>
        <div class="stack-list">
          ${record.timelineEntries.map((entry) => `
            <div class="timeline-item">
              <div>
                <strong>${escapeHtml(entry.label)}</strong>
                <p>${entry.kind === "derived" ? "Derived" : "Official"}</p>
              </div>
              <span class="source-badge">${formatDate(entry.date)}</span>
            </div>
          `).join("")}
        </div>
      </div>
    </div>
  `;

  const printButton = container.querySelector("#printCaseButton");
  if (printButton) {
    printButton.addEventListener("click", () => window.print());
  }
}
