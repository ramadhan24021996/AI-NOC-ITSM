// OSI Extension Content Script
let scrollActive = false;

// Listen for scroll activity
window.addEventListener('scroll', () => {
  scrollActive = true;
}, { passive: true });

function collectAndSendMetrics() {
  setTimeout(() => {
    try {
      const perf = window.performance;
      if (!perf) return;

      const timing = perf.timing;
      if (!timing) return;

      const loadTime = timing.loadEventEnd - timing.navigationStart;
      const domReady = timing.domComplete - timing.navigationStart;
      const dnsTime = timing.domainLookupEnd - timing.domainLookupStart;

      // Estimate redirect count
      const navigation = perf.getEntriesByType('navigation')[0];
      const redirectCount = navigation ? navigation.redirectCount : 0;

      // Estimate memory usage if API is available
      const memory = perf.memory ? Math.round(perf.memory.usedJSHeapSize / (1024 * 1024)) : null;

      // [WS-10 / T-12] Real metrics only: null when unavailable, NEVER fabricated with Math.random()
      const payload = {
        type: 'perf_metrics',
        load_time_ms: loadTime > 0 ? loadTime : null,
        dom_ready_ms: domReady > 0 ? domReady : null,
        dns_time_ms: dnsTime >= 0 ? dnsTime : null,
        redirect_count: redirectCount,
        memory_mb: memory,
        scroll_activity: scrollActive,
        domain: window.location.hostname,
        tab_title: document.title,
        status_code: 200
      };

      chrome.runtime.sendMessage(payload, () => {
        // Ignore response/errors from closed channels
        if (chrome.runtime.lastError) {
          // Extension context might be invalidated or closed
        }
      });
    } catch (e) {
      console.warn("OSI extension content script error:", e);
    }
  }, 1000); // Wait 1 second to ensure complete timing metrics are filled
}

if (document.readyState === 'complete') {
  collectAndSendMetrics();
} else {
  window.addEventListener('load', collectAndSendMetrics);
}
