export function formatDate(value) {
  if (!value) return "Not available";
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatElapsed(days) {
  if (days === null || days === undefined) return "Unknown elapsed time";
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  if (days < 30) return `${days} days`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month" : `${months} months`;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function normalizePhone(value) {
  return String(value || "").replace(/\s+/g, "").replace(/[^0-9+]/g, "");
}

export function uniqueValues(items, getter) {
  return [...new Set(items.map(getter).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}
