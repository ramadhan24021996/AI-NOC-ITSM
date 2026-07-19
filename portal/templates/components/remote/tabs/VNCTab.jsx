import React, { useState } from 'react';
import CredentialForm from '../forms/CredentialForm';
import './RemoteToolTab.css';

/**
 * VNCTab Component
 * 
 * Configure VNC remote access
 * - Display detected VNC port
 * - Manual VNC host/port entry
 * - Password management
 * - Launch button
 */
export const VNCTab = ({ config, deviceId, onUpdate, onLaunch }) => {
  const [showForm, setShowForm] = useState(false);
  const [vncHost, setVncHost] = useState(config?.vnc_host || '127.0.0.1');
  const [vncPort, setVncPort] = useState(config?.vnc_port || 5900);

  const handleSaveConfig = async () => {
    await onUpdate({
      vnc_host: vncHost,
      vnc_port: vncPort,
    });
  };

  return (
    <div className="remote-tool-tab">
      <div className="tool-header">
        <h3>🟢 VNC Configuration</h3>
        <p className="tool-description">
          Configure VNC viewer for remote connection
        </p>
      </div>

      {config?.vnc_port && (
        <div className="detected-info">
          <div className="info-box">
            <h4>✓ Detected VNC</h4>
            <value className="vnc-connection">
              {config.vnc_host}:{config.vnc_port}
            </value>
            <small>Auto-detected from device</small>
          </div>
        </div>
      )}

      <div className="manual-entry-section">
        <h4>Manual Configuration</h4>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="vnc-host">VNC Host</label>
            <input
              id="vnc-host"
              type="text"
              value={vncHost}
              onChange={(e) => setVncHost(e.target.value)}
              placeholder="e.g., 192.168.1.100"
              className="form-control"
            />
            <small>IP address or hostname</small>
          </div>
          <div className="form-group">
            <label htmlFor="vnc-port">VNC Port</label>
            <input
              id="vnc-port"
              type="number"
              value={vncPort}
              onChange={(e) => setVncPort(parseInt(e.target.value))}
              placeholder="5900"
              min="1024"
              max="65535"
              className="form-control"
            />
            <small>Default: 5900</small>
          </div>
        </div>
        <button
          className="btn-save"
          onClick={handleSaveConfig}
        >
          Save Configuration
        </button>
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
            toolType="vnc"
            onSuccess={() => setShowForm(false)}
            onCancel={() => setShowForm(false)}
          />
        )}
      </div>

      <div className="action-section">
        <button
          className="btn-launch vnc"
          onClick={onLaunch}
          disabled={!vncHost}
        >
          🟢 Launch VNC
        </button>
      </div>
    </div>
  );
};

export default VNCTab;
