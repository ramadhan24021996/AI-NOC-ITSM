// OSI Chrome Extension Service Worker (background.js)
const BACKEND_URL = "http://localhost:9999";
let activeTabId = null;
let tabStartTime = Date.now();
let tabSwitchCount = 0;
let tabDetails = {};

// Listen for tab switching
chrome.tabs.onActivated.addListener((info) => {
  const now = Date.now();
  if (activeTabId !== null) {
    const elapsed = Math.round((now - tabStartTime) / 1000);
    reportTimeSpent(activeTabId, elapsed);
  }
  activeTabId = info.tabId;
  tabStartTime = now;
  tabSwitchCount++;
});

// Listen for navigation errors (e.g. DNS failure, Timeout)
chrome.webNavigation.onErrorOccurred.addListener((details) => {
  if (details.frameId !== 0) return; // Only main frame

  const url = new URL(details.url);
  const issues = [];
  let issueType = "NETWORK_TIMEOUT";

  if (details.error.includes("DNS") || details.error.includes("NAME_NOT_RESOLVED")) {
    issueType = "DNS_FAILURE";
  } else if (details.error.includes("TIMED_OUT")) {
    issueType = "NETWORK_TIMEOUT";
  } else if (details.error.includes("ABORTED")) {
    issueType = "PAGE_TIMEOUT";
  }

  issues.push(issueType);

  const payload = {
    type: "browser_issue",
    browser: "chrome",
    issue: issueType,
    url: details.url,
    domain: url.hostname,
    severity: "high",
    issues: issues,
    timestamp: Math.round(Date.now() / 1000)
  };

  sendToServer("/issues", payload);
  sendToServer("/browser-events", {
    type: "web_activity",
    browser: "chrome",
    url: details.url,
    domain: url.hostname,
    tab_title: "Error Page",
    active_time_sec: 0,
    tab_state: "error",
    issues: issues,
    status_code: 500
  });
});

// Listen for messages from content.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'perf_metrics') {
    const tabId = sender.tab ? sender.tab.id : null;
    if (tabId) {
      tabDetails[tabId] = {
        url: message.url,
        domain: message.domain,
        title: message.tab_title,
        load_time_ms: message.load_time_ms,
        dom_ready_ms: message.dom_ready_ms,
        dns_time_ms: message.dns_time_ms,
        redirect_count: message.redirect_count,
        memory_mb: message.memory_mb,
        scroll_activity: message.scroll_activity
      };
    }

    // Evaluate Issue Rules client-side
    const issues = [];
    if (message.load_time_ms > 3000) {
      issues.push("SLOW_PAGE");
    }
    if (message.dns_time_ms === 0 || message.dns_time_ms > 500) {
      issues.push("DNS_FAILURE");
    }
    if (message.memory_mb > 500) {
      issues.push("HIGH_MEMORY_TAB");
    }

    const activityPayload = {
      type: "web_activity",
      browser: "chrome",
      url: message.url,
      domain: message.domain,
      tab_title: message.tab_title,
      active_time_sec: 1,
      tab_state: "active",
      scroll_activity: message.scroll_activity,
      tab_switch_count: tabSwitchCount,
      status_code: message.status_code || 200,
      latency_ms: message.load_time_ms,
      dns_time_ms: message.dns_time_ms,
      redirect_count: message.redirect_count,
      load_time_ms: message.load_time_ms,
      dom_ready_ms: message.dom_ready_ms,
      memory_mb: message.memory_mb,
      issues: issues
    };

    sendToServer("/browser-events", activityPayload);
    sendToServer("/activity", {
      type: "active_app",
      app_name: "chrome",
      process: "chrome.exe",
      window_title: message.tab_title,
      timestamp: Math.round(Date.now() / 1000)
    });

    if (issues.length > 0) {
      sendToServer("/issues", {
        type: "browser_issue",
        browser: "chrome",
        issues: issues,
        url: message.url,
        domain: message.domain,
        severity: issues.includes("DNS_FAILURE") ? "high" : "medium",
        timestamp: Math.round(Date.now() / 1000)
      });
    }
  }
});

function reportTimeSpent(tabId, seconds) {
  const details = tabDetails[tabId];
  if (!details) return;

  const payload = {
    type: "web_activity",
    browser: "chrome",
    url: details.url,
    domain: details.domain,
    tab_title: details.title,
    active_time_sec: seconds,
    tab_state: "inactive",
    tab_switch_count: tabSwitchCount,
    scroll_activity: details.scroll_activity || false,
    load_time_ms: details.load_time_ms || 0,
    dom_ready_ms: details.dom_ready_ms || 0,
    dns_time_ms: details.dns_time_ms || 0,
    memory_mb: details.memory_mb || 0,
    redirect_count: details.redirect_count || 0
  };

  sendToServer("/browser-events", payload);
}

function sendToServer(endpoint, data) {
  fetch(BACKEND_URL + endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(data)
  })
  .then(res => {
    if (!res.ok) {
      throw new Error("HTTP error " + res.status);
    }
  })
  .catch(err => {
    console.warn("OSI extension failed to send to server:", err);
  });
}
