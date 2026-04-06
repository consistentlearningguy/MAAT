function textScore(record, query) {
  if (!query) return 1;
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return 1;
  const haystack = record.searchText.toLowerCase();
  let score = 0;
  for (const term of terms) {
    if (haystack.includes(term)) {
      score += term.length > 3 ? 2 : 1;
      continue;
    }
    const compact = haystack.replace(/[^a-z0-9]/g, "");
    if (compact.includes(term.replace(/[^a-z0-9]/g, ""))) {
      score += 0.8;
    }
  }
  return score / terms.length;
}

function compareValues(left, right, mode) {
  switch (mode) {
    case "age-asc":
      return (left.age ?? 99) - (right.age ?? 99);
    case "age-desc":
      return (right.age ?? 0) - (left.age ?? 0);
    case "status":
      return left.statusLabel.localeCompare(right.statusLabel);
    case "name":
      return left.name.localeCompare(right.name);
    case "risk":
      return (right.riskRank ?? 0) - (left.riskRank ?? 0) || (right.elapsedDays ?? 0) - (left.elapsedDays ?? 0);
    case "recency":
    default:
      return new Date(right.missingSince || 0) - new Date(left.missingSince || 0);
  }
}

export function filterCases(cases, filters) {
  const results = cases.filter((record) => {
    if (filters.province && record.province !== filters.province) return false;
    if (filters.city && record.city !== filters.city) return false;
    if (filters.status && record.status !== filters.status) return false;
    if (filters.minAge && (record.age ?? -1) < Number(filters.minAge)) return false;
    if (filters.maxAge && (record.age ?? 99) > Number(filters.maxAge)) return false;
    return textScore(record, filters.search) > 0.45;
  });

  results.sort((left, right) => compareValues(left, right, filters.sort));
  return results;
}

export function summarizeCases(cases) {
  const total = cases.length;
  const highRisk = cases.filter((record) => record.riskRank >= 2).length;
  const recent = cases.filter((record) => (record.elapsedDays ?? 9999) <= 30).length;
  const latestUpdate = [...cases]
    .map((record) => record.updatedAt)
    .filter(Boolean)
    .sort((a, b) => new Date(b) - new Date(a))[0] || null;
  return { total, highRisk, recent, latestUpdate };
}
