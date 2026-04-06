(function () {
  if (!window.OsintMissingPersons || document.body.dataset.page !== "profiles") {
    return;
  }

  const App = window.OsintMissingPersons;

  const state = {
    datasetMeta: null,
    referenceLayers: null,
    cases: [],
    filteredCases: [],
    selectedCaseId: null,
    viewMode: "list",
    mapContext: null,
  };

  const elements = {
    dataModeBadge: document.getElementById("dataModeBadge"),
    feedTimestamp: document.getElementById("feedTimestamp"),
    feedSafetyNotice: document.getElementById("feedSafetyNotice"),
    metricsGrid: document.getElementById("metricsGrid"),
    signalRibbon: document.getElementById("signalRibbon"),
    signalTicker: document.getElementById("signalTicker"),
    signalQueue: document.getElementById("signalQueue"),
    caseList: document.getElementById("caseList"),
    detailPanel: document.getElementById("detailPanel"),
    provinceSelect: document.getElementById("provinceSelect"),
    citySelect: document.getElementById("citySelect"),
    statusSelect: document.getElementById("statusSelect"),
    sortSelect: document.getElementById("sortSelect"),
    searchInput: document.getElementById("searchInput"),
    minAgeInput: document.getElementById("minAgeInput"),
    maxAgeInput: document.getElementById("maxAgeInput"),
    resultsCount: document.getElementById("resultsCount"),
    provinceStrip: document.getElementById("provinceStrip"),
    recentUpdatesList: document.getElementById("recentUpdatesList"),
    provinceResourcesList: document.getElementById("provinceResourcesList"),
    fitMapButton: document.getElementById("fitMapButton"),
    resetFiltersButton: document.getElementById("resetFiltersButton"),
    liveModeButton: document.getElementById("liveModeButton"),
    evidenceNavLink: document.getElementById("evidenceNavLink"),
    openEvidencePage: document.getElementById("openEvidencePage"),
  };

  let routeState = App.readRouteState();

  function currentFilters() {
    return {
      search: elements.searchInput.value.trim(),
      province: elements.provinceSelect.value,
      city: elements.citySelect.value,
      minAge: elements.minAgeInput.value,
      maxAge: elements.maxAgeInput.value,
      status: elements.statusSelect.value,
      sort: elements.sortSelect.value,
      view: state.viewMode,
      selectedCaseId: state.selectedCaseId,
      live: routeState.live,
      apiBase: routeState.apiBase,
    };
  }

  function populateSelect(select, values, placeholder) {
    const current = select.value;
    select.innerHTML = `<option value="">${placeholder}</option>`;
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      if (value === current) option.selected = true;
      select.appendChild(option);
    });
  }

  function syncControlsFromRoute() {
    elements.searchInput.value = routeState.search || "";
    elements.minAgeInput.value = routeState.minAge || "";
    elements.maxAgeInput.value = routeState.maxAge || "";
    elements.statusSelect.value = routeState.status || "";
    elements.sortSelect.value = routeState.sort || "recency";
    state.viewMode = routeState.view || "list";
    document.querySelectorAll(".toggle-button").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === state.viewMode);
    });
  }

  function updateFilterOptions() {
    populateSelect(
      elements.provinceSelect,
      App.uniqueValues(state.cases, (item) => item.province),
      "All provinces"
    );
    elements.provinceSelect.value = routeState.province || "";
    const citySource = routeState.province
      ? state.cases.filter((item) => item.province === routeState.province)
      : state.cases;
    populateSelect(
      elements.citySelect,
      App.uniqueValues(citySource, (item) => item.city),
      "All cities"
    );
    elements.citySelect.value = routeState.city || "";
  }

  function renderProvinceStrip(records) {
    const counts = {};
    records.forEach((record) => {
      counts[record.province] = (counts[record.province] || 0) + 1;
    });
    elements.provinceStrip.innerHTML = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(
        ([province, count]) =>
          `<span class="province-chip">${App.escapeHtml(province)} ${count}</span>`
      )
      .join("");
  }

  function renderMetrics(container, summary) {
    container.innerHTML = [
      {
        label: "Tracked cases",
        value: summary.total,
        note: "Visible in the current query scope.",
        tone: "neutral",
      },
      {
        label: "Priority statuses",
        value: summary.highRisk,
        note: "Amber, vulnerable, and child-search escalations.",
        tone: "alert",
      },
      {
        label: "Updated in 30 days",
        value: summary.recent,
        note: "Recently active records worth reviewing first.",
        tone: "live",
      },
      {
        label: "Latest sync",
        value: summary.latestUpdate ? App.formatDate(summary.latestUpdate) : "Unavailable",
        note: "Most recent public update timestamp in scope.",
        tone: "hot",
      },
    ]
      .map(
        (metric) => `
        <article class="metric-card metric-${metric.tone}">
          <span class="metric-kicker">${metric.label}</span>
          <strong class="metric-value">${metric.value}</strong>
          <p class="metric-note">${metric.note}</p>
        </article>
      `
      )
      .join("");
  }

  function renderSignalBands(records) {
    const items = App.buildCaseSignalItems(records, state.datasetMeta);
    App.renderMarquee(elements.signalRibbon, items, "signal-ribbon-track");
    App.renderMarquee(elements.signalTicker, items, "signal-marquee-track");
  }

  function renderSignalQueue(container, records) {
    const items = [...records]
      .sort(
        (a, b) =>
          (b.riskRank ?? 0) - (a.riskRank ?? 0) ||
          new Date(b.updatedAt || b.missingSince || 0) -
            new Date(a.updatedAt || a.missingSince || 0)
      )
      .slice(0, 5);

    if (!items.length) {
      container.innerHTML =
        '<div class="empty-state">No cases match the current filters, so no signal queue is visible.</div>';
      return;
    }

    container.innerHTML = items
      .map(
        (record) => `
        <div class="signal-item priority-${record.riskRank ?? 1}">
          <div class="signal-item-head">
            <div>
              <strong>${App.escapeHtml(record.name)}</strong>
              <p>${App.escapeHtml(record.city || "Unknown city")}, ${App.escapeHtml(
                record.province
              )}</p>
            </div>
            <span class="signal-priority">P${record.riskRank ?? 1}</span>
          </div>
          <p>${App.escapeHtml(record.inferenceSummary)}</p>
          <div class="source-row">
            <span class="status-tag status-${record.status}">${App.escapeHtml(
              record.statusLabel
            )}</span>
            <span class="flag-chip">Elapsed ${App.formatElapsed(record.elapsedDays)}</span>
            <span class="geo-chip">${App.escapeHtml(
              record.geoContext && record.geoContext[0]
                ? record.geoContext[0].label
                : "No nearby public layer"
            )}</span>
            <span class="source-badge">${record.sources.length} source${
              record.sources.length === 1 ? "" : "s"
            }</span>
          </div>
        </div>
      `
      )
      .join("");
  }

  function renderRecentUpdates(container, records) {
    const items = [...records]
      .sort((a, b) => new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0))
      .slice(0, 5);
    container.innerHTML = items
      .map(
        (record) => `
        <div class="update-item">
          <div>
            <strong>${App.escapeHtml(record.name)}</strong>
            <p>${App.escapeHtml(record.city || "Unknown city")}, ${App.escapeHtml(
              record.province
            )}</p>
          </div>
          <div class="update-meta">
            <span class="status-tag status-${record.status}">${App.escapeHtml(
              record.statusLabel
            )}</span>
            <span class="source-badge">${App.formatDate(
              record.updatedAt || record.missingSince
            )}</span>
          </div>
        </div>
      `
      )
      .join("");
  }

  function renderProvinceResources(container, records) {
    const byProvince = new Map();
    records.forEach((record) => {
      if (!byProvince.has(record.province)) {
        byProvince.set(record.province, record.resources || []);
      }
    });

    container.innerHTML = [...byProvince.entries()]
      .map(
        ([province, resources]) => `
        <div class="resource-item">
          <div>
            <strong>${App.escapeHtml(province)}</strong>
            <p>${resources
              .map(
                (item) =>
                  `<a href="${item.url}" target="_blank" rel="noopener">${App.escapeHtml(
                    item.label
                  )}</a>`
              )
              .join(" • ")}</p>
          </div>
          <span class="source-badge">${resources.length} route${
            resources.length === 1 ? "" : "s"
          }</span>
        </div>
      `
      )
      .join("");
  }

  function buildChartRows(entries) {
    const max = Math.max(...entries.map((entry) => entry.value), 1);
    return entries
      .map(
        (entry) => `
        <div class="chart-row">
          <div class="detail-section-head"><strong>${entry.label}</strong><span>${entry.value}</span></div>
          <div class="chart-bar"><span style="width:${(entry.value / max) * 100}%"></span></div>
        </div>
      `
      )
      .join("");
  }

  function renderCharts(cases) {
    const provinceCounts = {};
    const ageCounts = { "0-5": 0, "6-10": 0, "11-15": 0, "16-18": 0, Unknown: 0 };
    const statusCounts = {};
    const trendCounts = {};

    cases.forEach((record) => {
      provinceCounts[record.province] = (provinceCounts[record.province] || 0) + 1;
      statusCounts[record.statusLabel] = (statusCounts[record.statusLabel] || 0) + 1;
      if (record.age === null || record.age === undefined) ageCounts.Unknown += 1;
      else if (record.age <= 5) ageCounts["0-5"] += 1;
      else if (record.age <= 10) ageCounts["6-10"] += 1;
      else if (record.age <= 15) ageCounts["11-15"] += 1;
      else ageCounts["16-18"] += 1;
      const trendKey = (record.updatedAt || record.missingSince || "").slice(0, 10);
      trendCounts[trendKey] = (trendCounts[trendKey] || 0) + 1;
    });

    document.getElementById("provinceChart").innerHTML = buildChartRows(
      Object.entries(provinceCounts).map(([label, value]) => ({ label, value }))
    );
    document.getElementById("ageChart").innerHTML = buildChartRows(
      Object.entries(ageCounts).map(([label, value]) => ({ label, value }))
    );
    document.getElementById("statusChart").innerHTML = buildChartRows(
      Object.entries(statusCounts).map(([label, value]) => ({ label, value }))
    );

    const trendEntries = Object.entries(trendCounts).sort((a, b) => a[0].localeCompare(b[0]));
    const max = Math.max(...trendEntries.map((entry) => entry[1]), 1);
    document.getElementById("trendChart").innerHTML = `
      <div class="sparkline">
        ${trendEntries
          .map(
            ([label, value]) =>
              `<div title="${App.formatDate(label)}: ${value}" class="sparkline-bar" style="height:${Math.max(
                16,
                (value / max) * 140
              )}px"></div>`
          )
          .join("")}
      </div>
    `;
  }

  function renderCaseList(container, records, selectedCaseId, viewMode, onSelect) {
    container.className = `case-list ${viewMode}-view`;
    if (!records.length) {
      container.innerHTML =
        '<div class="empty-state">No active profiles match the current filters.</div>';
      return;
    }

    container.innerHTML = records
      .map(
        (record) => `
        <article class="case-card ${record.id === selectedCaseId ? "active" : ""}" data-case-id="${record.id}">
          <div class="case-card-media">
            <img src="${
              record.photos && record.photos[0] && record.photos[0].thumb_url
                ? record.photos[0].thumb_url
                : "./assets/case-a.svg"
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
            <p class="case-card-context">${App.escapeHtml(
              record.geoContext && record.geoContext[0]
                ? record.geoContext[0].label
                : "No nearby public context layer"
            )}</p>
            <div class="source-row">
              ${
                (record.riskFlags || [])
                  .slice(0, 2)
                  .map((flag) => `<span class="flag-chip">${App.escapeHtml(flag)}</span>`)
                  .join("") || '<span class="flag-chip">No derived flags</span>'
              }
              <span class="source-badge">${App.escapeHtml(
                record.sources[0] && record.sources[0].label
                  ? record.sources[0].label
                  : "Official source"
              )}</span>
              <span class="source-badge">Elapsed ${App.formatElapsed(
                record.elapsedDays
              )}</span>
            </div>
          </div>
        </article>
      `
      )
      .join("");

    container.querySelectorAll(".case-card").forEach((card) => {
      card.addEventListener("click", () => onSelect(Number(card.dataset.caseId), true));
    });
  }

  function renderDetail(container, record) {
    if (!record) {
      container.innerHTML = `
        <div class="empty-state">
          <p class="eyebrow">Select a case</p>
          <h3>Open a case file to inspect official facts, public context, reporting routes, and source trails.</h3>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="detail-stack">
        <div class="detail-top">
          <div>
            <p class="eyebrow">Selected Case</p>
            <h3>${App.escapeHtml(record.name)}</h3>
            <div class="case-label-row">
              <span class="status-tag status-${record.status}">${App.escapeHtml(
                record.statusLabel
              )}</span>
              <span class="source-badge">Case ${record.id}</span>
              <span class="source-badge">${App.escapeHtml(record.slug)}</span>
            </div>
          </div>
          <button class="primary-button" id="printCaseButton" type="button">Print packet</button>
        </div>

        <div class="detail-photo-grid">
          ${
            (record.photos || [])
              .map(
                (photo) =>
                  `<img src="${photo.url}" alt="${App.escapeHtml(record.name)}" loading="lazy">`
              )
              .join("") || '<div class="empty-state">No photo provided</div>'
          }
        </div>

        <div class="detail-card">
          <div class="detail-section-head"><strong>Official facts</strong><span>Primary record</span></div>
          <div class="detail-grid">
            <div><strong>City</strong><p>${App.escapeHtml(record.city || "Not listed")}</p></div>
            <div><strong>Province</strong><p>${App.escapeHtml(record.province || "Not listed")}</p></div>
            <div><strong>Age</strong><p>${record.age ?? "Unknown"}</p></div>
            <div><strong>Missing since</strong><p>${App.formatDate(record.missingSince)}</p></div>
            <div><strong>Last update</strong><p>${App.formatDate(record.updatedAt)}</p></div>
            <div><strong>Authority</strong><p>${App.escapeHtml(
              record.authority.name || "Official authority"
            )}</p></div>
          </div>
          <div class="detail-body">${App.sanitizeHtml(record.summaryHtml) || "<p>No official summary provided.</p>"}</div>
        </div>

        <div class="inference-card">
          <div class="detail-section-head"><strong>Unverified signal layer</strong><span>Derived context only</span></div>
          <p>${App.escapeHtml(record.inferenceSummary)}</p>
          <div class="geo-chip-row">
            ${
              (record.geoContext || [])
                .map(
                  (item) =>
                    `<span class="geo-chip">${App.escapeHtml(item.context_type)} • ${App.escapeHtml(
                      item.label
                    )} • ${item.distance_km ?? "?"} km</span>`
                )
                .join("") || '<span class="geo-chip">No bundled geospatial context</span>'
            }
          </div>
          <div class="geo-chip-row">
            ${
              (record.riskFlags || [])
                .map((flag) => `<span class="flag-chip">${App.escapeHtml(flag)}</span>`)
                .join("") || '<span class="flag-chip">No derived flags</span>'
            }
            <span class="flag-chip">Elapsed ${App.formatElapsed(record.elapsedDays)}</span>
            <span class="flag-chip">Estimated current age ${
              record.estimatedCurrentAge ?? "Unknown"
            }</span>
            <span class="flag-chip">${record.sources.length} source trail</span>
          </div>
        </div>

        <div class="detail-card">
          <div class="detail-section-head"><strong>Authority contacts</strong><span>Report, do not intervene</span></div>
          <div class="contact-grid">
            ${
              record.authority.url
                ? `<a class="link-button" href="${record.authority.url}" target="_blank" rel="noopener">Open authority page</a>`
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
        </div>

        <div class="detail-card">
          <div class="detail-section-head"><strong>What to report</strong><span>Checklist</span></div>
          <ul class="checklist">${record.whatToReport
            .map((item) => `<li>${App.escapeHtml(item)}</li>`)
            .join("")}</ul>
        </div>

        <div class="detail-card">
          <div class="detail-section-head"><strong>How to help safely</strong><span>Guardrail</span></div>
          <ul class="checklist">${record.howToHelpSafely
            .map((item) => `<li>${App.escapeHtml(item)}</li>`)
            .join("")}</ul>
        </div>

        <div class="detail-card">
          <div class="detail-section-head"><strong>Source attribution</strong><span>Transparency</span></div>
          <div class="stack-list">
            ${record.sources
              .map(
                (source) => `
                <div class="resource-item">
                  <div>
                    <strong>${App.escapeHtml(source.label)}</strong>
                    <p><a href="${source.source_url}" target="_blank" rel="noopener">${App.escapeHtml(
                      source.source_url
                    )}</a></p>
                  </div>
                  <span class="source-badge">${source.official ? "Official" : "Public"}</span>
                </div>
              `
              )
              .join("")}
          </div>
        </div>

        <div class="detail-card">
          <div class="detail-section-head"><strong>Timeline</strong><span>${record.timelineEntries.length} entries</span></div>
          <div class="stack-list">
            ${record.timelineEntries
              .map(
                (entry) => `
                <div class="timeline-item">
                  <div>
                    <strong>${App.escapeHtml(entry.label)}</strong>
                    <p>${entry.kind === "derived" ? "Derived" : "Official"}</p>
                  </div>
                  <span class="source-badge">${App.formatDate(entry.date)}</span>
                </div>
              `
              )
              .join("")}
          </div>
        </div>
      </div>
    `;

    const printButton = container.querySelector("#printCaseButton");
    if (printButton) {
      printButton.addEventListener("click", () => window.print());
    }
  }

  function updateNavigationLinks() {
    const sharedState = currentFilters();
    if (elements.evidenceNavLink) {
      elements.evidenceNavLink.href = App.buildPageHref("./evidence.html", sharedState);
    }
    if (elements.openEvidencePage) {
      elements.openEvidencePage.href = App.buildPageHref("./evidence.html", sharedState);
    }
  }

  function renderAll() {
    const filters = currentFilters();
    state.filteredCases = App.filterCases(state.cases, filters);
    if (!state.filteredCases.some((item) => item.id === state.selectedCaseId)) {
      state.selectedCaseId = state.filteredCases[0] ? state.filteredCases[0].id : null;
    }
    filters.selectedCaseId = state.selectedCaseId;
    routeState = { ...routeState, ...filters };
    App.writeRouteState(filters);

    const displayRecords = state.filteredCases.length ? state.filteredCases : state.cases;
    const selected =
      state.filteredCases.find((item) => item.id === state.selectedCaseId) ||
      state.cases.find((item) => item.id === state.selectedCaseId) ||
      null;

    renderCaseList(
      elements.caseList,
      state.filteredCases,
      state.selectedCaseId,
      state.viewMode,
      selectCase
    );
    App.renderCaseMarkers(
      state.mapContext,
      state.filteredCases,
      state.selectedCaseId,
      selectCase
    );
    renderDetail(elements.detailPanel, selected);
    renderMetrics(elements.metricsGrid, App.summarizeCases(displayRecords));
    renderSignalBands(displayRecords);
    renderSignalQueue(elements.signalQueue, state.filteredCases);
    renderRecentUpdates(elements.recentUpdatesList, displayRecords);
    renderProvinceResources(elements.provinceResourcesList, state.cases);
    renderCharts(displayRecords);
    renderProvinceStrip(state.filteredCases);
    elements.resultsCount.textContent = `${state.filteredCases.length} result${
      state.filteredCases.length === 1 ? "" : "s"
    }`;
    updateNavigationLinks();
  }

  function selectCase(caseId, flyTo) {
    state.selectedCaseId = caseId;
    routeState.selectedCaseId = String(caseId);
    renderAll();
    if (flyTo) {
      const marker = state.mapContext.markerIndex.get(caseId);
      const selected =
        state.filteredCases.find((item) => item.id === caseId) ||
        state.cases.find((item) => item.id === caseId);
      if (marker && selected) {
        state.mapContext.map.flyTo([selected.latitude, selected.longitude], 8, {
          duration: App.prefersReducedMotion ? 0 : 0.8,
        });
        marker.openPopup();
      }
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
    elements.feedSafetyNotice.textContent = meta.safety_notice || "";
    document.body.dataset.feedMode = liveMode ? "live" : "static";
  }

  async function loadAndRender(preferLive) {
    const dataset = await App.loadDataset(preferLive);
    state.datasetMeta = dataset.meta;
    state.referenceLayers = dataset.referenceLayers;
    state.cases = dataset.cases;
    state.selectedCaseId = routeState.selectedCaseId
      ? Number(routeState.selectedCaseId)
      : dataset.cases[0]
        ? dataset.cases[0].id
        : null;
    applyDatasetMeta(dataset.meta);
    updateFilterOptions();
    renderAll();
  }

  function bindControls() {
    [
      elements.searchInput,
      elements.provinceSelect,
      elements.citySelect,
      elements.minAgeInput,
      elements.maxAgeInput,
      elements.statusSelect,
      elements.sortSelect,
    ].forEach((element) => {
      element.addEventListener("input", () => {
        routeState = { ...routeState, ...currentFilters() };
        updateFilterOptions();
        renderAll();
      });
      element.addEventListener("change", () => {
        routeState = { ...routeState, ...currentFilters() };
        updateFilterOptions();
        renderAll();
      });
    });

    document.querySelectorAll(".toggle-button").forEach((button) => {
      button.addEventListener("click", () => {
        state.viewMode = button.dataset.view;
        routeState.view = state.viewMode;
        document.querySelectorAll(".toggle-button").forEach((item) => {
          item.classList.toggle("active", item === button);
        });
        renderAll();
      });
    });

    elements.fitMapButton.addEventListener("click", () =>
      App.fitToRecords(state.mapContext, state.filteredCases)
    );
    elements.resetFiltersButton.addEventListener("click", () => {
      routeState = {
        search: "",
        province: "",
        city: "",
        minAge: "",
        maxAge: "",
        status: "",
        sort: "recency",
        view: "list",
        selectedCaseId: "",
        live: routeState.live,
        apiBase: routeState.apiBase,
      };
      syncControlsFromRoute();
      updateFilterOptions();
      renderAll();
    });
    elements.liveModeButton.addEventListener("click", async () => {
      routeState.live = true;
      await loadAndRender(true);
    });
  }

  async function initDashboard() {
    syncControlsFromRoute();
    state.mapContext = App.createMap("map", "dark");
    bindControls();
    await loadAndRender(routeState.live);
  }

  initDashboard().catch((error) => {
    console.error(error);
    elements.detailPanel.innerHTML =
      '<div class="empty-state">Unable to load case data right now.</div>';
    elements.caseList.innerHTML =
      '<div class="empty-state">Unable to load active profiles right now.</div>';
    elements.dataModeBadge.textContent = "Load failed";
    elements.feedTimestamp.textContent = error.message;
  });
})();
