import React, { useState } from 'react';
import './UtilityTab.css';
import { testConnection } from '../api/remoteApi';

/**
 * TestConnectionTab Component
 * 
 * Test connectivity to device
 * - Detect available tools
 * - Verify connectivity
 * - Show detection status
 */
export const TestConnectionTab = ({ config, deviceId }) => {
  const [testResults, setTestResults] = useState(null);
  const [isTesting, setIsTesting] = useState(false);

  const handleTestConnection = async () => {
    try {
      setIsTesting(true);
      const results = await testConnection(deviceId);
      setTestResults(results);
    } catch (error) {
      setTestResults({
        success: false,
        error: error.message,
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="utility-tab">
      <div className="info-box info-green">
        <h4>✓ Test Connection</h4>
        <p>
          Verify device connectivity and remote access tool availability
        </p>
      </div>

      <div className="section">
        <h3>Current Configuration</h3>
        <div className="config-summary">
          {config?.anydesk_id && (
            <div className="config-item">
              <span className="icon">🔴</span>
              <div>
                <strong>AnyDesk:</strong> {config.anydesk_id}
              </div>
            </div>
          )}
          {config?.rustdesk_id && (
            <div className="config-item">
              <span className="icon">🔵</span>
              <div>
                <strong>RustDesk:</strong> {config.rustdesk_id}
              </div>
            </div>
          )}
          {config?.vnc_host && (
            <div className="config-item">
              <span className="icon">🟢</span>
              <div>
                <strong>VNC:</strong> {config.vnc_host}:{config.vnc_port || 5900}
              </div>
            </div>
          )}
          {!config?.anydesk_id && !config?.rustdesk_id && !config?.vnc_host && (
            <p className="no-config">No remote tools configured yet</p>
          )}
        </div>
      </div>

      <div className="section">
        <button
          className="btn-test"
          onClick={handleTestConnection}
          disabled={isTesting}
        >
          {isTesting ? '🔄 Testing...' : '✓ Test Connection'}
        </button>
      </div>

      {testResults && (
        <div className="section">
          <h3>Test Results</h3>
          {testResults.success ? (
            <div className="results-success">
              <p>✓ Connection test passed</p>
              {testResults.details && (
                <pre>{JSON.stringify(testResults.details, null, 2)}</pre>
              )}
            </div>
          ) : (
            <div className="results-error">
              <p>✗ Connection test failed</p>
              <p>{testResults.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TestConnectionTab;
