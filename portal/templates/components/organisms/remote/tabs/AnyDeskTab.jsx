import React, { useState } from 'react';
import CredentialForm from '../forms/CredentialForm';
import './RemoteToolTab.css';

/**
 * AnyDeskTab Component
 * 
 * Configure AnyDesk remote access
 * - Display detected AnyDesk ID
 * - Manual AnyDesk ID entry
 * - Password management
 * - Launch button
 */
export const AnyDeskTab = ({ config, deviceId, onUpdate, onLaunch }) => {
  const [showForm, setShowForm] = useState(false);
  const [manualId, setManualId] = useState(config?.anydesk_id || '');

  const handleSaveId = async (password) => {
    await onUpdate({
      anydesk_id: manualId,
    });
    // Note: Password is handled by CredentialForm POST to /api/remote/device/<id>/credentials
    setShowForm(false);
  };

  return (
    <div className="remote-tool-tab">
      <div className="tool-header">
        <h3>🔴 AnyDesk Configuration</h3>
        <p className="tool-description">
          Configure AnyDesk Unattended Access for remote connection
        </p>
      </div>

      {config?.anydesk_id && (
        <div className="detected-info">
          <div className="info-box">
            <h4>✓ Detected AnyDesk ID</h4>
            <value className="anydesk-id">{config.anydesk_id}</value>
            <small>Auto-detected from device registry</small>
          </div>
        </div>
      )}

      <div className="manual-entry-section">
        <h4>Manual Configuration</h4>
        <div className="form-group">
          <label htmlFor="anydesk-id">AnyDesk ID</label>
          <input
            id="anydesk-id"
            type="text"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
            placeholder="e.g., 123456789"
            className="form-control"
          />
          <small>12-digit numeric ID from this device</small>
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
            toolType="anydesk"
            onSuccess={() => setShowForm(false)}
            onCancel={() => setShowForm(false)}
          />
        )}
      </div>

      <div className="action-section">
        <button
          className="btn-launch anydesk"
          onClick={onLaunch}
          disabled={!config?.anydesk_id && !manualId}
        >
          🔴 Launch AnyDesk
        </button>
      </div>
    </div>
  );
};

export default AnyDeskTab;
