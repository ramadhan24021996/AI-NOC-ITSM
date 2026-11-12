/* core/error-handler.js
 * Global error handler & fetch interceptor
 * Extracted from index.html - Phase 2 refactor
 */

window.onerror = function (msg, url, lineNo, columnNo, error) {
      var errDiv = document.createElement('div');
      errDiv.style.position = 'fixed';
      errDiv.style.top = '10px';
      errDiv.style.left = '10px';
      errDiv.style.background = 'red';
      errDiv.style.color = 'white';
      errDiv.style.padding = '10px';
      errDiv.style.zIndex = '99999';
      errDiv.innerHTML = 'ERROR: ' + msg + '<br>Line: ' + lineNo;
      document.body ? document.body.appendChild(errDiv) : window.addEventListener('DOMContentLoaded', () => document.body.appendChild(errDiv));
      return false;
    };
    window.addEventListener('unhandledrejection', function (event) {
      var errDiv = document.createElement('div');
      errDiv.style.position = 'fixed';
      errDiv.style.top = '50px';
      errDiv.style.left = '10px';
      errDiv.style.background = 'orange';
      errDiv.style.color = 'black';
      errDiv.style.padding = '10px';
      errDiv.style.zIndex = '99999';
      errDiv.innerHTML = 'PROMISE REJECTION: ' + (event.reason ? event.reason.message || event.reason : 'Unknown error');
      document.body ? document.body.appendChild(errDiv) : window.addEventListener('DOMContentLoaded', () => document.body.appendChild(errDiv));
    });

    // Intercept window.fetch globally to inject Basic Auth credentials from sessionStorage
    (function () {
      const originalFetch = window.fetch;
      window.fetch = function (url, options) {
        options = options || {};
        options.headers = options.headers || {};

        let headersObj = {};
        if (options.headers instanceof Headers) {
          options.headers.forEach((value, key) => {
            headersObj[key] = value;
          });
        } else {
          headersObj = options.headers;
        }

        const token = sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token') || localStorage.getItem('token');
        if (token && !headersObj['Authorization']) {
          const urlStr = String(url);
          if (urlStr.startsWith('/') || urlStr.startsWith(window.location.origin) || !urlStr.match(/^[a-z0-9]+:\/\//i)) {
            headersObj['Authorization'] = 'Bearer ' + token;
            if (options.method && options.method.toUpperCase() !== 'GET' && options.method.toUpperCase() !== 'HEAD') {
              headersObj['X-CSRF-Token'] = token;
            }
          }
        }

        options.headers = headersObj;
        return originalFetch(url, options);
      };
    })();
