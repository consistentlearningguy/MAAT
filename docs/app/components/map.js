export function createMap(containerId) {
  const map = L.map(containerId, {
    center: [56.1304, -106.3468],
    zoom: 4,
    scrollWheelZoom: true,
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);

  const layer = L.layerGroup().addTo(map);
  return { map, layer, markerIndex: new Map() };
}

function markerClass(record, isSelected) {
  return `marker-shell marker-${record.status}${isSelected ? " is-selected" : ""}`;
}

export function renderMapMarkers(mapContext, records, selectedCaseId, onSelect) {
  mapContext.layer.clearLayers();
  mapContext.markerIndex.clear();
  const bounds = [];

  records.forEach((record) => {
    if (record.latitude === null || record.longitude === null) return;
    const marker = L.marker([record.latitude, record.longitude], {
      icon: L.divIcon({
        className: "",
        html: `
          <span class="${markerClass(record, record.id === selectedCaseId)}">
            <span class="marker-ring"></span>
            <span class="marker-core"></span>
            <span class="marker-ping"></span>
          </span>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      }),
    });
    marker.on("click", () => onSelect(record.id, true));
    marker.bindPopup(`<strong>${record.name}</strong><br>${record.city || "Unknown city"}, ${record.province}<br>${record.statusLabel}`);
    marker.addTo(mapContext.layer);
    mapContext.markerIndex.set(record.id, marker);
    bounds.push([record.latitude, record.longitude]);
  });

  if (bounds.length) {
    mapContext.map.fitBounds(L.latLngBounds(bounds).pad(0.22), { maxZoom: 7 });
  }
}

export function fitToRecords(mapContext, records) {
  const points = records.filter((record) => record.latitude !== null && record.longitude !== null).map((record) => [record.latitude, record.longitude]);
  if (!points.length) return;
  mapContext.map.fitBounds(L.latLngBounds(points).pad(0.22), { maxZoom: 7 });
}
