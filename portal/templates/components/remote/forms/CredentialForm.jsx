import React, { useState } from 'react';
import { storeCredential } from '../api/remoteApi';
import './CredentialForm.css';

/**
 * CredentialForm Component
 * 
 * Form untuk input dan store encrypted credential
 * - Password input
 * - Remember password checkbox
 * - Validation
 * - API integration
 */
export const CredentialForm = ({
  deviceId,
  toolType,
  onSuccess,
  onCancel,
}) => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rememberPassword, setRememberPassword] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  const validateForm = () => {
    if (!password || !confirmPassword) {
      setError('Both password fields are required');
      return false;
    }
    if (password.length < 4) {
      setError('Password must be at least 4 characters');
      return false;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      await storeCredential(deviceId, toolType, {
        password,
        remember_password: rememberPassword,
      });

      setPassword('');
      setConfirmPassword('');
      onSuccess?.();
    } catch (err) {
      setError(`Failed to save credential: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form className="credential-form" onSubmit={handleSubmit}>
      {error && <div className="form-error">{error}</div>}

      <div className="form-group">
        <label htmlFor={`password-${toolType}`}>Password</label>
        <div className="password-input-group">
          <input
            id={`password-${toolType}`}
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            className="form-control"
            disabled={isLoading}
            autoComplete="off"
          />
          <button
            type="button"
            className="show-password-btn"
            onClick={() => setShowPassword(!showPassword)}
            title={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? '👁️' : '👁️‍🗨️'}
          </button>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor={`confirm-password-${toolType}`}>Confirm Password</label>
        <input
          id={`confirm-password-${toolType}`}
          type={showPassword ? 'text' : 'password'}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Confirm password"
          className="form-control"
          disabled={isLoading}
          autoComplete="off"
        />
      </div>

      <div className="form-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={rememberPassword}
            onChange={(e) => setRememberPassword(e.target.checked)}
            disabled={isLoading}
          />
          <span>Remember this password</span>
        </label>
        <small>Uncheck if sharing this account</small>
      </div>

      <div className="form-actions">
        <button
          type="submit"
          className="btn-submit"
          disabled={isLoading}
        >
          {isLoading ? '💾 Saving...' : '💾 Save Password'}
        </button>
        <button
          type="button"
          className="btn-cancel"
          onClick={onCancel}
          disabled={isLoading}
        >
          Cancel
        </button>
      </div>

      <div className="form-info">
        <p>
          🔒 Your password will be encrypted with AES-256-GCM before storage.
          Never stored or logged in plaintext.
        </p>
      </div>
    </form>
  );
};

export default CredentialForm;
