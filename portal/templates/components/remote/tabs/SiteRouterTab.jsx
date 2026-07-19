import React from 'react';
import './UtilityTab.css';

/**
 * SiteRouterTab Component
 * 
 * Configure multi-site routing
 * - Select site assignment
 * - Route configuration
 * - Gateway settings
 */
export const SiteRouterTab = ({ config, deviceId, onUpdate }) => {
  return (
    <div className="utility-tab">
      <div className="info-box info-blue">
        <h4>🌐 Site Router Configuration</h4>
        <p>
          Configure which site/network this device belongs to and set routing preferences.
        </p>
      </div>

      <div className="section">
        <h3>Site Assignment</h3>
        <div className="feature-list">
          <div className="feature-item">
            <span className="feature-status">📍</span>
            <div>
              <h4>Primary Site</h4>
              <p>Assign device to headquarter, branch, or remote site</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-status">🛣️</span>
            <div>
              <h4>Route Preference</h4>
              <p>Select preferred network route for connection</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-status">⚙️</span>
            <div>
              <h4>Gateway Configuration</h4>
              <p>Configure VPN or proxy gateway if needed</p>
            </div>
          </div>
        </div>
      </div>

      <div className="info-box info-note">
        <p>
          <strong>Note:</strong> Site assignment is automatically detected during device
          discovery. You can override these settings here if needed.
        </p>
      </div>

      <div className="coming-soon">
        <p>🔄 Site routing configuration will be available in Phase 4</p>
      </div>
    </div>
  );
};

export default SiteRouterTab;
