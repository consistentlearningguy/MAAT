export function readRouteState() {
  const params = new URLSearchParams(window.location.search);
  return {
    search: params.get("q") || "",
    province: params.get("province") || "",
    city: params.get("city") || "",
    minAge: params.get("minAge") || "",
    maxAge: params.get("maxAge") || "",
    status: params.get("status") || "",
    sort: params.get("sort") || "recency",
    view: params.get("view") || "list",
    selectedCaseId: params.get("case") || "",
    live: params.get("live") === "1",
  };
}

export function writeRouteState(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "" || value === false) {
      return;
    }
    if (key === "selectedCaseId") {
      params.set("case", String(value));
      return;
    }
    if (key === "live") {
      params.set("live", "1");
      return;
    }
    params.set(key, String(value));
  });
  const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
  window.history.replaceState({}, "", next);
}
