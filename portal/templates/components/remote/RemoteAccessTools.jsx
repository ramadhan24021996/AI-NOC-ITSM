import React, { useState, useEffect } from 'react';
import RemoteSettingsModal from './RemoteSettingsModal';
import { launchRemoteTool, checkLauncherHealth } from './api/launchApi';
import './RemoteAccessTools.css';

/**
 * RemoteAccessTools Component - Phase 3 & 4
 * 
 * Main UI component untuk Remote Access Settings
 * - Display settings icon (⚙) untuk konfigurasi
 * - Quick launch buttons untuk one-click remote access
 * - Direct integration dengan Launcher Service (Phase 1)
 */
export const RemoteAccessTools = ({ deviceId, deviceName, onLaunchRequest }) => {
  const [showModal, setShowModal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [launcherHealthy, setLauncherHealthy] = useState(true);
  const [launchStatus, setLaunchStatus] = useState(null);
  const [error, setError] = useState(null);

  const handleSettingsClick = () => {
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
  };

  return (
    <>
      {/* Settings Icon Button */}
      <div className="remote-access-tools">
        <button
          className="settings-btn"
          onClick={handleSettingsClick}
          title="Configure Remote Access"
          disabled={isLoading}
        >
          <span className="settings-icon">⚙</span>
          <span className="settings-label">Settings</span>
        </button>

        {/* Quick Launch Buttons */}
        <div className="quick-launch-buttons">
          <button
            className="launch-btn anydesk-btn"
            onClick={() => onLaunchRequest?.(deviceId, 'anydesk')}
            title="Launch AnyDesk"
          >
            AnyDesk
          </button>
          <button
            className="launch-btn rustdesk-btn"
            onClick={() => onLaunchRequest?.(deviceId, 'rustdesk')}
            title="Launch RustDesk"
          >
            RustDesk
          </button>
          <button
            className="launch-btn vnc-btn"
            onClick={() => onLaunchRequest?.(deviceId, 'vnc')}
            title="Launch VNC"
          >
            VNC
          </button>
        </div>
      </div>

      {/* Settings Modal */}
      {showModal && (
        <RemoteSettingsModal
          deviceId={deviceId}
          deviceName={deviceName}
          onClose={handleCloseModal}
          onLaunchRequest={onLaunchRequest}
        />
      )}
    </>
  );
};

export default RemoteAccessTools;
