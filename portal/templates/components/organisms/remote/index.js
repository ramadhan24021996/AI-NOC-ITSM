/**
 * Remote Access Components Index
 * 
 * Export all remote access components for easy integration
 */

// Main components
export { RemoteAccessTools } from './RemoteAccessTools';
export { RemoteSettingsModal } from './RemoteSettingsModal';

// Tab components
export { GeneralTab } from './tabs/GeneralTab';
export { AnyDeskTab } from './tabs/AnyDeskTab';
export { RustDeskTab } from './tabs/RustDeskTab';
export { VNCTab } from './tabs/VNCTab';
export { SiteRouterTab } from './tabs/SiteRouterTab';
export { SecurityTab } from './tabs/SecurityTab';
export { TestConnectionTab } from './tabs/TestConnectionTab';

// Form components
export { CredentialForm } from './forms/CredentialForm';

// API service
export * from './api/remoteApi';
