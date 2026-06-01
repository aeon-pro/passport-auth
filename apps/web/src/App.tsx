import { type FormEvent, useEffect, useState } from "react";

const AUTH_TOKEN_KEY = "passport-auth-token";

type OwnerAccount = {
  email: string;
};

type DashboardUser = {
  email: string;
  role: string;
};

type SetupStatusResponse = {
  setup_complete: boolean;
  owner: OwnerAccount | null;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: DashboardUser;
};

type PasswordResetStartResponse = {
  sent: boolean;
  dev_otp?: string | null;
};

async function readSetupStatus(): Promise<SetupStatusResponse> {
  const response = await fetch("/api/v1/setup/status");
  const responseBody = (await response.json().catch(() => null)) as
    | (Partial<SetupStatusResponse> & { detail?: string })
    | null;

  if (!response.ok) {
    throw new Error(responseBody?.detail ?? "Could not load setup status.");
  }

  return {
    setup_complete: Boolean(responseBody?.setup_complete),
    owner: responseBody?.owner?.email ? { email: responseBody.owner.email } : null,
  };
}

async function createOwnerAccount(email: string, password: string): Promise<OwnerAccount> {
  const response = await fetch("/api/v1/setup/owner", {
    body: JSON.stringify({ email, password }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  const responseBody = (await response.json().catch(() => null)) as
    | (Partial<SetupStatusResponse> & { detail?: string })
    | null;

  if (!response.ok) {
    throw new Error(responseBody?.detail ?? "Could not create owner account.");
  }

  if (!responseBody?.owner?.email) {
    throw new Error("Setup API returned an invalid response.");
  }

  return responseBody.owner;
}

async function loginDashboard(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch("/api/v1/dashboard/auth/login", {
    body: JSON.stringify({ email, password }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  const responseBody = (await response.json().catch(() => null)) as
    | (Partial<LoginResponse> & { detail?: string })
    | null;

  if (!response.ok) {
    throw new Error(responseBody?.detail ?? "Could not sign in.");
  }

  if (!responseBody?.access_token || !responseBody.user?.email) {
    throw new Error("Login API returned an invalid response.");
  }

  return {
    access_token: responseBody.access_token,
    token_type: responseBody.token_type ?? "bearer",
    user: responseBody.user,
  };
}

async function readDashboardProfile(token: string): Promise<DashboardUser> {
  const response = await fetch("/api/v1/dashboard/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const responseBody = (await response.json().catch(() => null)) as
    | (Partial<DashboardUser> & { detail?: string })
    | null;

  if (!response.ok) {
    throw new Error(responseBody?.detail ?? "Not authenticated.");
  }

  if (!responseBody?.email || !responseBody.role) {
    throw new Error("Profile API returned an invalid response.");
  }

  return { email: responseBody.email, role: responseBody.role };
}

async function startPasswordReset(email: string): Promise<PasswordResetStartResponse> {
  const response = await fetch("/api/v1/dashboard/auth/password-reset/start", {
    body: JSON.stringify({ email }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  const responseBody = (await response.json().catch(() => null)) as
    | (Partial<PasswordResetStartResponse> & { detail?: string })
    | null;

  if (!response.ok) {
    throw new Error(responseBody?.detail ?? "Could not start password reset.");
  }

  return { sent: Boolean(responseBody?.sent), dev_otp: responseBody?.dev_otp };
}

async function confirmPasswordReset(email: string, otp: string, password: string): Promise<void> {
  const response = await fetch("/api/v1/dashboard/auth/password-reset/confirm", {
    body: JSON.stringify({ email, otp, password }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  const responseBody = (await response.json().catch(() => null)) as { detail?: string } | null;

  if (!response.ok) {
    throw new Error(responseBody?.detail ?? "Could not update password.");
  }
}

function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

function storeAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

function clearAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function App() {
  const currentPath = typeof window === "undefined" ? "/" : window.location.pathname;
  const activePath = currentPath === "/" ? "/" : currentPath;
  const isSetupRoute = currentPath === "/setup";
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null);
  const [ownerAccount, setOwnerAccount] = useState<OwnerAccount | null>(null);
  const [setupError, setSetupError] = useState("");
  const [isSubmittingSetup, setIsSubmittingSetup] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(() => getStoredAuthToken());
  const [currentUser, setCurrentUser] = useState<DashboardUser | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "reset-start" | "reset-confirm">("login");
  const [authError, setAuthError] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const sections = [
    { label: "Setup", href: "/setup" },
    { label: "Users", href: "/users" },
    { label: "Settings", href: "/settings" },
    { label: "Analytics", href: "/analytics" },
  ];
  const setupComplete = Boolean(ownerAccount ?? setupStatus?.owner);
  const setupItems = [
    { label: "Owner account", complete: setupComplete },
    { label: "Auth domain", complete: false },
    { label: "Redirect URLs", complete: false },
    { label: "Email provider", complete: false },
  ];
  const metrics = [
    { label: "Domains", value: "0", detail: "Allowed origins" },
    { label: "Providers", value: "0", detail: "Enabled methods" },
    { label: "API keys", value: "0", detail: "Service access" },
    { label: "Events", value: "0", detail: "Last 24 hours" },
  ];

  useEffect(() => {
    let isCurrent = true;

    void readSetupStatus()
      .then((status) => {
        if (!isCurrent) {
          return;
        }

        setSetupStatus(status);
        setOwnerAccount(status.owner);
        if (!status.setup_complete) {
          setCurrentUser(null);
          setAuthToken(null);
          clearAuthToken();
        }
      })
      .catch(() => {
        if (isCurrent) {
          setSetupStatus({ setup_complete: false, owner: null });
        }
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  useEffect(() => {
    if (!setupComplete || !authToken || currentUser) {
      return;
    }

    let isCurrent = true;

    void readDashboardProfile(authToken)
      .then((user) => {
        if (isCurrent) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setCurrentUser(null);
          setAuthToken(null);
          clearAuthToken();
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [authToken, currentUser, setupComplete]);

  const handleOwnerSetupSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const ownerEmail = String(formData.get("ownerEmail") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    const confirmPassword = String(formData.get("confirmPassword") ?? "");

    if (!ownerEmail || !password || !confirmPassword) {
      setSetupError("Enter an owner email and password to continue.");
      return;
    }

    if (password.length < 12) {
      setSetupError("Use a password with at least 12 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setSetupError("Passwords do not match.");
      return;
    }

    setSetupError("");
    setIsSubmittingSetup(true);

    try {
      const owner = await createOwnerAccount(ownerEmail, password);
      setOwnerAccount(owner);
      setSetupStatus({ setup_complete: true, owner });
    } catch (error) {
      setSetupError(error instanceof Error ? error.message : "Could not create owner account.");
    } finally {
      setIsSubmittingSetup(false);
    }
  };

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    setAuthError("");
    setAuthMessage("");
    setIsSubmittingAuth(true);

    try {
      const login = await loginDashboard(email, password);
      storeAuthToken(login.access_token);
      setAuthToken(login.access_token);
      setCurrentUser(login.user);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Could not sign in.");
    } finally {
      setIsSubmittingAuth(false);
    }
  };

  const handlePasswordResetStart = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();

    setAuthError("");
    setAuthMessage("");
    setIsSubmittingAuth(true);

    try {
      const reset = await startPasswordReset(email);
      setResetEmail(email);
      setDevOtp(reset.dev_otp ?? null);
      setAuthMode("reset-confirm");
      setAuthMessage("Enter the OTP sent to the owner email.");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Could not start password reset.");
    } finally {
      setIsSubmittingAuth(false);
    }
  };

  const handlePasswordResetConfirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const otp = String(formData.get("otp") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    setAuthError("");
    setAuthMessage("");
    setIsSubmittingAuth(true);

    try {
      await confirmPasswordReset(resetEmail, otp, password);
      setAuthMode("login");
      setDevOtp(null);
      setAuthMessage("Password updated. Sign in with the new password.");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Could not update password.");
    } finally {
      setIsSubmittingAuth(false);
    }
  };

  const handleSignOut = () => {
    clearAuthToken();
    setAuthToken(null);
    setCurrentUser(null);
    setAuthMode("login");
  };

  const renderBrand = () => (
    <a className="brand" href="/">
      <span className="brand-mark" aria-hidden="true">
        PA
      </span>
      <span>
        <h1>Passport Auth</h1>
        <small>Single app auth</small>
      </span>
    </a>
  );

  const renderAuthScreen = () => (
    <main className="auth-layout">
      {renderBrand()}
      <section className="auth-card" aria-label="Dashboard authentication">
        <div className="page-heading compact-heading">
          <span className="eyebrow">Dashboard auth</span>
          <h2>{authMode === "login" ? "Sign in to Passport Auth" : "Reset dashboard password"}</h2>
          <p>
            {authMode === "login"
              ? "Use the owner email and password created during first launch."
              : "Reset access with a one-time code sent to the owner email."}
          </p>
        </div>

        {authMode === "login" ? (
          <form className="setup-form auth-form" aria-label="Sign in" onSubmit={handleLoginSubmit}>
            <label className="field">
              <span>Email</span>
              <input autoComplete="email" name="email" placeholder="owner@example.com" required type="email" />
            </label>

            <label className="field">
              <span>Password</span>
              <input autoComplete="current-password" name="password" required type="password" />
            </label>

            {authError ? (
              <p className="form-error" role="alert">
                {authError}
              </p>
            ) : null}
            {authMessage ? <p className="form-message">{authMessage}</p> : null}

            <div className="form-actions">
              <button className="primary-action" disabled={isSubmittingAuth} type="submit">
                {isSubmittingAuth ? "Signing in..." : "Sign in"}
              </button>
              <button className="text-action" type="button" onClick={() => setAuthMode("reset-start")}>
                Reset password
              </button>
            </div>
          </form>
        ) : null}

        {authMode === "reset-start" ? (
          <form className="setup-form auth-form" aria-label="Start password reset" onSubmit={handlePasswordResetStart}>
            <label className="field">
              <span>Owner email</span>
              <input autoComplete="email" name="email" placeholder="owner@example.com" required type="email" />
            </label>

            {authError ? (
              <p className="form-error" role="alert">
                {authError}
              </p>
            ) : null}

            <div className="form-actions">
              <button className="primary-action" disabled={isSubmittingAuth} type="submit">
                {isSubmittingAuth ? "Sending..." : "Send reset OTP"}
              </button>
              <button className="text-action" type="button" onClick={() => setAuthMode("login")}>
                Back to login
              </button>
            </div>
          </form>
        ) : null}

        {authMode === "reset-confirm" ? (
          <form className="setup-form auth-form" aria-label="Confirm password reset" onSubmit={handlePasswordResetConfirm}>
            {authMessage ? <p className="form-message">{authMessage}</p> : null}
            {devOtp ? <p className="dev-otp">Development OTP: {devOtp}</p> : null}

            <label className="field">
              <span>OTP</span>
              <input inputMode="numeric" name="otp" placeholder="123456" required type="text" />
            </label>

            <label className="field">
              <span>New password</span>
              <input
                autoComplete="new-password"
                minLength={12}
                name="password"
                placeholder="Minimum 12 characters"
                required
                type="password"
              />
            </label>

            {authError ? (
              <p className="form-error" role="alert">
                {authError}
              </p>
            ) : null}

            <div className="form-actions">
              <button className="primary-action" disabled={isSubmittingAuth} type="submit">
                {isSubmittingAuth ? "Updating..." : "Update password"}
              </button>
              <button className="text-action" type="button" onClick={() => setAuthMode("login")}>
                Back to login
              </button>
            </div>
          </form>
        ) : null}
      </section>
    </main>
  );

  const renderSetupRoute = () => (
    <div className="setup-route">
      <div className="page-heading">
        <span className="eyebrow">Setup</span>
        <h2>Setup Passport Auth</h2>
        <p>Create the first owner account. Domains, OAuth, and email delivery can be configured later.</p>
      </div>

      {ownerAccount ? (
        <section className="setup-form setup-success" aria-label="Owner account created">
          <div className="panel-heading">
            <span className="eyebrow">Owner account</span>
            <h3>Owner account created</h3>
          </div>

          <div className="owner-summary">
            <span>Email</span>
            <strong>{ownerAccount.email}</strong>
          </div>

          <p>Email delivery can be configured later in Settings.</p>

          <div className="form-actions">
            <a className="primary-action" href="/">
              Continue to sign in
            </a>
            <a className="secondary-action" href="/">
              Back to overview
            </a>
          </div>
        </section>
      ) : (
        <form className="setup-form" aria-label="Setup Passport Auth" onSubmit={handleOwnerSetupSubmit}>
          <div className="form-grid owner-form-grid">
            <label className="field">
              <span>Owner email</span>
              <input autoComplete="email" name="ownerEmail" placeholder="owner@example.com" required type="email" />
            </label>

            <label className="field">
              <span>Password</span>
              <input
                autoComplete="new-password"
                minLength={12}
                name="password"
                placeholder="Minimum 12 characters"
                required
                type="password"
              />
            </label>

            <label className="field">
              <span>Confirm password</span>
              <input
                autoComplete="new-password"
                minLength={12}
                name="confirmPassword"
                placeholder="Repeat password"
                required
                type="password"
              />
            </label>
          </div>

          {setupError ? (
            <p className="form-error" role="alert">
              {setupError}
            </p>
          ) : null}

          <div className="form-actions">
            <button className="primary-action" disabled={isSubmittingSetup} type="submit">
              {isSubmittingSetup ? "Creating owner..." : "Create owner account"}
            </button>
            <a className="secondary-action" href="/">
              Back to overview
            </a>
          </div>
        </form>
      )}
    </div>
  );

  const renderDashboard = () => (
    <>
      <div className="hero">
        <div className="page-heading">
          <span className="eyebrow">{setupComplete ? "Dashboard" : "First launch"}</span>
          <h2>Deploy your auth surface</h2>
          <p>Hosted pages, public API, dashboard, and service keys behind one web service.</p>
        </div>

        <div className="setup-panel">
          <div className="panel-heading">
            <span className="eyebrow">Setup state</span>
            <strong>{setupComplete ? "Owner configured" : "Not configured"}</strong>
          </div>

          <ul className="setup-list" aria-label="Setup checklist">
            {setupItems.map((item) => (
              <li className={item.complete ? "complete" : undefined} key={item.label}>
                <span aria-hidden="true" />
                {item.label}
              </li>
            ))}
          </ul>

          <a className="primary-action" href={setupComplete ? "/settings" : "/setup"}>
            {setupComplete ? "Edit settings" : "Configure setup"}
          </a>
        </div>
      </div>

      <div className="metric-grid" aria-label="Auth readiness">
        {metrics.map((metric) => (
          <div className="metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </div>
        ))}
      </div>
    </>
  );

  if (setupStatus === null && !isSetupRoute) {
    return (
      <main className="auth-layout">
        {renderBrand()}
        <section className="auth-card">
          <span className="eyebrow">Loading</span>
          <h2>Loading Passport Auth</h2>
        </section>
      </main>
    );
  }

  if (setupComplete && !currentUser && !isSetupRoute) {
    return renderAuthScreen();
  }

  const statusLabel = setupComplete ? "Setup complete" : "Owner setup required";

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Workspace">
        {renderBrand()}

        <nav className="nav" aria-label="Primary">
          {sections.map((section) => (
            <a
              key={section.href}
              className={section.href === activePath ? "active" : undefined}
              href={section.href}
            >
              {section.label}
            </a>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div className="topbar-meta">
            <span className="eyebrow">Environment</span>
            <strong>Local</strong>
          </div>
          <div className="topbar-actions">
            <span className="status-pill">
              <span aria-hidden="true" />
              {statusLabel}
            </span>
            {currentUser ? <span className="user-label">{currentUser.email}</span> : null}
            {currentUser ? (
              <button className="text-action" type="button" onClick={handleSignOut}>
                Sign out
              </button>
            ) : (
              <a href="/settings">Edit settings</a>
            )}
          </div>
        </header>

        <section className="workspace">{isSetupRoute ? renderSetupRoute() : renderDashboard()}</section>
      </main>
    </div>
  );
}
