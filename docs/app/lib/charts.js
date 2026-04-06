import { formatDate } from "./formatters.js";

function buildChartRows(entries) {
  const max = Math.max(...entries.map((entry) => entry.value), 1);
  return entries.map((entry) => `
    <div class="chart-row">
      <div class="detail-section-head"><strong>${entry.label}</strong><span>${entry.value}</span></div>
      <div class="chart-bar"><span style="width:${(entry.value / max) * 100}%"></span></div>
    </div>
  `).join("");
}

export function renderCharts(cases) {
  const provinceCounts = {};
  const ageCounts = { "0-5": 0, "6-10": 0, "11-15": 0, "16-18": 0, Unknown: 0 };
  const statusCounts = {};
  const trendCounts = {};

  for (const record of cases) {
    provinceCounts[record.province] = (provinceCounts[record.province] || 0) + 1;
    statusCounts[record.statusLabel] = (statusCounts[record.statusLabel] || 0) + 1;
    const age = record.age;
    if (age === null || age === undefined) ageCounts.Unknown += 1;
    else if (age <= 5) ageCounts["0-5"] += 1;
    else if (age <= 10) ageCounts["6-10"] += 1;
    else if (age <= 15) ageCounts["11-15"] += 1;
    else ageCounts["16-18"] += 1;
    const trendKey = (record.updatedAt || record.missingSince || "").slice(0, 10);
    trendCounts[trendKey] = (trendCounts[trendKey] || 0) + 1;
  }

  document.getElementById("provinceChart").innerHTML = buildChartRows(Object.entries(provinceCounts).map(([label, value]) => ({ label, value })));
  document.getElementById("ageChart").innerHTML = buildChartRows(Object.entries(ageCounts).map(([label, value]) => ({ label, value })));
  document.getElementById("statusChart").innerHTML = buildChartRows(Object.entries(statusCounts).map(([label, value]) => ({ label, value })));

  const trendEntries = Object.entries(trendCounts).sort((a, b) => a[0].localeCompare(b[0]));
  const max = Math.max(...trendEntries.map(([, value]) => value), 1);
  document.getElementById("trendChart").innerHTML = `
    <div class="sparkline">
      ${trendEntries.map(([label, value]) => `<div title="${formatDate(label)}: ${value}" class="sparkline-bar" style="height:${Math.max(16, (value / max) * 140)}px"></div>`).join("")}
    </div>
  `;
}
