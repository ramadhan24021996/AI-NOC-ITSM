import React, { useState } from 'react';
import './GeneralTab.css';

/**
 * GeneralTab Component
 * 
 * Menampilkan device information dan general settings
 * - Device name, hostname, IP address
 * - Site assignment
 * - Status, last online
 * - Preferred tool selection
 * - Auto-connect toggle
 */
export const GeneralTab = ({ config, deviceId, deviceName, onUpdate }) => {
  const [preferredTool, setPreferredTool] = useState(config?.preferred_tool || 'rustdesk');
  const [autoConnect, setAutoConnect] = useState(config?.auto_connect !== false);
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveSettings = async () => {
    try {
      setIsSaving(true);
      await onUpdate({
        preferred_tool: preferredTool,
        auto_connect: autoConnect,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="general-tab">
      <div className="tab-section">
        <h3>Device Information</h3>
        <div className="info-grid">
          <div className="info-item">
            <label>Device Name</label>
            <value>{deviceName || 'N/A'}</value>
          </div>
          <div className="info-item">
            <label>Device ID</label>
            <value className="monospace">{deviceId}</value>
          </div>
          <div className="info-item">
            <label>Status</label>
            <value>
              <span className={`status-badge ${config?.status || 'unknown'}`}>
                {config?.status || 'Unknown'}
              </span>
            </value>
          </div>
          <div className="info-item">
            <label>Last Online</label>
            <value>
              {config?.last_online
                ? new Date(config.last_online).toLocaleString()
                : 'Never'}
            </value>
          </div>
        </div>
      </div>

      <div className="tab-section">
        <h3>Remote Access Settings</h3>
        <div className="settings-form">
          <div className="form-group">
            <label htmlFor="preferred-tool">Preferred Remote Tool</label>
            <select
              id="preferred-tool"
              value={preferredTool}
              onChange={(e) => setPreferredTool(e.target.value)}
              className="form-control"
            >
              <option value="anydesk">AnyDesk</option>
              <option value="rustdesk">RustDesk</option>
              <option value="vnc">VNC</option>
            </select>
            <small>Default tool for one-click launch</small>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={autoConnect}
                onChange={(e) => setAutoConnect(e.target.checked)}
              />
              <span>Auto-connect on launch</span>
            </label>
            <small>Automatically establish connection when launching</small>
          </div>

          <button
            className="btn-save"
            onClick={handleSaveSettings}
            disabled={isSaving}
          >
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>

      {config?.detection_info && (
        <div className="tab-section info-section">
          <h3>Detection Information</h3>
          <div className="detection-info">
            <p>
              <strong>Last Detected:</strong>{' '}
              {new Date(config.detection_info.last_detected).toLocaleString()}
            </p>
            <p>
              <strong>Status:</strong> {config.detection_info.status}
            </p>
            {config.detection_info.anydesk_id && (
              <p>
                <strong>AnyDesk:</strong> {config.detection_info.anydesk_id}
              </p>
            )}
            {config.detection_info.rustdesk_id && (
              <p>
                <strong>RustDesk:</strong> {config.detection_info.rustdesk_id}
              </p>
            )}
            {config.detection_info.vnc_port && (
              <p>
                <strong>VNC:</strong> Port {config.detection_info.vnc_port}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default GeneralTab;
