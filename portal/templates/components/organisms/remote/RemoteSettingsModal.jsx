import React, { useState, useEffect } from 'react';
import GeneralTab from './tabs/GeneralTab';
import AnyDeskTab from './tabs/AnyDeskTab';
import RustDeskTab from './tabs/RustDeskTab';
import VNCTab from './tabs/VNCTab';
import SiteRouterTab from './tabs/SiteRouterTab';
import SecurityTab from './tabs/SecurityTab';
import TestConnectionTab from './tabs/TestConnectionTab';
import { fetchDeviceConfig, updateDeviceConfig } from '../api/remoteApi';
import './RemoteSettingsModal.css';

/**
 * RemoteSettingsModal Component
 * 
 * Multi-tab modal para configure remote access
 * Tabs:
 * 1. General - Device info, site assignment
 * 2. AnyDesk - AnyDesk ID, password
 * 3. RustDesk - RustDesk ID, password
 * 4. VNC - Host, port, password
 * 5. SiteRouter - Multi-site routing config
 * 6. Security - TLS, encryption, auth settings
 * 7. TestConnection - Verify connectivity
 */
export const RemoteSettingsModal = ({ deviceId, deviceName, onClose, onLaunchRequest }) => {
  const [activeTab, setActiveTab] = useState('general');
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const tabs = [
    { id: 'general', label: 'General', icon: '📋' },
    { id: 'anydesk', label: 'AnyDesk', icon: '🔴' },
    { id: 'rustdesk', label: 'RustDesk', icon: '🔵' },
    { id: 'vnc', label: 'VNC', icon: '🟢' },
    { id: 'siterouter', label: 'SiteRouter', icon: '🌐' },
    { id: 'security', label: 'Security', icon: '🔒' },
    { id: 'testconnection', label: 'Test Connection', icon: '✓' },
  ];

  // Load device config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        const data = await fetchDeviceConfig(deviceId);
        setConfig(data);
        setError(null);
      } catch (err) {
        setError(`Failed to load device config: ${err.message}`);
        setConfig(null);
      } finally {
        setLoading(false);
      }
    };

    loadConfig();
  }, [deviceId]);

  // Handle config update
  const handleConfigUpdate = async (updates) => {
    try {
      setSaving(true);
      const updated = await updateDeviceConfig(deviceId, updates);
      setConfig(updated);
      setSuccess('Configuration saved successfully');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(`Failed to save config: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Render tab content
  const renderTabContent = () => {
    if (loading) {
      return <div className="tab-loading">Loading configuration...</div>;
    }

    if (error) {
      return <div className="tab-error">{error}</div>;
    }

    switch (activeTab) {
      case 'general':
        return (
          <GeneralTab
            config={config}
            deviceId={deviceId}
            deviceName={deviceName}
            onUpdate={handleConfigUpdate}
          />
        );
      case 'anydesk':
        return (
          <AnyDeskTab
            config={config}
            deviceId={deviceId}
            onUpdate={handleConfigUpdate}
            onLaunch={() => onLaunchRequest?.(deviceId, 'anydesk')}
          />
        );
      case 'rustdesk':
        return (
          <RustDeskTab
            config={config}
            deviceId={deviceId}
            onUpdate={handleConfigUpdate}
            onLaunch={() => onLaunchRequest?.(deviceId, 'rustdesk')}
          />
        );
      case 'vnc':
        return (
          <VNCTab
            config={config}
            deviceId={deviceId}
            onUpdate={handleConfigUpdate}
            onLaunch={() => onLaunchRequest?.(deviceId, 'vnc')}
          />
        );
      case 'siterouter':
        return (
          <SiteRouterTab
            config={config}
            deviceId={deviceId}
            onUpdate={handleConfigUpdate}
          />
        );
      case 'security':
        return (
          <SecurityTab
            config={config}
            deviceId={deviceId}
            onUpdate={handleConfigUpdate}
          />
        );
      case 'testconnection':
        return (
          <TestConnectionTab
            config={config}
            deviceId={deviceId}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <h2>Remote Access Settings</h2>
          <div className="header-info">
            <span className="device-name">{deviceName}</span>
            <span className="device-id">{deviceId}</span>
          </div>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Messages */}
        {success && <div className="success-message">{success}</div>}
        {error && <div className="error-message">{error}</div>}

        {/* Tab Navigation */}
        <div className="tab-navigation">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
              title={tab.label}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {renderTabContent()}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button
            className="btn-cancel"
            onClick={onClose}
            disabled={saving || loading}
          >
            Close
          </button>
          <span className="save-indicator">
            {saving && <span className="spinner">⟳ Saving...</span>}
          </span>
        </div>
      </div>
    </div>
  );
};

export default RemoteSettingsModal;
