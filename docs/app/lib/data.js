const STATIC_EXPORT_URL = "./data/public-cases.json";
const REFERENCE_URL = "./data/reference-layers.json";
const ARCGIS_URL = "https://services.arcgis.com/Sv9ZXFjH5h1fYAaI/arcgis/rest/services/Missing_Children_Cases_View_Master/FeatureServer/0";

const STATUS_LABELS = {
  missing: "Missing",
  vulnerable: "Vulnerable",
  abudction: "Abduction",
  abduction: "Abduction",
  amberalert: "Amber Alert",
  childsearchalert: "Child Search Alert",
};

const PROVINCE_RESOURCES = {
  Ontario: [
    { label: "Ontario Provincial Police Missing Persons", url: "https://www.opp.ca/index.php?id=132", category: "official-reporting", official: true, authority_type: "police" },
    { label: "Ontario 211 Community Supports", url: "https://211ontario.ca/", category: "support", official: true, authority_type: "provincial" },
  ],
  "British Columbia": [
    { label: "BC RCMP Missing Persons", url: "https://www.rcmp-grc.gc.ca/en/missing-persons", category: "official-reporting", official: true, authority_type: "RCMP" },
    { label: "VictimLinkBC", url: "https://www2.gov.bc.ca/gov/content/justice/criminal-justice/victims-of-crime/victimlinkbc", category: "support", official: true, authority_type: "provincial" },
  ],
  Manitoba: [
    { label: "Manitoba RCMP Missing Persons", url: "https://www.rcmp-grc.gc.ca/en/missing-persons", category: "official-reporting", official: true, authority_type: "RCMP" },
  ],
  Quebec: [
    { label: "Surete du Quebec Missing Persons", url: "https://www.sq.gouv.qc.ca/en/report-an-event/missing-persons/", category: "official-reporting", official: true, authority_type: "police" },
  ],
};

function haversineKm(lat1, lon1, lat2, lon2) {
  const toRadians = (value) => (value * Math.PI) / 180;
  const radiusKm = 6371;
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  return +(radiusKm * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)))).toFixed(1);
}

function computeGeoContext(latitude, longitude, layers) {
  if (latitude === null || longitude === null || !layers) return [];
  const groups = [
    ["airport", layers.airports || []],
    ["border-crossing", layers.borderCrossings || []],
    ["highway", layers.highways || []],
    ["youth-service", layers.youthServices || []],
  ];
  return groups.map(([type, items]) => {
    const nearest = [...items].map((item) => ({ ...item, distance_km: haversineKm(latitude, longitude, item.latitude, item.longitude) }))
      .sort((a, b) => a.distance_km - b.distance_km)[0];
    return nearest ? {
      context_type: type,
      label: nearest.label,
      distance_km: nearest.distance_km,
      source_url: nearest.source_url,
      jurisdiction: nearest.jurisdiction,
    } : null;
  }).filter(Boolean);
}

function buildInternalRecord(payload) {
  const coordinates = payload.facts.coordinates || {};
  const latitude = coordinates.latitude ?? null;
  const longitude = coordinates.longitude ?? null;
  const record = {
    id: payload.id,
    slug: payload.slug,
    name: payload.facts.name,
    aliases: payload.facts.aliases || [],
    age: payload.facts.age,
    gender: payload.facts.gender,
    ethnicity: payload.facts.ethnicity,
    city: payload.facts.city,
    province: payload.facts.province,
    status: payload.facts.status,
    statusLabel: payload.facts.status_label,
    caseStatus: payload.facts.case_status,
    missingSince: payload.facts.missing_since,
    updatedAt: payload.facts.updated_at,
    authority: {
      name: payload.facts.authority_name,
      email: payload.facts.authority_email,
      phone: payload.facts.authority_phone,
      phoneAlt: payload.facts.authority_phone_alt,
      url: payload.facts.authority_case_url,
    },
    mcsc: {
      email: payload.facts.mcsc_email,
      phone: payload.facts.mcsc_phone,
    },
    summaryHtml: payload.facts.official_summary_html,
    latitude,
    longitude,
    photos: payload.photos || [],
    sources: payload.sources || [],
    resources: payload.resource_links || [],
    geoContext: payload.geo_context || [],
    riskFlags: payload.inference.risk_flags || [],
    riskRank: payload.inference.risk_rank || 1,
    elapsedDays: payload.inference.elapsed_days,
    estimatedCurrentAge: payload.inference.estimated_current_age,
    timelineEntries: payload.inference.timeline_entries || [],
    whatToReport: payload.inference.what_to_report || [],
    howToHelpSafely: payload.inference.how_to_help_safely || [],
    inferenceSummary: payload.inference.summary,
  };
  record.searchText = [record.name, ...record.aliases, record.city, record.province, record.statusLabel, record.authority.name].filter(Boolean).join(" ");
  return record;
}

function normalizeExportDataset(payload) {
  return {
    meta: payload.meta,
    cases: (payload.cases || []).map(buildInternalRecord),
  };
}
function normalizeArcgisFeature(feature, layers) {
  const attributes = feature.attributes || {};
  const geometry = feature.geometry || {};
  const missingDate = attributes.missing ? new Date(attributes.missing).toISOString() : null;
  const updatedAt = attributes.EditDate ? new Date(attributes.EditDate).toISOString() : null;
  const latitude = geometry.y ?? null;
  const longitude = geometry.x ?? null;
  const status = (attributes.status || "missing").toLowerCase();
  const elapsedDays = missingDate ? Math.max(0, Math.floor((Date.now() - new Date(missingDate).getTime()) / 86400000)) : null;
  const riskFlags = [];
  if (["amberalert", "abudction", "abduction", "vulnerable", "childsearchalert"].includes(status)) riskFlags.push("high-priority-status");
  if (Number.isFinite(attributes.age) && attributes.age <= 12) riskFlags.push("young-child");
  if (elapsedDays !== null && elapsedDays <= 7) riskFlags.push("recent-disappearance");
  const province = attributes.province || "Unknown";
  const photos = attributes.thumb_url ? [{ url: attributes.thumb_url, thumb_url: attributes.thumb_url, caption: "Official case photo", is_primary: true }] : [];
  const geoContext = computeGeoContext(latitude, longitude, layers);
  return {
    id: attributes.objectid,
    slug: `${String(attributes.name || `case-${attributes.objectid}`).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    name: attributes.name || "Name unavailable",
    aliases: [],
    age: Number.isFinite(attributes.age) ? attributes.age : null,
    gender: attributes.gender || "",
    ethnicity: attributes.ethnicity || "",
    city: attributes.city || "",
    province,
    status,
    statusLabel: STATUS_LABELS[status] || "Missing",
    caseStatus: attributes.casestatus || "open",
    missingSince: missingDate,
    updatedAt,
    authority: {
      name: attributes.authname || "Official authority",
      email: attributes.authemail || "",
      phone: attributes.authphone || "",
      phoneAlt: attributes.authphonetwo || "",
      url: attributes.authlink || "",
    },
    mcsc: {
      email: attributes.mcscemail || "tips@mcsc.ca",
      phone: attributes.mcscphone || "",
    },
    summaryHtml: attributes.description || "<p>No public summary was provided.</p>",
    latitude,
    longitude,
    photos,
    sources: [{ label: "Live MCSC ArcGIS feed", source_name: "MCSC", source_url: ARCGIS_URL, source_type: "official-feed", official: true, retrieved_at: new Date().toISOString(), trust_weight: 1 }],
    resources: PROVINCE_RESOURCES[province] || [],
    geoContext,
    riskFlags,
    riskRank: status === "amberalert" || status === "abudction" ? 3 : (status === "vulnerable" || status === "childsearchalert" ? 2 : 1),
    elapsedDays,
    estimatedCurrentAge: Number.isFinite(attributes.age) ? attributes.age + Math.floor((elapsedDays || 0) / 365) : null,
    timelineEntries: [
      ...(missingDate ? [{ label: "Official disappearance date", date: missingDate, kind: "official" }] : []),
      ...(updatedAt ? [{ label: "Latest public update", date: updatedAt, kind: "official" }] : []),
      ...(elapsedDays !== null ? [{ label: "Elapsed time since disappearance", date: new Date().toISOString(), kind: "derived", value: elapsedDays }] : []),
    ],
    whatToReport: [
      "Time and place seen.",
      "Public-post links, images, or usernames if publicly visible.",
      "Transit, border, or highway context relevant to the sighting.",
    ],
    howToHelpSafely: [
      "Report to the listed authority or MCSC.",
      "Do not confront or attempt recovery yourself.",
      "Share official posts rather than rumors.",
    ],
    inferenceSummary: "Derived context uses public overlays only and is not confirmation of movement.",
    searchText: [attributes.name, attributes.city, province, attributes.status, attributes.authname].filter(Boolean).join(" "),
  };
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

async function fetchLiveCases(referenceLayers) {
  const params = new URLSearchParams({
    where: "casestatus='open'",
    outFields: "objectid,globalid,status,casestatus,name,age,gender,ethnicity,city,province,missing,description,authname,authemail,authlink,authphone,authphonetwo,thumb_url,mcscemail,mcscphone,CreationDate,EditDate",
    returnGeometry: "true",
    orderByFields: "missing DESC",
    resultRecordCount: "1000",
    f: "json",
  });
  const payload = await fetchJson(`${ARCGIS_URL}/query?${params.toString()}`);
  return {
    meta: {
      generated_at: new Date().toISOString(),
      dataset_mode: "live-arcgis",
      source_name: "Live MCSC ArcGIS feed",
      safety_notice: "Live mode pulls official public case records directly from MCSC. Derived context remains unverified and should only be used to support official reporting.",
    },
    cases: (payload.features || []).map((feature) => normalizeArcgisFeature(feature, referenceLayers)),
  };
}
export async function loadDataset(preferLive = false) {
  const referenceLayers = await fetchJson(REFERENCE_URL).catch(() => null);
  let staticPayload = null;
  if (!preferLive) {
    staticPayload = await fetchJson(STATIC_EXPORT_URL).catch(() => null);
  }
  if (staticPayload) {
    return { referenceLayers, ...normalizeExportDataset(staticPayload) };
  }
  try {
    const livePayload = await fetchLiveCases(referenceLayers);
    return { referenceLayers, ...livePayload };
  } catch (error) {
    if (staticPayload) {
      return { referenceLayers, ...normalizeExportDataset(staticPayload) };
    }
    throw error;
  }
}
