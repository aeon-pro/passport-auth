const TOKEN_KEY = "passport-auth-token";
const app = document.querySelector("#app");

const state = {
  setup: null,
  user: null,
  settings: null,
  settingsLoading: false,
  token: localStorage.getItem(TOKEN_KEY),
  authMode: "login",
  resetEmail: "",
  devOtp: "",
  message: "",
  error: "",
  busy: false,
};

const routes = [
  { href: "/setup", label: "Setup" },
  { href: "/users", label: "Users" },
  { href: "/settings", label: "Settings" },
  { href: "/analytics", label: "Analytics" },
];

const metrics = [
  { label: "Domains", value: "0", detail: "Allowed origins" },
  { label: "Providers", value: "0", detail: "Enabled methods" },
  { label: "API keys", value: "0", detail: "Service access" },
  { label: "Events", value: "0", detail: "Last 24 hours" },
];

const authMethodLabels = {
  password_login_enabled: "Password login",
  otp_login_enabled: "OTP login",
  magic_link_enabled: "Magic link",
  google_oauth_enabled: "Google OAuth",
  password_reset_otp_enabled: "Password reset OTP",
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function linesToList(value) {
  return String(value || "")
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToLines(value) {
  return (value || []).join("\n");
}

function checkboxValue(formData, name) {
  return formData.get(name) === "on";
}

function ensureOrigin(domain) {
  const cleanDomain = String(domain || "").trim();
  if (!cleanDomain) {
    return "";
  }
  if (cleanDomain.startsWith("http://") || cleanDomain.startsWith("https://")) {
    return cleanDomain.replace(/\/+$/, "");
  }
  return `https://${cleanDomain.replace(/\/+$/, "")}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(body?.detail || "Request failed.");
  }

  return body;
}

async function loadSetupStatus() {
  state.setup = await api("/api/v1/setup/status");
}

async function loadProfile() {
  if (!state.token) {
    state.user = null;
    return;
  }

  try {
    state.user = await api("/api/v1/dashboard/auth/me");
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
  }
}

async function loadSettings({ quiet = false } = {}) {
  if (!state.token || state.settingsLoading) {
    return;
  }

  state.settingsLoading = true;
  if (!quiet) {
    render();
  }

  try {
    state.settings = await api("/api/v1/dashboard/settings");
  } catch (error) {
    if (!quiet) {
      state.error = error.message;
    }
  } finally {
    state.settingsLoading = false;
    if (!quiet) {
      render();
    }
  }
}

function setupComplete() {
  return Boolean(state.setup?.setup_complete && state.setup?.owner);
}

function currentPath() {
  return window.location.pathname || "/";
}

function navigate(path) {
  if (currentPath() !== path) {
    window.history.pushState({}, "", path);
  }
  state.error = "";
  state.message = "";
  render();
}

function brandMarkup(compact = false) {
  return `
    <a class="brand ${compact ? "compact" : ""}" href="/" data-link>
      <span class="brand-mark" aria-hidden="true">PA</span>
      <span>
        <h1>Passport Auth</h1>
        <small>Single app auth</small>
      </span>
    </a>
  `;
}

function renderAppShell(content) {
  const path = currentPath();
  const setupDone = setupComplete();
  const status = setupDone ? "Setup complete" : "Owner setup required";
  const userLabel = state.user ? `<span class="user-label">${escapeHtml(state.user.email)}</span>` : "";
  const authAction = state.user
    ? `<button class="text-action" type="button" data-action="sign-out">Sign out</button>`
    : `<a class="text-action" href="/" data-link>Sign in</a>`;

  app.className = "app-shell";
  app.innerHTML = `
    <aside class="sidebar" aria-label="Workspace">
      ${brandMarkup()}
      <nav class="nav" aria-label="Primary">
        ${routes
          .map(
            (route) => `
              <a href="${route.href}" data-link class="${route.href === path ? "active" : ""}">
                ${route.label}
              </a>
            `,
          )
          .join("")}
      </nav>
    </aside>

    <main class="content">
      <header class="topbar">
        <div class="topbar-meta">
          <span class="eyebrow">Environment</span>
          <strong>Local</strong>
        </div>
        <div class="topbar-actions">
          <span class="status-pill">${status}</span>
          ${userLabel}
          ${authAction}
        </div>
      </header>
      <section class="workspace">${content}</section>
    </main>
  `;
}

function renderSetup() {
  const owner = state.setup?.owner;
  const form = owner
    ? `
      <section class="form-panel">
        <div class="panel-heading">
          <span class="eyebrow">Owner account</span>
          <h3>Owner account created</h3>
        </div>
        <div class="summary">
          <span>Email</span>
          <strong>${escapeHtml(owner.email)}</strong>
        </div>
        <p>Email delivery can be configured later in Settings.</p>
        <div class="form-actions">
          <button class="primary-action" type="button" data-action="go-dashboard">Go to dashboard</button>
          <a class="secondary-action" href="/" data-link>Back to overview</a>
        </div>
      </section>
    `
    : `
      <form class="form-panel" data-form="setup">
        <div class="form-grid">
          <label class="field">
            <span>Owner email</span>
            <input name="ownerEmail" type="email" autocomplete="email" placeholder="owner@example.com" required />
          </label>
          <label class="field">
            <span>Password</span>
            <input name="password" type="password" autocomplete="new-password" placeholder="Minimum 12 characters" minlength="12" required />
          </label>
          <label class="field">
            <span>Confirm password</span>
            <input name="confirmPassword" type="password" autocomplete="new-password" placeholder="Repeat password" minlength="12" required />
          </label>
        </div>
        ${renderError()}
        <div class="form-actions">
          <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
            ${state.busy ? "Creating owner..." : "Create owner account"}
          </button>
          <a class="secondary-action" href="/" data-link>Back to overview</a>
        </div>
      </form>
    `;

  renderAppShell(`
    <div class="route-stack">
      <div class="page-heading">
        <span class="eyebrow">Setup</span>
        <h2>Setup Passport Auth</h2>
        <p>Create the first owner account. Domains, OAuth, and email delivery can be configured later.</p>
      </div>
      ${form}
    </div>
  `);
}

function renderAuth() {
  const login = state.authMode === "login";
  const resetStart = state.authMode === "reset-start";
  const resetConfirm = state.authMode === "reset-confirm";

  app.className = "auth-screen";
  app.innerHTML = `
    ${brandMarkup(true)}
    <section class="auth-card" aria-label="Dashboard authentication">
      <div class="page-heading">
        <span class="eyebrow">Dashboard auth</span>
        <h2>${login ? "Sign in to Passport Auth" : "Reset dashboard password"}</h2>
        <p>${
          login
            ? "Use the owner email and password created during first launch."
            : "Reset access with a one-time code sent to the owner email."
        }</p>
      </div>

      ${
        login
          ? `
            <form class="form-grid" data-form="login">
              <label class="field">
                <span>Email</span>
                <input name="email" type="email" autocomplete="email" placeholder="owner@example.com" required />
              </label>
              <label class="field">
                <span>Password</span>
                <input name="password" type="password" autocomplete="current-password" required />
              </label>
              ${renderError()}
              ${renderMessage()}
              <div class="form-actions">
                <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
                  ${state.busy ? "Signing in..." : "Sign in"}
                </button>
                <button class="text-action" type="button" data-action="reset-start">Reset password</button>
              </div>
            </form>
          `
          : ""
      }

      ${
        resetStart
          ? `
            <form class="form-grid" data-form="reset-start">
              <label class="field">
                <span>Owner email</span>
                <input name="email" type="email" autocomplete="email" placeholder="owner@example.com" required />
              </label>
              ${renderError()}
              <div class="form-actions">
                <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
                  ${state.busy ? "Sending..." : "Send reset OTP"}
                </button>
                <button class="text-action" type="button" data-action="login">Back to login</button>
              </div>
            </form>
          `
          : ""
      }

      ${
        resetConfirm
          ? `
            <form class="form-grid" data-form="reset-confirm">
              ${renderMessage()}
              ${state.devOtp ? `<p class="dev-otp">Development OTP: ${escapeHtml(state.devOtp)}</p>` : ""}
              <label class="field">
                <span>OTP</span>
                <input name="otp" type="text" inputmode="numeric" placeholder="123456" required />
              </label>
              <label class="field">
                <span>New password</span>
                <input name="password" type="password" autocomplete="new-password" placeholder="Minimum 12 characters" minlength="12" required />
              </label>
              ${renderError()}
              <div class="form-actions">
                <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
                  ${state.busy ? "Updating..." : "Update password"}
                </button>
                <button class="text-action" type="button" data-action="login">Back to login</button>
              </div>
            </form>
          `
          : ""
      }
    </section>
  `;
}

function dashboardMetrics() {
  if (!state.settings) {
    return metrics;
  }

  const enabledMethods = Object.keys(authMethodLabels).filter((key) => state.settings[key]);
  const domainCount = [
    state.settings.app_domain,
    state.settings.auth_domain,
    ...(state.settings.allowed_origins || []),
    ...(state.settings.redirect_urls || []),
  ].filter(Boolean).length;

  return [
    { label: "Domains", value: String(domainCount), detail: "Origins and redirects" },
    { label: "Providers", value: String(enabledMethods.length), detail: "Enabled methods" },
    { label: "API keys", value: "0", detail: "Service access" },
    { label: "Events", value: "0", detail: "Last 24 hours" },
  ];
}

function renderDashboard() {
  const readySettings = state.settings || {};
  const setupItems = [
    { label: "Owner account", complete: setupComplete() },
    { label: "Auth domain", complete: Boolean(readySettings.auth_domain) },
    { label: "Redirect URLs", complete: Boolean(readySettings.redirect_urls?.length) },
    { label: "Email provider", complete: Boolean(readySettings.resend_configured) },
  ];
  const visibleMetrics = dashboardMetrics();

  renderAppShell(`
    <div class="hero">
      <div class="page-heading">
        <span class="eyebrow">Dashboard</span>
        <h2>Deploy your auth surface</h2>
        <p>Hosted pages, public API, dashboard, and service keys behind one web service.</p>
      </div>
      <div class="panel">
        <div class="panel-heading">
          <span class="eyebrow">Setup state</span>
          <h3>Owner configured</h3>
        </div>
        <ul class="setup-list" aria-label="Setup checklist">
          ${setupItems.map((item) => `<li class="${item.complete ? "complete" : ""}">${item.label}</li>`).join("")}
        </ul>
        <a class="primary-action" href="/settings" data-link>Edit settings</a>
      </div>
    </div>
    <div class="metric-grid" aria-label="Auth readiness">
      ${visibleMetrics
        .map(
          (metric) => `
            <div class="metric">
              <span>${metric.label}</span>
              <strong>${metric.value}</strong>
              <small>${metric.detail}</small>
            </div>
          `,
        )
        .join("")}
    </div>
  `);
}

function renderPlaceholder(title, body) {
  renderAppShell(`
    <div class="placeholder-view">
      <div class="page-heading">
        <span class="eyebrow">Dashboard</span>
        <h2>${title}</h2>
        <p>${body}</p>
      </div>
      <div class="panel">
        <p class="form-message">This section is ready for the next feature commit.</p>
      </div>
    </div>
  `);
}

function renderSettings() {
  if (!state.settings && !state.settingsLoading) {
    void loadSettings();
  }

  if (!state.settings) {
    renderAppShell(`
      <div class="placeholder-view">
        <div class="page-heading">
          <span class="eyebrow">Dashboard</span>
          <h2>Settings</h2>
          <p>Loading saved configuration.</p>
        </div>
      </div>
    `);
    return;
  }

  const settings = state.settings;
  const googleOrigin = ensureOrigin(settings.auth_domain || settings.app_domain);
  const googleRedirectUrl = googleOrigin
    ? `${googleOrigin}/api/v1/auth/google/callback`
    : "https://auth.example.com/api/v1/auth/google/callback";

  renderAppShell(`
    <form class="route-stack settings-route" data-form="settings">
      <div class="page-heading">
        <span class="eyebrow">Dashboard</span>
        <h2>Settings</h2>
        <p>Configure domains, redirect URLs, Resend, Google OAuth, branding, and auth methods.</p>
      </div>

      <section class="settings-section">
        <div class="section-heading">
          <span class="eyebrow">Domains</span>
          <h3>Public URLs</h3>
        </div>
        <div class="form-grid two-columns">
          <label class="field">
            <span>Application domain</span>
            <input name="app_domain" type="text" value="${escapeHtml(settings.app_domain)}" placeholder="app.example.com" />
          </label>
          <label class="field">
            <span>Auth domain</span>
            <input name="auth_domain" type="text" value="${escapeHtml(settings.auth_domain)}" placeholder="auth.example.com" />
          </label>
          <label class="field">
            <span>Allowed origins</span>
            <textarea name="allowed_origins" rows="4" placeholder="https://app.example.com">${escapeHtml(
              listToLines(settings.allowed_origins),
            )}</textarea>
          </label>
          <label class="field">
            <span>Redirect URLs</span>
            <textarea name="redirect_urls" rows="4" placeholder="https://app.example.com/auth/callback">${escapeHtml(
              listToLines(settings.redirect_urls),
            )}</textarea>
          </label>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <span class="eyebrow">Email</span>
          <h3>Resend</h3>
        </div>
        <div class="form-grid two-columns">
          <label class="field">
            <span>From email</span>
            <input name="resend_from_email" type="text" value="${escapeHtml(
              settings.resend_from_email,
            )}" placeholder="Passport Auth <auth@example.com>" />
          </label>
          <label class="field">
            <span>API key</span>
            <input name="resend_api_key" type="password" placeholder="${
              settings.resend_configured ? "Configured" : "re_..."
            }" />
          </label>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <span class="eyebrow">OAuth</span>
          <h3>Google</h3>
        </div>
        <div class="form-grid two-columns">
          <label class="field">
            <span>Client ID</span>
            <input name="google_client_id" type="text" value="${escapeHtml(
              settings.google_client_id,
            )}" placeholder="000000000000-example.apps.googleusercontent.com" />
          </label>
          <label class="field">
            <span>Client secret</span>
            <input name="google_client_secret" type="password" placeholder="${
              settings.google_configured ? "Configured" : "GOCSPX-..."
            }" />
          </label>
        </div>
        <div class="guidance">
          <div>
            <span>Authorized JavaScript origin</span>
            <code>${escapeHtml(googleOrigin || "https://auth.example.com")}</code>
          </div>
          <div>
            <span>Authorized redirect URI</span>
            <code>${escapeHtml(googleRedirectUrl)}</code>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <span class="eyebrow">Branding</span>
          <h3>Identity</h3>
        </div>
        <div class="form-grid two-columns">
          <label class="field">
            <span>Brand name</span>
            <input name="brand_name" type="text" value="${escapeHtml(
              settings.brand_name,
            )}" placeholder="Passport Auth" />
          </label>
          <label class="field">
            <span>Primary color</span>
            <input name="primary_color" type="text" value="${escapeHtml(
              settings.primary_color,
            )}" placeholder="#f5f5f7" />
          </label>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <span class="eyebrow">Methods</span>
          <h3>Auth toggles</h3>
        </div>
        <div class="toggle-grid">
          ${Object.entries(authMethodLabels)
            .map(
              ([name, label]) => `
                <label class="toggle-row">
                  <input name="${name}" type="checkbox" ${settings[name] ? "checked" : ""} />
                  <span class="toggle-control" aria-hidden="true"></span>
                  <span>${label}</span>
                </label>
              `,
            )
            .join("")}
        </div>
      </section>

      ${renderError()}
      ${renderMessage()}
      <div class="form-actions sticky-actions">
        <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
          ${state.busy ? "Saving..." : "Save settings"}
        </button>
      </div>
    </form>
  `);
}

function renderError() {
  return state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : "";
}

function renderMessage() {
  return state.message ? `<p class="form-message">${escapeHtml(state.message)}</p>` : "";
}

function render() {
  if (!state.setup) {
    app.className = "boot-screen";
    app.innerHTML = `${brandMarkup(true)}<p>Loading Passport Auth</p>`;
    return;
  }

  const path = currentPath();
  const done = setupComplete();

  if (!done) {
    renderSetup();
    return;
  }

  if (!state.user) {
    renderAuth();
    return;
  }

  if (path === "/setup") {
    window.history.replaceState({}, "", "/");
    renderDashboard();
    return;
  }

  if (path === "/users") {
    renderPlaceholder("Users", "Create, review, and deactivate application users.");
    return;
  }

  if (path === "/settings") {
    renderSettings();
    return;
  }

  if (path === "/analytics") {
    renderPlaceholder("Analytics", "Track public auth events and sign-in health.");
    return;
  }

  renderDashboard();
}

async function handleSetupSubmit(form) {
  const formData = new FormData(form);
  const email = String(formData.get("ownerEmail") || "").trim();
  const password = String(formData.get("password") || "");
  const confirmPassword = String(formData.get("confirmPassword") || "");

  if (password !== confirmPassword) {
    state.error = "Passwords do not match.";
    render();
    return;
  }

  state.busy = true;
  state.error = "";
  render();

  try {
    state.setup = await api("/api/v1/setup/owner", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    state.message = "Owner created. Sign in with that password.";
    window.history.replaceState({}, "", "/");
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleLoginSubmit(form) {
  const formData = new FormData(form);
  const email = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const login = await api("/api/v1/dashboard/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      headers: {},
    });
    state.token = login.access_token;
    state.user = login.user;
    localStorage.setItem(TOKEN_KEY, state.token);
    await loadSettings({ quiet: true });
    window.history.replaceState({}, "", "/");
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleResetStart(form) {
  const formData = new FormData(form);
  const email = String(formData.get("email") || "").trim();

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const reset = await api("/api/v1/dashboard/auth/password-reset/start", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    state.resetEmail = email;
    state.devOtp = reset.dev_otp || "";
    state.authMode = "reset-confirm";
    state.message = "Enter the OTP sent to the owner email.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleResetConfirm(form) {
  const formData = new FormData(form);
  const otp = String(formData.get("otp") || "").trim();
  const password = String(formData.get("password") || "");

  state.busy = true;
  state.error = "";
  render();

  try {
    await api("/api/v1/dashboard/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ email: state.resetEmail, otp, password }),
    });
    state.authMode = "login";
    state.devOtp = "";
    state.message = "Password updated. Sign in with the new password.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleSettingsSubmit(form) {
  const formData = new FormData(form);
  const payload = {
    app_domain: String(formData.get("app_domain") || "").trim(),
    auth_domain: String(formData.get("auth_domain") || "").trim(),
    allowed_origins: linesToList(formData.get("allowed_origins")),
    redirect_urls: linesToList(formData.get("redirect_urls")),
    resend_from_email: String(formData.get("resend_from_email") || "").trim(),
    google_client_id: String(formData.get("google_client_id") || "").trim(),
    brand_name: String(formData.get("brand_name") || "").trim() || "Passport Auth",
    primary_color: String(formData.get("primary_color") || "").trim() || "#f5f5f7",
    password_login_enabled: checkboxValue(formData, "password_login_enabled"),
    otp_login_enabled: checkboxValue(formData, "otp_login_enabled"),
    magic_link_enabled: checkboxValue(formData, "magic_link_enabled"),
    google_oauth_enabled: checkboxValue(formData, "google_oauth_enabled"),
    password_reset_otp_enabled: checkboxValue(formData, "password_reset_otp_enabled"),
  };
  const resendApiKey = String(formData.get("resend_api_key") || "").trim();
  const googleClientSecret = String(formData.get("google_client_secret") || "").trim();

  if (resendApiKey) {
    payload.resend_api_key = resendApiKey;
  }
  if (googleClientSecret) {
    payload.google_client_secret = googleClientSecret;
  }

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    state.settings = await api("/api/v1/dashboard/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.message = "Settings saved.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

app.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  const formName = form.dataset.form;

  if (formName === "setup") {
    void handleSetupSubmit(form);
  }
  if (formName === "login") {
    void handleLoginSubmit(form);
  }
  if (formName === "reset-start") {
    void handleResetStart(form);
  }
  if (formName === "reset-confirm") {
    void handleResetConfirm(form);
  }
  if (formName === "settings") {
    void handleSettingsSubmit(form);
  }
});

app.addEventListener("click", (event) => {
  const link = event.target.closest("[data-link]");
  if (link) {
    event.preventDefault();
    navigate(link.getAttribute("href") || "/");
    return;
  }

  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!action) {
    return;
  }

  if (action === "sign-out") {
    localStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
    state.settings = null;
    state.authMode = "login";
    state.message = "";
    state.error = "";
    render();
  }
  if (action === "reset-start") {
    state.authMode = "reset-start";
    state.error = "";
    state.message = "";
    render();
  }
  if (action === "login") {
    state.authMode = "login";
    state.error = "";
    state.message = "";
    render();
  }
  if (action === "go-dashboard") {
    navigate("/");
  }
});

window.addEventListener("popstate", () => render());

async function boot() {
  render();

  try {
    await loadSetupStatus();
    if (setupComplete()) {
      await loadProfile();
      if (state.user) {
        await loadSettings({ quiet: true });
      }
    }
  } catch (error) {
    state.error = error.message;
    state.setup = { setup_complete: false, owner: null };
  }

  render();
}

void boot();
