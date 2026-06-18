const TOKEN_KEY = "passport-auth-token";
const app = document.querySelector("#app");
const defaultTemplateColor = "#f5f5f7";
const defaultBlockedMessage = "This account is blocked. Contact support for more help.";
const templateColorPresets = [
  defaultTemplateColor,
  "#7cffaa",
  "#b8f3ff",
  "#ffd27a",
  "#ff9fb2",
  "#c7b7ff",
];
const templateSaveLabels = {
  magic_link: "Save Magic link",
  otp: "Save One-time passcode",
  password_reset: "Save Password reset OTP",
  dashboard_invite: "Save Admin invite",
};

const defaultEmailTemplates = [
  {
    key: "magic_link",
    name: "Magic link",
    subject: "Sign in to {{brand_name}}",
    headline: "Your sign-in link is ready",
    body: "Use the secure link below to finish signing in. The link expires soon.",
    button_label: "Open magic link",
    accent_color: defaultTemplateColor,
    footer_text: "If you did not request this sign-in link, you can safely ignore this email.",
    support_label: "Contact support",
    support_url: "mailto:support@example.com",
  },
  {
    key: "otp",
    name: "One-time passcode",
    subject: "Your {{brand_name}} verification code",
    headline: "Your verification code",
    body: "Enter {{code}} to continue. This code expires soon.",
    button_label: "Use this code",
    accent_color: defaultTemplateColor,
    footer_text: "If you did not request this code, you can safely ignore this email.",
    support_label: "Contact support",
    support_url: "mailto:support@example.com",
  },
  {
    key: "password_reset",
    name: "Password reset OTP",
    subject: "Reset your {{brand_name}} password",
    headline: "Reset your password",
    body:
      "Enter {{code}} to reset your dashboard password. Ignore this email if you did not request it.",
    button_label: "Reset password",
    accent_color: defaultTemplateColor,
    footer_text: "If you did not request this password reset, contact support immediately.",
    support_label: "Contact support",
    support_url: "mailto:support@example.com",
  },
  {
    key: "dashboard_invite",
    name: "Admin invite",
    subject: "Set up your {{brand_name}} admin access",
    headline: "You have been invited",
    body: "Use the secure link below to set your dashboard password. The link expires soon.",
    button_label: "Set admin password",
    accent_color: defaultTemplateColor,
    footer_text: "If you did not request this dashboard invite, you can safely ignore this email.",
    support_label: "Contact support",
    support_url: "mailto:support@example.com",
  },
];

const defaultOnboarding = {
  ownerEmail: "",
  password: "",
  confirmPassword: "",
  app_domain: "",
  auth_domain: "",
  allowed_origins: "",
  redirect_urls: "",
  password_login_enabled: true,
  otp_login_enabled: false,
  magic_link_enabled: false,
  google_oauth_enabled: false,
  password_reset_otp_enabled: true,
  resend_from_email: "",
  resend_api_key: "",
  google_client_id: "",
  google_client_secret: "",
  brand_name: "Passport Auth",
  primary_color: defaultTemplateColor,
  logo_url: "",
  mark_url: "",
  email_templates: cloneEmailTemplates(),
};

const state = {
  setup: null,
  user: null,
  settings: null,
  branding: null,
  users: [],
  usersTotal: 0,
  usersQuery: "",
  usersLoaded: false,
  usersLoading: false,
  selectedUserId: "",
  editingUserId: "",
  admins: [],
  adminsTotal: 0,
  adminsLoaded: false,
  adminsLoading: false,
  adminInviteDevLink: "",
  adminInviteAccepted: false,
  analytics: null,
  analyticsLoaded: false,
  analyticsLoading: false,
  analyticsError: "",
  settingsLoading: false,
  token: localStorage.getItem(TOKEN_KEY),
  authMode: "login",
  onboardingStep: 0,
  onboarding: { ...defaultOnboarding, email_templates: cloneEmailTemplates() },
  resetEmail: "",
  devOtp: "",
  hostedRegisterEmail: "",
  hostedRegisterDevCode: "",
  hostedOtpEmail: "",
  hostedOtpDevCode: "",
  hostedResetEmail: "",
  hostedResetDevCode: "",
  hostedMagicDevLink: "",
  hostedMagicConsumeKey: "",
  hostedRequestValidation: { key: "", status: "idle", error: "" },
  message: "",
  error: "",
  busy: false,
  onboardingLogoFiles: {
    primary: null,
    mark: null,
  },
  onboardingLogoPreviews: {
    primary: "",
    mark: "",
  },
};

const routes = [
  { href: "/", label: "Dashboard" },
  { href: "/users", label: "Users" },
  { href: "/admins", label: "Admins" },
  { href: "/settings", label: "Settings" },
  { href: "/templates", label: "Templates" },
  { href: "/analytics", label: "Analytics" },
];

const routeMeta = {
  "/": {
    title: "Dashboard",
    hint: "Auth operations",
    icon: "home",
  },
  "/users": {
    title: "Users",
    hint: "Application directory",
    icon: "users",
  },
  "/admins": {
    title: "Admins",
    hint: "Dashboard access",
    icon: "key",
  },
  "/settings": {
    title: "Settings",
    hint: "Domains and providers",
    icon: "sliders",
  },
  "/templates": {
    title: "Templates",
    hint: "Email copy",
    icon: "mail",
  },
  "/analytics": {
    title: "Analytics",
    hint: "Auth health",
    icon: "chart",
  },
};

const hostedAuthPaths = ["/login", "/register", "/verify", "/reset-password"];

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

const userRoleOptions = [
  { value: "user", label: "User" },
  { value: "admin", label: "Admin" },
  { value: "owner", label: "Owner" },
];

const onboardingSteps = [
  {
    title: "Welcome",
    eyebrow: "Start here",
    summary: "Set the owner account, URLs, auth methods, providers, and branding.",
    lessonTitle: "What you are creating",
    lessons: [
      "One public FastAPI service serves hosted auth pages, APIs, and this dashboard.",
      "The owner account protects the dashboard and can change these settings later.",
      "Tokens and one-time codes stay out of redirect URLs; setup creates the safe defaults.",
    ],
  },
  {
    title: "Owner",
    eyebrow: "Dashboard access",
    summary: "Create the first dashboard user. This locks the first-run setup flow.",
    lessonTitle: "Why this comes first",
    lessons: [
      "The owner account is the root dashboard identity.",
      "Use a strong password; the stored value is hashed before it reaches persistence.",
      "After this, future dashboard access goes through the JWT-backed login screen.",
    ],
  },
  {
    title: "URLs",
    eyebrow: "Public surface",
    summary: "Tell Passport Auth where your app lives and where browser redirects may return.",
    lessonTitle: "Redirect safety",
    lessons: [
      "Allowed origins control which browser apps can call public auth endpoints.",
      "Redirect URLs prevent auth codes from being sent to unknown destinations.",
      "The auth domain is used to build hosted page and Google OAuth callback guidance.",
    ],
  },
  {
    title: "Methods",
    eyebrow: "Auth options",
    summary: "Choose the sign-in methods your app should expose on day one.",
    lessonTitle: "Keep the surface small",
    lessons: [
      "Password login is the simplest baseline and stays enabled by default.",
      "OTP and magic links require working email delivery before production use.",
      "Google OAuth needs an authorized origin and redirect URI in Google Cloud.",
    ],
  },
  {
    title: "Providers",
    eyebrow: "Delivery and OAuth",
    summary: "Add email delivery and Google OAuth credentials now, or leave them blank.",
    lessonTitle: "Secrets stay private",
    lessons: [
      "Provider secrets are accepted once and hidden after save.",
      "Resend powers OTP, magic links, and password reset messages.",
      "The Google guidance below updates from the domains you entered.",
    ],
  },
  {
    title: "Branding",
    eyebrow: "Hosted pages",
    summary: "Set the name and accent color shown on hosted auth screens.",
    lessonTitle: "Small brand surface",
    lessons: [
      "Branding should be recognizable without making the auth flow feel noisy.",
      "A single accent color is enough for buttons, focus rings, and active states.",
      "You can revise this later from Settings without touching environment variables.",
    ],
  },
  {
    title: "Templates",
    eyebrow: "Email",
    summary: "Customize the email copy and accent colors for links, codes, and resets.",
    lessonTitle: "Reusable placeholders",
    lessons: [
      "Use {{brand_name}} where the saved brand name should appear.",
      "Use {{code}} for OTP and password reset codes.",
      "Template colors can follow the brand accent or use a separate email-specific accent.",
    ],
  },
  {
    title: "Review",
    eyebrow: "Launch",
    summary: "Confirm the setup details, then create the owner and save the configuration.",
    lessonTitle: "What happens next",
    lessons: [
      "Passport Auth creates the owner account, signs you in, and stores the settings.",
      "Email and OAuth secrets are saved as protected settings and never echoed back.",
      "After launch, the dashboard opens with setup progress and editable settings.",
    ],
  },
];

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

function normalizeHexColor(value) {
  const color = String(value || "").trim().toLowerCase();
  return /^#[0-9a-f]{6}$/.test(color) ? color : defaultTemplateColor;
}

function hexToRgb(color) {
  return [1, 3, 5].map((start) => Number.parseInt(color.slice(start, start + 2), 16));
}

function closestPresetColor(value) {
  const color = normalizeHexColor(value);
  if (templateColorPresets.includes(color)) {
    return color;
  }

  const target = hexToRgb(color);
  return templateColorPresets.reduce((closest, preset) => {
    const presetRgb = hexToRgb(preset);
    const closestRgb = hexToRgb(closest);
    const presetDistance = target.reduce(
      (total, channel, index) => total + (channel - presetRgb[index]) ** 2,
      0,
    );
    const closestDistance = target.reduce(
      (total, channel, index) => total + (channel - closestRgb[index]) ** 2,
      0,
    );
    return presetDistance < closestDistance ? preset : closest;
  }, defaultTemplateColor);
}

function normalizePresetColor(value) {
  return closestPresetColor(value);
}

function renderColorPresetButtons(selectedColor) {
  return templateColorPresets
    .map(
      (color) => `
        <button
          class="color-preset-swatch ${color === selectedColor ? "active" : ""}"
          type="button"
          style="--preset-color: ${escapeHtml(color)}"
          data-color-preset="${escapeHtml(color)}"
          aria-label="Use ${escapeHtml(color)}"
        ></button>
      `,
    )
    .join("");
}

function renderColorPresetField({ name, value, label }) {
  const selectedColor = normalizePresetColor(value);
  return `
    <div class="color-field preset-color-field">
      <input
        class="color-value"
        name="${escapeHtml(name)}"
        type="hidden"
        value="${escapeHtml(selectedColor)}"
        data-color-value
      />
      <div class="color-preset-box">
        <div class="color-preset-grid" aria-label="${escapeHtml(label)}">
          ${renderColorPresetButtons(selectedColor)}
        </div>
      </div>
    </div>
  `;
}

function renderLogoPreview(url, fallbackText) {
  if (url) {
    return `<img src="${escapeHtml(url)}" alt="" />`;
  }
  return `<span>${escapeHtml(brandInitials(fallbackText))}</span>`;
}

function renderLogoUploadField({ label, name, hiddenName, currentUrl, fallbackText, note }) {
  return `
    <label class="logo-upload-card">
      <input name="${escapeHtml(hiddenName)}" type="hidden" value="${escapeHtml(currentUrl || "")}" />
      <input name="${escapeHtml(name)}" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" />
      <span class="logo-upload-preview" aria-hidden="true">
        ${renderLogoPreview(currentUrl, fallbackText)}
      </span>
      <span class="logo-upload-copy">
        <strong>${escapeHtml(label)}</strong>
        <small>${escapeHtml(note)}</small>
      </span>
    </label>
  `;
}

function cloneEmailTemplates(templates = defaultEmailTemplates) {
  return templates.map((template) => ({ ...template }));
}

function normalizeEmailTemplates(templates) {
  const templatesByKey = new Map((templates || []).map((template) => [template.key, template]));
  return defaultEmailTemplates.map((defaultTemplate) => {
    const template = {
      ...defaultTemplate,
      ...(templatesByKey.get(defaultTemplate.key) || {}),
    };
    return {
      ...template,
      accent_color: normalizePresetColor(template.accent_color),
    };
  });
}

function sampleTemplateText(value, brandName = "Passport Auth") {
  return String(value || "")
    .replaceAll("{{brand_name}}", brandName || "Passport Auth")
    .replaceAll("{{code}}", "482913")
    .replaceAll("{{magic_link}}", "https://auth.example.com/magic/secure-token")
    .replaceAll("{{invite_link}}", "https://auth.example.com/admin-invite?token=secure-token");
}

function readEmailTemplatesFromForm(form) {
  const formData = new FormData(form);
  return defaultEmailTemplates.map((defaultTemplate, index) => ({
    key:
      String(formData.get(`email_templates.${index}.key`) || "").trim() ||
      defaultTemplate.key,
    name:
      String(formData.get(`email_templates.${index}.name`) || "").trim() ||
      defaultTemplate.name,
    subject:
      String(formData.get(`email_templates.${index}.subject`) || "").trim() ||
      defaultTemplate.subject,
    headline:
      String(formData.get(`email_templates.${index}.headline`) || "").trim() ||
      defaultTemplate.headline,
    body:
      String(formData.get(`email_templates.${index}.body`) || "").trim() ||
      defaultTemplate.body,
    button_label:
      String(formData.get(`email_templates.${index}.button_label`) || "").trim() ||
      defaultTemplate.button_label,
    accent_color: normalizePresetColor(
      String(formData.get(`email_templates.${index}.accent_color`) || "").trim() ||
        defaultTemplate.accent_color,
    ),
    footer_text:
      String(formData.get(`email_templates.${index}.footer_text`) || "").trim() ||
      defaultTemplate.footer_text,
    support_label:
      String(formData.get(`email_templates.${index}.support_label`) || "").trim() ||
      defaultTemplate.support_label,
    support_url:
      String(formData.get(`email_templates.${index}.support_url`) || "").trim() ||
      defaultTemplate.support_url,
  }));
}

function readEmailTemplateFromForm(form, index) {
  return readEmailTemplatesFromForm(form)[index] || null;
}

function rememberOnboardingLogo(formData, fieldName, slot) {
  const file = selectedFormFile(formData, fieldName);
  if (!file) {
    return;
  }

  state.onboardingLogoFiles[slot] = file;
  if (state.onboardingLogoPreviews[slot]) {
    URL.revokeObjectURL(state.onboardingLogoPreviews[slot]);
  }
  state.onboardingLogoPreviews[slot] = URL.createObjectURL(file);
}

function selectedFormFile(formData, name) {
  const file = formData.get(name);
  if (typeof File === "undefined" || !(file instanceof File) || file.size === 0) {
    return null;
  }
  return file;
}

async function uploadLogoAsset(slot, file) {
  const formData = new FormData();
  formData.append("file", file);
  return api(`/api/v1/dashboard/assets/logos/${slot}`, {
    method: "POST",
    body: formData,
  });
}

async function applySettingsLogoUploads(formData, payload) {
  payload.logo_url = String(formData.get("logo_url") || "").trim();
  payload.mark_url = String(formData.get("mark_url") || "").trim();

  const logoFile = selectedFormFile(formData, "logo_file");
  if (logoFile) {
    const uploaded = await uploadLogoAsset("primary", logoFile);
    payload.logo_url = uploaded.url;
  }

  const markFile = selectedFormFile(formData, "mark_file");
  if (markFile) {
    const uploaded = await uploadLogoAsset("mark", markFile);
    payload.mark_url = uploaded.url;
  }
}

async function applyOnboardingLogoUploads(payload) {
  if (state.onboardingLogoFiles.primary) {
    const uploaded = await uploadLogoAsset("primary", state.onboardingLogoFiles.primary);
    payload.logo_url = uploaded.url;
  }
  if (state.onboardingLogoFiles.mark) {
    const uploaded = await uploadLogoAsset("mark", state.onboardingLogoFiles.mark);
    payload.mark_url = uploaded.url;
  }
}

function ownerInitials() {
  return state.user?.email?.slice(0, 2).toUpperCase() || "PA";
}

function initialsFromUser(user) {
  const source = user?.name || user?.email || "User";
  const words = String(source).trim().split(/\s+/).filter(Boolean);
  const initials = words.length > 1 ? `${words[0][0]}${words[1][0]}` : words[0]?.slice(0, 2);
  return (initials || "U").toUpperCase();
}

function selectedUser() {
  return state.users.find((user) => user.id === state.selectedUserId) || state.users[0] || null;
}

function editingUser() {
  return state.users.find((user) => user.id === state.editingUserId) || null;
}

function stringifyMetadata(value) {
  return JSON.stringify(value || {}, null, 2);
}

function formatUserDate(value) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatAuthMethod(value) {
  const labels = {
    google: "Google OAuth",
    magic_link: "Magic link",
    otp: "OTP",
    password: "Password",
  };
  return labels[value] || value || "Not recorded";
}

function formatUserRole(value) {
  return userRoleOptions.find((role) => role.value === value)?.label || "User";
}

function formatDashboardRole(value) {
  return value === "owner" ? "Owner" : "Admin";
}

function formatMetricNumber(value) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(numeric);
}

function formatPercent(value) {
  return `${formatMetricNumber(value)}%`;
}

function humanizeAnalyticsEvent(value) {
  return String(value || "event")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatInviteStatus(value) {
  return value === "accepted" ? "Accepted" : "Pending";
}

function renderRoleSelect(selectedRole) {
  const normalizedRole = userRoleOptions.some((role) => role.value === selectedRole)
    ? selectedRole
    : "user";
  return `
    <select name="role" class="role-select-field">
      ${userRoleOptions
        .map(
          (role) =>
            `<option value="${role.value}" ${role.value === normalizedRole ? "selected" : ""}>${role.label}</option>`,
        )
        .join("")}
    </select>
  `;
}

function renderPencilIcon() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 20h4.3L19.7 8.6a2 2 0 0 0 0-2.8l-1.5-1.5a2 2 0 0 0-2.8 0L4 15.7V20Z"></path>
      <path d="m14 5 5 5"></path>
    </svg>
  `;
}

function renderRouteIcon(icon) {
  const paths = {
    home: '<path d="M4 11.5 12 5l8 6.5V20H5v-8.5Z"></path><path d="M9 20v-5h6v5"></path>',
    users:
      '<path d="M16 20v-1.8c0-1.9-1.8-3.2-4-3.2s-4 1.3-4 3.2V20"></path><circle cx="12" cy="9" r="3"></circle><path d="M20 20v-1.5c0-1.4-.9-2.4-2.3-2.9"></path><path d="M16.8 6.4a2.5 2.5 0 0 1 0 5"></path>',
    key: '<circle cx="8" cy="12" r="3.2"></circle><path d="M11.2 12H21"></path><path d="M16 12v3"></path><path d="M19 12v2"></path>',
    sliders:
      '<path d="M5 7h14"></path><path d="M5 17h14"></path><circle cx="9" cy="7" r="2"></circle><circle cx="15" cy="17" r="2"></circle>',
    mail: '<rect x="4" y="6" width="16" height="12" rx="2"></rect><path d="m5 8 7 5 7-5"></path>',
    chart: '<path d="M5 19V5"></path><path d="M5 19h14"></path><path d="M8 15l3-4 3 2 4-6"></path>',
  };
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      ${paths[icon] || paths.home}
    </svg>
  `;
}

function currentRouteMeta() {
  return routeMeta[currentPath()] || { title: "Dashboard", hint: "Auth operations", icon: "home" };
}

function parseMetadata(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return {};
  }

  const parsed = JSON.parse(trimmed);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Metadata JSON must be an object.");
  }
  return parsed;
}

async function api(path, options = {}) {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body && !isFormData ? { "Content-Type": "application/json" } : {}),
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

async function publicApi(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
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

async function loadBranding() {
  try {
    state.branding = await api("/api/v1/dashboard/settings/branding");
  } catch {
    state.branding = null;
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

async function loadUsers({ query = state.usersQuery, quiet = false } = {}) {
  if (!state.token || state.usersLoading) {
    return;
  }

  state.usersQuery = query;
  state.usersLoading = true;
  if (!quiet) {
    render();
  }

  try {
    const params = new URLSearchParams();
    if (query) {
      params.set("query", query);
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api(`/api/v1/dashboard/users${suffix}`);
    state.users = response.users || [];
    state.usersTotal = response.total || state.users.length;
    state.usersLoaded = true;
    if (!state.users.some((user) => user.id === state.selectedUserId)) {
      state.selectedUserId = state.users[0]?.id || "";
    }
    if (!state.users.some((user) => user.id === state.editingUserId)) {
      state.editingUserId = "";
    }
  } catch (error) {
    if (!quiet) {
      state.error = error.message;
    }
  } finally {
    state.usersLoading = false;
    if (!quiet) {
      render();
    }
  }
}

async function loadAnalytics({ quiet = false } = {}) {
  if (!state.token || state.analyticsLoading) {
    return;
  }

  state.analyticsLoading = true;
  state.analyticsError = "";
  if (!quiet) {
    render();
  }

  try {
    state.analytics = await api("/api/v1/dashboard/analytics/summary");
    state.analyticsLoaded = true;
  } catch (error) {
    state.analyticsError = error.message;
  } finally {
    state.analyticsLoading = false;
    if (!quiet) {
      render();
    }
  }
}

async function loadAdmins({ quiet = false } = {}) {
  if (!state.token || state.adminsLoading) {
    return;
  }

  state.adminsLoading = true;
  if (!quiet) {
    render();
  }

  try {
    const response = await api("/api/v1/dashboard/admins");
    state.admins = response.admins || [];
    state.adminsTotal = response.total || state.admins.length;
    state.adminsLoaded = true;
  } catch (error) {
    if (!quiet) {
      state.error = error.message;
    }
  } finally {
    state.adminsLoading = false;
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

function isHostedAuthPath(path = currentPath()) {
  return hostedAuthPaths.includes(path);
}

function hostedAuthContext() {
  const params = new URLSearchParams(window.location.search);
  return {
    redirectUrl: params.get("redirect_url") || "",
    codeChallenge: params.get("code_challenge") || "",
    token: params.get("token") || "",
  };
}

function hostedAuthQuery() {
  const params = new URLSearchParams(window.location.search);
  params.delete("token");
  const query = params.toString();
  return query ? `?${query}` : "";
}

function hostedLink(path) {
  return `${path}${hostedAuthQuery()}`;
}

function hasHostedAuthRequest() {
  const context = hostedAuthContext();
  return Boolean(context.redirectUrl && context.codeChallenge);
}

function needsHostedAuthRequest(path, context) {
  return path !== "/reset-password" && !(path === "/verify" && context.token);
}

function hostedRequestValidationKey(path, context) {
  return `${path}|${context.redirectUrl}|${context.codeChallenge}`;
}

function startHostedMagicConsume(context) {
  if (!context.token || state.busy || state.hostedMagicConsumeKey === context.token) {
    return;
  }

  state.hostedMagicConsumeKey = context.token;
  void handleHostedMagicConsume(context.token);
}

function startHostedRequestValidation(path, context) {
  const key = hostedRequestValidationKey(path, context);
  if (state.hostedRequestValidation.key === key) {
    return state.hostedRequestValidation;
  }

  state.hostedRequestValidation = { key, status: "loading", error: "" };
  const query = new URLSearchParams({
    redirect_url: context.redirectUrl,
    code_challenge: context.codeChallenge,
  });

  publicApi(`/api/v1/auth/request/validate?${query.toString()}`)
    .then(() => {
      if (state.hostedRequestValidation.key === key) {
        state.hostedRequestValidation = { key, status: "valid", error: "" };
        render();
      }
    })
    .catch((error) => {
      if (state.hostedRequestValidation.key === key) {
        state.hostedRequestValidation = { key, status: "invalid", error: error.message };
        render();
      }
    });

  return state.hostedRequestValidation;
}

function navigate(path) {
  if (currentPath() !== path) {
    window.history.pushState({}, "", path);
  }
  state.error = "";
  state.message = "";
  render();
}

function completeHostedAuth(authCodeResponse) {
  const redirectUrl = new URL(authCodeResponse.redirect_url);
  redirectUrl.searchParams.set("code", authCodeResponse.authorization_code);
  window.location.href = redirectUrl.toString();
}

function currentBrandName() {
  return (
    state.settings?.brand_name ||
    state.branding?.brand_name ||
    state.onboarding?.brand_name ||
    "Passport Auth"
  );
}

function currentBrandLogoUrl({ preferMark = true } = {}) {
  const sources = [state.settings, state.branding, state.onboarding];
  for (const source of sources) {
    const preferred = preferMark ? source?.mark_url || source?.logo_url : source?.logo_url || source?.mark_url;
    if (preferred) {
      return preferred;
    }
  }
  return "";
}

function brandInitials(name = currentBrandName()) {
  const words = String(name || "Passport Auth")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const initials = words.length > 1 ? `${words[0][0]}${words[1][0]}` : words[0]?.slice(0, 2);
  return (initials || "PA").toUpperCase();
}

function brandMarkup(compact = false, { showFallbackMark = true } = {}) {
  const name = currentBrandName();
  const hasBrandVisual = showFallbackMark || Boolean(currentBrandLogoUrl({ preferMark: compact }));
  return `
    <a class="brand ${compact ? "compact" : ""} ${hasBrandVisual ? "" : "text-only"}" href="/" data-link>
      ${brandVisualMarkup(name, { compact, showFallbackMark })}
      <span>
        <h1>${escapeHtml(name)}</h1>
      </span>
    </a>
  `;
}

function brandVisualMarkup(name = currentBrandName(), { compact = false, showFallbackMark = true } = {}) {
  const logoUrl = currentBrandLogoUrl({ preferMark: compact });
  if (logoUrl) {
    return `<img class="brand-logo" src="${escapeHtml(logoUrl)}" alt="" />`;
  }
  if (!showFallbackMark) {
    return "";
  }
  return `<span class="brand-mark" aria-hidden="true">${escapeHtml(brandInitials(name))}</span>`;
}

function renderSidebarProfile() {
  if (!state.user) {
    return "";
  }

  return `
    <details class="profile-menu">
      <summary class="profile-summary">
        <span class="profile-avatar" aria-hidden="true">${escapeHtml(ownerInitials())}</span>
        <span>
          <strong>Profile</strong>
          <small>Owner account</small>
        </span>
      </summary>
      <div class="profile-dropdown">
        <div class="profile-detail">
          <span>Signed in as</span>
          <strong>${escapeHtml(state.user.email)}</strong>
        </div>
        <button class="profile-signout" type="button" data-action="sign-out">Sign out</button>
      </div>
    </details>
  `;
}

function renderAppShell(content) {
  const path = currentPath();
  const meta = currentRouteMeta();
  const brandName = currentBrandName();

  app.className = "app-shell studio-shell";
  app.innerHTML = `
    <aside class="workspace-rail" aria-label="Primary app rail">
      <a class="rail-brand" href="/" data-link aria-label="${escapeHtml(brandName)} dashboard">
        ${brandVisualMarkup(brandName, { compact: true, showFallbackMark: false })}
      </a>
      <nav class="rail-nav" aria-label="Icon navigation">
        ${routes
          .map(
            (route) => `<a
                href="${route.href}"
                data-link
                class="${route.href === path ? "active" : ""}"
                title="${route.label}"
                aria-label="${route.label}"
              >
                ${renderRouteIcon(routeMeta[route.href]?.icon)}
              </a>
            `,
          )
          .join("")}
      </nav>
    </aside>

    <aside class="workspace-sidebar sidebar" aria-label="Workspace">
      ${brandMarkup(true, { showFallbackMark: false })}
      <nav class="nav" aria-label="Primary">
        ${routes
          .map(
            (route) => `
              <a href="${route.href}" data-link class="${route.href === path ? "active" : ""}">
                <span>${route.label}</span>
              </a>
            `,
          )
          .join("")}
      </nav>
      ${renderSidebarProfile()}
    </aside>

    <main class="content">
      <header class="workspace-topbar">
        <div>
          <strong>${escapeHtml(meta.title)}</strong>
          <small>${escapeHtml(meta.hint)}</small>
        </div>
        <div class="toolbar-search" aria-hidden="true">
          <span>${renderRouteIcon("home")}</span>
          <strong>${escapeHtml(brandName)}</strong>
        </div>
      </header>
      <section class="workspace studio-main">${content}</section>
    </main>
  `;
}

function renderSetup() {
  renderOnboarding();
}

function renderOnboarding() {
  const step = onboardingSteps[state.onboardingStep];
  const isFinalStep = state.onboardingStep === onboardingSteps.length - 1;
  const canGoBack = state.onboardingStep > 0;

  renderAppShell(`
    <form class="onboarding-layout onboarding-command" data-form="onboarding">
      <aside class="step-rail" aria-label="Onboarding steps">
        <span class="eyebrow">First run</span>
        <h2>Configure Passport Auth</h2>
        <ol>
          ${onboardingSteps
            .map(
              (item, index) => `
                <li class="${index === state.onboardingStep ? "active" : ""} ${
                  index < state.onboardingStep ? "complete" : ""
                }">
                  <span>${index + 1}</span>
                  <strong>${item.title}</strong>
                </li>
              `,
            )
            .join("")}
        </ol>
      </aside>

      <section class="onboarding-main">
        <div class="page-heading compact-heading">
          <span class="eyebrow">${escapeHtml(step.eyebrow)}</span>
          <h2>${escapeHtml(step.title)}</h2>
          <p>${escapeHtml(step.summary)}</p>
        </div>

        <div class="lesson-panel">
          <div>
            <span class="eyebrow">${escapeHtml(step.lessonTitle)}</span>
            <ul>
              ${step.lessons.map((lesson) => `<li>${escapeHtml(lesson)}</li>`).join("")}
            </ul>
          </div>
        </div>

        ${renderOnboardingFields(state.onboardingStep)}
        ${renderError()}
        <div class="form-actions">
          ${
            canGoBack
              ? `<button class="secondary-action" type="button" data-action="onboarding-back">Back</button>`
              : `<a class="secondary-action" href="/" data-link>Back to overview</a>`
          }
          <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
            ${state.busy ? "Saving..." : isFinalStep ? "Complete setup" : "Continue"}
          </button>
        </div>
      </section>
    </form>
  `);
}

function renderOnboardingFields(stepIndex) {
  const data = state.onboarding;

  if (stepIndex === 0) {
    return `
      <div class="welcome-panel">
        <div>
          <span class="eyebrow">Setup path</span>
          <strong>7 focused steps</strong>
          <p>Nothing is saved until the final review. You can leave optional provider fields blank.</p>
        </div>
        <div>
          <span class="eyebrow">After launch</span>
          <strong>Protected dashboard</strong>
          <p>The setup wizard closes and the dashboard login protects the admin surface.</p>
        </div>
      </div>
    `;
  }

  if (stepIndex === 1) {
    return `
      <div class="form-grid">
        <label class="field">
          <span>Owner email</span>
          <input name="ownerEmail" type="email" autocomplete="email" value="${escapeHtml(
            data.ownerEmail,
          )}" placeholder="owner@example.com" required />
        </label>
        <label class="field">
          <span>Password</span>
          <input name="password" type="password" autocomplete="new-password" value="${escapeHtml(
            data.password,
          )}" placeholder="Minimum 12 characters" minlength="12" required />
        </label>
        <label class="field">
          <span>Confirm password</span>
          <input name="confirmPassword" type="password" autocomplete="new-password" value="${escapeHtml(
            data.confirmPassword,
          )}" placeholder="Repeat password" minlength="12" required />
        </label>
      </div>
    `;
  }

  if (stepIndex === 2) {
    return `
      <div class="form-grid two-columns">
        <label class="field">
          <span>Application domain</span>
          <input name="app_domain" type="text" value="${escapeHtml(
            data.app_domain,
          )}" placeholder="app.example.com" />
        </label>
        <label class="field">
          <span>Auth domain</span>
          <input name="auth_domain" type="text" value="${escapeHtml(
            data.auth_domain,
          )}" placeholder="auth.example.com" />
        </label>
        <label class="field">
          <span>Allowed origins</span>
          <textarea name="allowed_origins" rows="4" placeholder="https://app.example.com">${escapeHtml(
            data.allowed_origins,
          )}</textarea>
        </label>
        <label class="field">
          <span>Redirect URLs</span>
          <textarea name="redirect_urls" rows="4" placeholder="https://app.example.com/auth/callback">${escapeHtml(
            data.redirect_urls,
          )}</textarea>
        </label>
      </div>
    `;
  }

  if (stepIndex === 3) {
    return `
      <div class="toggle-grid">
        ${Object.entries(authMethodLabels)
          .map(
            ([name, label]) => `
              <label class="toggle-row">
                <input name="${name}" type="checkbox" ${data[name] ? "checked" : ""} />
                <span class="toggle-control" aria-hidden="true"></span>
                <span>${label}</span>
              </label>
            `,
          )
          .join("")}
      </div>
    `;
  }

  if (stepIndex === 4) {
    const googleOrigin = ensureOrigin(data.auth_domain || data.app_domain);
    const googleRedirectUrl = googleOrigin
      ? `${googleOrigin}/api/v1/auth/google/callback`
      : "https://auth.example.com/api/v1/auth/google/callback";

    return `
      <div class="form-grid two-columns">
        <label class="field">
          <span>Resend from email</span>
          <input name="resend_from_email" type="text" value="${escapeHtml(
            data.resend_from_email,
          )}" placeholder="Passport Auth <auth@example.com>" />
        </label>
        <label class="field">
          <span>Resend API key</span>
          <input name="resend_api_key" type="password" value="${escapeHtml(
            data.resend_api_key,
          )}" placeholder="re_..." />
        </label>
        <label class="field">
          <span>Google client ID</span>
          <input name="google_client_id" type="text" value="${escapeHtml(
            data.google_client_id,
          )}" placeholder="000000000000-example.apps.googleusercontent.com" />
        </label>
        <label class="field">
          <span>Google client secret</span>
          <input name="google_client_secret" type="password" value="${escapeHtml(
            data.google_client_secret,
          )}" placeholder="GOCSPX-..." />
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
    `;
  }

  if (stepIndex === 5) {
    const logoPreview = state.onboardingLogoPreviews.primary || data.logo_url;
    const markPreview = state.onboardingLogoPreviews.mark || data.mark_url || logoPreview;
    return `
      <div class="form-grid two-columns">
        <label class="field">
          <span>Brand name</span>
          <input name="brand_name" type="text" value="${escapeHtml(
            data.brand_name,
          )}" placeholder="Passport Auth" />
        </label>
        <label class="field">
          <span>Primary color</span>
          ${renderColorPresetField({
            name: "primary_color",
            value: data.primary_color,
            label: "Primary color presets",
          })}
        </label>
        ${renderLogoUploadField({
          label: "Primary logo",
          name: "logo_file",
          hiddenName: "logo_url",
          currentUrl: logoPreview,
          fallbackText: data.brand_name,
          note: "Used in emails, hosted pages, and wide brand moments.",
        })}
        ${renderLogoUploadField({
          label: "Compact mark",
          name: "mark_file",
          hiddenName: "mark_url",
          currentUrl: markPreview,
          fallbackText: data.brand_name,
          note: "Used in the dashboard sidebar and compact auth chrome.",
        })}
      </div>
      <div class="brand-preview" style="--preview-color: ${escapeHtml(normalizePresetColor(data.primary_color))}">
        <span class="brand-preview-mark">${renderLogoPreview(markPreview, data.brand_name)}</span>
        <div>
          <strong>${escapeHtml(data.brand_name || "Passport Auth")}</strong>
          <small>Hosted auth preview</small>
        </div>
      </div>
    `;
  }

  if (stepIndex === 6) {
    return renderTemplateCards(
      data.email_templates,
      data.brand_name || "Passport Auth",
      state.onboardingLogoPreviews.primary || data.logo_url || data.mark_url,
    );
  }

  return renderOnboardingReview();
}

function renderOnboardingReview() {
  const data = state.onboarding;
  const methods = Object.entries(authMethodLabels)
    .filter(([key]) => data[key])
    .map(([, label]) => label);
  const urls = [
    data.app_domain || "Application domain not set",
    data.auth_domain || "Auth domain not set",
  ];

  return `
    <div class="review-grid">
      <div>
        <span class="eyebrow">Owner</span>
        <strong>${escapeHtml(data.ownerEmail || "Missing owner email")}</strong>
      </div>
      <div>
        <span class="eyebrow">URLs</span>
        <strong>${urls.map(escapeHtml).join(" · ")}</strong>
      </div>
      <div>
        <span class="eyebrow">Methods</span>
        <strong>${escapeHtml(methods.join(", ") || "No methods selected")}</strong>
      </div>
      <div>
        <span class="eyebrow">Providers</span>
        <strong>${data.resend_api_key ? "Resend configured" : "Resend skipped"} · ${
          data.google_client_secret ? "Google configured" : "Google skipped"
        }</strong>
      </div>
      <div>
        <span class="eyebrow">Brand</span>
        <strong>${escapeHtml(data.brand_name || "Passport Auth")}</strong>
      </div>
      <div>
        <span class="eyebrow">Templates</span>
        <strong>${escapeHtml(normalizeEmailTemplates(data.email_templates).length)} email templates ready</strong>
      </div>
    </div>
  `;
}

function renderTemplateCards(templates, brandName, logoUrl = "") {
  const normalizedTemplates = normalizeEmailTemplates(templates);

  return `
    <div class="template-tabs" aria-label="Email template types">
      ${normalizedTemplates
        .map(
          (template) => `
            <span>
              <strong>${escapeHtml(template.name)}</strong>
              <small>${escapeHtml(template.key.replaceAll("_", " "))}</small>
            </span>
          `,
        )
        .join("")}
    </div>
    <div class="template-gallery">
      ${normalizedTemplates
        .map((template, index) => renderTemplateCard(template, index, brandName, logoUrl))
        .join("")}
    </div>
  `;
}

function renderTemplateLogo(brandName, logoUrl = "") {
  if (logoUrl) {
    return `
      <span class="template-logo-frame">
        <img class="template-logo-image" src="${escapeHtml(logoUrl)}" alt="" />
      </span>
    `;
  }
  return `<span class="template-logo">${escapeHtml((brandName || "PA").slice(0, 2).toUpperCase())}</span>`;
}

function renderTemplateCard(template, index, brandName, logoUrl = "") {
  const accentColor = normalizePresetColor(template.accent_color);
  const saveLabel = templateSaveLabels[template.key] || `Save ${template.name}`;
  const sampleSubject = sampleTemplateText(template.subject, brandName);
  const sampleHeadline = sampleTemplateText(template.headline, brandName);
  const sampleBody = sampleTemplateText(template.body, brandName);
  const sampleButton = sampleTemplateText(template.button_label, brandName);
  const sampleFooter = sampleTemplateText(template.footer_text, brandName);
  const sampleSupportLabel = sampleTemplateText(template.support_label, brandName);
  const sampleSupportUrl = sampleTemplateText(template.support_url, brandName);

  return `
    <section class="template-card">
      <input name="email_templates.${index}.key" type="hidden" value="${escapeHtml(
        template.key,
      )}" />
      <input name="email_templates.${index}.name" type="hidden" value="${escapeHtml(
        template.name,
      )}" />
      <div class="template-editor">
        <div class="section-heading">
          <span class="eyebrow">Template</span>
          <h3>${escapeHtml(template.name)}</h3>
        </div>
        <div class="form-grid">
          <label class="field">
            <span>Subject</span>
            <input name="email_templates.${index}.subject" type="text" value="${escapeHtml(
              template.subject,
            )}" />
          </label>
          <label class="field">
            <span>Headline</span>
            <input name="email_templates.${index}.headline" type="text" value="${escapeHtml(
              template.headline,
            )}" />
          </label>
          <label class="field">
            <span>Body</span>
            <textarea name="email_templates.${index}.body" rows="4">${escapeHtml(
              template.body,
            )}</textarea>
          </label>
          <label class="field">
            <span>Footer note</span>
            <textarea name="email_templates.${index}.footer_text" rows="3">${escapeHtml(
              template.footer_text,
            )}</textarea>
          </label>
          <div class="form-grid two-columns">
            <label class="field">
              <span>Button label</span>
              <input name="email_templates.${index}.button_label" type="text" value="${escapeHtml(
                template.button_label,
              )}" />
            </label>
            <label class="field">
              <span>Support label</span>
              <input name="email_templates.${index}.support_label" type="text" value="${escapeHtml(
                template.support_label,
              )}" />
            </label>
          </div>
          <div class="form-grid two-columns">
            <label class="field">
              <span>Support URL</span>
              <input name="email_templates.${index}.support_url" type="text" value="${escapeHtml(
                template.support_url,
              )}" placeholder="mailto:support@example.com" />
            </label>
            <label class="field">
              <span>Accent color</span>
              ${renderColorPresetField({
                name: `email_templates.${index}.accent_color`,
                value: accentColor,
                label: `${template.name} accent color presets`,
              })}
            </label>
          </div>
          <div class="template-card-actions">
            <button
              class="secondary-action section-save"
              type="button"
              data-action="save-template"
              data-template-index="${index}"
              ${state.busy ? "disabled" : ""}
            >
              ${state.busy ? "Saving..." : escapeHtml(saveLabel)}
            </button>
          </div>
        </div>
      </div>
      <article class="template-preview" style="--template-color: ${escapeHtml(accentColor)}">
        <span class="template-subject">${escapeHtml(sampleSubject)}</span>
        <div class="template-mail">
          ${renderTemplateLogo(brandName, logoUrl)}
          <h4>${escapeHtml(sampleHeadline)}</h4>
          <p class="email-body-copy">${escapeHtml(sampleBody)}</p>
          <strong>${escapeHtml(sampleButton)}</strong>
          <footer class="email-preview-footer">
            <p class="email-safe-note">${escapeHtml(sampleFooter)}</p>
            <div class="email-contact-row">
              <span>Need help?</span>
              <a href="${escapeHtml(sampleSupportUrl || "#")}">${escapeHtml(sampleSupportLabel)}</a>
            </div>
          </footer>
        </div>
      </article>
    </section>
  `;
}

function renderAuth() {
  const login = state.authMode === "login";
  const resetStart = state.authMode === "reset-start";
  const resetConfirm = state.authMode === "reset-confirm";

  app.className = "auth-studio-shell";
  app.innerHTML = `
    <section class="auth-form-pane" aria-label="Dashboard authentication">
      ${brandMarkup(true)}
      <div class="auth-card">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Dashboard access</span>
          <h2>${login ? "Welcome back" : "Reset password"}</h2>
          <p>${
            login
              ? "Sign in to manage users, providers, templates, and analytics."
              : "Reset access with a one-time code sent to your dashboard email."
          }</p>
        </div>

        ${
          login
            ? `
              <form class="form-grid" data-form="login">
                <label class="field">
                  <span>Email address</span>
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
      </div>
    </section>
    <aside class="auth-visual-pane" aria-hidden="true">
      <div class="identity-card-visual">
        <span>${brandVisualMarkup(currentBrandName(), { compact: false })}</span>
        <div>
          <small>Users</small>
          <strong>Verified identities</strong>
        </div>
        <dl>
          <div><dt>Auth</dt><dd>PKCE</dd></div>
          <div><dt>Tokens</dt><dd>Rotating</dd></div>
          <div><dt>Email</dt><dd>OTP</dd></div>
          <div><dt>Admin</dt><dd>Protected</dd></div>
        </dl>
      </div>
      <div class="identity-strip-visual">
        <span>Hosted pages</span>
        <span>Public API</span>
        <span>Dashboard</span>
      </div>
    </aside>
  `;
}

function adminInviteToken() {
  const params = new URLSearchParams(window.location.search);
  return params.get("token") || "";
}

function renderAdminInviteAccept() {
  const token = adminInviteToken();
  app.className = "admin-invite-shell auth-screen";
  app.innerHTML = `
    ${brandMarkup(true)}
    <section class="auth-card admin-invite-card" aria-label="Set dashboard password">
      <div class="page-heading compact-heading">
        <h2>${state.adminInviteAccepted ? "Password set" : "Set admin password"}</h2>
        <p>${
          state.adminInviteAccepted
            ? "Your dashboard account is ready. Sign in with the password you just created."
            : "Create the password for your Passport Auth dashboard account."
        }</p>
      </div>
      ${
        state.adminInviteAccepted
          ? `
            ${renderMessage()}
            <div class="form-actions">
              <a class="primary-action" href="/" data-link>Go to sign in</a>
            </div>
          `
          : `
            <form class="form-grid" data-form="admin-invite-accept">
              <input name="token" type="hidden" value="${escapeHtml(token)}" />
              <label class="field">
                <span>Password</span>
                <input name="password" type="password" autocomplete="new-password" placeholder="Minimum 12 characters" required />
              </label>
              <label class="field">
                <span>Confirm password</span>
                <input name="confirm_password" type="password" autocomplete="new-password" placeholder="Repeat password" required />
              </label>
              ${renderError()}
              ${renderMessage()}
              <div class="form-actions">
                <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
                  ${state.busy ? "Saving..." : "Set password"}
                </button>
              </div>
            </form>
          `
      }
    </section>
  `;
}

function renderHostedAuthPage(path = currentPath()) {
  if (!setupComplete()) {
    renderHostedSetupRequired();
    return;
  }

  const context = hostedAuthContext();
  const needsAuthRequest = needsHostedAuthRequest(path, context);
  const missingContext = needsAuthRequest && !hasHostedAuthRequest();
  const validation =
    !missingContext && needsAuthRequest
      ? startHostedRequestValidation(path, context)
      : { status: "valid", error: "" };
  const title = {
    "/login": "Sign in",
    "/register": "Create account",
    "/verify": context.token ? "Complete sign in" : "Verify code",
    "/reset-password": "Reset password",
  }[path] || "Sign in";

  app.className = "hosted-auth-shell studio-shell";
  app.innerHTML = `
    <main class="hosted-auth-main">
      <div class="hosted-auth-brand">
        ${brandVisualMarkup(currentBrandName(), { compact: false })}
        <strong>${escapeHtml(currentBrandName())}</strong>
      </div>
      <section class="hosted-auth-card" aria-label="${escapeHtml(title)}">
        <div class="page-heading compact-heading">
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(hostedAuthSubtitle(path, Boolean(context.token)))}</p>
        </div>
        ${
          missingContext
            ? renderHostedMissingContext()
            : validation.status === "loading"
              ? renderHostedRequestChecking()
              : validation.status === "invalid"
                ? renderHostedInvalidRequest(validation.error)
                : renderHostedAuthContent(path, context)
        }
        ${renderError()}
        ${renderMessage()}
      </section>
    </main>
  `;

  if (path === "/verify" && context.token && !missingContext && validation.status === "valid") {
    startHostedMagicConsume(context);
  }
}

function renderHostedSetupRequired() {
  app.className = "hosted-auth-shell studio-shell";
  app.innerHTML = `
    <main class="hosted-auth-main">
      <div class="hosted-auth-brand">
        ${brandVisualMarkup(currentBrandName(), { compact: false })}
        <strong>${escapeHtml(currentBrandName())}</strong>
      </div>
      <section class="hosted-auth-card" aria-label="Passport Auth setup required">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Auth service unavailable</span>
          <h2>Setup required</h2>
          <p>
            Passport Auth has not been configured yet. Create the owner account and save
            the dashboard settings before using hosted auth pages.
          </p>
        </div>
        <a class="primary-action" href="/" data-link>Open setup</a>
      </section>
    </main>
  `;
}

function hostedAuthSubtitle(path, hasToken) {
  if (path === "/register") {
    return "Create a password account and return to the app with an authorization code.";
  }
  if (path === "/verify" && hasToken) {
    return "Use the secure link from your email to finish signing in.";
  }
  if (path === "/verify") {
    return "Enter the one-time passcode sent to your email.";
  }
  if (path === "/reset-password") {
    return "Use an email OTP to update your password.";
  }
  return "Choose a sign-in method and return to the app with an authorization code.";
}

function renderHostedMissingContext() {
  return `
    <div class="hosted-auth-note">
      <strong>Missing auth request</strong>
      <p>This page needs a redirect URL and PKCE challenge from the application.</p>
    </div>
  `;
}

function renderHostedRequestChecking() {
  return `
    <div class="hosted-auth-note">
      <strong>Checking auth request</strong>
      <p>Passport Auth is validating the redirect URL and PKCE challenge before continuing.</p>
    </div>
  `;
}

function renderHostedInvalidRequest(error) {
  return `
    <div class="hosted-auth-note danger">
      <strong>Invalid auth request</strong>
      <p>${escapeHtml(error || "The application sent a redirect URL that is not configured.")}</p>
      <p>Update the app integration or add the exact redirect URL in Passport Auth Settings.</p>
    </div>
  `;
}

function renderHostedAuthContent(path, context) {
  if (path === "/register") {
    return `
      <form class="form-grid" data-form="${state.hostedRegisterEmail ? "hosted-register-verify" : "hosted-register"}">
        ${state.hostedRegisterDevCode ? `<p class="dev-otp">Development OTP: ${escapeHtml(state.hostedRegisterDevCode)}</p>` : ""}
        ${
          state.hostedRegisterEmail
            ? ""
            : `
              <label class="field">
                <span>Name</span>
                <input name="name" type="text" autocomplete="name" placeholder="Jane Appleseed" required />
              </label>
            `
        }
        <label class="field">
          <span>Email</span>
          <input name="email" type="email" autocomplete="email" value="${escapeHtml(
            state.hostedRegisterEmail,
          )}" placeholder="you@example.com" required ${state.hostedRegisterEmail ? "readonly" : ""} />
        </label>
        ${
          state.hostedRegisterEmail
            ? `
              <label class="field">
                <span>OTP</span>
                <input name="otp" type="text" inputmode="numeric" placeholder="123456" required />
              </label>
            `
            : `
              <label class="field">
                <span>Password</span>
                <input name="password" type="password" autocomplete="new-password" placeholder="Minimum 12 characters" minlength="12" required />
              </label>
            `
        }
        <div class="form-actions">
          <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
            ${state.busy ? "Working..." : state.hostedRegisterEmail ? "Verify email" : "Create account"}
          </button>
          <a class="text-action" href="${hostedLink("/login")}" data-link>Sign in</a>
        </div>
      </form>
    `;
  }

  if (path === "/verify" && context.token) {
    return `
      <div class="hosted-auth-note">
        <strong>Completing sign in</strong>
        <p>Verifying your magic link and returning to your application.</p>
      </div>
    `;
  }

  if (path === "/verify") {
    return `
      <form class="form-grid" data-form="${state.hostedOtpEmail ? "hosted-otp-verify" : "hosted-otp-start"}">
        ${state.hostedOtpDevCode ? `<p class="dev-otp">Development OTP: ${escapeHtml(state.hostedOtpDevCode)}</p>` : ""}
        <label class="field">
          <span>Email</span>
          <input name="email" type="email" autocomplete="email" value="${escapeHtml(
            state.hostedOtpEmail,
          )}" placeholder="you@example.com" required ${state.hostedOtpEmail ? "readonly" : ""} />
        </label>
        ${
          state.hostedOtpEmail
            ? `
              <label class="field">
                <span>OTP</span>
                <input name="otp" type="text" inputmode="numeric" placeholder="123456" required />
              </label>
            `
            : ""
        }
        <div class="form-actions">
          <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
            ${state.busy ? "Working..." : state.hostedOtpEmail ? "Verify code" : "Send code"}
          </button>
          <a class="text-action" href="${hostedLink("/login")}" data-link>Back to sign in</a>
        </div>
      </form>
    `;
  }

  if (path === "/reset-password") {
    return `
      <form class="form-grid" data-form="${state.hostedResetEmail ? "hosted-reset-confirm" : "hosted-reset-start"}">
        ${state.hostedResetDevCode ? `<p class="dev-otp">Development OTP: ${escapeHtml(state.hostedResetDevCode)}</p>` : ""}
        <label class="field">
          <span>Email</span>
          <input name="email" type="email" autocomplete="email" value="${escapeHtml(
            state.hostedResetEmail,
          )}" placeholder="you@example.com" required ${state.hostedResetEmail ? "readonly" : ""} />
        </label>
        ${
          state.hostedResetEmail
            ? `
              <label class="field">
                <span>OTP</span>
                <input name="otp" type="text" inputmode="numeric" placeholder="123456" required />
              </label>
              <label class="field">
                <span>New password</span>
                <input name="password" type="password" autocomplete="new-password" placeholder="Minimum 12 characters" minlength="12" required />
              </label>
            `
            : ""
        }
        <div class="form-actions">
          <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
            ${state.busy ? "Working..." : state.hostedResetEmail ? "Update password" : "Send reset code"}
          </button>
          <a class="text-action" href="${hostedLink("/login")}" data-link>Back to sign in</a>
        </div>
      </form>
    `;
  }

  return `
    <form class="form-grid" data-form="hosted-login">
      <label class="field">
        <span>Email</span>
        <input name="email" type="email" autocomplete="email" placeholder="you@example.com" required />
      </label>
      <label class="field">
        <span>Password</span>
        <input name="password" type="password" autocomplete="current-password" required />
      </label>
      <div class="form-actions">
        <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
          ${state.busy ? "Signing in..." : "Sign in"}
        </button>
        <button class="secondary-action" type="button" data-action="hosted-google-start" ${state.busy ? "disabled" : ""}>
          Google
        </button>
      </div>
      <div class="hosted-auth-links">
        <a href="${hostedLink("/register")}" data-link>Create account</a>
        <a href="${hostedLink("/verify")}" data-link>Use OTP</a>
        <button type="button" data-action="hosted-magic-start">Email magic link</button>
        <a href="${hostedLink("/reset-password")}" data-link>Reset password</a>
      </div>
      ${state.hostedMagicDevLink ? `<p class="dev-otp">Development magic link: ${escapeHtml(state.hostedMagicDevLink)}</p>` : ""}
    </form>
  `;
}

function dashboardMetrics() {
  const settings = state.settings || {};
  const enabledMethods = Object.keys(authMethodLabels).filter((key) => settings[key]);
  const domainCount = [
    settings.app_domain,
    settings.auth_domain,
    ...(settings.allowed_origins || []),
    ...(settings.redirect_urls || []),
  ].filter(Boolean).length;
  const blockedUsers = state.users.filter((user) => user.is_blocked).length;

  return [
    { label: "Domains", value: String(domainCount), detail: "Origins and redirects" },
    { label: "Users", value: String(state.usersTotal || state.users.length), detail: "Public accounts" },
    { label: "Blocked users", value: String(blockedUsers), detail: "Support review" },
    { label: "Methods", value: String(enabledMethods.length), detail: "Enabled auth" },
  ];
}

function renderDashboardEvents(settings = {}, users = []) {
  const blockedUsers = users.filter((user) => user.is_blocked).length;
  const redirectCount = (settings.redirect_urls || []).length;
  const enabledMethods = Object.keys(authMethodLabels)
    .filter((key) => settings[key])
    .map((key) => authMethodLabels[key]);
  const events = [
    {
      title: "Email delivery",
      value: settings.resend_configured ? "Configured" : "Not configured",
      detail: settings.resend_configured
        ? "Resend can deliver OTP, magic link, and reset templates."
        : "OTP, magic link, and reset emails need Resend before production use.",
    },
    {
      title: "Blocked users",
      value: `${blockedUsers}`,
      detail: blockedUsers
        ? "Blocked accounts cannot sign in, refresh, or access /me."
        : "No customer accounts are blocked right now.",
    },
    {
      title: "Redirect policy",
      value: `${redirectCount} allowed`,
      detail: redirectCount
        ? "Hosted auth requests must use one of the configured callback URLs."
        : "Add redirect URLs before accepting production sign-ins.",
    },
    {
      title: "Enabled methods",
      value: enabledMethods.length ? enabledMethods.join(", ") : "None",
      detail: enabledMethods.length
        ? "Hosted pages expose only the methods enabled here."
        : "Enable at least one sign-in method from Settings.",
    },
  ];

  return `
    <section class="overview-card dashboard-events" aria-label="Important events">
      <div class="panel-heading">
        <span class="eyebrow">Important events</span>
        <h3>Operations</h3>
      </div>
      <div class="event-list">
        ${events
          .map(
            (event) => `
              <article class="event-row">
                <div>
                  <strong>${escapeHtml(event.title)}</strong>
                  <small>${escapeHtml(event.detail)}</small>
                </div>
                <span>${escapeHtml(event.value)}</span>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderDashboard() {
  if (state.token && !state.usersLoaded && !state.usersLoading) {
    void loadUsers({ quiet: true }).then(() => {
      if (currentPath() === "/") {
        render();
      }
    });
  }

  const settings = state.settings || {};
  const visibleMetrics = dashboardMetrics();
  const brandName = currentBrandName();
  const authSurface = ensureOrigin(settings.auth_domain || settings.app_domain) || "No auth domain";

  renderAppShell(`
    <div class="hero dashboard-command">
      <div class="page-heading compact-heading">
        <span class="eyebrow">Dashboard</span>
        <h2>Auth control plane</h2>
        <p>Hosted pages, public APIs, dashboard controls, and service keys behind one web service.</p>
      </div>
      <div class="overview-card control-overview">
        <div class="panel-heading">
          <span class="eyebrow">Control surface</span>
          <h3>${escapeHtml(brandName)}</h3>
        </div>
        <p>${escapeHtml(authSurface)}</p>
        <a class="secondary-action" href="/settings" data-link>Edit settings</a>
      </div>
    </div>
    <div class="metric-grid signal-grid" aria-label="Auth readiness">
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
    ${renderDashboardEvents(settings, state.users)}
  `);
}

function emptyAnalyticsSummary() {
  return {
    enabled: false,
    reason: "Analytics are only recorded in production with ClickHouse enabled.",
    overview: {
      dau: 0,
      wau: 0,
      mau: 0,
      signups: 0,
      logins: 0,
      login_success_rate: 0,
      failures: 0,
      refreshes: 0,
      active_users: 0,
    },
    retention: [
      { label: "Week 1", value: 0 },
      { label: "Week 2", value: 0 },
      { label: "Week 3", value: 0 },
      { label: "Week 4", value: 0 },
    ],
    methods: [],
    recent_events: [],
  };
}

function renderAnalytics() {
  if (!state.analyticsLoaded && !state.analyticsLoading) {
    void loadAnalytics();
  }

  const summary = state.analytics || emptyAnalyticsSummary();
  const overview = summary.overview || emptyAnalyticsSummary().overview;
  const retention = summary.retention?.length ? summary.retention : emptyAnalyticsSummary().retention;
  const methods = summary.methods || [];
  const recentEvents = summary.recent_events || [];
  const maxMethodCount = Math.max(1, ...methods.map((method) => Number(method.count || 0)));
  const inactiveMessage = state.analyticsLoading
    ? "Loading analytics from the dashboard API."
    : summary.reason || "Analytics are waiting for production ClickHouse events.";

  const overviewMetrics = [
    { label: "DAU", value: overview.dau, detail: "Distinct users today" },
    { label: "MAU", value: overview.mau, detail: "Distinct users in 30 days" },
    { label: "Signups", value: overview.signups, detail: "Last 30 days" },
    { label: "Logins", value: overview.logins, detail: "Successful attempts" },
    {
      label: "Login success rate",
      value: formatPercent(overview.login_success_rate),
      detail: "Success vs failures",
    },
    { label: "Refreshes", value: overview.refreshes, detail: "Token rotations" },
    { label: "Failures", value: overview.failures, detail: "Public auth errors" },
    { label: "Active users", value: overview.active_users, detail: "Any auth activity" },
  ];

  renderAppShell(`
    <div class="hero analytics-hero">
      <div class="page-heading compact-heading">
        <span class="eyebrow">Dashboard</span>
        <h2>Analytics</h2>
        <p>Track public auth events, sign-in health, user activity, and retention from production ClickHouse events.</p>
      </div>
      <div class="overview-card analytics-status-card">
        <div class="panel-heading">
          <span class="eyebrow">Pipeline</span>
          <h3>${summary.enabled ? "ClickHouse live" : "Analytics inactive"}</h3>
        </div>
        <p>${escapeHtml(inactiveMessage)}</p>
      </div>
    </div>
    ${state.analyticsError ? `<p class="form-error">${escapeHtml(state.analyticsError)}</p>` : ""}
    <div class="metric-grid analytics-grid" aria-label="Analytics overview">
      ${overviewMetrics
        .map(
          (metric) => `
            <div class="metric">
              <span>${escapeHtml(metric.label)}</span>
              <strong>${escapeHtml(String(metric.value))}</strong>
              <small>${escapeHtml(metric.detail)}</small>
            </div>
          `,
        )
        .join("")}
    </div>
    <section class="overview-card retention-panel">
      <div class="panel-heading">
        <span class="eyebrow">Retention</span>
        <h3>Cohort return rate</h3>
      </div>
      <div class="retention-grid">
        ${retention
          .map(
            (item) => `
              <article class="retention-card">
                <span>${escapeHtml(item.label)} retention</span>
                <strong>${escapeHtml(formatPercent(item.value))}</strong>
                <div class="retention-track">
                  <span style="width: ${Math.max(0, Math.min(100, Number(item.value || 0)))}%"></span>
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
    <div class="analytics-columns">
      <section class="overview-card">
        <div class="panel-heading">
          <span class="eyebrow">Methods</span>
          <h3>Auth method usage</h3>
        </div>
        <div class="method-list">
          ${
            methods.length
              ? methods
                  .map(
                    (method) => `
                      <article class="method-row">
                        <div class="method-bar">
                          <span style="width: ${(Number(method.count || 0) / maxMethodCount) * 100}%"></span>
                        </div>
                        <strong>${escapeHtml(formatAuthMethod(method.method))}</strong>
                        <small>${escapeHtml(formatMetricNumber(method.count))}</small>
                      </article>
                    `,
                  )
                  .join("")
              : `<p class="muted-copy">No production sign-in events have been recorded yet.</p>`
          }
        </div>
      </section>
      <section class="overview-card">
        <div class="panel-heading">
          <span class="eyebrow">Events</span>
          <h3>Recent auth activity</h3>
        </div>
        <div class="event-list analytics-event-list">
          ${
            recentEvents.length
              ? recentEvents
                  .map(
                    (event) => `
                      <article class="event-row analytics-event-row">
                        <div>
                          <strong>${escapeHtml(humanizeAnalyticsEvent(event.event_type))}</strong>
                          <small>${escapeHtml(formatAuthMethod(event.auth_method))} · ${escapeHtml(event.email || "No email")} · ${escapeHtml(formatUserDate(event.occurred_at))}</small>
                          ${event.reason ? `<small>${escapeHtml(event.reason)}</small>` : ""}
                        </div>
                        <span>${escapeHtml(event.status || "event")}</span>
                      </article>
                    `,
                  )
                  .join("")
              : `<p class="muted-copy">No recent production auth events are available.</p>`
          }
        </div>
      </section>
    </div>
  `);
}

function renderPlaceholder(title, body) {
  renderAppShell(`
    <div class="placeholder-view">
      <div class="page-heading compact-heading">
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

function renderUsers() {
  if (!state.usersLoaded && !state.usersLoading) {
    void loadUsers();
  }

  renderAppShell(`
    <div class="users-route">
      <header class="settings-intro">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Dashboard</span>
          <h2>Users</h2>
          <p>Search, review, update, and deactivate application users. Metadata is custom JSON for app-specific fields like plans and subscriptions.</p>
        </div>
        <div class="settings-state">
          <span class="eyebrow">Directory</span>
          <strong>${escapeHtml(String(state.usersTotal))} users</strong>
          <small>${state.usersLoading ? "Refreshing users" : "Public auth users"}</small>
        </div>
      </header>

      <section class="users-table-panel" aria-label="Application users">
        <form class="users-search" data-form="users-search">
          <label class="field">
            <span>Search users</span>
            <input name="query" type="search" value="${escapeHtml(
              state.usersQuery,
            )}" placeholder="Name, email, role, or blocked message" />
          </label>
          <button class="secondary-action" type="submit" ${state.usersLoading ? "disabled" : ""}>
            ${state.usersLoading ? "Searching..." : "Search"}
          </button>
        </form>
        <div class="users-table" role="table" aria-label="Public auth users">
          <div class="users-table-head" role="row">
            <span>User</span>
            <span>Role</span>
            <span>Status</span>
            <span>Created</span>
            <span>Last login</span>
            <span>Method</span>
            <span>Edit</span>
          </div>
          ${renderUserRows()}
        </div>
      </section>

      ${renderError()}
      ${renderMessage()}
      ${renderUserEditDialog()}
    </div>
  `);
}

function renderUserRows() {
  if (state.usersLoading && !state.users.length) {
    return `<p class="form-message">Loading users.</p>`;
  }
  if (!state.users.length) {
    return `<p class="form-message">No users found.</p>`;
  }

  return state.users
    .map((user) => {
      const status = userStatus(user);
      return `
        <div class="user-row" role="row">
          <span class="user-identity-cell" role="cell">
            <span class="profile-avatar" aria-hidden="true">${escapeHtml(initialsFromUser(user))}</span>
            <span class="user-row-main">
              <strong>${escapeHtml(user.name || "Unnamed user")}</strong>
              <small>${escapeHtml(user.email)}</small>
            </span>
          </span>
          <span class="role-chip" role="cell">${escapeHtml(formatUserRole(user.role))}</span>
          <span class="status-chip ${status.className}" role="cell">
            ${status.label}
          </span>
          <span class="user-data-cell" role="cell">${escapeHtml(formatUserDate(user.created_at))}</span>
          <span class="user-data-cell" role="cell">${escapeHtml(formatUserDate(user.last_login_at))}</span>
          <span class="user-data-cell" role="cell">${escapeHtml(formatAuthMethod(user.last_auth_method || user.first_auth_method))}</span>
          <span class="user-action-cell" role="cell">
            <button
              class="icon-action user-edit-button"
              type="button"
              data-action="edit-user"
              data-user-id="${escapeHtml(user.id)}"
              aria-label="Edit ${escapeHtml(user.email)}"
              title="Edit user"
            >
              ${renderPencilIcon()}
            </button>
          </span>
        </div>
      `;
    })
    .join("");
}

function userStatus(user) {
  if (user.is_blocked) {
    return { className: "blocked", label: "Blocked" };
  }
  if (!user.is_active) {
    return { className: "inactive", label: "Inactive" };
  }
  return { className: "active", label: "Active" };
}

function renderUserEditDialog() {
  const user = editingUser();
  if (!user) {
    return "";
  }

  const metadata = stringifyMetadata(user.user_metadata);
  return `
    <div class="dialog-backdrop" role="presentation">
      <section
        class="user-edit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-edit-title"
      >
        <div class="dialog-header">
          <div class="dialog-title-group">
            <span class="profile-avatar" aria-hidden="true">${escapeHtml(initialsFromUser(user))}</span>
            <div>
              <span class="eyebrow">Edit user</span>
              <h3 id="user-edit-title">${escapeHtml(user.name || user.email)}</h3>
              <p>${escapeHtml(user.email)}</p>
            </div>
          </div>
          <button class="icon-action dialog-close" type="button" data-action="close-user-dialog" aria-label="Close user editor">
            Close
          </button>
        </div>
        <form class="user-editor" data-form="user-update" data-user-id="${escapeHtml(user.id)}">
          <div class="user-activity-grid" aria-label="User activity">
            <div>
              <span>Created</span>
              <strong>${escapeHtml(formatUserDate(user.created_at))}</strong>
            </div>
            <div>
              <span>First method</span>
              <strong>${escapeHtml(formatAuthMethod(user.first_auth_method))}</strong>
            </div>
            <div>
              <span>Last login</span>
              <strong>${escapeHtml(formatUserDate(user.last_login_at))}</strong>
            </div>
            <div>
              <span>Last method</span>
              <strong>${escapeHtml(formatAuthMethod(user.last_auth_method))}</strong>
            </div>
            <div>
              <span>Login count</span>
              <strong>${escapeHtml(String(user.login_count || 0))}</strong>
            </div>
          </div>
          <div class="form-grid two-columns">
            <label class="field">
              <span>Name</span>
              <input name="name" type="text" value="${escapeHtml(user.name)}" placeholder="Jane Appleseed" />
            </label>
            <label class="field">
              <span>Email</span>
              <input name="email" type="email" value="${escapeHtml(user.email)}" />
            </label>
            <label class="field">
              <span>Role</span>
              ${renderRoleSelect(user.role)}
            </label>
            <div class="user-flags" aria-label="User status">
              <label class="toggle-row compact">
                <input name="is_active" type="checkbox" ${user.is_active ? "checked" : ""} />
                <span class="toggle-control" aria-hidden="true"></span>
                <span>Active</span>
              </label>
              <label class="toggle-row compact">
                <input name="email_verified" type="checkbox" ${user.email_verified ? "checked" : ""} />
                <span class="toggle-control" aria-hidden="true"></span>
                <span>Email verified</span>
              </label>
              <label class="toggle-row compact">
                <input name="is_blocked" type="checkbox" ${user.is_blocked ? "checked" : ""} />
                <span class="toggle-control" aria-hidden="true"></span>
                <span>Blocked</span>
              </label>
            </div>
            <label class="field full-span">
              <span>Blocked message</span>
              <textarea name="blocked_message" rows="3" placeholder="${escapeHtml(defaultBlockedMessage)}">${escapeHtml(
                user.blocked_message || "",
              )}</textarea>
            </label>
            <label class="field full-span">
              <span>Metadata JSON</span>
              <textarea name="user_metadata" rows="9" spellcheck="false" placeholder='{"plan":"pro"}'>${escapeHtml(
                metadata,
              )}</textarea>
            </label>
          </div>
          <div class="user-editor-actions">
            <button class="secondary-action danger-action" type="button" data-action="delete-user" data-user-id="${escapeHtml(
              user.id,
            )}" ${state.busy ? "disabled" : ""}>
              Delete user
            </button>
            <span class="dialog-action-spacer" aria-hidden="true"></span>
            <button class="secondary-action" type="button" data-action="close-user-dialog" ${state.busy ? "disabled" : ""}>
              Cancel
            </button>
            <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
              ${state.busy ? "Saving..." : "Save user"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderAdmins() {
  if (!state.adminsLoaded && !state.adminsLoading) {
    void loadAdmins();
  }

  renderAppShell(`
    <div class="admins-route">
      <header class="settings-intro">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Dashboard</span>
          <h2>Admins</h2>
          <p>Invite operators who can sign into this Passport Auth dashboard. Invited admins receive a secure link to set their password.</p>
        </div>
        <div class="settings-state">
          <span class="eyebrow">Admin access</span>
          <strong>${escapeHtml(String(state.adminsTotal))} accounts</strong>
          <small>${state.adminsLoading ? "Refreshing admins" : "Dashboard operators"}</small>
        </div>
      </header>

      <section class="admins-table-panel" aria-label="Dashboard admin users">
        <form class="admin-invite-form" data-form="admin-invite">
          <label class="field">
            <span>Invite email</span>
            <input name="email" type="email" placeholder="admin@example.com" required />
          </label>
          <label class="field">
            <span>Role</span>
            <select name="role">
              <option value="admin">Admin</option>
            </select>
          </label>
          <button class="primary-action" type="submit" ${state.busy ? "disabled" : ""}>
            ${state.busy ? "Sending..." : "Send invite"}
          </button>
        </form>
        ${
          state.adminInviteDevLink
            ? `<p class="dev-otp">Development invite link: ${escapeHtml(state.adminInviteDevLink)}</p>`
            : ""
        }
        <div class="admins-table" role="table" aria-label="Dashboard admins">
          <div class="admins-table-head" role="row">
            <span>Account</span>
            <span>Role</span>
            <span>Status</span>
          </div>
          ${renderAdminRows()}
        </div>
      </section>

      ${renderError()}
      ${renderMessage()}
    </div>
  `);
}

function renderAdminRows() {
  if (state.adminsLoading && !state.admins.length) {
    return `<p class="form-message">Loading admins.</p>`;
  }
  if (!state.admins.length) {
    return `<p class="form-message">No dashboard admins found.</p>`;
  }

  return state.admins
    .map(
      (admin) => `
        <div class="admin-row" role="row">
          <span class="user-identity-cell" role="cell">
            <span class="profile-avatar" aria-hidden="true">${escapeHtml(
              admin.email.slice(0, 2).toUpperCase(),
            )}</span>
            <span class="user-row-main">
              <strong>${escapeHtml(admin.email)}</strong>
              <small>Dashboard sign-in</small>
            </span>
          </span>
          <span class="role-chip" role="cell">${escapeHtml(formatDashboardRole(admin.role))}</span>
          <span class="status-chip ${admin.invite_status === "accepted" ? "active" : "inactive"}" role="cell">
            ${escapeHtml(formatInviteStatus(admin.invite_status))}
          </span>
        </div>
      `,
    )
    .join("");
}

function renderSettings() {
  if (!state.settings && !state.settingsLoading) {
    void loadSettings();
  }

  if (!state.settings) {
    renderAppShell(`
      <div class="placeholder-view">
        <div class="page-heading compact-heading">
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
    <form class="settings-route settings-matrix" data-form="settings">
      <header class="settings-intro">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Dashboard</span>
          <h2>Settings</h2>
          <p>Configure domains, redirect URLs, Resend, Google OAuth, branding, and auth methods.</p>
        </div>
        <div class="settings-state">
          <span class="eyebrow">Control surface</span>
          <strong>${escapeHtml(settings.brand_name || "Passport Auth")}</strong>
          <small>${escapeHtml(settings.auth_domain || "Auth domain pending")}</small>
        </div>
      </header>

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
          ${renderSectionSave("URLs")}
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
          ${renderSectionSave("Resend")}
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
        ${renderSectionSave("Google")}
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
            ${renderColorPresetField({
              name: "primary_color",
              value: settings.primary_color,
              label: "Primary color presets",
            })}
          </label>
          ${renderLogoUploadField({
            label: "Primary logo",
            name: "logo_file",
            hiddenName: "logo_url",
            currentUrl: settings.logo_url,
            fallbackText: settings.brand_name,
            note: "Used in email templates, hosted pages, and larger brand surfaces.",
          })}
          ${renderLogoUploadField({
            label: "Compact mark",
            name: "mark_file",
            hiddenName: "mark_url",
            currentUrl: settings.mark_url || settings.logo_url,
            fallbackText: settings.brand_name,
            note: "Used in the sidebar, profile chrome, and tight layouts.",
          })}
          ${renderSectionSave("branding")}
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
        ${renderSectionSave("methods")}
      </section>

      ${renderError()}
      ${renderMessage()}
    </form>
  `);
}

function renderTemplates() {
  if (!state.settings && !state.settingsLoading) {
    void loadSettings();
  }

  if (!state.settings) {
    renderAppShell(`
      <div class="placeholder-view">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Dashboard</span>
          <h2>Templates</h2>
          <p>Loading email templates.</p>
        </div>
      </div>
    `);
    return;
  }

  const settings = state.settings;
  const templates = normalizeEmailTemplates(settings.email_templates);

  renderAppShell(`
    <form class="templates-route">
      <header class="settings-intro">
        <div class="page-heading compact-heading">
          <span class="eyebrow">Dashboard</span>
          <h2>Templates</h2>
          <p>Customize the HTML email copy for magic links, OTPs, and password resets.</p>
        </div>
        <div class="settings-state">
          <span class="eyebrow">Saved set</span>
          <strong>${escapeHtml(templates.length)} templates</strong>
          <small>Placeholders: {{brand_name}}, {{code}}, {{magic_link}}, {{invite_link}}</small>
        </div>
      </header>

      ${renderTemplateCards(
        templates,
        settings.brand_name || "Passport Auth",
        settings.logo_url || settings.mark_url,
      )}

      ${renderError()}
      ${renderMessage()}
    </form>
  `);
}

function renderSectionSave(label) {
  return `
    <div class="section-actions">
      <button class="secondary-action section-save" type="button" data-action="save-settings" ${
        state.busy ? "disabled" : ""
      }>
        ${state.busy ? "Saving..." : `Save ${label}`}
      </button>
    </div>
  `;
}

function renderError() {
  return state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : "";
}

function renderMessage() {
  return state.message ? `<p class="form-message">${escapeHtml(state.message)}</p>` : "";
}

function renderBootScreen() {
  const name = currentBrandName();
  app.className = "boot-screen";
  app.innerHTML = `
    <section class="loading-panel" aria-label="Loading dashboard">
      <div class="loading-wordmark">
        ${brandVisualMarkup(currentBrandName(), { compact: false })}
        <strong>${escapeHtml(name)}</strong>
      </div>
      <div class="loading-copy">
        <span class="eyebrow">Dashboard</span>
        <p>Preparing control plane</p>
      </div>
      <div class="loading-track" aria-hidden="true">
        <span></span>
      </div>
    </section>
  `;
}

function render() {
  if (!state.setup) {
    renderBootScreen();
    return;
  }

  const path = currentPath();
  const done = setupComplete();

  if (path === "/admin-invite") {
    renderAdminInviteAccept();
    return;
  }

  if (isHostedAuthPath(path)) {
    renderHostedAuthPage(path);
    return;
  }

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
    renderUsers();
    return;
  }

  if (path === "/admins") {
    renderAdmins();
    return;
  }

  if (path === "/settings") {
    renderSettings();
    return;
  }

  if (path === "/templates") {
    renderTemplates();
    return;
  }

  if (path === "/analytics") {
    renderAnalytics();
    return;
  }

  renderDashboard();
}

function syncOnboardingFromForm(form) {
  const formData = new FormData(form);
  const fields = [
    "ownerEmail",
    "password",
    "confirmPassword",
    "app_domain",
    "auth_domain",
    "allowed_origins",
    "redirect_urls",
    "resend_from_email",
    "resend_api_key",
    "google_client_id",
    "google_client_secret",
    "brand_name",
    "primary_color",
    "logo_url",
    "mark_url",
  ];

  for (const field of fields) {
    if (formData.has(field)) {
      state.onboarding[field] = String(formData.get(field) || "").trim();
    }
  }

  for (const method of Object.keys(authMethodLabels)) {
    if (state.onboardingStep === 3) {
      state.onboarding[method] = checkboxValue(formData, method);
    }
  }

  if (formData.has("email_templates.0.key")) {
    state.onboarding.email_templates = readEmailTemplatesFromForm(form);
  }

  rememberOnboardingLogo(formData, "logo_file", "primary");
  rememberOnboardingLogo(formData, "mark_file", "mark");
}

function validateOnboardingStep(stepIndex) {
  const data = state.onboarding;

  if (stepIndex === 1) {
    if (!data.ownerEmail || !data.ownerEmail.includes("@")) {
      return "Enter a valid owner email.";
    }
    if (data.password.length < 12) {
      return "Password must be at least 12 characters.";
    }
    if (data.password !== data.confirmPassword) {
      return "Passwords do not match.";
    }
  }

  if (stepIndex === 3) {
    const hasMethod = Object.keys(authMethodLabels).some((key) => state.onboarding[key]);
    if (!hasMethod) {
      return "Enable at least one auth method.";
    }
  }

  if (stepIndex === 6 && !data.ownerEmail) {
    return "Owner account details are required before launch.";
  }

  return "";
}

function buildSettingsPayload() {
  const data = state.onboarding;
  const payload = {
    app_domain: data.app_domain,
    auth_domain: data.auth_domain,
    allowed_origins: linesToList(data.allowed_origins),
    redirect_urls: linesToList(data.redirect_urls),
    resend_from_email: data.resend_from_email,
    google_client_id: data.google_client_id,
    brand_name: data.brand_name || "Passport Auth",
    primary_color: normalizePresetColor(data.primary_color),
    logo_url: data.logo_url || "",
    mark_url: data.mark_url || "",
    password_login_enabled: data.password_login_enabled,
    otp_login_enabled: data.otp_login_enabled,
    magic_link_enabled: data.magic_link_enabled,
    google_oauth_enabled: data.google_oauth_enabled,
    password_reset_otp_enabled: data.password_reset_otp_enabled,
    email_templates: normalizeEmailTemplates(data.email_templates),
  };

  if (data.resend_api_key) {
    payload.resend_api_key = data.resend_api_key;
  }
  if (data.google_client_secret) {
    payload.google_client_secret = data.google_client_secret;
  }

  return payload;
}

async function completeOnboarding() {
  state.busy = true;
  state.error = "";
  render();

  try {
    state.setup = await api("/api/v1/setup/owner", {
      method: "POST",
      body: JSON.stringify({
        email: state.onboarding.ownerEmail,
        password: state.onboarding.password,
      }),
      headers: {},
    });
    const login = await api("/api/v1/dashboard/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: state.onboarding.ownerEmail,
        password: state.onboarding.password,
      }),
      headers: {},
    });
    state.token = login.access_token;
    state.user = login.user;
    localStorage.setItem(TOKEN_KEY, state.token);
    const settingsPayload = buildSettingsPayload();
    await applyOnboardingLogoUploads(settingsPayload);
    state.settings = await api("/api/v1/dashboard/settings", {
      method: "PUT",
      body: JSON.stringify(settingsPayload),
    });
    state.branding = {
      brand_name: state.settings.brand_name,
      primary_color: state.settings.primary_color,
      logo_url: state.settings.logo_url,
      mark_url: state.settings.mark_url,
    };
    state.onboarding = { ...defaultOnboarding, email_templates: cloneEmailTemplates() };
    state.onboardingLogoFiles = { primary: null, mark: null };
    state.onboardingLogoPreviews = { primary: "", mark: "" };
    state.onboardingStep = 0;
    window.history.replaceState({}, "", "/");
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleOnboardingSubmit(form) {
  syncOnboardingFromForm(form);
  const validationError = validateOnboardingStep(state.onboardingStep);
  if (validationError) {
    state.error = validationError;
    render();
    return;
  }

  state.error = "";
  state.message = "";

  if (state.onboardingStep < onboardingSteps.length - 1) {
    state.onboardingStep += 1;
    render();
    return;
  }

  await completeOnboarding();
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

async function handleAdminInvite(form) {
  const formData = new FormData(form);
  const email = String(formData.get("email") || "").trim();
  const role = String(formData.get("role") || "admin").trim();

  state.busy = true;
  state.error = "";
  state.message = "";
  state.adminInviteDevLink = "";
  render();

  try {
    const invite = await api("/api/v1/dashboard/admins/invite", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
    state.adminInviteDevLink = invite.dev_invite_url || "";
    state.message = `Invite sent to ${invite.user?.email || email}.`;
    await loadAdmins({ quiet: true });
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleAdminInviteAccept(form) {
  const formData = new FormData(form);
  const token = String(formData.get("token") || "").trim();
  const password = String(formData.get("password") || "");
  const confirmPassword = String(formData.get("confirm_password") || "");

  if (!token) {
    state.error = "Admin invite token is missing.";
    render();
    return;
  }
  if (password.length < 12) {
    state.error = "Password must be at least 12 characters.";
    render();
    return;
  }
  if (password !== confirmPassword) {
    state.error = "Passwords do not match.";
    render();
    return;
  }

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    await publicApi("/api/v1/dashboard/admins/accept", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
    state.adminInviteAccepted = true;
    state.message = "Password set. You can sign in now.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

function hostedPayloadFromForm(form) {
  const formData = new FormData(form);
  const context = hostedAuthContext();
  return {
    name: String(formData.get("name") || "").trim(),
    email: String(formData.get("email") || "").trim(),
    password: String(formData.get("password") || ""),
    otp: String(formData.get("otp") || "").trim(),
    redirect_url: context.redirectUrl,
    code_challenge: context.codeChallenge,
  };
}

async function handleHostedPasswordLogin(form) {
  const payload = hostedPayloadFromForm(form);

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const authCode = await publicApi("/api/v1/auth/password/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    completeHostedAuth(authCode);
  } catch (error) {
    state.error = error.message;
    state.busy = false;
    render();
  }
}

async function handleHostedRegister(form) {
  const payload = hostedPayloadFromForm(form);

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const start = await publicApi("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.hostedRegisterEmail = payload.email;
    state.hostedRegisterDevCode = start.dev_otp || "";
    state.message = "Enter the code sent to your email.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleHostedRegisterVerify(form) {
  const payload = hostedPayloadFromForm(form);

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const authCode = await publicApi("/api/v1/auth/register/verify", {
      method: "POST",
      body: JSON.stringify({
        email: state.hostedRegisterEmail || payload.email,
        otp: payload.otp,
      }),
    });
    completeHostedAuth(authCode);
  } catch (error) {
    state.error = error.message;
    state.busy = false;
    render();
  }
}

async function handleHostedOtpStart(form) {
  const payload = hostedPayloadFromForm(form);

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const start = await publicApi("/api/v1/auth/otp/start", {
      method: "POST",
      body: JSON.stringify({
        email: payload.email,
        redirect_url: payload.redirect_url,
        code_challenge: payload.code_challenge,
      }),
    });
    state.hostedOtpEmail = payload.email;
    state.hostedOtpDevCode = start.dev_otp || "";
    state.message = "Enter the code sent to your email.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleHostedOtpVerify(form) {
  const payload = hostedPayloadFromForm(form);

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const authCode = await publicApi("/api/v1/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({
        email: state.hostedOtpEmail || payload.email,
        otp: payload.otp,
        redirect_url: payload.redirect_url,
        code_challenge: payload.code_challenge,
      }),
    });
    completeHostedAuth(authCode);
  } catch (error) {
    state.error = error.message;
    state.busy = false;
    render();
  }
}

async function handleHostedMagicStart(form) {
  const formData = new FormData(form);
  const email = String(formData.get("email") || "").trim();
  const context = hostedAuthContext();
  if (!email) {
    state.error = "Enter an email address first.";
    render();
    return;
  }

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const start = await publicApi("/api/v1/auth/magic-link/start", {
      method: "POST",
      body: JSON.stringify({
        email,
        redirect_url: context.redirectUrl,
        code_challenge: context.codeChallenge,
      }),
    });
    state.hostedMagicDevLink = start.dev_magic_link || "";
    state.message = "Check your email for the magic link.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleHostedMagicConsume(token = hostedAuthContext().token) {
  const context = hostedAuthContext();

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const authCode = await publicApi("/api/v1/auth/magic-link/consume", {
      method: "POST",
      body: JSON.stringify({ token: token || context.token }),
    });
    completeHostedAuth(authCode);
  } catch (error) {
    state.error = error.message;
    state.busy = false;
    render();
  }
}

async function handleHostedGoogleStart() {
  const context = hostedAuthContext();
  const query = new URLSearchParams({
    redirect_url: context.redirectUrl,
    code_challenge: context.codeChallenge,
  });

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const start = await publicApi(`/api/v1/auth/google/start?${query.toString()}`);
    window.location.href = start.authorization_url;
  } catch (error) {
    state.error = error.message;
    state.busy = false;
    render();
  }
}

async function handleHostedPasswordResetStart(form) {
  const formData = new FormData(form);
  const email = String(formData.get("email") || "").trim();

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const start = await publicApi("/api/v1/auth/password-reset/start", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    state.hostedResetEmail = email;
    state.hostedResetDevCode = start.dev_otp || "";
    state.message = "Enter the reset code sent to your email.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleHostedPasswordResetConfirm(form) {
  const formData = new FormData(form);
  const otp = String(formData.get("otp") || "").trim();
  const password = String(formData.get("password") || "");

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    await publicApi("/api/v1/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ email: state.hostedResetEmail, otp, password }),
    });
    state.hostedResetEmail = "";
    state.hostedResetDevCode = "";
    state.message = "Password updated. You can sign in now.";
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
    primary_color: normalizePresetColor(String(formData.get("primary_color") || "").trim()),
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
    await applySettingsLogoUploads(formData, payload);
    state.settings = await api("/api/v1/dashboard/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.branding = {
      brand_name: state.settings.brand_name,
      primary_color: state.settings.primary_color,
      logo_url: state.settings.logo_url,
      mark_url: state.settings.mark_url,
    };
    state.message = "Settings saved.";
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleTemplateSave(form, index) {
  const editedTemplate = readEmailTemplateFromForm(form, index);
  if (!editedTemplate) {
    state.error = "Select a template section to save.";
    render();
    return;
  }

  const currentTemplates = normalizeEmailTemplates(state.settings?.email_templates);
  const emailTemplates = currentTemplates.map((template, templateIndex) =>
    templateIndex === index ? editedTemplate : template,
  );
  const payload = { email_templates: emailTemplates };

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    state.settings = await api("/api/v1/dashboard/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.message = `${editedTemplate.name} saved.`;
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleUserSearch(form) {
  const formData = new FormData(form);
  const query = String(formData.get("query") || "").trim();
  state.error = "";
  state.message = "";
  await loadUsers({ query });
}

async function handleUserUpdate(form) {
  const userId = form.dataset.userId || state.selectedUserId;
  const formData = new FormData(form);
  let userMetadata = {};
  try {
    userMetadata = parseMetadata(formData.get("user_metadata"));
  } catch (error) {
    state.error = error.message;
    state.message = "";
    render();
    return;
  }

  await updateUser(
    userId,
    {
      name: String(formData.get("name") || "").trim(),
      email: String(formData.get("email") || "").trim(),
      role: String(formData.get("role") || "user").trim(),
      is_active: checkboxValue(formData, "is_active"),
      email_verified: checkboxValue(formData, "email_verified"),
      is_blocked: checkboxValue(formData, "is_blocked"),
      blocked_message: String(formData.get("blocked_message") || "").trim(),
      user_metadata: userMetadata,
    },
    "User saved.",
  );
}

async function updateUser(userId, payload, successMessage) {
  if (!userId) {
    state.error = "Select a user first.";
    render();
    return;
  }

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    const updatedUser = await api(`/api/v1/dashboard/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    state.users = state.users.map((user) => (user.id === updatedUser.id ? updatedUser : user));
    state.selectedUserId = updatedUser.id;
    state.editingUserId = "";
    state.message = successMessage;
    await loadUsers({ query: state.usersQuery, quiet: true });
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

async function handleUserDelete(userId) {
  if (!userId) {
    state.error = "Select a user first.";
    render();
    return;
  }

  const user = state.users.find((candidate) => candidate.id === userId);
  const label = user?.email || "this user";
  if (!window.confirm(`Delete ${label}? This cannot be undone.`)) {
    return;
  }

  state.busy = true;
  state.error = "";
  state.message = "";
  render();

  try {
    await api(`/api/v1/dashboard/users/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
    state.users = state.users.filter((candidate) => candidate.id !== userId);
    state.usersTotal = Math.max(0, state.usersTotal - 1);
    state.selectedUserId = state.users[0]?.id || "";
    state.editingUserId = "";
    state.message = "User deleted.";
    await loadUsers({ query: state.usersQuery, quiet: true });
  } catch (error) {
    state.error = error.message;
  } finally {
    state.busy = false;
    render();
  }
}

function syncColorField(colorField, value) {
  const color = normalizePresetColor(value);
  const valueInput = colorField?.querySelector("[data-color-value]");
  if (valueInput) {
    valueInput.value = color;
  }

  const templatePreview = colorField?.closest(".template-card")?.querySelector(".template-preview");
  if (templatePreview) {
    templatePreview.style.setProperty("--template-color", color);
  }

  const brandPreview = colorField?.closest("form")?.querySelector(".brand-preview");
  if (brandPreview && valueInput?.name === "primary_color") {
    brandPreview.style.setProperty("--preview-color", color);
  }

  colorField?.querySelectorAll("[data-color-preset]").forEach((preset) => {
    preset.classList.toggle("active", preset.dataset.colorPreset === color);
  });

  return color;
}

app.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  const formName = form.dataset.form;

  if (formName === "onboarding") {
    void handleOnboardingSubmit(form);
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
  if (formName === "admin-invite") {
    void handleAdminInvite(form);
  }
  if (formName === "admin-invite-accept") {
    void handleAdminInviteAccept(form);
  }
  if (formName === "hosted-login") {
    void handleHostedPasswordLogin(form);
  }
  if (formName === "hosted-register") {
    void handleHostedRegister(form);
  }
  if (formName === "hosted-register-verify") {
    void handleHostedRegisterVerify(form);
  }
  if (formName === "hosted-otp-start") {
    void handleHostedOtpStart(form);
  }
  if (formName === "hosted-otp-verify") {
    void handleHostedOtpVerify(form);
  }
  if (formName === "hosted-reset-start") {
    void handleHostedPasswordResetStart(form);
  }
  if (formName === "hosted-reset-confirm") {
    void handleHostedPasswordResetConfirm(form);
  }
  if (formName === "settings") {
    void handleSettingsSubmit(form);
  }
  if (formName === "users-search") {
    void handleUserSearch(form);
  }
  if (formName === "user-update") {
    void handleUserUpdate(form);
  }
});

app.addEventListener("click", (event) => {
  if (event.target.classList.contains("dialog-backdrop")) {
    state.editingUserId = "";
    state.error = "";
    render();
    return;
  }

  const colorPreset = event.target.closest("[data-color-preset]");
  if (colorPreset) {
    const colorField = colorPreset.closest(".color-field");
    syncColorField(colorField, colorPreset.dataset.colorPreset || defaultTemplateColor);
    return;
  }

  const link = event.target.closest("[data-link]");
  if (link) {
    event.preventDefault();
    navigate(link.getAttribute("href") || "/");
    return;
  }

  const actionButton = event.target.closest("[data-action]");
  const action = actionButton?.dataset.action;
  if (!action) {
    return;
  }

  if (action === "sign-out") {
    localStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
    state.settings = null;
    state.users = [];
    state.usersLoaded = false;
    state.selectedUserId = "";
    state.editingUserId = "";
    state.admins = [];
    state.adminsLoaded = false;
    state.adminInviteDevLink = "";
    state.adminInviteAccepted = false;
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
  if (action === "onboarding-back") {
    state.onboardingStep = Math.max(0, state.onboardingStep - 1);
    state.error = "";
    render();
  }
  if (action === "save-settings") {
    const form = event.target.closest("form");
    if (form) {
      void handleSettingsSubmit(form);
    }
  }
  if (action === "save-template") {
    const form = event.target.closest("form");
    const index = Number.parseInt(actionButton.dataset.templateIndex || "", 10);
    if (form && Number.isInteger(index)) {
      void handleTemplateSave(form, index);
    }
  }
  if (action === "edit-user") {
    state.editingUserId = actionButton.dataset.userId || "";
    state.error = "";
    state.message = "";
    render();
  }
  if (action === "close-user-dialog") {
    state.editingUserId = "";
    state.error = "";
    render();
  }
  if (action === "delete-user") {
    const userId = actionButton.dataset.userId || "";
    if (userId) {
      void handleUserDelete(userId);
    }
  }
  if (action === "hosted-google-start") {
    void handleHostedGoogleStart();
  }
  if (action === "hosted-magic-start") {
    const form = event.target.closest("form");
    if (form) {
      void handleHostedMagicStart(form);
    }
  }
  if (action === "hosted-magic-consume") {
    void handleHostedMagicConsume();
  }
});

window.addEventListener("popstate", () => render());

async function boot() {
  render();

  try {
    await loadSetupStatus();
    if (setupComplete()) {
      await loadBranding();
      renderBootScreen();
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
