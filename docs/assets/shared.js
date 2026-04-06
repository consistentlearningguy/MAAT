(function () {
  const STATIC_EXPORT_URL = "./data/public-cases.json";
  const REFERENCE_URL = "./data/reference-layers.json";
  const ARCGIS_URL =
    "https://services.arcgis.com/Sv9ZXFjH5h1fYAaI/arcgis/rest/services/Missing_Children_Cases_View_Master/FeatureServer/0";

  const STATUS_LABELS = {
    missing: "Missing",
    vulnerable: "Vulnerable",
    abudction: "Abduction",
    abduction: "Abduction",
    amberalert: "Amber Alert",
    childsearchalert: "Child Search Alert",
    policeoption1: "Police Option 1",
  };

  const PROVINCE_LABELS = {
    AB: "Alberta",
    BC: "British Columbia",
    MB: "Manitoba",
    NB: "New Brunswick",
    NL: "Newfoundland and Labrador",
    NS: "Nova Scotia",
    NT: "Northwest Territories",
    NU: "Nunavut",
    ON: "Ontario",
    PE: "Prince Edward Island",
    QC: "Quebec",
    SK: "Saskatchewan",
    YT: "Yukon",
    Alberta: "Alberta",
    BritishColumbia: "British Columbia",
    Manitoba: "Manitoba",
    NewBrunswick: "New Brunswick",
    NewfoundlandandLabrador: "Newfoundland and Labrador",
    NovaScotia: "Nova Scotia",
    Ontario: "Ontario",
    PrinceEdwardIsland: "Prince Edward Island",
    Quebec: "Quebec",
    Saskatchewan: "Saskatchewan",
  };

  const PROVINCE_RESOURCES = {
    Ontario: [
      {
        label: "Ontario Provincial Police Missing Persons",
        url: "https://www.opp.ca/index.php?id=132",
        category: "official-reporting",
        official: true,
        authority_type: "police",
      },
      {
        label: "Ontario 211 Community Supports",
        url: "https://211ontario.ca/",
        category: "support",
        official: true,
        authority_type: "provincial",
      },
    ],
    "British Columbia": [
      {
        label: "BC RCMP Missing Persons",
        url: "https://www.rcmp-grc.gc.ca/en/missing-persons",
        category: "official-reporting",
        official: true,
        authority_type: "RCMP",
      },
      {
        label: "VictimLinkBC",
        url: "https://www2.gov.bc.ca/gov/content/justice/criminal-justice/victims-of-crime/victimlinkbc",
        category: "support",
        official: true,
        authority_type: "provincial",
      },
    ],
    Manitoba: [
      {
        label: "Manitoba RCMP Missing Persons",
        url: "https://www.rcmp-grc.gc.ca/en/missing-persons",
        category: "official-reporting",
        official: true,
        authority_type: "RCMP",
      },
    ],
    Quebec: [
      {
        label: "Surete du Quebec Missing Persons",
        url: "https://www.sq.gouv.qc.ca/en/report-an-event/missing-persons/",
        category: "official-reporting",
        official: true,
        authority_type: "police",
      },
    ],
  };

  const QUERY_ALIASES = {
    search: "q",
    selectedCaseId: "case",
    runId: "run",
    apiBase: "api",
  };

  const STORAGE_KEYS = {
    apiBase: "osint-missing-persons-api-base",
  };

  const prefersReducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function formatDate(value) {
    if (!value) return "Not available";
    const date = value instanceof Date ? value : new Date(value);
    return new Intl.DateTimeFormat("en-CA", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(date);
  }

  function formatElapsed(days) {
    if (days === null || days === undefined) return "Unknown elapsed time";
    if (days === 0) return "Today";
    if (days === 1) return "1 day";
    if (days < 30) return `${days} days`;
    const months = Math.floor(days / 30);
    return months === 1 ? "1 month" : `${months} months`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function sanitizeHtml(value) {
    const ALLOWED_TAGS = new Set(["p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "a", "span", "div"]);
    const ALLOWED_ATTRS = { a: new Set(["href", "target", "rel"]) };
    const tmp = document.createElement("div");
    tmp.innerHTML = String(value || "");
    // Remove script, style, iframe and other dangerous elements
    tmp.querySelectorAll("script,style,iframe,object,embed,form,input,textarea,link,meta,base,svg,math").forEach(
      (el) => el.remove()
    );
    // Remove event handlers and dangerous attributes from all elements
    tmp.querySelectorAll("*").forEach((el) => {
      const tag = el.tagName.toLowerCase();
      if (!ALLOWED_TAGS.has(tag)) {
        el.replaceWith(...el.childNodes);
        return;
      }
      for (const attr of [...el.attributes]) {
        const name = attr.name.toLowerCase();
        if (name.startsWith("on") || name === "style" || name === "class" || name === "id") {
          el.removeAttribute(attr.name);
        } else if (!(ALLOWED_ATTRS[tag] || new Set()).has(name)) {
          el.removeAttribute(attr.name);
        }
      }
      // Force safe link attributes
      if (tag === "a") {
        const href = el.getAttribute("href") || "";
        if (!/^https?:\/\//i.test(href) && !href.startsWith("mailto:")) {
          el.removeAttribute("href");
        }
        el.setAttribute("target", "_blank");
        el.setAttribute("rel", "noopener noreferrer");
      }
    });
    return tmp.innerHTML;
  }

  function normalizePhone(value) {
    return String(value || "").replace(/\s+/g, "").replace(/[^0-9+]/g, "");
  }

  function normalizeWhitespace(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function summaryLines(summaryHtml) {
    const text = String(summaryHtml || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(p|div|li|tr)>/gi, "\n")
      .replace(/<[^>]+>/g, " ");
    const container = document.createElement("textarea");
    container.innerHTML = text;
    return container.value
      .split(/\n+/)
      .map((line) => normalizeWhitespace(line))
      .filter(Boolean);
  }

  function extractOfficialContext(summaryHtml, city, province) {
    const lines = summaryLines(summaryHtml);
    const fields = {};
    const fieldAliases = {
      "missing since": "missingSinceText",
      location: "locationText",
      age: "ageText",
      height: "height",
      weight: "weight",
      "hair color": "hairColor",
      "eye color": "eyeColor",
      "last seen wearing": "lastSeenWearing",
      circumstances: "circumstances",
    };

    lines.forEach((line) => {
      const parts = line.split(":");
      if (parts.length < 2) return;
      const key = normalizeWhitespace(parts.shift()).toLowerCase();
      const value = normalizeWhitespace(parts.join(":"));
      const targetKey = fieldAliases[key];
      if (targetKey && value && !fields[targetKey]) {
        fields[targetKey] = value;
      }
    });

    const locationText = fields.locationText || "";
    const provinceParts = locationText
      .split(",")
      .map((part) => normalizeWhitespace(part).replace(/[.]/g, ""))
      .filter(Boolean);
    let inferredProvince = province || "";
    for (const part of [...provinceParts].reverse()) {
      if (PROVINCE_LABELS[part]) {
        inferredProvince = PROVINCE_LABELS[part];
        break;
      }
    }

    let inferredCity = city || "";
    if (locationText && city && locationText.toLowerCase().includes(city.toLowerCase())) {
      inferredCity = city;
    } else if (provinceParts.length >= 2 && PROVINCE_LABELS[provinceParts.at(-1)]) {
      inferredCity = provinceParts.at(-2);
    }

    const descriptorChips = [
      fields.height ? `Height ${fields.height}` : "",
      fields.weight ? `Weight/build ${fields.weight}` : "",
      fields.hairColor ? `Hair ${fields.hairColor}` : "",
      fields.eyeColor ? `Eyes ${fields.eyeColor}` : "",
      fields.lastSeenWearing ? `Clothing ${fields.lastSeenWearing}` : "",
    ].filter(Boolean);

    const qualityWarnings = [];
    if (province && inferredProvince && province !== inferredProvince) {
      qualityWarnings.push(
        `ArcGIS province field says ${province}, but the official summary location points to ${inferredProvince}.`
      );
    }

    return {
      fields,
      locationText,
      inferredCity,
      inferredProvince,
      descriptorChips,
      qualityWarnings,
    };
  }

  function uniqueValues(items, getter) {
    return [...new Set(items.map(getter).filter(Boolean))].sort((a, b) =>
      String(a).localeCompare(String(b))
    );
  }

  function normalizeApiBase(value) {
    return String(value || "").trim().replace(/\/+$/, "");
  }

  function readStoredApiBase() {
    try {
      return normalizeApiBase(localStorage.getItem(STORAGE_KEYS.apiBase) || "");
    } catch (error) {
      return "";
    }
  }

  function storeApiBase(value) {
    const normalized = normalizeApiBase(value);
    try {
      if (!normalized) {
        localStorage.removeItem(STORAGE_KEYS.apiBase);
      } else {
        localStorage.setItem(STORAGE_KEYS.apiBase, normalized);
      }
    } catch (error) {
      return;
    }
  }

  function defaultApiBase() {
    const stored = readStoredApiBase();
    if (stored) return stored;
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return normalizeApiBase(window.location.origin);
    }
    return "";
  }

  function readRouteState() {
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
      runId: params.get("run") || "",
      apiBase: normalizeApiBase(params.get("api") || ""),
      reviewStatus: params.get("reviewStatus") || "",
      minConfidence: params.get("minConfidence") || "0",
      limit: params.get("limit") || "100",
    };
  }

  function buildSearchParams(nextState) {
    const params = new URLSearchParams();
    Object.entries(nextState || {}).forEach(([key, value]) => {
      if (
        value === null ||
        value === undefined ||
        value === "" ||
        value === false
      ) {
        return;
      }
      const queryKey = QUERY_ALIASES[key] || key;
      if (key === "live") {
        params.set(queryKey, "1");
        return;
      }
      params.set(queryKey, String(value));
    });
    return params;
  }

  function writeRouteState(nextState) {
    const params = buildSearchParams(nextState);
    const next = `${window.location.pathname}${
      params.toString() ? `?${params.toString()}` : ""
    }`;
    window.history.replaceState({}, "", next);
  }

  function buildPageHref(pathname, nextState) {
    const url = new URL(pathname, window.location.href);
    const params = buildSearchParams(nextState);
    url.search = params.toString() ? `?${params.toString()}` : "";
    return url.href;
  }

  async function fetchJson(url, init) {
    const response = await fetch(url, {
      cache: "no-store",
      ...init,
    });
    const contentType = response.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");
    const payload = isJson ? await response.json() : await response.text();
    if (!response.ok) {
      const detail =
        typeof payload === "string"
          ? payload
          : payload && typeof payload.detail === "string"
            ? payload.detail
            : `${url} returned ${response.status}`;
      const error = new Error(detail || `Request failed with ${response.status}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function haversineKm(lat1, lon1, lat2, lon2) {
    const toRadians = (value) => (value * Math.PI) / 180;
    const radiusKm = 6371;
    const dLat = toRadians(lat2 - lat1);
    const dLon = toRadians(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRadians(lat1)) *
        Math.cos(toRadians(lat2)) *
        Math.sin(dLon / 2) ** 2;
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
    return groups
      .map(([type, items]) => {
        const nearest = [...items]
          .map((item) => ({
            ...item,
            distance_km: haversineKm(
              latitude,
              longitude,
              item.latitude,
              item.longitude
            ),
          }))
          .sort((a, b) => a.distance_km - b.distance_km)[0];
        return nearest
          ? {
              context_type: type,
              label: nearest.label,
              distance_km: nearest.distance_km,
              source_url: nearest.source_url,
              jurisdiction: nearest.jurisdiction,
            }
          : null;
      })
      .filter(Boolean);
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
      officialContext: payload.facts.official_context || null,
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
    record.searchText = [
      record.name,
      ...record.aliases,
      record.city,
      record.province,
      record.statusLabel,
      record.authority.name,
    ]
      .filter(Boolean)
      .join(" ");
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
    const missingDate = attributes.missing
      ? new Date(attributes.missing).toISOString()
      : null;
    const updatedAt = attributes.EditDate
      ? new Date(attributes.EditDate).toISOString()
      : null;
    const latitude = geometry.y ?? null;
    const longitude = geometry.x ?? null;
    const status = String(attributes.status || "missing").toLowerCase();
    const elapsedDays = missingDate
      ? Math.max(
          0,
          Math.floor((Date.now() - new Date(missingDate).getTime()) / 86400000)
        )
      : null;
    const riskFlags = [];
    if (
      ["amberalert", "abudction", "abduction", "vulnerable", "childsearchalert"].includes(
        status
      )
    ) {
      riskFlags.push("high-priority-status");
    }
    if (Number.isFinite(attributes.age) && attributes.age <= 12) {
      riskFlags.push("young-child");
    }
    if (elapsedDays !== null && elapsedDays <= 7) {
      riskFlags.push("recent-disappearance");
    }
    const rawProvince = attributes.province || "Unknown";
    const canonicalProvince = PROVINCE_LABELS[rawProvince] || rawProvince || "Unknown";
    const officialContext = extractOfficialContext(
      attributes.description || "",
      attributes.city || "",
      canonicalProvince
    );
    const province = officialContext.inferredProvince || canonicalProvince;
    const city = officialContext.inferredCity || attributes.city || "";
    if (officialContext.qualityWarnings.length) {
      riskFlags.push("official-field-conflict");
    }
    const photos = attributes.thumb_url
      ? [
          {
            url: attributes.thumb_url,
            thumb_url: attributes.thumb_url,
            caption: "Official case photo",
            is_primary: true,
          },
        ]
      : [];
    const geoContext = computeGeoContext(latitude, longitude, layers);
    return {
      id: attributes.objectid,
      slug: `${String(attributes.name || `case-${attributes.objectid}`)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")}`,
      name: attributes.name || "Name unavailable",
      aliases: [],
      age: Number.isFinite(attributes.age) ? attributes.age : null,
      gender: attributes.gender || "",
      ethnicity: attributes.ethnicity || "",
      city,
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
      officialContext,
      latitude,
      longitude,
      photos,
      sources: [
        {
          label: "Live MCSC ArcGIS feed",
          source_name: "MCSC",
          source_url: ARCGIS_URL,
          source_type: "official-feed",
          official: true,
          retrieved_at: new Date().toISOString(),
          trust_weight: 1,
        },
      ],
      resources: PROVINCE_RESOURCES[province] || [],
      geoContext,
      riskFlags,
      riskRank:
        status === "amberalert" || status === "abudction" || status === "abduction"
          ? 3
          : status === "vulnerable" || status === "childsearchalert"
            ? 2
            : 1,
      elapsedDays,
      estimatedCurrentAge: Number.isFinite(attributes.age)
        ? attributes.age + Math.floor((elapsedDays || 0) / 365)
        : null,
      timelineEntries: [
        ...(missingDate
          ? [{ label: "Official disappearance date", date: missingDate, kind: "official" }]
          : []),
        ...(updatedAt
          ? [{ label: "Latest public update", date: updatedAt, kind: "official" }]
          : []),
        ...(elapsedDays !== null
          ? [
              {
                label: "Elapsed time since disappearance",
                date: new Date().toISOString(),
                kind: "derived",
                value: elapsedDays,
              },
            ]
          : []),
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
      inferenceSummary:
        "Derived context uses public overlays only and is not confirmation of movement.",
      searchText: [
        attributes.name,
        city,
        province,
        attributes.status,
        attributes.authname,
      ]
        .filter(Boolean)
        .join(" "),
    };
  }

  async function fetchLiveCases(referenceLayers) {
    const params = new URLSearchParams({
      where: "casestatus='open'",
      outFields:
        "objectid,globalid,status,casestatus,name,age,gender,ethnicity,city,province,missing,description,authname,authemail,authlink,authphone,authphonetwo,thumb_url,mcscemail,mcscphone,CreationDate,EditDate",
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
        safety_notice:
          "Live mode pulls official public case records directly from MCSC. Derived context remains unverified and should only be used to support official reporting.",
      },
      cases: (payload.features || []).map((feature) =>
        normalizeArcgisFeature(feature, referenceLayers)
      ),
    };
  }

  async function loadDataset(preferLive) {
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

  function textScore(record, query) {
    if (!query) return 1;
    const terms = String(query)
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);
    if (!terms.length) return 1;
    const haystack = String(record.searchText || "").toLowerCase();
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
        return String(left.statusLabel).localeCompare(String(right.statusLabel));
      case "name":
        return String(left.name).localeCompare(String(right.name));
      case "risk":
        return (
          (right.riskRank ?? 0) - (left.riskRank ?? 0) ||
          (right.elapsedDays ?? 0) - (left.elapsedDays ?? 0)
        );
      case "recency":
      default:
        return new Date(right.missingSince || 0) - new Date(left.missingSince || 0);
    }
  }

  function filterCases(cases, filters) {
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

  function summarizeCases(cases) {
    const total = cases.length;
    const highRisk = cases.filter((record) => record.riskRank >= 2).length;
    const recent = cases.filter((record) => (record.elapsedDays ?? 9999) <= 30).length;
    const latestUpdate =
      [...cases]
        .map((record) => record.updatedAt)
        .filter(Boolean)
        .sort((a, b) => new Date(b) - new Date(a))[0] || null;
    return { total, highRisk, recent, latestUpdate };
  }

  function createMap(containerId, theme) {
    const tileTheme = theme === "light" ? "light" : "dark";
    const map = L.map(containerId, {
      center: [56.1304, -106.3468],
      zoom: 4,
      scrollWheelZoom: true,
    });
    const tileUrl =
      tileTheme === "light"
        ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";

    L.tileLayer(tileUrl, {
      attribution: "&copy; OpenStreetMap &copy; CARTO",
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    return { map, layer, markerIndex: new Map() };
  }

  function caseMarkerHtml(record, isSelected) {
    return `
      <span class="marker-shell marker-${escapeHtml(record.status)}${
        isSelected ? " is-selected" : ""
      }">
        <span class="marker-ring"></span>
        <span class="marker-core"></span>
        <span class="marker-ping"></span>
      </span>
    `;
  }

  function renderCaseMarkers(mapContext, records, selectedCaseId, onSelect) {
    mapContext.layer.clearLayers();
    mapContext.markerIndex.clear();
    const bounds = [];

    records.forEach((record) => {
      if (record.latitude === null || record.longitude === null) return;
      const marker = L.marker([record.latitude, record.longitude], {
        icon: L.divIcon({
          className: "",
          html: caseMarkerHtml(record, record.id === selectedCaseId),
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        }),
      });
      marker.on("click", () => onSelect(record.id, true));
      marker.bindPopup(
        `<strong>${escapeHtml(record.name)}</strong><br>${escapeHtml(
          record.city || "Unknown city"
        )}, ${escapeHtml(record.province)}<br>${escapeHtml(record.statusLabel)}`
      );
      marker.addTo(mapContext.layer);
      mapContext.markerIndex.set(record.id, marker);
      bounds.push([record.latitude, record.longitude]);
    });

    if (bounds.length) {
      mapContext.map.fitBounds(L.latLngBounds(bounds).pad(0.22), { maxZoom: 7 });
    }
  }

  function evidenceMarkerHtml(tone, isSelected) {
    return `
      <span class="marker-shell marker-${escapeHtml(tone)} marker-evidence${
        isSelected ? " is-selected" : ""
      }">
        <span class="marker-ring"></span>
        <span class="marker-core"></span>
        <span class="marker-ping"></span>
      </span>
    `;
  }

  function renderEvidenceMarkers(mapContext, record, leads, activeLeadId, onLeadSelect) {
    mapContext.layer.clearLayers();
    mapContext.markerIndex.clear();
    const bounds = [];

    if (record && record.latitude !== null && record.longitude !== null) {
      const anchor = L.marker([record.latitude, record.longitude], {
        icon: L.divIcon({
          className: "",
          html: evidenceMarkerHtml(record.status || "missing", false),
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        }),
      });
      anchor.bindPopup(
        `<strong>${escapeHtml(record.name)}</strong><br>Official anchor location`
      );
      anchor.addTo(mapContext.layer);
      bounds.push([record.latitude, record.longitude]);
    }

    (leads || []).forEach((lead) => {
      if (lead.latitude === null || lead.longitude === null) return;
      const marker = L.marker([lead.latitude, lead.longitude], {
        icon: L.divIcon({
          className: "",
          html: evidenceMarkerHtml("lead", lead.id === activeLeadId),
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        }),
      });
      marker.on("click", () => onLeadSelect(lead.id));
      marker.bindPopup(
        `<strong>${escapeHtml(lead.title || lead.source_name)}</strong><br>${escapeHtml(
          lead.location_text || "Derived public location"
        )}<br>Confidence ${Math.round((lead.confidence || 0) * 100)}%`
      );
      marker.addTo(mapContext.layer);
      mapContext.markerIndex.set(lead.id, marker);
      bounds.push([lead.latitude, lead.longitude]);
    });

    if (bounds.length) {
      mapContext.map.fitBounds(L.latLngBounds(bounds).pad(0.22), { maxZoom: 8 });
    }
  }

  function fitToRecords(mapContext, records) {
    const points = records
      .filter((record) => record.latitude !== null && record.longitude !== null)
      .map((record) => [record.latitude, record.longitude]);
    if (!points.length) return;
    mapContext.map.fitBounds(L.latLngBounds(points).pad(0.22), { maxZoom: 7 });
  }

  function buildCaseSignalItems(records, meta) {
    const latest =
      [...records]
        .sort(
          (a, b) =>
            new Date(b.updatedAt || b.missingSince || 0) -
            new Date(a.updatedAt || a.missingSince || 0)
        )[0] || null;
    const provinceCounts = {};
    records.forEach((record) => {
      provinceCounts[record.province] = (provinceCounts[record.province] || 0) + 1;
    });
    const topProvince = Object.entries(provinceCounts).sort((a, b) => b[1] - a[1])[0];
    const highRisk = records.filter((record) => record.riskRank >= 2).length;
    return [
      meta && meta.dataset_mode === "live-arcgis"
        ? "LIVE ARCGIS FEED ONLINE"
        : "BUNDLED STATIC EXPORT ACTIVE",
      `${records.length} CASES IN CURRENT FIELD OF VIEW`,
      `${highRisk} PRIORITY STATUS CASES IN SCOPE`,
      topProvince
        ? `${topProvince[0].toUpperCase()} HOLDS THE LARGEST CASE CLUSTER`
        : "PROVINCE DISTRIBUTION ONLINE",
      latest
        ? `LATEST PUBLIC UPDATE ${formatDate(
            latest.updatedAt || latest.missingSince
          ).toUpperCase()}`
        : "AWAITING UPDATE SIGNAL",
      "OFFICIAL FACTS AND INFERRED CONTEXT REMAIN SEPARATE",
      "ROUTE ALL TIPS TO THE LISTED AUTHORITY OR MCSC",
      ...records.slice(0, 6).map(
        (record) =>
          `${record.statusLabel.toUpperCase()} // ${record.name.toUpperCase()} // ${(
            record.city || "UNKNOWN CITY"
          ).toUpperCase()}, ${record.province.toUpperCase()} // ELAPSED ${formatElapsed(
            record.elapsedDays
          ).toUpperCase()}`
      ),
    ];
  }

  function buildEvidenceSignalItems(record, run, leads, queryLogs) {
    const latestLead = (leads || [])[0];
    const latestQuery = (queryLogs || [])[0];
    const connectors = (run && run.connectors) || [];
    return [
      record ? `${record.name.toUpperCase()} EVIDENCE DESK` : "EVIDENCE DESK IDLE",
      run ? `RUN ${run.id} ${String(run.status || "queued").toUpperCase()}` : "NO RUN LOADED",
      `${(leads || []).length} LEADS IN CURRENT VIEW`,
      `${(queryLogs || []).length} QUERY LOG ENTRIES`,
      connectors.length
        ? `${connectors.join(" / ").toUpperCase()} CONNECTORS`
        : "CONNECTOR STACK WAITING",
      latestLead
        ? `${(latestLead.source_name || "SOURCE").toUpperCase()} TOP SIGNAL ${
            Math.round((latestLead.confidence || 0) * 100)
          }%`
        : "NO SCORED LEADS YET",
      latestQuery
        ? `${latestQuery.connector_name.toUpperCase()} LAST QUERY ${String(
            latestQuery.status || "unknown"
          ).toUpperCase()}`
        : "QUERY LOG WAITING",
      "PUBLIC LEADS REQUIRE HUMAN REVIEW BEFORE ACTION",
    ];
  }

  function renderMarquee(container, items, className) {
    if (!container) return;
    const trackClass = className || "signal-marquee-track";
    const stream = (items || [])
      .map((item) => `<span>${escapeHtml(item)}</span>`)
      .join("");
    container.innerHTML = `
      <div class="signal-marquee">
        <div class="${trackClass}">
          ${stream}
          ${stream}
        </div>
      </div>
    `;
  }

  function resolveApiUrl(apiBase, path) {
    const normalized = normalizeApiBase(apiBase || defaultApiBase());
    if (!normalized) {
      const error = new Error(
        "Set a backend URL before using online investigation features."
      );
      error.status = 400;
      throw error;
    }
    return `${normalized}${path}`;
  }

  async function requestApiJson(apiBase, path, init) {
    const url = resolveApiUrl(apiBase, path);
    return fetchJson(url, init);
  }

  async function listCaseRuns(apiBase, caseId, limit) {
    const params = new URLSearchParams({
      limit: String(limit || 8),
    });
    return requestApiJson(
      apiBase,
      `/api/investigations/cases/${caseId}/runs?${params.toString()}`
    );
  }

  async function getCaseResourcePack(apiBase, caseId) {
    return requestApiJson(apiBase, `/api/investigations/cases/${caseId}/resource-pack`);
  }

  async function runInvestigation(apiBase, caseId) {
    return requestApiJson(apiBase, `/api/investigations/${caseId}`, {
      method: "POST",
    });
  }

  async function getRun(apiBase, runId) {
    return requestApiJson(apiBase, `/api/investigations/runs/${runId}`);
  }

  async function getRunLeads(apiBase, runId, options) {
    const params = new URLSearchParams({
      min_confidence: String(options && options.minConfidence ? options.minConfidence : 0),
      limit: String(options && options.limit ? options.limit : 100),
    });
    if (options && options.reviewStatus) {
      params.set("review_status", options.reviewStatus);
    }
    return requestApiJson(
      apiBase,
      `/api/investigations/runs/${runId}/leads?${params.toString()}`
    );
  }

  async function getRunQueryLogs(apiBase, runId) {
    return requestApiJson(apiBase, `/api/investigations/runs/${runId}/query-logs`);
  }

  async function reviewLead(apiBase, leadId, decision, notes) {
    return requestApiJson(apiBase, `/api/investigations/leads/${leadId}/review`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        decision,
        notes: notes || null,
      }),
    });
  }

  async function getRunSynthesis(apiBase, runId) {
    return requestApiJson(apiBase, `/api/investigations/runs/${runId}/synthesis`);
  }

  window.OsintMissingPersons = {
    ARCGIS_URL,
    STATUS_LABELS,
    prefersReducedMotion,
    formatDate,
    formatElapsed,
    escapeHtml,
    sanitizeHtml,
    normalizePhone,
    uniqueValues,
    readRouteState,
    writeRouteState,
    buildPageHref,
    normalizeApiBase,
    readStoredApiBase,
    storeApiBase,
    defaultApiBase,
    loadDataset,
    filterCases,
    summarizeCases,
    createMap,
    renderCaseMarkers,
    renderEvidenceMarkers,
    fitToRecords,
    buildCaseSignalItems,
    buildEvidenceSignalItems,
    renderMarquee,
    listCaseRuns,
    getCaseResourcePack,
    runInvestigation,
    getRun,
    getRunLeads,
    getRunQueryLogs,
    reviewLead,
    getRunSynthesis,
    fetchJson,
  };
})();
