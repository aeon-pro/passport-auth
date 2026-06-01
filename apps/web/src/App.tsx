import { type FormEvent, useState } from "react";

export function App() {
  const currentPath = typeof window === "undefined" ? "/" : window.location.pathname;
  const activePath = currentPath === "/" ? "/setup" : currentPath;
  const isSetupRoute = currentPath === "/setup";
  const [ownerAccount, setOwnerAccount] = useState<{ email: string } | null>(null);
  const [setupError, setSetupError] = useState("");
  const sections = [
    { label: "Setup", href: "/setup" },
    { label: "Users", href: "/users" },
    { label: "Settings", href: "/settings" },
    { label: "Analytics", href: "/analytics" },
  ];
  const setupItems = ["Owner account", "Auth domain", "Redirect URLs", "Email provider"];
  const metrics = [
    { label: "Domains", value: "0", detail: "Allowed origins" },
    { label: "Providers", value: "0", detail: "Enabled methods" },
    { label: "API keys", value: "0", detail: "Service access" },
    { label: "Events", value: "0", detail: "Last 24 hours" },
  ];
  const handleOwnerSetupSubmit = (event: FormEvent<HTMLFormElement>) => {
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
    setOwnerAccount({ email: ownerEmail });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Workspace">
        <a className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            PA
          </span>
          <span>
            <h1>Passport Auth</h1>
            <small>Single app auth</small>
          </span>
        </a>

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
              Owner setup required
            </span>
            <a href="/settings">Edit settings</a>
          </div>
        </header>

        <section className="workspace">
          {isSetupRoute ? (
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
                    <a className="primary-action" href="/settings">
                      Continue to settings
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
                      <input
                        autoComplete="email"
                        name="ownerEmail"
                        placeholder="owner@example.com"
                        required
                        type="email"
                      />
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
                    <button className="primary-action" type="submit">
                      Create owner account
                    </button>
                    <a className="secondary-action" href="/">
                      Back to overview
                    </a>
                  </div>
                </form>
              )}
            </div>
          ) : (
            <>
              <div className="hero">
                <div className="page-heading">
                  <span className="eyebrow">First launch</span>
                  <h2>Deploy your auth surface</h2>
                  <p>Hosted pages, public API, dashboard, and service keys behind one web service.</p>
                </div>

                <div className="setup-panel">
                  <div className="panel-heading">
                    <span className="eyebrow">Setup state</span>
                    <strong>Not configured</strong>
                  </div>

                  <ul className="setup-list" aria-label="Setup checklist">
                    {setupItems.map((item) => (
                      <li key={item}>
                        <span aria-hidden="true" />
                        {item}
                      </li>
                    ))}
                  </ul>

                  <a className="primary-action" href="/setup">
                    Configure setup
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
          )}
        </section>
      </main>
    </div>
  );
}
