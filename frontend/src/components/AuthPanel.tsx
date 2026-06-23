import { FormEvent, useState } from "react";

export type AuthMode = "login" | "register";

const IS_DEV_LOGIN_ENABLED =
  import.meta.env.VITE_ENABLE_DEV_LOGIN === "true" ||
  (import.meta.env.DEV &&
    import.meta.env.VITE_ENABLE_DEV_LOGIN !== "false");

interface AuthPanelProps {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  onSubmit: (
    mode: AuthMode,
    displayName: string,
    email: string,
    password: string,
    rememberMe: boolean,
  ) => Promise<void>;
  onDevLogin: (rememberMe: boolean) => Promise<void>;
  onRequestReset: (email: string) => Promise<string | null>;
  onConfirmReset: (
    resetToken: string,
    newPassword: string,
    rememberMe: boolean,
  ) => Promise<void>;
  isSubmitting: boolean;
  error: string | null;
}

export function AuthPanel({
  mode,
  onModeChange,
  onSubmit,
  onDevLogin,
  onRequestReset,
  onConfirmReset,
  isSubmitting,
  error,
}: AuthPanelProps) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetNotice, setResetNotice] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit(mode, displayName, email, password, rememberMe);
  }

  async function handleResetRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = await onRequestReset(resetEmail || email);
    if (token) {
      setResetToken(token);
      setResetNotice("Use the development reset code below.");
    } else {
      setResetNotice(
        "If that email exists, a reset code has been prepared.",
      );
    }
  }

  async function handleResetConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onConfirmReset(resetToken, resetPassword, rememberMe);
  }

  return (
    <main className="app-shell auth-shell">
      <section className="auth-card">
        <div>
          <p className="eyebrow">Safety-aware AI demo</p>
          <h1>Emotional Support Guide</h1>
          <p className="subtitle">
            Sign in to keep saved chats private to your account.
          </p>
        </div>

        <div className="segmented-control auth-toggle" role="group">
          <button
            type="button"
            className={mode === "login" ? "active" : undefined}
            onClick={() => onModeChange("login")}
          >
            Log in
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : undefined}
            onClick={() => onModeChange("register")}
          >
            Sign up
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "register" && (
            <label>
              Name
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                minLength={1}
                maxLength={80}
                required
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            Password
            <span className="password-field">
              <input
                type={isPasswordVisible ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                required
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() =>
                  setIsPasswordVisible((current) => !current)
                }
              >
                {isPasswordVisible ? "Hide" : "Show"}
              </button>
            </span>
            <span className="auth-hint">
              Use at least 8 characters for local testing.
            </span>
          </label>

          <label className="remember-me-control">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
            />
            <span>Remember me on this device</span>
          </label>

          {error && (
            <div className="error-banner auth-error" role="alert">
              {error}
            </div>
          )}

          <button
            className="primary-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Working..."
              : mode === "register"
                ? "Create account"
                : "Log in"}
          </button>
        </form>

        <div className="reset-login-panel">
          <button
            className="link-button"
            type="button"
            onClick={() => setIsResetOpen((current) => !current)}
          >
            {isResetOpen ? "Hide password reset" : "Forgot password?"}
          </button>

          {isResetOpen && (
            <div className="reset-forms">
              <form
                className="auth-form compact-auth-form"
                onSubmit={handleResetRequest}
              >
                <label>
                  Account email
                  <input
                    type="email"
                    value={resetEmail}
                    onChange={(event) =>
                      setResetEmail(event.target.value)
                    }
                    placeholder={email || "you@example.com"}
                    required
                  />
                </label>

                <button
                  className="secondary-button"
                  type="submit"
                  disabled={isSubmitting}
                >
                  Create reset code
                </button>
              </form>

              <form
                className="auth-form compact-auth-form"
                onSubmit={handleResetConfirm}
              >
                <label>
                  Reset code
                  <input
                    value={resetToken}
                    onChange={(event) =>
                      setResetToken(event.target.value)
                    }
                    required
                  />
                </label>

                <label>
                  New password
                  <input
                    type="password"
                    value={resetPassword}
                    onChange={(event) =>
                      setResetPassword(event.target.value)
                    }
                    minLength={8}
                    required
                  />
                </label>

                {resetNotice && (
                  <p className="auth-notice">{resetNotice}</p>
                )}

                <button
                  className="primary-button"
                  type="submit"
                  disabled={isSubmitting}
                >
                  Reset password
                </button>
              </form>
            </div>
          )}
        </div>

        {IS_DEV_LOGIN_ENABLED && (
          <div className="dev-login-panel">
            <p>Development only</p>
            <button
              className="secondary-button dev-login-button"
              type="button"
              onClick={() => void onDevLogin(rememberMe)}
              disabled={isSubmitting}
            >
              Continue as developer
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
