/**
 * OSINT Missing Persons Canada - Dashboard JavaScript
 * Handles map initialization, case loading, filtering, and interactions.
 */

// --- Global state ---
let map = null;
let markersLayer = null;
let currentCases = [];
let currentOffset = 0;
const PAGE_SIZE = 50;
let searchTimeout = null;

// Status colors for map markers
const STATUS_COLORS = {
    vulnerable: '#dc2626',
    abudction: '#2563eb',
    amberalert: '#ea580c',
    childsearchalert: '#9333ea',
    missing: '#eab308',
};

const STATUS_LABELS = {
    vulnerable: 'Vulnerable',
    abudction: 'Abduction',
    amberalert: 'Amber Alert',
    childsearchalert: 'Child Search Alert',
    missing: 'Missing',
};

const PROVINCE_LABELS = {
    Alberta: 'Alberta',
    BritishColumbia: 'British Columbia',
    Manitoba: 'Manitoba',
    NewBrunswick: 'New Brunswick',
    NewfoundlandandLabrador: 'Newfoundland & Labrador',
    NT: 'Northwest Territories',
    NovaScotia: 'Nova Scotia',
    NU: 'Nunavut',
    Ontario: 'Ontario',
    PrinceEdwardIsland: 'Prince Edward Island',
    Quebec: 'Quebec',
    Saskatchewan: 'Saskatchewan',
    YT: 'Yukon',
};

// --- Dashboard initialization ---

function initDashboard() {
    initMap();
    loadStats();
    loadCases(true);
}

// --- Map ---

function initMap() {
    map = L.map('map', {
        center: [56.1304, -106.3468], // Center of Canada
        zoom: 4,
        zoomControl: true,
        attributionControl: true,
    });

    // Dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19,
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);
}

function loadMapMarkers() {
    const params = getFilterParams();
    const qs = new URLSearchParams(params).toString();

    fetch(`/api/cases/geojson?${qs}`)
        .then(r => r.json())
        .then(data => {
            markersLayer.clearLayers();

            data.features.forEach(feature => {
                if (!feature.geometry) return;

                const [lng, lat] = feature.geometry.coordinates;
                const props = feature.properties;
                const color = STATUS_COLORS[props.status] || '#eab308';

                const marker = L.circleMarker([lat, lng], {
                    radius: 8,
                    fillColor: color,
                    color: '#fff',
                    weight: 1.5,
                    opacity: 0.9,
                    fillOpacity: 0.8,
                });

                // Build popup
                const missingSince = props.missing_since
                    ? new Date(props.missing_since).toLocaleDateString('en-CA')
                    : 'Unknown';
                const statusLabel = STATUS_LABELS[props.status] || props.status;
                const photoHtml = props.thumb_url
                    ? `<img src="${props.thumb_url}" style="width:60px;height:60px;object-fit:cover;border-radius:4px;float:left;margin-right:8px;" onerror="this.style.display='none'">`
                    : '';

                marker.bindPopup(`
                    <div style="min-width:180px;">
                        ${photoHtml}
                        <strong style="font-size:14px;">${props.name || 'Unknown'}</strong><br>
                        <span style="font-size:11px;color:#94a3b8;">Age: ${props.age || '?'} | ${props.city || '?'}, ${PROVINCE_LABELS[props.province] || props.province}</span><br>
                        <span style="font-size:11px;color:#94a3b8;">Missing: ${missingSince}</span><br>
                        <span class="status-${props.status}" style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;margin-top:4px;">${statusLabel}</span>
                        <br clear="both">
                        <a href="/case/${props.objectid}" style="font-size:11px;margin-top:6px;display:inline-block;">View Details &rarr;</a>
                    </div>
                `);

                // Click handler to highlight corresponding card
                marker.on('click', () => {
                    highlightCard(props.objectid);
                });

                marker.addTo(markersLayer);
            });
        })
        .catch(err => console.error('Failed to load map markers:', err));
}

// --- Case list ---

function loadCases(reset = false) {
    if (reset) {
        currentOffset = 0;
        currentCases = [];
    }

    const params = getFilterParams();
    params.limit = PAGE_SIZE;
    params.offset = currentOffset;
    const qs = new URLSearchParams(params).toString();

    fetch(`/api/cases?${qs}`)
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('caseList');
            const loadMoreBtn = document.getElementById('loadMore');

            if (reset) {
                container.innerHTML = '';
            }

            if (data.cases.length === 0 && currentOffset === 0) {
                container.innerHTML = '<div class="text-center text-gray-500 py-8">No cases found</div>';
                loadMoreBtn.classList.add('hidden');
                return;
            }

            data.cases.forEach(c => {
                currentCases.push(c);
                container.appendChild(createCaseCard(c));
            });

            currentOffset += data.cases.length;

            if (currentOffset < data.total) {
                loadMoreBtn.classList.remove('hidden');
            } else {
                loadMoreBtn.classList.add('hidden');
            }

            // Also load map markers
            loadMapMarkers();
        })
        .catch(err => {
            console.error('Failed to load cases:', err);
            document.getElementById('caseList').innerHTML =
                '<div class="text-center text-red-400 py-8">Failed to load cases</div>';
        });
}

function createCaseCard(c) {
    const card = document.createElement('div');
    card.className = 'case-card flex items-start space-x-3';
    card.id = `case-card-${c.objectid}`;
    card.onclick = () => {
        // Zoom map to this case
        if (c.latitude && c.longitude && map) {
            map.flyTo([c.latitude, c.longitude], 12, { duration: 1 });
        }
        // Highlight
        document.querySelectorAll('.case-card.active').forEach(el => el.classList.remove('active'));
        card.classList.add('active');
    };

    const missingSince = c.missing_since
        ? new Date(c.missing_since).toLocaleDateString('en-CA')
        : 'Unknown date';
    const statusLabel = STATUS_LABELS[c.status] || c.status || 'Unknown';
    const provinceName = PROVINCE_LABELS[c.province] || c.province || '';

    // Try to get photo URL - use MCSC attachment URL or thumb_url
    let photoSrc = '';
    if (c.photos && c.photos.length > 0 && c.photos[0].url) {
        photoSrc = c.photos[0].url;
    } else if (c.thumb_url) {
        photoSrc = c.thumb_url;
    } else if (c.photo_url) {
        photoSrc = c.photo_url;
    }

    const photoHtml = photoSrc
        ? `<img src="${photoSrc}" class="case-card-photo" alt="${c.name || 'Photo'}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
           <div class="case-card-photo items-center justify-center text-gray-600 text-xs" style="display:none;">No photo</div>`
        : `<div class="case-card-photo flex items-center justify-center text-gray-600 text-xs bg-dark-700">No photo</div>`;

    card.innerHTML = `
        ${photoHtml}
        <div class="flex-1 min-w-0">
            <div class="flex items-center space-x-2">
                <span class="text-sm font-semibold text-white truncate">${c.name || 'Name Unknown'}</span>
                <span class="status-${c.status} px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0">${statusLabel}</span>
            </div>
            <div class="text-xs text-gray-400 mt-0.5">Age: ${c.age || '?'}</div>
            <div class="text-xs text-gray-500 mt-0.5">${c.city || '?'}, ${provinceName}</div>
            <div class="text-xs text-gray-500 mt-0.5">Missing: ${missingSince}</div>
            <a href="/case/${c.objectid}" class="text-xs text-blue-400 hover:underline mt-1 inline-block" onclick="event.stopPropagation()">Details &rarr;</a>
        </div>
    `;

    return card;
}

function loadMoreCases() {
    loadCases(false);
}

function highlightCard(objectid) {
    document.querySelectorAll('.case-card.active').forEach(el => el.classList.remove('active'));
    const card = document.getElementById(`case-card-${objectid}`);
    if (card) {
        card.classList.add('active');
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// --- Stats ---

function loadStats() {
    fetch('/api/cases/stats')
        .then(r => r.json())
        .then(data => {
            document.getElementById('statTotal').textContent = data.total || 0;
            document.getElementById('statRecent').textContent = data.recent_30_days || 0;
            document.getElementById('statAmber').textContent = data.amber_alerts || 0;
        })
        .catch(err => console.error('Failed to load stats:', err));

    // Load face stats if the element exists
    const faceStat = document.getElementById('statFaces');
    if (faceStat) {
        fetch('/api/faces/stats')
            .then(r => r.json())
            .then(data => {
                faceStat.textContent = data.total_face_encodings || 0;
            })
            .catch(() => {
                faceStat.textContent = '0';
            });
    }
}

// --- Filters ---

function getFilterParams() {
    const params = {};
    const province = document.getElementById('filterProvince');
    const status = document.getElementById('filterStatus');
    const search = document.getElementById('filterSearch');

    if (province && province.value) params.province = province.value;
    if (status && status.value) params.status = status.value;
    if (search && search.value.trim()) params.search = search.value.trim();
    params.case_status = 'open';

    return params;
}

function applyFilters() {
    loadCases(true);
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => applyFilters(), 400);
}

// --- Sync ---

function triggerSync() {
    const btn = document.getElementById('syncBtn');
    btn.textContent = 'Syncing...';
    btn.classList.add('sync-running');
    btn.disabled = true;

    fetch('/api/sync', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            btn.textContent = `Done (+${data.added || 0})`;
            btn.classList.remove('sync-running');
            setTimeout(() => {
                btn.textContent = 'Sync Now';
                btn.disabled = false;
            }, 3000);
            // Reload data
            loadStats();
            loadCases(true);
        })
        .catch(err => {
            console.error('Sync failed:', err);
            btn.textContent = 'Sync Failed';
            btn.classList.remove('sync-running');
            setTimeout(() => {
                btn.textContent = 'Sync Now';
                btn.disabled = false;
            }, 3000);
        });
}

// --- Case Detail Page ---

function loadCaseDetail(objectid) {
    fetch(`/api/cases/${objectid}`)
        .then(r => {
            if (!r.ok) throw new Error('Not found');
            return r.json();
        })
        .then(data => {
            document.getElementById('caseLoading').classList.add('hidden');
            document.getElementById('caseContent').classList.remove('hidden');
            renderCaseDetail(data);
        })
        .catch(err => {
            console.error('Failed to load case:', err);
            document.getElementById('caseLoading').classList.add('hidden');
            document.getElementById('caseNotFound').classList.remove('hidden');
        });
}

function renderCaseDetail(c) {
    // Name & status
    document.getElementById('caseName').textContent = c.name || 'Name Unknown';
    const badge = document.getElementById('caseStatusBadge');
    badge.textContent = STATUS_LABELS[c.status] || c.status || 'Unknown';
    badge.className = `status-${c.status} px-2 py-0.5 rounded text-xs font-medium`;

    const missingSince = c.missing_since
        ? new Date(c.missing_since).toLocaleDateString('en-CA', { year: 'numeric', month: 'long', day: 'numeric' })
        : 'Unknown';
    const provinceName = PROVINCE_LABELS[c.province] || c.province || '';
    document.getElementById('caseSubline').textContent =
        `Missing since ${missingSince} | ${c.city || '?'}, ${provinceName}`;

    // Photo
    const photoContainer = document.getElementById('casePhoto');
    let photoSrc = '';
    if (c.photos && c.photos.length > 0 && c.photos[0].url) {
        photoSrc = c.photos[0].url;
    } else if (c.photo_url) {
        photoSrc = c.photo_url;
    } else if (c.thumb_url) {
        photoSrc = c.thumb_url;
    }

    if (photoSrc) {
        photoContainer.innerHTML = `<img src="${photoSrc}" class="max-w-64 max-h-80 rounded object-contain" alt="${c.name || 'Photo'}" onerror="this.outerHTML='<div class=\\'w-64 h-80 bg-dark-700 rounded flex items-center justify-center text-gray-500\\'>Photo unavailable</div>'">`;
    }

    // Details
    const details = document.getElementById('caseDetails');
    const rows = [
        ['Age', c.age],
        ['Gender', c.gender ? c.gender.charAt(0).toUpperCase() + c.gender.slice(1) : null],
        ['Ethnicity', c.ethnicity ? c.ethnicity.charAt(0).toUpperCase() + c.ethnicity.slice(1) : null],
        ['City', c.city],
        ['Province', provinceName],
        ['Case Status', c.case_status ? c.case_status.charAt(0).toUpperCase() + c.case_status.slice(1) : null],
    ].filter(([, v]) => v && v !== 'notlisted');

    details.innerHTML = rows.map(([label, value]) =>
        `<div class="detail-row"><dt>${label}</dt><dd>${value}</dd></div>`
    ).join('');

    // Authority
    const auth = document.getElementById('authorityDetails');
    const authRows = [
        ['Agency', c.authority_name],
        ['Phone', c.authority_phone ? `<a href="tel:${c.authority_phone}" class="text-blue-400 hover:underline">${c.authority_phone}</a>` : null],
        ['Alt Phone', c.authority_phone_alt ? `<a href="tel:${c.authority_phone_alt}" class="text-blue-400 hover:underline">${c.authority_phone_alt}</a>` : null],
        ['Email', c.authority_email ? `<a href="mailto:${c.authority_email}" class="text-blue-400 hover:underline">${c.authority_email}</a>` : null],
    ].filter(([, v]) => v);

    auth.innerHTML = authRows.map(([label, value]) =>
        `<div class="detail-row"><dt>${label}</dt><dd>${value}</dd></div>`
    ).join('');

    // Description
    document.getElementById('caseDescription').textContent = c.description || 'No additional information available.';

    // Map
    const detailMap = L.map('detailMap', {
        center: [56.1304, -106.3468],
        zoom: 4,
        zoomControl: true,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OSM &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
    }).addTo(detailMap);

    if (c.latitude && c.longitude) {
        const color = STATUS_COLORS[c.status] || '#eab308';
        L.circleMarker([c.latitude, c.longitude], {
            radius: 12,
            fillColor: color,
            color: '#fff',
            weight: 2,
            fillOpacity: 0.8,
        }).addTo(detailMap);

        detailMap.setView([c.latitude, c.longitude], 13);
    }

    // Load existing investigation leads for this case
    loadInvestigationData(c.objectid);

    // Load face crops (Phase 3)
    loadFaceCrops(c.objectid);
}

// --- Face Crops (Phase 3) ---

function loadFaceCrops(caseObjectId) {
    fetch(`/api/faces/case/${caseObjectId}`)
        .then(r => {
            if (!r.ok) return null;
            return r.json();
        })
        .then(data => {
            if (!data || data.total_faces === 0) return;

            const section = document.getElementById('faceCropsSection');
            const container = document.getElementById('faceCrops');
            const info = document.getElementById('faceInfo');

            section.classList.remove('hidden');

            container.innerHTML = '';
            data.faces.forEach(face => {
                if (!face.crop_path) return;
                const img = document.createElement('img');
                img.src = `/data/faces/${face.crop_path}`;
                img.alt = `Face ${face.face_index + 1}`;
                img.title = `Face #${face.face_index + 1} (photo ${face.photo_id})`;
                img.className = 'w-20 h-20 object-cover rounded border border-gray-600 hover:border-blue-400 cursor-pointer transition';
                img.onerror = function() { this.style.display = 'none'; };
                container.appendChild(img);
            });

            info.textContent = `${data.total_faces} face(s) detected across all photos`;
        })
        .catch(err => {
            // Silently fail — face index may not exist yet
            console.debug('Face crops not available:', err);
        });
}

// --- Investigation System ---

let currentLeads = [];
let currentLeadFilter = 'all';
let investigationPollTimer = null;

function triggerInvestigation(caseObjectId) {
    const btn = document.getElementById('investigateBtn');
    const statusEl = document.getElementById('investigationStatus');

    btn.textContent = 'Running...';
    btn.disabled = true;
    btn.classList.add('sync-running');

    statusEl.textContent = 'Investigation in progress...';
    statusEl.classList.remove('hidden');

    fetch(`/api/investigations/${caseObjectId}`, { method: 'POST' })
        .then(r => {
            if (r.status === 409) {
                throw new Error('Already running');
            }
            if (!r.ok) throw new Error('Failed to start');
            return r.json();
        })
        .then(data => {
            // Start polling for completion
            pollInvestigationStatus(caseObjectId);
        })
        .catch(err => {
            console.error('Failed to start investigation:', err);
            btn.textContent = err.message === 'Already running' ? 'Already Running' : 'Failed — Retry';
            btn.classList.remove('sync-running');
            setTimeout(() => {
                btn.textContent = 'Run Investigation';
                btn.disabled = false;
            }, 3000);
            if (err.message !== 'Already running') {
                statusEl.textContent = 'Investigation failed to start';
            }
        });
}

function pollInvestigationStatus(caseObjectId) {
    clearInterval(investigationPollTimer);

    investigationPollTimer = setInterval(() => {
        fetch(`/api/investigations/${caseObjectId}`)
            .then(r => r.json())
            .then(data => {
                if (!data.is_running) {
                    // Investigation finished
                    clearInterval(investigationPollTimer);

                    const btn = document.getElementById('investigateBtn');
                    btn.textContent = 'Run Investigation';
                    btn.disabled = false;
                    btn.classList.remove('sync-running');

                    const statusEl = document.getElementById('investigationStatus');

                    if (data.investigations.length > 0) {
                        const latest = data.investigations[0];
                        if (latest.status === 'completed') {
                            statusEl.textContent = `Completed — ${latest.total_leads} leads found`;
                            statusEl.className = 'text-xs text-green-400';
                        } else if (latest.status === 'failed') {
                            statusEl.textContent = 'Investigation failed';
                            statusEl.className = 'text-xs text-red-400';
                        }
                    }

                    // Reload leads
                    loadLeads(caseObjectId);
                }
            })
            .catch(err => {
                console.error('Poll failed:', err);
                clearInterval(investigationPollTimer);
            });
    }, 2000); // Poll every 2 seconds
}

function loadInvestigationData(caseObjectId) {
    // Load investigation status + leads
    fetch(`/api/investigations/${caseObjectId}`)
        .then(r => r.json())
        .then(data => {
            const btn = document.getElementById('investigateBtn');
            const statusEl = document.getElementById('investigationStatus');

            if (data.is_running) {
                btn.textContent = 'Running...';
                btn.disabled = true;
                btn.classList.add('sync-running');
                statusEl.textContent = 'Investigation in progress...';
                statusEl.classList.remove('hidden');
                pollInvestigationStatus(caseObjectId);
            } else if (data.investigations.length > 0) {
                const latest = data.investigations[0];
                statusEl.classList.remove('hidden');
                if (latest.status === 'completed') {
                    statusEl.textContent = `Last run: ${latest.total_leads} leads found`;
                    statusEl.className = 'text-xs text-green-400';
                } else if (latest.status === 'failed') {
                    statusEl.textContent = 'Last run failed';
                    statusEl.className = 'text-xs text-red-400';
                }
            }
        })
        .catch(err => console.error('Failed to load investigation status:', err));

    // Load leads
    loadLeads(caseObjectId);
}

function loadLeads(caseObjectId) {
    fetch(`/api/investigations/${caseObjectId}/leads?limit=200`)
        .then(r => r.json())
        .then(data => {
            currentLeads = data.leads || [];
            renderLeads();
        })
        .catch(err => console.error('Failed to load leads:', err));
}

function renderLeads() {
    const container = document.getElementById('leadsList');
    const placeholder = document.getElementById('leadsPlaceholder');
    const summary = document.getElementById('investigationSummary');
    const filtersEl = document.getElementById('leadFilters');

    if (currentLeads.length === 0) {
        if (placeholder) placeholder.style.display = '';
        summary.classList.add('hidden');
        filtersEl.classList.add('hidden');
        return;
    }

    if (placeholder) placeholder.style.display = 'none';
    summary.classList.remove('hidden');
    filtersEl.classList.remove('hidden');

    // Count by confidence
    let highCount = 0, medCount = 0, lowCount = 0;
    currentLeads.forEach(l => {
        if (l.confidence >= 0.7) highCount++;
        else if (l.confidence >= 0.45) medCount++;
        else if (l.confidence >= 0.2) lowCount++;
    });

    document.getElementById('leadCountTotal').textContent = currentLeads.length;
    document.getElementById('leadCountHigh').textContent = highCount;
    document.getElementById('leadCountMedium').textContent = medCount;
    document.getElementById('leadCountLow').textContent = lowCount;

    // Filter leads
    let filtered = currentLeads;
    if (currentLeadFilter !== 'all') {
        filtered = currentLeads.filter(l => l.lead_type === currentLeadFilter);
    }

    // Sort by confidence desc
    filtered.sort((a, b) => b.confidence - a.confidence);

    // Render
    container.innerHTML = '';

    if (filtered.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500 py-2 text-center">No leads matching filter</p>';
        return;
    }

    filtered.forEach(lead => {
        container.appendChild(createLeadCard(lead));
    });
}

function createLeadCard(lead) {
    const card = document.createElement('div');
    card.className = `lead-card lead-confidence-${getConfidenceClass(lead.confidence)}`;
    card.id = `lead-${lead.id}`;

    const confidencePct = Math.round(lead.confidence * 100);
    const confidenceClass = getConfidenceClass(lead.confidence);
    const typeIcon = getLeadTypeIcon(lead.lead_type);
    const typeLabel = getLeadTypeLabel(lead.lead_type);

    // Build content section
    let contentHtml = '';
    if (lead.lead_type === 'face_match' && lead.source_url) {
        // Show face crop thumbnail for face match leads
        contentHtml = `<div class="mt-1"><img src="${escapeHtml(lead.source_url)}" alt="Face match" class="w-12 h-12 object-cover rounded border border-gray-600 inline-block" onerror="this.style.display='none'"></div>`;
        if (lead.content) {
            const truncated = lead.content.length > 200
                ? lead.content.substring(0, 200) + '...'
                : lead.content;
            contentHtml += `<div class="text-xs text-gray-400 mt-1 leading-relaxed">${escapeHtml(truncated)}</div>`;
        }
    } else if (lead.content) {
        const truncated = lead.content.length > 200
            ? lead.content.substring(0, 200) + '...'
            : lead.content;
        contentHtml = `<div class="text-xs text-gray-400 mt-1 leading-relaxed">${escapeHtml(truncated)}</div>`;
    }

    // Review status
    let reviewHtml = '';
    if (lead.reviewed) {
        const actionableClass = lead.is_actionable ? 'text-green-400' : 'text-gray-500';
        const actionableText = lead.is_actionable ? 'Actionable' : 'Noise';
        reviewHtml = `<span class="${actionableClass} text-[10px] font-medium">${actionableText}</span>`;
    }

    card.innerHTML = `
        <div class="flex items-start justify-between">
            <div class="flex items-start space-x-2 flex-1 min-w-0">
                <span class="text-base mt-0.5 flex-shrink-0">${typeIcon}</span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center space-x-2">
                        <span class="text-xs font-medium text-white truncate">${escapeHtml(lead.title || 'Untitled')}</span>
                        <span class="lead-type-badge">${typeLabel}</span>
                    </div>
                    <div class="flex items-center space-x-2 mt-0.5">
                        <span class="text-[10px] text-gray-500">${escapeHtml(lead.source_name || '')}</span>
                        ${lead.content_date ? `<span class="text-[10px] text-gray-600">${new Date(lead.content_date).toLocaleDateString('en-CA')}</span>` : ''}
                    </div>
                    ${contentHtml}
                </div>
            </div>
            <div class="flex flex-col items-end space-y-1 flex-shrink-0 ml-2">
                <span class="confidence-badge confidence-${confidenceClass}">${confidencePct}%</span>
                ${reviewHtml}
            </div>
        </div>
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-gray-700/50">
            <div class="flex items-center space-x-2">
                ${lead.source_url ? `<a href="${escapeHtml(lead.source_url)}" target="_blank" rel="noopener" class="text-[10px] text-blue-400 hover:underline">Open Source</a>` : ''}
            </div>
            <div class="flex items-center space-x-1">
                ${!lead.reviewed ? `
                    <button onclick="reviewLead(${lead.id}, true, true)" class="lead-review-btn lead-review-actionable" title="Mark as actionable">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    </button>
                    <button onclick="reviewLead(${lead.id}, true, false)" class="lead-review-btn lead-review-noise" title="Mark as noise">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                ` : ''}
            </div>
        </div>
    `;

    return card;
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.7) return 'high';
    if (confidence >= 0.45) return 'medium';
    if (confidence >= 0.2) return 'low';
    return 'noise';
}

function getLeadTypeIcon(type) {
    const icons = {
        username_hit: '@',
        news_article: '#',
        web_mention: '~',
        forum_post: '>',
        social_post: '*',
        sighting_report: '!',
        face_match: '&#9786;',
    };
    return icons[type] || '?';
}

function getLeadTypeLabel(type) {
    const labels = {
        username_hit: 'Username',
        news_article: 'News',
        web_mention: 'Web',
        forum_post: 'Forum',
        social_post: 'Social',
        sighting_report: 'Sighting',
        face_match: 'Face',
    };
    return labels[type] || type;
}

function filterLeads(type, btnEl) {
    currentLeadFilter = type;

    // Update active tab
    document.querySelectorAll('.lead-filter-tab').forEach(t => t.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');

    renderLeads();
}

function reviewLead(leadId, reviewed, isActionable) {
    fetch(`/api/investigations/leads/${leadId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            reviewed: reviewed,
            is_actionable: isActionable,
        }),
    })
        .then(r => r.json())
        .then(updatedLead => {
            // Update local data
            const idx = currentLeads.findIndex(l => l.id === leadId);
            if (idx !== -1) {
                currentLeads[idx] = updatedLead;
            }
            renderLeads();
        })
        .catch(err => console.error('Failed to review lead:', err));
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
