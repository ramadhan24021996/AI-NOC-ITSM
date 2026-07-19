import React, { useState } from 'react';
import CredentialForm from '../forms/CredentialForm';
import './RemoteToolTab.css';

/**
 * RustDeskTab Component
 * 
 * Configure RustDesk remote access
 * - Display detected RustDesk ID
 * - Manual RustDesk ID entry
 * - Password management
 * - Launch button
 */
export const RustDeskTab = ({ config, deviceId, onUpdate, onLaunch }) => {
  const [showForm, setShowForm] = useState(false);
  const [manualId, setManualId] = useState(config?.rustdesk_id || '');

  const handleSaveId = async (password) => {
    await onUpdate({
      rustdesk_id: manualId,
    });
    setShowForm(false);
  };

  return (
    <div className="remote-tool-tab">
      <div className="tool-header">
        <h3>🔵 RustDesk Configuration</h3>
        <p className="tool-description">
          Configure RustDesk remote access for this device
        </p>
      </div>

      {config?.rustdesk_id && (
        <div className="detected-info">
          <div className="info-box">
            <h4>✓ Detected RustDesk ID</h4>
            <value className="rustdesk-id">{config.rustdesk_id}</value>
            <small>Auto-detected from device configuration</small>
          </div>
        </div>
      )}

      <div className="manual-entry-section">
        <h4>Manual Configuration</h4>
        <div className="form-group">
          <label htmlFor="rustdesk-id">RustDesk ID</label>
          <input
            id="rustdesk-id"
            type="text"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
            placeholder="e.g., 987654321"
            className="form-control"
          />
          <small>Numeric ID from this device</small>
        </div>
      </div>

      <div className="credential-section">
        <h4>Credentials</h4>
        {!showForm ? (
          <button
            className="btn-primary"
            onClick={() => setShowForm(true)}
          >
            + Add/Update Password
          </button>
        ) : (
          <CredentialForm
            deviceId={deviceId}
            toolType="rustdesk"
            onSuccess={() => setShowForm(false)}
            onCancel={() => setShowForm(false)}
          />
        )}
      </div>

      <div className="action-section">
        <button
          className="btn-launch rustdesk"
          onClick={onLaunch}
          disabled={!config?.rustdesk_id && !manualId}
        >
          🔵 Launch RustDesk
        </button>
      </div>
    </div>
  );
};

export default RustDeskTab;
