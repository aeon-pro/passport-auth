const AUTH_BASE_KEY = "passport-local-auth-base";
const ACCESS_TOKEN_KEY = "passport-local-access-token";
const REFRESH_TOKEN_KEY = "passport-local-refresh-token";
const PKCE_VERIFIER_KEY = "passport-local-pkce-verifier";

const app = document.querySelector("#app");
const defaultAuthBase = "http://localhost:8000";
const state = {
  authBase: localStorage.getItem(AUTH_BASE_KEY) || defaultAuthBase,
  accessToken: localStorage.getItem(ACCESS_TOKEN_KEY) || "",
  refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || "",
  user: null,
  loading: true,
  message: "",
  error: "",
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function appOrigin() {
  return window.location.origin;
}

function redirectUrl() {
  return `${appOrigin()}/auth/callback`;
}

function cleanAuthBase(value) {
  return String(value || "")
    .trim()
    .replace(/\/+$/, "");
}

function displayName(user) {
  const emailName = String(user?.email || "")
    .split("@")[0]
    .replace(/[._-]+/g, " ");
  const fallbackName = emailName
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
  return user?.name || fallbackName || "Signed in user";
}

function tokenPayload(token) {
  try {
    const [, payload] = token.split(".");
    const padded = `${payload}${"=".repeat((4 - (payload.length % 4)) % 4)}`;
    return JSON.parse(atob(padded.replaceAll("-", "+").replaceAll("_", "/")));
  } catch {
    return null;
  }
}

async function sha256Base64Url(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function randomBase64Url(byteLength = 48) {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

async function createPkceChallenge() {
  const verifier = randomBase64Url(64);
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  return sha256Base64Url(verifier);
}

async function api(path, options = {}) {
  const response = await fetch(`${state.authBase}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {}),
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(body?.detail || "Request failed.");
  }

  return body;
}

async function startHostedFlow(path) {
  state.error = "";
  state.message = "";
  render();

  const codeChallenge = await createPkceChallenge();
  const params = new URLSearchParams({
    redirect_url: redirectUrl(),
    code_challenge: codeChallenge,
  });
  window.location.href = `${state.authBase}${path}?${params.toString()}`;
}

async function startGoogleFlow() {
  state.error = "";
  state.message = "";
  render();

  try {
    const codeChallenge = await createPkceChallenge();
    const params = new URLSearchParams({
      redirect_url: redirectUrl(),
      code_challenge: codeChallenge,
    });
    const start = await api(`/api/v1/auth/google/start?${params.toString()}`, {
      headers: {},
    });
    window.location.href = start.authorization_url;
  } catch (error) {
    state.error = error.message;
    render();
  }
}

async function exchangeCallbackCode() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (!code) {
    return;
  }

  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  if (!verifier) {
    state.error = "Missing PKCE verifier. Start the sign-in flow again.";
    return;
  }

  const token = await api("/api/v1/auth/token", {
    method: "POST",
    body: JSON.stringify({ code, code_verifier: verifier }),
    headers: {},
  });
  state.accessToken = token.access_token;
  state.refreshToken = token.refresh_token;
  localStorage.setItem(ACCESS_TOKEN_KEY, state.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, state.refreshToken);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  window.history.replaceState({}, "", "/");
}

async function refreshTokens() {
  if (!state.refreshToken) {
    return false;
  }

  try {
    const token = await api("/api/v1/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: state.refreshToken }),
      headers: {},
    });
    state.accessToken = token.access_token;
    state.refreshToken = token.refresh_token;
    localStorage.setItem(ACCESS_TOKEN_KEY, state.accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, state.refreshToken);
    return true;
  } catch {
    clearSession();
    return false;
  }
}

async function loadUser() {
  if (!state.accessToken) {
    state.user = null;
    return;
  }

  try {
    state.user = await api("/api/v1/auth/me");
  } catch {
    if (await refreshTokens()) {
      state.user = await api("/api/v1/auth/me");
      return;
    }
    state.user = null;
  }
}

async function logout() {
  state.error = "";
  state.message = "";

  try {
    if (state.refreshToken) {
      await api("/api/v1/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
    }
  } catch {
    // Local demos should still clear the browser session if the server token is already gone.
  }

  clearSession();
  state.message = "Signed out.";
  render();
}

function clearSession() {
  state.accessToken = "";
  state.refreshToken = "";
  state.user = null;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function saveAuthBase(form) {
  const formData = new FormData(form);
  const authBase = cleanAuthBase(formData.get("authBase"));
  if (!authBase.startsWith("http://") && !authBase.startsWith("https://")) {
    state.error = "Enter a full Passport Auth URL, including http:// or https://.";
    render();
    return;
  }

  state.authBase = authBase;
  localStorage.setItem(AUTH_BASE_KEY, state.authBase);
  state.message = "Passport Auth URL saved.";
  state.error = "";
  render();
}

function render() {
  app.innerHTML = `
    <section class="hero">
      <div>
        <span class="eyebrow">Local client app</span>
        <h1>Passport Auth test dashboard</h1>
        <p>
          This app runs on <strong>${escapeHtml(appOrigin())}</strong>, signs in through
          Passport Auth hosted pages, and shows the current public auth user.
        </p>
      </div>
      <form class="auth-base-card" data-form="auth-base">
        <label>
          <span>Passport Auth URL</span>
          <input name="authBase" value="${escapeHtml(state.authBase)}" placeholder="https://auth.example.com" />
        </label>
        <button type="submit">Save URL</button>
      </form>
    </section>

    ${state.loading ? renderLoading() : state.user ? renderDashboard() : renderSignedOut()}

    <section class="setup-card">
      <span class="eyebrow">Passport settings for this local app</span>
      <dl>
        <div>
          <dt>Application domain</dt>
          <dd>${escapeHtml(appOrigin())}</dd>
        </div>
        <div>
          <dt>Allowed origins</dt>
          <dd>${escapeHtml(appOrigin())}</dd>
        </div>
        <div>
          <dt>Redirect URLs</dt>
          <dd>${escapeHtml(redirectUrl())}</dd>
        </div>
      </dl>
    </section>
  `;
}

function renderLoading() {
  return `
    <section class="panel">
      <span class="eyebrow">Checking session</span>
      <h2>Loading</h2>
      <p>Reading local tokens and asking Passport Auth for the current user.</p>
    </section>
  `;
}

function renderDashboard() {
  const payload = tokenPayload(state.accessToken);
  return `
    <section class="dashboard">
      <div class="profile-card">
        <span class="avatar">${escapeHtml(displayName(state.user).slice(0, 2).toUpperCase())}</span>
        <div>
          <span class="eyebrow">Logged in user</span>
          <h2>${escapeHtml(displayName(state.user))}</h2>
          <p>${escapeHtml(state.user.email)}</p>
        </div>
      </div>
      <div class="detail-grid">
        <div>
          <span>Name</span>
          <strong>${escapeHtml(displayName(state.user))}</strong>
        </div>
        <div>
          <span>Email</span>
          <strong>${escapeHtml(state.user.email)}</strong>
        </div>
        <div>
          <span>Role</span>
          <strong>${escapeHtml(state.user.role)}</strong>
        </div>
        <div>
          <span>User ID</span>
          <strong>${escapeHtml(state.user.id)}</strong>
        </div>
        <div>
          <span>Token expires</span>
          <strong>${payload?.exp ? new Date(payload.exp * 1000).toLocaleString() : "Unknown"}</strong>
        </div>
        <div>
          <span>Auth service</span>
          <strong>${escapeHtml(state.authBase)}</strong>
        </div>
      </div>
      <button class="danger" type="button" data-action="logout">Log out</button>
    </section>
  `;
}

function renderSignedOut() {
  return `
    <section class="panel">
      <span class="eyebrow">Signed out</span>
      <h2>Choose a hosted auth flow</h2>
      <p>The auth code returns to <strong>${escapeHtml(redirectUrl())}</strong>, then this app exchanges it for tokens.</p>
      ${state.error ? `<p class="error">${escapeHtml(state.error)}</p>` : ""}
      ${state.message ? `<p class="message">${escapeHtml(state.message)}</p>` : ""}
      <div class="actions">
        <button type="button" data-action="login">Sign in</button>
        <button type="button" data-action="register">Create account</button>
        <button type="button" data-action="otp">Use OTP</button>
        <button type="button" data-action="google">Google OAuth</button>
      </div>
    </section>
  `;
}

app.addEventListener("submit", (event) => {
  event.preventDefault();
  if (event.target.dataset.form === "auth-base") {
    saveAuthBase(event.target);
  }
});

app.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) {
    return;
  }

  const action = button.dataset.action;
  if (action === "login") {
    void startHostedFlow("/login");
  }
  if (action === "register") {
    void startHostedFlow("/register");
  }
  if (action === "otp") {
    void startHostedFlow("/verify");
  }
  if (action === "google") {
    void startGoogleFlow();
  }
  if (action === "logout") {
    void logout();
  }
});

async function boot() {
  render();
  try {
    await exchangeCallbackCode();
    await loadUser();
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loading = false;
    render();
  }
}

void boot();
