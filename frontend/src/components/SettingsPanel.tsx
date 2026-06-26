import type { AdminDashboard } from "../types";
import type { DisplayMode } from "../authStorage";

export type SettingsTab =
  | "general"
  | "account"
  | "privacy"
  | "safety"
  | "admin";
export type ExportScope = "all" | "current";

// SettingsPanel is intentionally controlled by App.tsx. The panel renders the
// active tab, while App owns auth tokens, profile state, export filters, and
// admin dashboard loading.
interface SettingsPanelProps {
  activeTab: SettingsTab;
  tabs: SettingsTab[];
  displayMode: DisplayMode;
  profileName: string;
  profileEmail: string;
  profileCurrentPassword: string;
  profileNewPassword: string;
  profileStatus: string | null;
  exportScope: ExportScope;
  exportFromDate: string;
  exportToDate: string;
  adminDashboard: AdminDashboard | null;
  isLoadingAdminDashboard: boolean;
  onClose: () => void;
  onTabChange: (tab: SettingsTab) => void;
  onDisplayModeChange: (mode: DisplayMode) => void;
  onProfileNameChange: (value: string) => void;
  onProfileEmailChange: (value: string) => void;
  onProfileCurrentPasswordChange: (value: string) => void;
  onProfileNewPasswordChange: (value: string) => void;
  onExportScopeChange: (value: ExportScope) => void;
  onExportFromDateChange: (value: string) => void;
  onExportToDateChange: (value: string) => void;
  onSaveProfile: () => void;
  onSignOut: () => void;
  onExportSavedChats: () => void;
  onDeleteAccount: () => void;
  onRefreshAdminDashboard: () => void;
}

export function SettingsPanel({
  activeTab,
  tabs,
  displayMode,
  profileName,
  profileEmail,
  profileCurrentPassword,
  profileNewPassword,
  profileStatus,
  exportScope,
  exportFromDate,
  exportToDate,
  adminDashboard,
  isLoadingAdminDashboard,
  onClose,
  onTabChange,
  onDisplayModeChange,
  onProfileNameChange,
  onProfileEmailChange,
  onProfileCurrentPasswordChange,
  onProfileNewPasswordChange,
  onExportScopeChange,
  onExportFromDateChange,
  onExportToDateChange,
  onSaveProfile,
  onSignOut,
  onExportSavedChats,
  onDeleteAccount,
  onRefreshAdminDashboard,
}: SettingsPanelProps) {
  return (
    <section
      id="settings-panel"
      className="settings-panel"
      aria-labelledby="settings-heading"
    >
      <div className="settings-header">
        <div>
          <h2 id="settings-heading">Settings</h2>
          <p>{activeTab[0].toUpperCase() + activeTab.slice(1)}</p>
        </div>

        <button
          className="secondary-button compact-button"
          type="button"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      <div className="settings-tabs" role="tablist">
        {tabs.map((tabName) => (
          <button
            key={tabName}
            type="button"
            role="tab"
            aria-selected={activeTab === tabName}
            className={activeTab === tabName ? "active" : undefined}
            onClick={() => onTabChange(tabName)}
          >
            {tabName[0].toUpperCase() + tabName.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === "general" && (
        <GeneralSettings
          displayMode={displayMode}
          onDisplayModeChange={onDisplayModeChange}
        />
      )}

      {activeTab === "account" && (
        <AccountSettings
          profileName={profileName}
          profileEmail={profileEmail}
          profileCurrentPassword={profileCurrentPassword}
          profileNewPassword={profileNewPassword}
          profileStatus={profileStatus}
          onProfileNameChange={onProfileNameChange}
          onProfileEmailChange={onProfileEmailChange}
          onProfileCurrentPasswordChange={onProfileCurrentPasswordChange}
          onProfileNewPasswordChange={onProfileNewPasswordChange}
          onSaveProfile={onSaveProfile}
          onSignOut={onSignOut}
        />
      )}

      {activeTab === "privacy" && (
        <PrivacySettings
          exportScope={exportScope}
          exportFromDate={exportFromDate}
          exportToDate={exportToDate}
          onExportScopeChange={onExportScopeChange}
          onExportFromDateChange={onExportFromDateChange}
          onExportToDateChange={onExportToDateChange}
          onExportSavedChats={onExportSavedChats}
          onDeleteAccount={onDeleteAccount}
        />
      )}

      {activeTab === "safety" && <SafetySettings />}

      {activeTab === "admin" && (
        <AdminSettings
          adminDashboard={adminDashboard}
          isLoadingAdminDashboard={isLoadingAdminDashboard}
          onRefreshAdminDashboard={onRefreshAdminDashboard}
        />
      )}
    </section>
  );
}

// General settings currently owns device-specific preferences such as theme.
function GeneralSettings({
  displayMode,
  onDisplayModeChange,
}: {
  displayMode: DisplayMode;
  onDisplayModeChange: (mode: DisplayMode) => void;
}) {
  return (
    <div className="setting-row">
      <div>
        <h3>Display mode</h3>
        <p>Choose how the app appears on this device.</p>
      </div>

      <div
        className="segmented-control"
        role="group"
        aria-label="Display mode"
      >
        <button
          type="button"
          className={displayMode === "light" ? "active" : undefined}
          aria-pressed={displayMode === "light"}
          onClick={() => onDisplayModeChange("light")}
        >
          Light
        </button>

        <button
          type="button"
          className={displayMode === "dark" ? "active" : undefined}
          aria-pressed={displayMode === "dark"}
          onClick={() => onDisplayModeChange("dark")}
        >
          Dark
        </button>
      </div>
    </div>
  );
}

// Account settings edits the signed-in user profile and password.
function AccountSettings({
  profileName,
  profileEmail,
  profileCurrentPassword,
  profileNewPassword,
  profileStatus,
  onProfileNameChange,
  onProfileEmailChange,
  onProfileCurrentPasswordChange,
  onProfileNewPasswordChange,
  onSaveProfile,
  onSignOut,
}: {
  profileName: string;
  profileEmail: string;
  profileCurrentPassword: string;
  profileNewPassword: string;
  profileStatus: string | null;
  onProfileNameChange: (value: string) => void;
  onProfileEmailChange: (value: string) => void;
  onProfileCurrentPasswordChange: (value: string) => void;
  onProfileNewPasswordChange: (value: string) => void;
  onSaveProfile: () => void;
  onSignOut: () => void;
}) {
  return (
    <div className="settings-form-panel">
      <div>
        <h3>Profile</h3>
        <p>Update your local account details.</p>
      </div>

      <div className="settings-form-grid">
        <label>
          Display name
          <input
            value={profileName}
            onChange={(event) => onProfileNameChange(event.target.value)}
          />
        </label>

        <label>
          Email
          <input
            type="email"
            value={profileEmail}
            onChange={(event) => onProfileEmailChange(event.target.value)}
          />
        </label>

        <label>
          Current password
          <input
            type="password"
            value={profileCurrentPassword}
            onChange={(event) =>
              onProfileCurrentPasswordChange(event.target.value)
            }
            placeholder="Required for password changes"
          />
        </label>

        <label>
          New password
          <input
            type="password"
            value={profileNewPassword}
            onChange={(event) =>
              onProfileNewPasswordChange(event.target.value)
            }
            minLength={8}
          />
        </label>
      </div>

      {profileStatus && (
        <p className="settings-status">{profileStatus}</p>
      )}

      <div className="privacy-actions">
        <button
          className="primary-button"
          type="button"
          onClick={onSaveProfile}
        >
          Save profile
        </button>

        <button
          className="secondary-button"
          type="button"
          onClick={onSignOut}
        >
          Log out
        </button>
      </div>
    </div>
  );
}

// Privacy settings contains data export and destructive account deletion.
function PrivacySettings({
  exportScope,
  exportFromDate,
  exportToDate,
  onExportScopeChange,
  onExportFromDateChange,
  onExportToDateChange,
  onExportSavedChats,
  onDeleteAccount,
}: {
  exportScope: ExportScope;
  exportFromDate: string;
  exportToDate: string;
  onExportScopeChange: (value: ExportScope) => void;
  onExportFromDateChange: (value: string) => void;
  onExportToDateChange: (value: string) => void;
  onExportSavedChats: () => void;
  onDeleteAccount: () => void;
}) {
  return (
    <div className="settings-form-panel">
      <div>
        <h3>Privacy</h3>
        <p>Export saved chats or delete your account data.</p>
      </div>

      <div className="settings-form-grid">
        <label>
          Export scope
          <select
            value={exportScope}
            onChange={(event) =>
              onExportScopeChange(event.target.value as ExportScope)
            }
          >
            <option value="all">All saved chats</option>
            <option value="current">Current chat only</option>
          </select>
        </label>

        <label>
          From date
          <input
            type="date"
            value={exportFromDate}
            onChange={(event) =>
              onExportFromDateChange(event.target.value)
            }
          />
        </label>

        <label>
          To date
          <input
            type="date"
            value={exportToDate}
            onChange={(event) =>
              onExportToDateChange(event.target.value)
            }
          />
        </label>
      </div>

      <div className="privacy-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={onExportSavedChats}
        >
          Export chats
        </button>

        <button
          className="danger-button"
          type="button"
          onClick={onDeleteAccount}
        >
          Delete account
        </button>
      </div>
    </div>
  );
}

// Safety resources are static links available to all users.
function SafetySettings() {
  return (
    <div className="setting-row safety-setting">
      <div>
        <h3>Safety resources</h3>
        <p>
          If there is immediate danger, contact emergency services. In the
          U.S., 988 offers free crisis support.
        </p>
      </div>

      <div className="crisis-actions">
        <a className="crisis-action" href="tel:988">
          Call 988
        </a>
        <a className="crisis-action" href="sms:988">
          Text 988
        </a>
        <a
          className="crisis-action"
          href="https://chat.988lifeline.org/"
          target="_blank"
          rel="noreferrer"
        >
          Open 988 chat
        </a>
      </div>
    </div>
  );
}

// Admin settings are available only when App.tsx includes the admin tab.
function AdminSettings({
  adminDashboard,
  isLoadingAdminDashboard,
  onRefreshAdminDashboard,
}: {
  adminDashboard: AdminDashboard | null;
  isLoadingAdminDashboard: boolean;
  onRefreshAdminDashboard: () => void;
}) {
  return (
    <div className="settings-form-panel">
      <div className="admin-dashboard-heading">
        <div>
          <h3>Service dashboard</h3>
          <p>Internal development health and storage summary.</p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={onRefreshAdminDashboard}
          disabled={isLoadingAdminDashboard}
        >
          Refresh
        </button>
      </div>

      {isLoadingAdminDashboard ? (
        <p className="settings-status">Loading dashboard...</p>
      ) : adminDashboard ? (
        <div className="admin-diagnostics">
          <div className="admin-diagnostics-header">
            <div>
              <span>Mode</span>
              <strong>
                {adminDashboard.dependencies.mode ?? "live"}
              </strong>
            </div>
            <div>
              <span>Fallback</span>
              <strong>
                {adminDashboard.dependencies.fallback_enabled
                  ? "Enabled"
                  : "Disabled"}
              </strong>
            </div>
            <div>
              <span>Checked</span>
              <strong>
                {adminDashboard.dependencies.checked_at
                  ? new Date(
                      adminDashboard.dependencies.checked_at,
                    ).toLocaleString()
                  : "Not reported"}
              </strong>
            </div>
          </div>

          <div className="admin-service-details">
            {[
              ["gateway", adminDashboard.dependencies.gateway],
              ["safety service", adminDashboard.dependencies.safety_service],
              ["chat service", adminDashboard.dependencies.chat_service],
              ["save service", adminDashboard.dependencies.save_service],
            ].map(([service, statusText]) => (
              <div className="admin-service-detail" key={service}>
                <span>{service}</span>
                <strong>{statusText}</strong>
                <p>
                  {adminDashboard.dependencies.details?.[
                    service.replace(" ", "_")
                  ] ?? "No issue reported."}
                </p>
              </div>
            ))}
          </div>

          <div className="admin-dashboard-grid">
            <div className="admin-metric">
              <span>Users</span>
              <strong>{adminDashboard.storage.users}</strong>
            </div>
            <div className="admin-metric">
              <span>Conversations</span>
              <strong>{adminDashboard.storage.conversations}</strong>
            </div>
            <div className="admin-metric">
              <span>Messages</span>
              <strong>{adminDashboard.storage.messages}</strong>
            </div>
            <div className="admin-metric">
              <span>Expiring soon</span>
              <strong>{adminDashboard.storage.expiring_soon}</strong>
            </div>
          </div>
        </div>
      ) : (
        <p className="settings-status">
          Open this tab to load service health.
        </p>
      )}
    </div>
  );
}
