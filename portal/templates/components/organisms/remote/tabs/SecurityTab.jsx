import React from 'react';
import './UtilityTab.css';

/**
 * SecurityTab Component
 * 
 * Security settings and best practices
 * - TLS/SSL configuration
 * - Encryption settings
 * - Authentication options
 * - Audit logging
 */
export const SecurityTab = ({ config, deviceId, onUpdate }) => {
  return (
    <div className="utility-tab">
      <div className="info-box info-warning">
        <h4>🔒 Security Configuration</h4>
        <p>
          Manage security settings for remote access connections
        </p>
      </div>

      <div className="section">
        <h3>Security Features</h3>
        <div className="feature-list">
          <div className="feature-item">
            <span className="feature-status">✓</span>
            <div>
              <h4>AES-256-GCM Encryption</h4>
              <p>Passwords encrypted in database with authenticated encryption</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-status">✓</span>
            <div>
              <h4>JWT Token Authentication</h4>
              <p>All API requests require valid authentication tokens</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-status">✓</span>
            <div>
              <h4>Audit Logging</h4>
              <p>All actions logged for compliance and security review</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-status">✓</span>
            <div>
              <h4>Session Tracking</h4>
              <p>Active sessions monitored and logged</p>
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <h3>Best Practices</h3>
        <ul className="best-practices">
          <li>Use strong, unique passwords for each device</li>
          <li>Regularly rotate credentials</li>
          <li>Keep remote access software updated</li>
          <li>Monitor active sessions for unauthorized access</li>
          <li>Review audit logs regularly</li>
          <li>Use VPN when accessing from untrusted networks</li>
          <li>Enable multi-factor authentication when available</li>
        </ul>
      </div>

      <div className="coming-soon">
        <p>🔄 Advanced security settings available in Phase 5</p>
      </div>
    </div>
  );
};

export default SecurityTab;
