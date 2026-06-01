export function App() {
  const sections = [
    { label: "Setup", href: "/setup" },
    { label: "Users", href: "/users" },
    { label: "Settings", href: "/settings" },
    { label: "Analytics", href: "/analytics" },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Workspace">
        <a className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            PA
          </span>
          <h1>Passport Auth</h1>
        </a>

        <nav className="nav" aria-label="Primary">
          {sections.map((section) => (
            <a key={section.href} href={section.href}>
              {section.label}
            </a>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <span className="eyebrow">Environment</span>
            <strong>Local</strong>
          </div>
          <span className="status-pill">Setup open</span>
        </header>

        <section className="workspace">
          <div className="page-heading">
            <span className="eyebrow">First launch</span>
            <h2>Setup</h2>
          </div>

          <div className="setup-panel">
            <div>
              <span className="eyebrow">Owner account</span>
              <strong>Not configured</strong>
            </div>
            <a className="primary-action" href="/setup">
              Start setup
            </a>
          </div>

          <div className="metric-grid" aria-label="Auth readiness">
            <div className="metric">
              <span>Domains</span>
              <strong>0</strong>
            </div>
            <div className="metric">
              <span>Providers</span>
              <strong>0</strong>
            </div>
            <div className="metric">
              <span>API keys</span>
              <strong>0</strong>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
