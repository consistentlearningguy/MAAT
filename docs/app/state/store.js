export const state = {
  referenceLayers: null,
  datasetMeta: null,
  cases: [],
  filteredCases: [],
  selectedCaseId: null,
  viewMode: "list",
  mapContext: null,
};

export function getSelectedCase() {
  return state.filteredCases.find((item) => item.id === state.selectedCaseId)
    || state.cases.find((item) => item.id === state.selectedCaseId)
    || null;
}
