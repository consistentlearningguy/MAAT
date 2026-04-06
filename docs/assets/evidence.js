(function () {
  if (!window.OsintMissingPersons || document.body.dataset.page !== "evidence") {
    return;
  }

  const App = window.OsintMissingPersons;

  const state = {
    datasetMeta: null,
    cases: [],
    filteredCases: [],
    selectedCaseId: null,
    apiBase: "",
    runs: [],
    activeRunId: null,
    activeRun: null,
    resourcePack: null,
    synthesis: null,
    leads: [],
    queryLogs: [],
    activeLeadId: null,
    mapContext: null,
    runMessage: "Select a case to inspect online evidence.",
    loadingRun: false,
  };

  const elements = {
    dataModeBadge: document.getElementById("dataModeBadge"),
    feedTimestamp: document.getElementById("feedTimestamp"),
    signalRibbon: document.getElementById("signalRibbon"),
    signalTicker: document.getElementById("signalTicker"),
    backendStatus: document.getElementById("backendStatus"),
    apiBaseInput: document.getElementById("apiBaseInput"),
    saveApiBaseButton: document.getElementById("saveApiBaseButton"),
    runInvestigationButton: document.getElementById("runInvestigationButton"),
    refreshRunsButton: document.getElementById("refreshRunsButton"),
    liveModeButton: document.getElementById("liveModeButton"),
    caseSearchInput: document.getElementById("caseSearchInput"),
    provinceSelect: document.getElementById("provinceSelect"),
    sortSelect: document.getElementById("sortSelect"),
    reviewStatusSelect: document.getElementById("reviewStatusSelect"),
    minConfidenceInput: document.getElementById("minConfidenceInput"),
    leadLimitSelect: document.getElementById("leadLimitSelect"),
    evidenceCaseList: document.getElementById("evidenceCaseList"),
    evidenceResultsCount: document.getElementById("evidenceResultsCount"),
    selectedCaseCard: document.getElementById("selectedCaseCard"),
    runStatusBadge: document.getElementById("runStatusBadge"),
    runSummary: document.getElementById("runSummary"),
    runHistoryList: document.getElementById("runHistoryList"),
    leadList: document.getElementById("leadList"),
    queryLogList: document.getElementById("queryLogList"),
    evidenceMap: document.getElementById("evidenceMap"),
    synthesisContainer: document.getElementById("synthesisContainer"),
    profilesNavLink: document.getElementById("profilesNavLink"),
    openProfilesPage: document.getElementById("openProfilesPage"),
  };

  let routeState = App.readRouteState();
  let pollHandle = null;

  function currentFilters() {
    return {
      search: elements.caseSearchInput.value.trim(),
      province: elements.provinceSelect.value,
      sort: elements.sortSelect.value,
      selectedCaseId: state.selectedCaseId,
      live: routeState.live,
      apiBase: state.apiBase,
      runId: state.activeRunId,
      reviewStatus: elements.reviewStatusSelect.value,
      minConfidence: elements.minConfidenceInput.value || "0",
      limit: elements.leadLimitSelect.value || "100",
    };
  }

  function clearPoll() {
    if (pollHandle) {
      window.clearTimeout(pollHandle);
      pollHandle = null;
    }
  }

  function syncControlsFromRoute() {
    elements.caseSearchInput.value = routeState.search || "";
    elements.sortSelect.value = routeState.sort || "risk";
    elements.reviewStatusSelect.value = routeState.reviewStatus || "";
    elements.minConfidenceInput.value = routeState.minConfidence || "0";
    elements.leadLimitSelect.value = routeState.limit || "100";
    state.apiBase = App.normalizeApiBase(
      routeState.apiBase || App.readStoredApiBase() || App.defaultApiBase()
    );
    elements.apiBaseInput.value = state.apiBase;
  }

  function setBackendStatus(message, tone) {
    elements.backendStatus.textContent = message;
    elements.backendStatus.classList.remove("is-live", "is-static", "is-alert");
    if (tone === "live") elements.backendStatus.classList.add("is-live");
    else if (tone === "alert") elements.backendStatus.classList.add("is-alert");
    else elements.backendStatus.classList.add("is-static");
  }

  function populateCaseFilters() {
    const current = elements.provinceSelect.value;
    const provinces = App.uniqueValues(state.cases, (item) => item.province);
    elements.provinceSelect.innerHTML = '<option value="">All provinces</option>';
    provinces.forEach((province) => {
      const option = document.createElement("option");
      option.value = province;
      option.textContent = province;
      if (province === current) option.selected = true;
      elements.provinceSelect.appendChild(option);
    });
    elements.provinceSelect.value = routeState.province || "";
  }

  function filteredCases() {
    return App.filterCases(state.cases, {
      search: elements.caseSearchInput.value.trim(),
      province: elements.provinceSelect.value,
      city: "",
      minAge: "",
      maxAge: "",
      status: "",
      sort: elements.sortSelect.value,
    });
  }

  function renderSignalBands() {
    const record = state.cases.find((item) => item.id === state.selectedCaseId) || null;
    const items = App.buildEvidenceSignalItems(record, state.activeRun, state.leads, state.queryLogs);
    App.renderMarquee(elements.signalRibbon, items, "signal-ribbon-track");
    App.renderMarquee(elements.signalTicker, items, "signal-marquee-track");
  }

  function renderCaseRail() {
    state.filteredCases = filteredCases();
    elements.evidenceResultsCount.textContent = `${state.filteredCases.length} case${
      state.filteredCases.length === 1 ? "" : "s"
    }`;

    if (!state.filteredCases.length) {
      elements.evidenceCaseList.innerHTML =
        '<div class="empty-state">No profiles match the current investigation filters.</div>';
      return;
    }

    elements.evidenceCaseList.innerHTML = state.filteredCases
      .map(
        (record) => `
        <article class="case-card evidence-case-card ${
          record.id === state.selectedCaseId ? "active" : ""
        }" data-case-id="${record.id}">
          <div class="case-card-media">
            <img src="${
              record.photos && record.photos[0] && record.photos[0].thumb_url
                ? record.photos[0].thumb_url
                : "./assets/case-b.svg"
            }" alt="${App.escapeHtml(record.name)}" loading="lazy">
            <div class="case-card-overlay">
              <span class="case-card-index">#${record.id}</span>
              <span class="case-card-priority priority-${record.riskRank ?? 1}">P${record.riskRank ?? 1}</span>
            </div>
          </div>
          <div class="case-card-copy">
            <div class="case-card-top">
              <div>
                <p class="case-card-label">${App.escapeHtml(record.slug)}</p>
                <h4>${App.escapeHtml(record.name)}</h4>
                <p>${App.escapeHtml(record.city || "Unknown city")}, ${App.escapeHtml(
                  record.province
                )}</p>
              </div>
              <span class="status-tag status-${record.status}">${App.escapeHtml(
                record.statusLabel
              )}</span>
            </div>
            <p class="case-card-meta">Age ${record.age ?? "Unknown"} • Missing ${App.formatDate(
              record.missingSince
            )}</p>
            <div class="source-row">
              ${
                (record.riskFlags || [])
                  .slice(0, 2)
                  .map((flag) => `<span class="flag-chip">${App.escapeHtml(flag)}</span>`)
                  .join("") || '<span class="flag-chip">No derived flags</span>'
              }
              <span class="source-badge">${record.sources.length} source${
                record.sources.length === 1 ? "" : "s"
              }</span>
            </div>
          </div>
        </article>
      `
      )
      .join("");

    elements.evidenceCaseList.querySelectorAll(".case-card").forEach((card) => {
      card.addEventListener("click", () => selectCase(Number(card.dataset.caseId)));
    });
  }

  function renderChipRow(items, chipClass) {
    if (!items || !items.length) {
      return "";
    }
    return `
      <div class="geo-chip-row">
        ${items.map((item) => `<span class="${chipClass}">${App.escapeHtml(item)}</span>`).join("")}
      </div>
    `;
  }

  function renderCoveragePanel() {
    const coverage = state.resourcePack && state.resourcePack.coverage;
    if (!coverage || !coverage.categories || !coverage.categories.length) {
      return "";
    }

    return `
      <div class="detail-card">
        <div class="detail-section-head">
          <strong>Category Coverage</strong>
          <span>${App.escapeHtml(coverage.summary || "Coverage unavailable")}</span>
        </div>
        <p class="metric-note">${App.escapeHtml(
          coverage.description || "Coverage is derived from current case facts."
        )}</p>
        <div class="stack-list tight-stack">
          ${(coverage.categories || [])
            .map(
              (category) => `
                <div class="coverage-card coverage-${App.escapeHtml(category.status || "missing")}">
                  <div class="detail-section-head">
                    <strong>${App.escapeHtml(category.title || "Coverage category")}</strong>
                    <span class="status-tag coverage-tag coverage-${App.escapeHtml(
                      category.status || "missing"
                    )}">${App.escapeHtml(category.status_label || category.status || "Gap")}</span>
                  </div>
                  <p>${App.escapeHtml(category.summary || "No summary provided.")}</p>
                  ${renderChipRow(category.evidence || [], "geo-chip")}
                  ${renderChipRow(category.gaps || [], "flag-chip")}
                  ${
                    category.recommended_action
                      ? `<p class="metric-note">Next: ${App.escapeHtml(category.recommended_action)}</p>`
                      : ""
                  }
                </div>
              `
            )
            .join("")}
        </div>
        ${
          (coverage.next_steps || []).length
            ? `
              <div class="detail-section-head coverage-subhead">
                <strong>Suggested Next Steps</strong>
                <span>Queue</span>
              </div>
              ${renderChipRow(coverage.next_steps || [], "source-badge")}
            `
            : ""
        }
      </div>
    `;
  }

  function renderOfficialContext(record) {
    const packContext = state.resourcePack && state.resourcePack.official_context;
    const context = packContext || record.officialContext;
    if (!context) {
      return "";
    }

    const descriptors =
      context.descriptor_chips ||
      context.descriptorChips ||
      [];
    const warnings =
      context.quality_warnings ||
      context.qualityWarnings ||
      [];
    const missingSince = context.missing_since_text || context.missingSinceText;
    const locationText = context.location_text || context.locationText;
    const inferredCity = context.inferred_city || context.inferredCity;
    const inferredProvince = context.inferred_province || context.inferredProvince;

    return `
      <div class="detail-card">
        <div class="detail-section-head"><strong>Official Context</strong><span>Parsed anchor</span></div>
        ${
          locationText
            ? `<p><strong>Last-seen location:</strong> ${App.escapeHtml(locationText)}</p>`
            : ""
        }
        ${
          missingSince
            ? `<p><strong>Official missing since:</strong> ${App.escapeHtml(missingSince)}</p>`
            : ""
        }
        ${
          inferredCity || inferredProvince
            ? `<p class="metric-note">Resolved anchor: ${App.escapeHtml(
                [inferredCity, inferredProvince].filter(Boolean).join(", ")
              )}</p>`
            : ""
        }
        ${renderChipRow(descriptors, "geo-chip")}
        ${renderChipRow(warnings, "flag-chip")}
      </div>
    `;
  }

  function renderResourcePack() {
    if (!state.apiBase) {
      return `
        <div class="detail-card">
          <div class="detail-section-head"><strong>OSINT Resource Pack</strong><span>Backend required</span></div>
          <p class="metric-note">Set a backend URL to load the Trace Labs-inspired passive OSINT playbook for this case.</p>
        </div>
      `;
    }

    const pack = state.resourcePack;
    if (!pack || !pack.groups || !pack.groups.length) {
      return `
        <div class="detail-card">
          <div class="detail-section-head"><strong>OSINT Resource Pack</strong><span>Loading</span></div>
          <p class="metric-note">Case-specific resources will appear here when the backend returns them.</p>
        </div>
      `;
    }

    return `
      ${renderCoveragePanel()}
      <div class="detail-card">
        <div class="detail-section-head"><strong>OSINT Resource Pack</strong><span>Passive only</span></div>
        <p class="metric-note">${App.escapeHtml(
          pack.methodology && pack.methodology.summary
            ? pack.methodology.summary
            : "Passive, reviewable resource pack."
        )}</p>
        <div class="geo-chip-row">
          ${((pack.methodology && pack.methodology.notes) || [])
            .map((note) => `<span class="flag-chip">${App.escapeHtml(note)}</span>`)
            .join("")}
        </div>
        <div class="stack-list tight-stack">
          ${(pack.groups || [])
            .map(
              (group) => `
                <div class="resource-item">
                  <div>
                    <strong>${App.escapeHtml(group.title || "Resource group")}</strong>
                    <p>${App.escapeHtml(group.summary || "No summary provided.")}</p>
                  </div>
                  <div class="history-meta">
                    ${
                      group.mode
                        ? `<span class="source-badge">${App.escapeHtml(group.mode)}</span>`
                        : ""
                    }
                    <span class="source-badge">${App.escapeHtml(
                      group.trace_labs_category || "Trace Labs"
                    )}</span>
                  </div>
                </div>
                ${((group.items || [])).map(
                  (item) => `
                    <div class="timeline-item">
                      <div>
                        <strong>${App.escapeHtml(item.label || "Resource")}</strong>
                        <p>${App.escapeHtml(item.description || "No description provided.")}</p>
                        ${
                          item.target_value
                            ? `<p class="metric-note">Target: ${App.escapeHtml(item.target_value)}</p>`
                            : ""
                        }
                        ${
                          (item.queries || []).length
                            ? `<div class="geo-chip-row">${item.queries
                                .map((query) => `<span class="flag-chip">${App.escapeHtml(query)}</span>`)
                                .join("")}</div>`
                            : ""
                        }
                        ${
                          (item.notes || []).length
                            ? `<div class="geo-chip-row">${item.notes
                                .map((note) => `<span class="source-badge">${App.escapeHtml(note)}</span>`)
                                .join("")}</div>`
                            : ""
                        }
                      </div>
                      <div class="action-row">
                        ${((item.launchers || [])).map(
                          (launcher) => `
                            <a class="link-button" href="${launcher.url}" target="_blank" rel="noopener">
                              ${App.escapeHtml(launcher.label)}
                            </a>
                          `
                        ).join("")}
                      </div>
                    </div>
                  `
                ).join("")}
              `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  // ── MAAT Intelligence Synthesis Rendering ──

  function renderSynthesisPanel() {
    const syn = state.synthesis;
    if (!syn) {
      return "";
    }

    const priorityLabels = { 1: "CRITICAL", 2: "HIGH", 3: "MEDIUM" };
    const priorityClasses = { 1: "metric-alert", 2: "metric-hot", 3: "metric-neutral" };

    return `
      <section class="panel synthesis-panel reveal-up">
        <div class="panel-head">
          <div>
            <p class="eyebrow">MAAT Intelligence Synthesis</p>
            <h3>Truth from Chaos</h3>
          </div>
          <span class="panel-badge synthesis-badge">${syn.total_clusters} cluster${syn.total_clusters === 1 ? "" : "s"}</span>
        </div>

        <div class="detail-stack">
          <div class="detail-card synthesis-summary-card">
            <div class="detail-section-head">
              <strong>Situation Assessment</strong>
              <span>${App.formatDate(syn.generated_at)}</span>
            </div>
            <p class="synthesis-summary">${App.escapeHtml(syn.situation_summary)}</p>
            <div class="metric-grid compact-metrics">
              <article class="metric-card metric-neutral">
                <span class="metric-kicker">Leads Analyzed</span>
                <strong class="metric-value">${syn.total_leads}</strong>
              </article>
              <article class="metric-card metric-live">
                <span class="metric-kicker">High Confidence</span>
                <strong class="metric-value">${syn.high_confidence_leads}</strong>
              </article>
              <article class="metric-card metric-hot">
                <span class="metric-kicker">Clusters</span>
                <strong class="metric-value">${syn.total_clusters}</strong>
              </article>
            </div>
          </div>

          ${syn.recommendations && syn.recommendations.length ? `
            <div class="detail-card">
              <div class="detail-section-head">
                <strong>Actionable Recommendations</strong>
                <span>${syn.recommendations.length} action${syn.recommendations.length === 1 ? "" : "s"}</span>
              </div>
              <div class="stack-list tight-stack">
                ${syn.recommendations.map((rec) => `
                  <div class="recommendation-card ${priorityClasses[rec.priority] || "metric-neutral"}">
                    <div class="detail-section-head">
                      <strong>[${App.escapeHtml(priorityLabels[rec.priority] || "INFO")}] ${App.escapeHtml(rec.action)}</strong>
                    </div>
                    <p>${App.escapeHtml(rec.rationale)}</p>
                    ${rec.contact_info ? `<p class="metric-note contact-note">${App.escapeHtml(rec.contact_info)}</p>` : ""}
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}

          ${syn.key_findings && syn.key_findings.length ? `
            <div class="detail-card">
              <div class="detail-section-head">
                <strong>Key Findings</strong>
                <span>Intelligence Summary</span>
              </div>
              <div class="stack-list tight-stack">
                ${syn.key_findings.map((finding) => `
                  <div class="finding-item">
                    <p>${App.escapeHtml(finding)}</p>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}

          ${syn.clusters && syn.clusters.length ? `
            <div class="detail-card">
              <div class="detail-section-head">
                <strong>Lead Clusters</strong>
                <span>Thematic Analysis</span>
              </div>
              <div class="stack-list tight-stack">
                ${syn.clusters.slice(0, 8).map((cluster) => `
                  <div class="cluster-card">
                    <div class="detail-section-head">
                      <div>
                        <strong>${App.escapeHtml(cluster.label)}</strong>
                        <p class="metric-note">${App.escapeHtml(cluster.summary)}</p>
                      </div>
                      <span class="source-badge">${Math.round(cluster.max_confidence * 100)}% peak</span>
                    </div>
                    <div class="geo-chip-row">
                      <span class="geo-chip">${cluster.lead_ids ? cluster.lead_ids.length : 0} leads</span>
                      <span class="geo-chip">${cluster.source_count} source${cluster.source_count === 1 ? "" : "s"}</span>
                      <span class="flag-chip">${App.escapeHtml(cluster.theme)}</span>
                      ${cluster.location_text ? `<span class="geo-chip">${App.escapeHtml(cluster.location_text)}</span>` : ""}
                    </div>
                    ${cluster.unique_sources && cluster.unique_sources.length ? `
                      <div class="geo-chip-row">
                        ${cluster.unique_sources.map((s) => `<span class="source-badge">${App.escapeHtml(s)}</span>`).join("")}
                      </div>
                    ` : ""}
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}

          ${renderSynthesisTimeline()}
          ${renderPatterns()}

          ${syn.authority_brief ? `
            <div class="detail-card authority-brief-card">
              <div class="detail-section-head">
                <strong>Authority Brief</strong>
                <span>Ready to Forward</span>
              </div>
              <pre class="authority-brief">${App.escapeHtml(syn.authority_brief)}</pre>
              <p class="metric-note">Copy this brief and forward it to the investigating authority listed in the case profile.</p>
            </div>
          ` : ""}
        </div>
      </section>
    `;
  }

  function renderSynthesisTimeline() {
    const syn = state.synthesis;
    if (!syn || !syn.timeline || !syn.timeline.length) {
      return "";
    }

    const kindLabels = {
      official: "Official",
      news: "News",
      sighting: "Sighting",
      archive: "Archive",
      social: "Social",
      derived: "Derived",
    };
    const kindClasses = {
      official: "status-missing",
      news: "status-vulnerable",
      sighting: "status-abduction",
      archive: "status-childsearchalert",
      social: "status-policeoption1",
      derived: "",
    };

    return `
      <div class="detail-card">
        <div class="detail-section-head">
          <strong>Intelligence Timeline</strong>
          <span>${syn.timeline.length} event${syn.timeline.length === 1 ? "" : "s"}</span>
        </div>
        <div class="stack-list tight-stack timeline-stack">
          ${syn.timeline.map((event) => `
            <div class="timeline-item">
              <div>
                <div class="timeline-head">
                  <span class="status-tag ${kindClasses[event.kind] || ""}">${App.escapeHtml(kindLabels[event.kind] || event.kind)}</span>
                  <span class="timeline-date">${App.formatDate(event.date)}</span>
                  ${event.confidence != null ? `<span class="source-badge">${Math.round(event.confidence * 100)}%</span>` : ""}
                </div>
                <strong>${App.escapeHtml(event.label)}</strong>
                ${event.source_name ? `<p class="metric-note">Source: ${App.escapeHtml(event.source_name)}</p>` : ""}
              </div>
              ${event.source_url ? `<a class="link-button" href="${event.source_url}" target="_blank" rel="noopener">View Source</a>` : ""}
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderPatterns() {
    const syn = state.synthesis;
    if (!syn) return "";

    const geoPatterns = syn.geographic_patterns || [];
    const tempPatterns = syn.temporal_patterns || [];

    if (!geoPatterns.length && !tempPatterns.length) return "";

    return `
      <div class="detail-card">
        <div class="detail-section-head">
          <strong>Pattern Analysis</strong>
          <span>${geoPatterns.length + tempPatterns.length} pattern${(geoPatterns.length + tempPatterns.length) === 1 ? "" : "s"}</span>
        </div>
        <div class="stack-list tight-stack">
          ${geoPatterns.map((p) => `
            <div class="pattern-item pattern-${App.escapeHtml(p.significance || "low")}">
              <div class="detail-section-head">
                <strong>${App.escapeHtml(p.label)}</strong>
                <span class="flag-chip">${App.escapeHtml(p.significance || "info")}</span>
              </div>
              <div class="geo-chip-row">
                <span class="geo-chip">Geographic</span>
                ${p.distance_from_case_km != null ? `<span class="geo-chip">${p.distance_from_case_km.toFixed(0)}km from origin</span>` : ""}
                ${p.lead_count ? `<span class="source-badge">${p.lead_count} leads</span>` : ""}
              </div>
            </div>
          `).join("")}
          ${tempPatterns.map((p) => `
            <div class="pattern-item pattern-${App.escapeHtml(p.significance || "low")}">
              <div class="detail-section-head">
                <strong>${App.escapeHtml(p.label)}</strong>
                <span class="flag-chip">${App.escapeHtml(p.significance || "info")}</span>
              </div>
              <div class="geo-chip-row">
                <span class="geo-chip">Temporal</span>
                ${p.lead_count ? `<span class="source-badge">${p.lead_count} leads</span>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderSelectedCaseCard() {
    const record = state.cases.find((item) => item.id === state.selectedCaseId);
    if (!record) {
      elements.selectedCaseCard.innerHTML =
        '<div class="empty-state">Select a case to load official facts, authority routes, and evidence history.</div>';
      return;
    }

    elements.selectedCaseCard.innerHTML = `
      <div class="detail-stack">
        <div class="detail-top">
          <div>
            <p class="eyebrow">Selected Profile</p>
            <h3>${App.escapeHtml(record.name)}</h3>
            <div class="case-label-row">
              <span class="status-tag status-${record.status}">${App.escapeHtml(
                record.statusLabel
              )}</span>
              <span class="source-badge">${App.escapeHtml(record.city || "Unknown city")}, ${App.escapeHtml(
                record.province
              )}</span>
            </div>
          </div>
          <a class="primary-button" href="${App.buildPageHref("./index.html", {
            ...currentFilters(),
            selectedCaseId: record.id,
          })}" target="_self">Open full profile</a>
        </div>
        <div class="detail-grid">
          <div><strong>Age</strong><p>${record.age ?? "Unknown"}</p></div>
          <div><strong>Missing since</strong><p>${App.formatDate(record.missingSince)}</p></div>
          <div><strong>Authority</strong><p>${App.escapeHtml(record.authority.name || "Official authority")}</p></div>
          <div><strong>Source count</strong><p>${record.sources.length}</p></div>
        </div>
        ${renderOfficialContext(record)}
        <div class="detail-card">
          <div class="detail-section-head"><strong>Official summary</strong><span>Case anchor</span></div>
          <div class="detail-body">${record.summaryHtml || "<p>No official summary provided.</p>"}</div>
        </div>
        <div class="contact-grid">
          ${
            record.authority.url
              ? `<a class="link-button" href="${record.authority.url}" target="_blank" rel="noopener">Authority page</a>`
              : ""
          }
          ${
            record.authority.phone
              ? `<a class="link-button" href="tel:${App.normalizePhone(
                  record.authority.phone
                )}">Call ${App.escapeHtml(record.authority.phone)}</a>`
              : ""
          }
          ${
            record.mcsc.email
              ? `<a class="link-button" href="mailto:${record.mcsc.email}">Email MCSC</a>`
              : ""
          }
        </div>
        ${renderResourcePack()}
      </div>
    `;
  }

  function renderRunSummary() {
    const record = state.cases.find((item) => item.id === state.selectedCaseId) || null;
    const run = state.activeRun;
    const runStatus = run ? run.status : "idle";
    elements.runStatusBadge.textContent = run ? `Run ${run.id} • ${run.status}` : "No run";
    elements.runStatusBadge.className = `status-pill ${runStatus === "completed" ? "is-live" : "is-static"}`;

    if (!run) {
      elements.runSummary.innerHTML = `<div class="empty-state">${App.escapeHtml(
        state.runMessage
      )}</div>`;
      return;
    }

    const stats = run.stats || {};
    elements.runSummary.innerHTML = `
      <div class="metric-grid compact-metrics">
        <article class="metric-card metric-neutral">
          <span class="metric-kicker">Total leads</span>
          <strong class="metric-value">${stats.total_leads ?? 0}</strong>
          <p class="metric-note">Scored public leads in the active run.</p>
        </article>
        <article class="metric-card metric-live">
          <span class="metric-kicker">High confidence</span>
          <strong class="metric-value">${stats.high_confidence_leads ?? 0}</strong>
          <p class="metric-note">Leads at or above the current scoring threshold.</p>
        </article>
        <article class="metric-card metric-alert">
          <span class="metric-kicker">Reviewed</span>
          <strong class="metric-value">${stats.reviewed_leads ?? 0}</strong>
          <p class="metric-note">Human-reviewed items on this run.</p>
        </article>
        <article class="metric-card metric-hot">
          <span class="metric-kicker">Query warnings</span>
          <strong class="metric-value">${(stats.failed_queries ?? 0) + (stats.warning_queries ?? 0)}</strong>
          <p class="metric-note">Failed or warning connector requests.</p>
        </article>
      </div>
      <div class="detail-card">
        <div class="detail-section-head"><strong>Run summary</strong><span>${App.formatDate(
          run.started_at
        )}</span></div>
        <p>${App.escapeHtml(run.inference_summary || "No inference summary provided.")}</p>
        <div class="geo-chip-row">
          ${(run.connectors || [])
            .map((connector) => `<span class="source-badge">${App.escapeHtml(connector)}</span>`)
            .join("") || '<span class="source-badge">No connectors listed</span>'}
        </div>
        ${
          run.error_message
            ? `<p class="warning-copy">${App.escapeHtml(run.error_message)}</p>`
            : ""
        }
        ${
          record
            ? `<p class="metric-note">Official anchor: ${App.escapeHtml(
                record.name
              )} in ${App.escapeHtml(record.city || "Unknown city")}, ${App.escapeHtml(
                record.province
              )}</p>`
            : ""
        }
      </div>
    `;
  }

  function renderRunHistory() {
    if (!state.apiBase) {
      elements.runHistoryList.innerHTML =
        '<div class="empty-state">Set a backend URL to load investigation history.</div>';
      return;
    }

    if (!state.runs.length) {
      elements.runHistoryList.innerHTML =
        '<div class="empty-state">No prior investigation runs exist for the selected case.</div>';
      return;
    }

    elements.runHistoryList.innerHTML = state.runs
      .map(
        (run) => `
        <button class="history-item ${run.id === state.activeRunId ? "active" : ""}" type="button" data-run-id="${run.id}">
          <div>
            <strong>Run ${run.id}</strong>
            <p>${App.escapeHtml(run.status)} • ${App.formatDate(run.started_at)}</p>
          </div>
          <div class="history-meta">
            <span class="source-badge">${run.lead_count ?? 0} leads</span>
            <span class="source-badge">${run.query_count ?? 0} queries</span>
          </div>
        </button>
      `
      )
      .join("");

    elements.runHistoryList.querySelectorAll(".history-item").forEach((button) => {
      button.addEventListener("click", () => {
        state.activeRunId = Number(button.dataset.runId);
        routeState.runId = String(state.activeRunId);
        App.writeRouteState(currentFilters());
        loadRunDetails(state.activeRunId, true);
      });
    });
  }

  function renderLeads() {
    if (!state.activeRun) {
      elements.leadList.innerHTML = `<div class="empty-state">${App.escapeHtml(
        state.runMessage
      )}</div>`;
      return;
    }

    if (!state.leads.length) {
      elements.leadList.innerHTML =
        '<div class="empty-state">No leads match the current confidence or review filters.</div>';
      return;
    }

    elements.leadList.innerHTML = state.leads
      .map(
        (lead) => `
        <article class="detail-card evidence-card ${
          lead.id === state.activeLeadId ? "is-selected" : ""
        }" data-lead-id="${lead.id}">
          <div class="detail-section-head">
            <div>
              <strong>${App.escapeHtml(lead.title || lead.source_name || "Untitled lead")}</strong>
              <p>${App.escapeHtml(lead.source_name || "Unknown source")} • ${App.escapeHtml(
                lead.category || "uncategorized"
              )}</p>
            </div>
            <span class="source-badge">${Math.round((lead.confidence || 0) * 100)}%</span>
          </div>
          <p>${App.escapeHtml(
            lead.summary || lead.content_excerpt || "No public summary available."
          )}</p>
          <div class="geo-chip-row">
            <span class="geo-chip">${App.escapeHtml(lead.source_kind || "clear-web")}</span>
            <span class="geo-chip">${App.escapeHtml(
              lead.location_text || "No public location string"
            )}</span>
            <span class="flag-chip">Trust ${Math.round((lead.source_trust || 0) * 100)}%</span>
            <span class="flag-chip">Corroboration ${lead.corroboration_count ?? 0}</span>
          </div>
          <div class="stack-list tight-stack">
            <div class="resource-item">
              <div>
                <strong>Query used</strong>
                <p>${App.escapeHtml(lead.query_used || "Not logged")}</p>
              </div>
              <span class="source-badge">${App.formatDate(lead.found_at)}</span>
            </div>
            ${
              lead.source_url
                ? `<a class="link-button" href="${lead.source_url}" target="_blank" rel="noopener">Open source link</a>`
                : ""
            }
          </div>
          <div class="geo-chip-row">
            ${(lead.rationale || [])
              .map((item) => `<span class="flag-chip">${App.escapeHtml(item)}</span>`)
              .join("") || '<span class="flag-chip">No scoring rationale attached</span>'}
          </div>
          <div class="review-row">
            <span class="status-tag review-status">${App.escapeHtml(
              lead.review_status || "unreviewed"
            )}</span>
            <div class="action-row">
              <button class="ghost-button review-button ${
                lead.review_status === "route-now" ? "active" : ""
              }" type="button" data-review="route-now" data-lead-id="${lead.id}">Route</button>
              <button class="ghost-button review-button ${
                lead.review_status === "watch" ? "active" : ""
              }" type="button" data-review="watch" data-lead-id="${lead.id}">Watch</button>
              <button class="ghost-button review-button ${
                lead.review_status === "discarded" ? "active" : ""
              }" type="button" data-review="discarded" data-lead-id="${lead.id}">Discard</button>
            </div>
          </div>
        </article>
      `
      )
      .join("");
  }

  function renderQueryLogs() {
    if (!state.activeRun) {
      elements.queryLogList.innerHTML =
        '<div class="empty-state">Run query logs appear here after an investigation starts.</div>';
      return;
    }

    if (!state.queryLogs.length) {
      elements.queryLogList.innerHTML =
        '<div class="empty-state">No connector query logs were returned for this run.</div>';
      return;
    }

    elements.queryLogList.innerHTML = state.queryLogs
      .map(
        (log) => `
        <div class="timeline-item">
          <div>
            <strong>${App.escapeHtml(log.connector_name)}</strong>
            <p>${App.escapeHtml(log.query_used || "No query text logged")}</p>
            ${
              log.notes
                ? `<p class="metric-note">${App.escapeHtml(log.notes)}</p>`
                : ""
            }
          </div>
          <div class="history-meta">
            <span class="status-tag status-${App.escapeHtml(log.status || "missing")}">${App.escapeHtml(
              log.status || "unknown"
            )}</span>
            <span class="source-badge">${log.result_count ?? 0} results</span>
          </div>
        </div>
      `
      )
      .join("");
  }

  function syncEvidenceMap() {
    const record = state.cases.find((item) => item.id === state.selectedCaseId) || null;
    App.renderEvidenceMarkers(
      state.mapContext,
      record,
      state.leads,
      state.activeLeadId,
      (leadId) => {
        state.activeLeadId = leadId;
        renderLeads();
        syncEvidenceMap();
      }
    );
  }

  function updateNavigationLinks() {
    const sharedState = currentFilters();
    if (elements.profilesNavLink) {
      elements.profilesNavLink.href = App.buildPageHref("./index.html", sharedState);
    }
    if (elements.openProfilesPage) {
      elements.openProfilesPage.href = App.buildPageHref("./index.html", sharedState);
    }
  }

  function renderAll() {
    renderCaseRail();
    renderSelectedCaseCard();
    renderRunSummary();
    renderRunHistory();
    renderLeads();
    renderQueryLogs();
    renderSignalBands();
    syncEvidenceMap();
    updateNavigationLinks();
    // Render MAAT synthesis panel
    if (elements.synthesisContainer) {
      elements.synthesisContainer.innerHTML = renderSynthesisPanel();
    }
    App.writeRouteState(currentFilters());
    elements.runInvestigationButton.disabled = !state.apiBase || !state.selectedCaseId || state.loadingRun;
  }

  function clearRunState(message) {
    clearPoll();
    state.activeRun = null;
    state.activeRunId = null;
    state.leads = [];
    state.queryLogs = [];
    state.synthesis = null;
    state.activeLeadId = null;
    state.runMessage = message;
    routeState.runId = "";
  }

  async function loadRunDetails(runId, shouldPoll) {
    if (!runId) {
      clearRunState("No investigation run selected.");
      renderAll();
      return;
    }

    clearPoll();

    try {
      const [runPayload, leadsPayload, queryPayload, synthesisPayload] = await Promise.all([
        App.getRun(state.apiBase, runId),
        App.getRunLeads(state.apiBase, runId, {
          reviewStatus: elements.reviewStatusSelect.value,
          minConfidence: elements.minConfidenceInput.value || "0",
          limit: elements.leadLimitSelect.value || "100",
        }),
        App.getRunQueryLogs(state.apiBase, runId),
        App.getRunSynthesis(state.apiBase, runId).catch(() => null),
      ]);

      state.activeRunId = runId;
      state.activeRun = runPayload;
      state.leads = leadsPayload.leads || [];
      state.queryLogs = queryPayload.query_logs || [];
      state.synthesis = synthesisPayload;
      state.runMessage = "Investigation data loaded.";
      routeState.runId = String(runId);
      renderAll();

      if (
        shouldPoll &&
        state.activeRun &&
        (state.activeRun.status === "queued" || state.activeRun.status === "running")
      ) {
        pollHandle = window.setTimeout(() => {
          loadRunDetails(runId, true);
        }, 3000);
      }
    } catch (error) {
      clearRunState(error.message);
      renderAll();
      setBackendStatus(error.message, error.status === 403 ? "alert" : "static");
    }
  }

  async function loadCaseRuns() {
    const record = state.cases.find((item) => item.id === state.selectedCaseId) || null;
    if (!record) {
      state.resourcePack = null;
      clearRunState("Select a case to inspect investigation runs.");
      renderAll();
      return;
    }

    if (!state.apiBase) {
      state.resourcePack = null;
      clearRunState("Set a backend URL to enable investigation history and evidence gathering.");
      setBackendStatus("Backend URL required for evidence gathering.", "alert");
      renderAll();
      return;
    }

    try {
      const [runsPayload, resourcePayload] = await Promise.all([
        App.listCaseRuns(state.apiBase, record.id, 10),
        App.getCaseResourcePack(state.apiBase, record.id).catch(() => null),
      ]);
      state.runs = runsPayload.runs || [];
      state.resourcePack = resourcePayload;
      if (!state.activeRunId || !state.runs.some((run) => run.id === state.activeRunId)) {
        state.activeRunId = state.runs[0] ? state.runs[0].id : null;
      }
      setBackendStatus(`Backend connected to ${state.apiBase}`, "live");
      if (state.activeRunId) {
        await loadRunDetails(state.activeRunId, true);
      } else {
        clearRunState("No prior investigation runs for this case. Start one to gather evidence.");
        renderAll();
      }
    } catch (error) {
      state.runs = [];
      state.resourcePack = null;
      clearRunState(error.message);
      renderAll();
      setBackendStatus(error.message, error.status === 403 ? "alert" : "static");
    }
  }

  async function selectCase(caseId) {
    if (state.selectedCaseId === caseId) return;
    state.selectedCaseId = caseId;
    routeState.selectedCaseId = String(caseId);
    state.runs = [];
    state.resourcePack = null;
    clearRunState("Loading investigation history for the selected case.");
    renderAll();
    await loadCaseRuns();
  }

  async function saveApiBase() {
    state.apiBase = App.normalizeApiBase(elements.apiBaseInput.value);
    App.storeApiBase(state.apiBase);
    routeState.apiBase = state.apiBase;
    if (!state.apiBase) {
      clearRunState("Set a backend URL to enable evidence gathering.");
      setBackendStatus("Backend URL required for evidence gathering.", "alert");
      renderAll();
      return;
    }
    await loadCaseRuns();
  }

  async function runInvestigation() {
    const record = state.cases.find((item) => item.id === state.selectedCaseId);
    if (!record) return;

    state.loadingRun = true;
    elements.runInvestigationButton.disabled = true;
    setBackendStatus(`Starting evidence sweep for ${record.name}...`, "live");

    try {
      const payload = await App.runInvestigation(state.apiBase, record.id);
      state.activeRunId = payload.run_id;
      routeState.runId = String(payload.run_id);
      await loadCaseRuns();
    } catch (error) {
      clearRunState(error.message);
      renderAll();
      setBackendStatus(error.message, error.status === 403 ? "alert" : "static");
    } finally {
      state.loadingRun = false;
      elements.runInvestigationButton.disabled = !state.apiBase || !state.selectedCaseId;
    }
  }

  async function reviewLead(leadId, decision) {
    try {
      await App.reviewLead(
        state.apiBase,
        leadId,
        decision,
        `Set to ${decision} in the evidence dashboard.`
      );
      await loadRunDetails(state.activeRunId, false);
    } catch (error) {
      setBackendStatus(error.message, error.status === 403 ? "alert" : "static");
    }
  }

  function applyDatasetMeta(meta) {
    const liveMode = meta.dataset_mode === "live-arcgis";
    elements.dataModeBadge.textContent = liveMode ? "Live source" : "Bundled export";
    elements.dataModeBadge.classList.toggle("is-live", liveMode);
    elements.dataModeBadge.classList.toggle("is-static", !liveMode);
    elements.feedTimestamp.textContent = `${meta.source_name} • ${App.formatDate(
      meta.generated_at
    )}`;
  }

  async function loadDataset(preferLive) {
    const dataset = await App.loadDataset(preferLive);
    state.datasetMeta = dataset.meta;
    state.cases = dataset.cases;
    state.resourcePack = null;
    applyDatasetMeta(dataset.meta);
    populateCaseFilters();
    state.filteredCases = filteredCases();
    state.selectedCaseId = routeState.selectedCaseId
      ? Number(routeState.selectedCaseId)
      : state.filteredCases[0]
        ? state.filteredCases[0].id
        : state.cases[0]
          ? state.cases[0].id
          : null;
    if (
      state.filteredCases.length &&
      !state.filteredCases.some((item) => item.id === state.selectedCaseId)
    ) {
      state.selectedCaseId = state.filteredCases[0].id;
    }
    renderAll();
    await loadCaseRuns();
  }

  function bindControls() {
    [elements.caseSearchInput, elements.provinceSelect, elements.sortSelect].forEach((element) => {
      element.addEventListener("input", () => {
        routeState = { ...routeState, ...currentFilters() };
        const visibleCases = filteredCases();
        if (
          visibleCases.length &&
          !visibleCases.some((item) => item.id === state.selectedCaseId)
        ) {
          selectCase(visibleCases[0].id);
          return;
        }
        renderAll();
      });
      element.addEventListener("change", () => {
        routeState = { ...routeState, ...currentFilters() };
        const visibleCases = filteredCases();
        if (
          visibleCases.length &&
          !visibleCases.some((item) => item.id === state.selectedCaseId)
        ) {
          selectCase(visibleCases[0].id);
          return;
        }
        renderAll();
      });
    });

    [elements.reviewStatusSelect, elements.minConfidenceInput, elements.leadLimitSelect].forEach(
      (element) => {
        element.addEventListener("change", () => {
          routeState = { ...routeState, ...currentFilters() };
          App.writeRouteState(currentFilters());
          if (state.activeRunId) {
            loadRunDetails(state.activeRunId, false);
          } else {
            renderAll();
          }
        });
      }
    );

    elements.saveApiBaseButton.addEventListener("click", () => {
      saveApiBase();
    });
    elements.apiBaseInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        saveApiBase();
      }
    });
    elements.runInvestigationButton.addEventListener("click", () => {
      runInvestigation();
    });
    elements.refreshRunsButton.addEventListener("click", () => {
      loadCaseRuns();
    });
    elements.liveModeButton.addEventListener("click", async () => {
      routeState.live = true;
      await loadDataset(true);
    });
    elements.leadList.addEventListener("click", (event) => {
      const reviewButton = event.target.closest("[data-review]");
      if (reviewButton) {
        reviewLead(Number(reviewButton.dataset.leadId), reviewButton.dataset.review);
        return;
      }
      const leadCard = event.target.closest("[data-lead-id]");
      if (leadCard) {
        state.activeLeadId = Number(leadCard.dataset.leadId);
        renderLeads();
        syncEvidenceMap();
      }
    });
  }

  async function initEvidencePage() {
    syncControlsFromRoute();
    state.mapContext = App.createMap("evidenceMap", "dark");
    bindControls();
    await loadDataset(routeState.live);
  }

  initEvidencePage().catch((error) => {
    console.error(error);
    setBackendStatus(error.message, "static");
    elements.selectedCaseCard.innerHTML =
      '<div class="empty-state">Unable to load evidence workspace right now.</div>';
    elements.runSummary.innerHTML =
      '<div class="empty-state">Evidence data could not be loaded.</div>';
  });
})();
