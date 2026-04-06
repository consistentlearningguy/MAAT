import { renderCaseList } from "../components/case-list.js";
import { renderDetail } from "../components/detail.js";
import { createMap, fitToRecords, renderMapMarkers } from "../components/map.js";
import {
  renderMetrics,
  renderProvinceResources,
  renderRecentUpdates,
  renderSignalQueue,
  renderSignalTicker,
} from "../components/stats.js";
import { loadDataset } from "../lib/data.js";
import { filterCases, summarizeCases } from "../lib/filters.js";
import { renderCharts } from "../lib/charts.js";
import { formatDate, uniqueValues } from "../lib/formatters.js";
import { readRouteState, writeRouteState } from "../lib/router.js";
import { getSelectedCase, state } from "../state/store.js";

const elements = {
  dataModeBadge: document.getElementById("dataModeBadge"),
  feedTimestamp: document.getElementById("feedTimestamp"),
  metricsGrid: document.getElementById("metricsGrid"),
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
};

let routeState = readRouteState();

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
  populateSelect(elements.provinceSelect, uniqueValues(state.cases, (item) => item.province), "All provinces");
  elements.provinceSelect.value = routeState.province || "";
  const citySource = routeState.province ? state.cases.filter((item) => item.province === routeState.province) : state.cases;
  populateSelect(elements.citySelect, uniqueValues(citySource, (item) => item.city), "All cities");
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
    .map(([province, count]) => `<span class="province-chip">${province} ${count}</span>`)
    .join("");
}

function renderAll() {
  const filters = currentFilters();
  state.filteredCases = filterCases(state.cases, filters);
  if (!state.filteredCases.some((item) => item.id === state.selectedCaseId)) {
    state.selectedCaseId = state.filteredCases[0]?.id || null;
  }
  filters.selectedCaseId = state.selectedCaseId;
  writeRouteState(filters);

  const displayRecords = state.filteredCases.length ? state.filteredCases : state.cases;
  const selected = getSelectedCase();
  renderCaseList(elements.caseList, state.filteredCases, state.selectedCaseId, state.viewMode, selectCase);
  renderMapMarkers(state.mapContext, state.filteredCases, state.selectedCaseId, selectCase);
  renderDetail(elements.detailPanel, selected);
  renderMetrics(elements.metricsGrid, summarizeCases(displayRecords));
  renderSignalTicker(elements.signalTicker, displayRecords, state.datasetMeta);
  renderSignalQueue(elements.signalQueue, state.filteredCases);
  renderRecentUpdates(elements.recentUpdatesList, displayRecords);
  renderProvinceResources(elements.provinceResourcesList, state.cases);
  renderCharts(displayRecords);
  renderProvinceStrip(state.filteredCases);
  elements.resultsCount.textContent = `${state.filteredCases.length} result${state.filteredCases.length === 1 ? "" : "s"}`;
}

function selectCase(caseId, flyTo = false) {
  state.selectedCaseId = caseId;
  routeState.selectedCaseId = String(caseId);
  renderAll();
  if (flyTo) {
    const marker = state.mapContext.markerIndex.get(caseId);
    const selected = getSelectedCase();
    if (marker && selected) {
      state.mapContext.map.flyTo([selected.latitude, selected.longitude], 8, { duration: 0.8 });
      marker.openPopup();
    }
  }
}

function applyDatasetMeta(meta) {
  const liveMode = meta.dataset_mode === "live-arcgis";
  elements.dataModeBadge.textContent = liveMode ? "Live source" : "Bundled export";
  elements.dataModeBadge.classList.toggle("is-live", liveMode);
  elements.dataModeBadge.classList.toggle("is-static", !liveMode);
  elements.feedTimestamp.textContent = `${meta.source_name} • ${formatDate(meta.generated_at)}`;
  document.body.dataset.feedMode = liveMode ? "live" : "static";
}

async function loadAndRender(preferLive = routeState.live) {
  const dataset = await loadDataset(preferLive);
  state.datasetMeta = dataset.meta;
  state.referenceLayers = dataset.referenceLayers;
  state.cases = dataset.cases;
  state.selectedCaseId = routeState.selectedCaseId ? Number(routeState.selectedCaseId) : dataset.cases[0]?.id || null;
  applyDatasetMeta(dataset.meta);
  updateFilterOptions();
  renderAll();
}

function bindControls() {
  [elements.searchInput, elements.provinceSelect, elements.citySelect, elements.minAgeInput, elements.maxAgeInput, elements.statusSelect, elements.sortSelect].forEach((element) => {
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
      document.querySelectorAll(".toggle-button").forEach((item) => item.classList.toggle("active", item === button));
      renderAll();
    });
  });

  elements.fitMapButton.addEventListener("click", () => fitToRecords(state.mapContext, state.filteredCases));
  elements.resetFiltersButton.addEventListener("click", () => {
    routeState = { search: "", province: "", city: "", minAge: "", maxAge: "", status: "", sort: "recency", view: "list", selectedCaseId: "", live: routeState.live };
    syncControlsFromRoute();
    updateFilterOptions();
    renderAll();
  });
  elements.liveModeButton.addEventListener("click", async () => {
    routeState.live = true;
    await loadAndRender(true);
  });
}

export async function initDashboard() {
  syncControlsFromRoute();
  state.mapContext = createMap("map");
  bindControls();
  await loadAndRender(routeState.live);
}
