/**
 * S3 Compliance Dashboard
 * GitHub-style provider compliance visualization
 */

const DATA_BASE_URL = 'data';

// Current filter state
let currentFilter = null;
let allProviders = {};
let currentBaseUrl = '';

// Icons as SVG strings
const ICONS = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    providers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7c-2 0-3 1-3 3z"/><path d="M12 4v16m8-8H4"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>',
};

// Test case definitions with labels and descriptions
// Multipart upload tests (case_1, case_2, case_5-8)
// Single-part upload tests (case_9-12)
const TEST_CASES = {
    // Multipart upload tests
    case_1: { label: 'CL>', name: 'MP: CL > Body', desc: 'Multipart: Header claims more bytes than sent', expect: 'reject' },
    case_2: { label: 'CL<', name: 'MP: CL < Body', desc: 'Multipart: Header claims fewer bytes than sent', expect: 'reject' },
    case_5: { label: 'Sig>', name: 'MP: Sig > Actual', desc: 'Multipart: Presigned URL size exceeds upload', expect: 'reject' },
    case_6: { label: 'Sig<', name: 'MP: Sig < Actual', desc: 'Multipart: Upload exceeds presigned URL size', expect: 'reject' },
    case_7: { label: 'Ctrl', name: 'MP: Control', desc: 'Multipart: Valid request (baseline)', expect: 'accept' },
    case_8: { label: 'List', name: 'MP: List Parts', desc: 'Multipart: API returns accurate part info', expect: 'verify' },
    // Single-part upload tests
    case_9: { label: 'S:CL>', name: 'SP: CL > Body', desc: 'Single-part: Header claims more bytes than sent', expect: 'reject' },
    case_10: { label: 'S:CL<', name: 'SP: CL < Body', desc: 'Single-part: Header claims fewer bytes than sent', expect: 'reject' },
    case_11: { label: 'S:Sig<', name: 'SP: Sig < Actual', desc: 'Single-part: Upload exceeds presigned URL size', expect: 'reject' },
    case_12: { label: 'S:Ctrl', name: 'SP: Control', desc: 'Single-part: Valid request (baseline)', expect: 'accept' },
};

/**
 * Format timestamp for display
 */
function formatTimestamp(ts) {
    if (!ts) return 'Never';
    const date = new Date(ts);
    return date.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Fetch JSON data
 */
async function fetchJson(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`Failed to fetch ${url}:`, error);
        return null;
    }
}

/**
 * Render inline stats badges in the section header (clickable for filtering)
 */
function renderStats(providers) {
    const container = document.getElementById('stats-grid');
    if (!providers) {
        container.innerHTML = '';
        return;
    }

    const total = Object.keys(providers).length;
    const passed = Object.values(providers).filter(p => p.status === 'pass').length;
    const failed = Object.values(providers).filter(p => p.status === 'fail').length;
    const errors = Object.values(providers).filter(p => p.status === 'error').length;

    const activeClass = (status) => currentFilter === status ? 'active' : '';

    container.innerHTML = `
        <div class="stat-badge pass ${activeClass('pass')}" onclick="toggleFilter('pass')" data-tooltip="Click to filter">
            <span class="stat-badge-icon">${ICONS.check}</span>
            <span class="stat-badge-value">${passed}</span>
            <span class="stat-badge-label">Compliant</span>
        </div>
        <div class="stat-badge fail ${activeClass('fail')}" onclick="toggleFilter('fail')" data-tooltip="Click to filter">
            <span class="stat-badge-icon">${ICONS.x}</span>
            <span class="stat-badge-value">${failed}</span>
            <span class="stat-badge-label">Non-Compliant</span>
        </div>
        <div class="stat-badge error ${activeClass('error')}" onclick="toggleFilter('error')" data-tooltip="Click to filter">
            <span class="stat-badge-icon">${ICONS.alert}</span>
            <span class="stat-badge-value">${errors}</span>
            <span class="stat-badge-label">Errors</span>
        </div>
    `;
}

/**
 * Toggle filter by provider status
 */
function toggleFilter(status) {
    if (currentFilter === status) {
        currentFilter = null; // Clear filter
    } else {
        currentFilter = status;
    }
    renderStats(allProviders);
    renderProviderCards(allProviders, currentBaseUrl);
}

/**
 * Render provider cards with test case indicators and badge embed
 */
function renderProviderCards(providers, baseUrl) {
    const container = document.getElementById('provider-cards');
    const countEl = document.getElementById('provider-count');

    if (!providers || Object.keys(providers).length === 0) {
        container.innerHTML = '<div class="empty-state">No provider data available</div>';
        countEl.textContent = '0 providers';
        return;
    }

    // Apply filter if set
    const filteredEntries = Object.entries(providers).filter(([key, provider]) => {
        if (!currentFilter) return true;
        return provider.status === currentFilter;
    });

    const totalCount = Object.keys(providers).length;
    const filteredCount = filteredEntries.length;

    if (currentFilter) {
        countEl.textContent = `${filteredCount} of ${totalCount} providers`;
    } else {
        countEl.textContent = `${totalCount} provider${totalCount !== 1 ? 's' : ''}`;
    }

    if (filteredEntries.length === 0) {
        container.innerHTML = `<div class="empty-state">No ${currentFilter} providers</div>`;
        return;
    }

    container.innerHTML = filteredEntries.map(([key, provider]) => {
        const cases = provider.cases || {};
        // All case IDs: multipart (1,2,5,6,7,8) + single-part (9,10,11,12)
        const caseKeys = ['case_1', 'case_2', 'case_5', 'case_6', 'case_7', 'case_8', 'case_9', 'case_10', 'case_11', 'case_12'];

        const caseIndicators = caseKeys.map(caseKey => {
            const caseInfo = TEST_CASES[caseKey];
            const caseData = cases[caseKey];
            const status = caseData ? caseData.status : 'none';
            const statusText = status === 'pass' ? 'Passed' : status === 'fail' ? 'Failed' : status === 'error' ? 'Error' : 'Not tested';

            return `<div class="case-indicator ${status}" data-tooltip="${caseInfo.name}\n${caseInfo.desc}\nExpected: ${caseInfo.expect}\nResult: ${statusText}">${caseInfo.label}</div>`;
        }).join('');

        const duration = provider.duration_seconds
            ? `${provider.duration_seconds.toFixed(1)}s`
            : '';

        const badgeUrl = `${baseUrl}/data/badges/${key}.svg`;
        const badgeMarkdown = `![${provider.name}](${badgeUrl})`;

        const staleClass = provider.stale ? 'stale' : '';
        const staleIndicator = provider.stale
            ? `<span class="stale-badge" data-tooltip="Data from previous test run\nLast tested: ${provider.lastTested || 'Unknown'}">Stale</span>`
            : '';

        return `
            <div class="provider-card ${provider.status} ${staleClass}">
                <div class="provider-card-header">
                    <span class="provider-name">${provider.name}${staleIndicator}</span>
                    <span class="provider-status ${provider.status}">
                        <span class="provider-status-dot"></span>
                        ${provider.status}
                    </span>
                </div>
                <div class="provider-cases">${caseIndicators}</div>
                <div class="provider-footer">
                    <div class="provider-badge">
                        <img src="data/badges/${key}.svg" alt="${provider.name}" onerror="this.style.display='none'">
                        <button class="badge-copy-btn" onclick="copyToClipboard('${badgeMarkdown}', this)" title="Copy badge markdown">
                            ${ICONS.copy}
                        </button>
                    </div>
                    ${duration ? `<span class="provider-duration">${duration}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Copy text to clipboard and show feedback
 */
function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text).then(() => {
        const copyIcon = button.querySelector('.copy-icon');
        const checkIcon = button.querySelector('.check-icon');
        if (copyIcon && checkIcon) {
            copyIcon.style.display = 'none';
            checkIcon.style.display = 'block';
        }
        button.classList.add('copied');
        setTimeout(() => {
            if (copyIcon && checkIcon) {
                copyIcon.style.display = 'block';
                checkIcon.style.display = 'none';
            }
            button.classList.remove('copied');
        }, 1500);
    });
}

/**
 * Copy API example code to clipboard
 */
function copyApiExample() {
    const codeEl = document.getElementById('api-example-code');
    const button = document.querySelector('.copy-btn');
    if (codeEl && button) {
        copyToClipboard(codeEl.textContent, button);
    }
}

/**
 * Render GitHub-style heatmap grid
 * Rows = providers, Columns = test run dates
 */
function renderHeatmap(history) {
    const container = document.getElementById('heatmap-container');

    if (!history || !history.providers || Object.keys(history.providers).length === 0) {
        container.innerHTML = '<div class="empty-state">No historical data available yet. Run tests to build history.</div>';
        return;
    }

    // Get all unique dates across all providers, sorted chronologically (oldest first for left-to-right)
    const allDates = new Set();
    for (const provider of Object.values(history.providers)) {
        for (const entry of (provider.history || [])) {
            allDates.add(entry.date);
        }
    }

    if (allDates.size === 0) {
        container.innerHTML = '<div class="empty-state">No test history available</div>';
        return;
    }

    // Sort dates oldest to newest (left to right), limit to last 52 entries
    const dates = Array.from(allDates).sort().slice(-52);
    const providers = Object.entries(history.providers);

    // Build the grid HTML
    let html = '<div class="gh-heatmap">';

    // Provider labels column
    html += '<div class="gh-heatmap-labels">';
    html += '<div class="gh-heatmap-corner"></div>'; // Empty corner for date row alignment
    for (const [key, provider] of providers) {
        html += `<div class="gh-heatmap-label">${provider.name}</div>`;
    }
    html += '</div>';

    // Scrollable grid area
    html += '<div class="gh-heatmap-scroll">';

    // Date headers row
    html += '<div class="gh-heatmap-dates">';
    const showEvery = Math.max(1, Math.ceil(dates.length / 8));
    for (let i = 0; i < dates.length; i++) {
        const showLabel = (i % showEvery === 0) || (i === dates.length - 1);
        html += `<div class="gh-heatmap-date">${showLabel ? formatDate(dates[i]) : ''}</div>`;
    }
    html += '</div>';

    // Grid rows (one per provider)
    for (const [key, provider] of providers) {
        // Build status lookup for this provider
        const statusByDate = {};
        for (const entry of (provider.history || [])) {
            statusByDate[entry.date] = entry.status;
        }

        html += '<div class="gh-heatmap-row">';
        for (const date of dates) {
            const status = statusByDate[date] || 'none';
            const statusLabel = status === 'none' ? 'Not tested' :
                               status === 'pass' ? 'Passing' :
                               status === 'fail' ? 'Failing' : 'Error';
            const isClickable = status === 'fail' || status === 'error';
            const clickAttr = isClickable ? `onclick="scrollToActivity('${key}', '${date}', '${status}')"` : '';
            const cursorClass = isClickable ? 'clickable' : '';
            html += `<div class="gh-cell ${status} ${cursorClass}" ${clickAttr} data-tooltip="${provider.name}\n${formatDate(date)}: ${statusLabel}${isClickable ? '\n(Click to see activity)' : ''}"></div>`;
        }
        html += '</div>';
    }

    html += '</div>'; // .gh-heatmap-scroll
    html += '</div>'; // .gh-heatmap

    // Legend
    html += `
        <div class="gh-heatmap-legend">
            <span class="gh-legend-label">Status:</span>
            <div class="gh-legend-item"><span class="gh-legend-box pass"></span>Pass</div>
            <div class="gh-legend-item"><span class="gh-legend-box fail"></span>Fail</div>
            <div class="gh-legend-item"><span class="gh-legend-box error"></span>Error</div>
            <div class="gh-legend-item"><span class="gh-legend-box none"></span>No data</div>
        </div>
    `;

    container.innerHTML = html;
}

/**
 * Scroll to the relevant activity entry when clicking a heatmap cell
 */
function scrollToActivity(providerKey, date, status) {
    const activityId = `activity-${providerKey}-${date}`;
    const element = document.getElementById(activityId);

    if (element) {
        highlightActivity(element);
    } else {
        // No exact match - find the closest activity for this provider with matching status
        // that occurred on or before the clicked date
        const activities = document.querySelectorAll(`[id^="activity-${providerKey}-"]`);
        let bestMatch = null;
        let bestDate = null;

        for (const activity of activities) {
            // Extract date from ID: activity-{provider}-{date}
            const activityDate = activity.id.replace(`activity-${providerKey}-`, '');
            // Check if this activity matches the status we're looking for
            const activityIcon = activity.querySelector('.activity-icon');
            const activityStatus = activityIcon?.classList.contains('fail') ? 'fail' :
                                   activityIcon?.classList.contains('error') ? 'error' : 'pass';

            // Find activity with matching status that is closest to (but not after) the clicked date
            if (activityStatus === status && activityDate <= date) {
                if (!bestDate || activityDate > bestDate) {
                    bestMatch = activity;
                    bestDate = activityDate;
                }
            }
        }

        if (bestMatch) {
            highlightActivity(bestMatch);
        } else if (activities.length > 0) {
            // Fallback: find any activity for this provider with matching status
            for (const activity of activities) {
                const activityIcon = activity.querySelector('.activity-icon');
                const activityStatus = activityIcon?.classList.contains('fail') ? 'fail' :
                                       activityIcon?.classList.contains('error') ? 'error' : 'pass';
                if (activityStatus === status) {
                    highlightActivity(activity);
                    return;
                }
            }
            // Last resort: just highlight the first activity for this provider
            highlightActivity(activities[0]);
        } else {
            // Scroll to the changelog section if no provider activity found
            const changelog = document.getElementById('changelog');
            if (changelog) {
                changelog.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }
}

/**
 * Highlight an activity element with scroll and animation
 */
function highlightActivity(element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    element.classList.remove('highlight');
    void element.offsetWidth; // Force reflow
    element.classList.add('highlight');
    setTimeout(() => element.classList.remove('highlight'), 2000);
}

/**
 * Render activity feed (changelog) with IDs for linking from heatmap
 */
function renderChangelog(history) {
    const container = document.getElementById('changelog');

    if (!history || !history.changelog || history.changelog.length === 0) {
        container.innerHTML = '<div class="empty-state">No recent activity</div>';
        return;
    }

    const entries = history.changelog.slice(0, 20);
    container.innerHTML = entries.map(entry => {
        const icon = entry.change === 'pass' ? ICONS.check :
                     entry.change === 'fail' ? ICONS.x : ICONS.alert;
        const activityId = `activity-${entry.provider}-${entry.date}`;
        return `
            <div class="activity-item" id="${activityId}">
                <div class="activity-icon ${entry.change}">${icon}</div>
                <div class="activity-content">
                    <div class="activity-message">${entry.message}</div>
                    <div class="activity-date">${formatDate(entry.date)}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Update API example code with actual base URL
 */
function updateApiExample(baseUrl) {
    const codeEl = document.getElementById('api-example-code');
    if (codeEl) {
        const fullUrl = `${baseUrl}/data/latest.json`;
        codeEl.textContent = `fetch('${fullUrl}')
  .then(r => r.json())
  .then(data => {
    const aws = data.providers.aws;
    console.log(\`AWS S3: \${aws.status}\`); // "pass" | "fail" | "error"
  });`;
    }
}

/**
 * Merge providers from latest.json and history.json
 * Providers only in history are marked as stale
 */
function mergeProviders(latestProviders, historyProviders) {
    const merged = {};
    const latestKeys = new Set(Object.keys(latestProviders || {}));

    // Add all providers from latest (fresh data)
    for (const [key, provider] of Object.entries(latestProviders || {})) {
        merged[key] = { ...provider, stale: false };
    }

    // Add providers from history that aren't in latest (stale data)
    for (const [key, historyProvider] of Object.entries(historyProviders || {})) {
        if (!latestKeys.has(key)) {
            // Provider is in history but not in latest run - mark as stale
            merged[key] = {
                name: historyProvider.name,
                status: historyProvider.current_status,
                cases: {}, // No case data available for stale providers
                stale: true,
                lastTested: historyProvider.history?.[0]?.date || historyProvider.first_tested,
            };
        }
    }

    return merged;
}

/**
 * Initialize dashboard
 */
async function init() {
    // Build base URL without trailing slash
    const baseUrl = window.location.origin + window.location.pathname.replace(/\/index\.html$/, '').replace(/\/$/, '');

    // Fetch data
    const [latest, history] = await Promise.all([
        fetchJson(`${DATA_BASE_URL}/latest.json`),
        fetchJson(`${DATA_BASE_URL}/history.json`)
    ]);

    // Update last updated timestamp
    const lastUpdatedEl = document.getElementById('last-updated');
    if (latest && latest.timestamp) {
        lastUpdatedEl.textContent = `Updated ${formatTimestamp(latest.timestamp)}`;
    } else if (history && history.last_updated) {
        lastUpdatedEl.textContent = `Updated ${formatTimestamp(history.last_updated)}`;
    } else {
        lastUpdatedEl.textContent = 'No data yet';
    }

    // Merge providers from both sources (latest takes precedence, history fills gaps)
    allProviders = mergeProviders(latest?.providers, history?.providers);
    currentBaseUrl = baseUrl;

    renderStats(allProviders);
    renderProviderCards(allProviders, currentBaseUrl);
    renderHeatmap(history);
    renderChangelog(history);

    // Update API example with actual URL
    updateApiExample(currentBaseUrl);

    // Initialize tooltips
    initTooltips();
}

/**
 * Initialize custom tooltips for elements with data-tooltip attribute
 */
function initTooltips() {
    let tooltip = document.getElementById('custom-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'custom-tooltip';
        tooltip.className = 'custom-tooltip';
        document.body.appendChild(tooltip);
    }

    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('[data-tooltip]');
        if (target) {
            const text = target.getAttribute('data-tooltip');
            tooltip.innerHTML = text.replace(/\n/g, '<br>');
            tooltip.classList.add('visible');

            const rect = target.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();

            let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            let top = rect.top - tooltipRect.height - 8;

            // Keep tooltip within viewport
            if (left < 8) left = 8;
            if (left + tooltipRect.width > window.innerWidth - 8) {
                left = window.innerWidth - tooltipRect.width - 8;
            }
            if (top < 8) {
                top = rect.bottom + 8;
            }

            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
        }
    });

    document.addEventListener('mouseout', (e) => {
        const target = e.target.closest('[data-tooltip]');
        if (target) {
            tooltip.classList.remove('visible');
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
