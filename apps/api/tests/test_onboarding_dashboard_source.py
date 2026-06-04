import re
from pathlib import Path

WEB_DIR = Path(__file__).parents[2] / "web"


def css_rule_body(css: str, selector: str) -> str:
    match = re.search(
        rf"(?:^|\n){re.escape(selector)}\s*\{{(?P<body>.*?)\n\}}",
        css,
        re.DOTALL,
    )
    assert match is not None, f"Missing CSS rule for {selector}"
    return match.group("body")


def test_static_dashboard_contains_multi_step_onboarding() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "onboardingSteps" in app_js
    assert "renderOnboarding" in app_js
    assert "Complete setup" in app_js
    assert "onboarding-layout" in styles_css
    assert "step-rail" in styles_css


def test_static_dashboard_uses_obsidian_control_room_design() -> None:
    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "passport-auth-ui-version" in index_html
    assert "2026-06-05-loading-logo" in index_html
    assert "shell-rail" in app_js
    assert "command-surface" in app_js
    assert "settings-matrix" in app_js
    assert "obsidian-grid" in styles_css
    assert "kinetic-line" in styles_css


def test_static_dashboard_has_polished_loading_screen() -> None:
    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "renderBootScreen" in app_js
    assert "loading-panel" in index_html
    assert "loading-panel" in app_js
    assert "loading-track" in index_html
    assert "loading-track" in styles_css
    assert "loading-wordmark" in styles_css
    assert "brandVisualMarkup(currentBrandName(), { compact: false })" in app_js
    assert "await loadBranding();\n      renderBootScreen();" in app_js
    assert ".loading-wordmark .brand-logo" in styles_css
    assert "Loading Passport Auth" not in index_html
    assert "Loading Passport Auth" not in app_js


def test_dashboard_shell_does_not_show_environment_badge() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    assert "topbar-meta" not in app_js
    assert "Environment" not in app_js
    assert "<strong>Local</strong>" not in app_js


def test_dashboard_sidebar_owns_brand_and_profile_chrome() -> None:
    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "Single app auth" not in index_html
    assert "Single app auth" not in app_js
    assert "Setup complete" not in app_js
    assert "Owner setup required" not in app_js
    assert "status-pill" not in app_js
    assert "user-label" not in app_js
    assert "topbar-actions" not in app_js
    assert "renderSidebarProfile" in app_js
    assert "currentBrandName" in app_js
    assert "profile-menu" in app_js
    assert "profile-dropdown" in styles_css
    assert ".profile-summary > span:last-child" in styles_css


def test_dashboard_uses_uploaded_logos_across_brand_surfaces() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "logo_url" in app_js
    assert "mark_url" in app_js
    assert "uploadLogoAsset" in app_js
    assert "renderLogoUploadField" in app_js
    assert "brandVisualMarkup" in app_js
    assert "renderTemplateLogo" in app_js
    assert "logo_file" in app_js
    assert "mark_file" in app_js
    assert 'class="brand-logo"' in app_js
    assert 'class="template-logo-image"' in app_js
    assert "logo-upload-card" in styles_css
    assert "brand-logo" in styles_css
    assert "template-logo-image" in styles_css


def test_uploaded_brand_logo_keeps_transparency_in_sidebar() -> None:
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    brand_logo_body = css_rule_body(styles_css, ".brand-logo")
    assert "background: transparent;" in brand_logo_body
    assert "border: 0;" in brand_logo_body
    assert "padding: 0;" in brand_logo_body
    assert "#f4f4ee" not in brand_logo_body


def test_dashboard_sidebar_has_dashboard_route_and_simple_nav_states() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    nav_body = css_rule_body(styles_css, ".nav")
    nav_link_body = css_rule_body(styles_css, ".nav a")
    nav_state_body = css_rule_body(
        styles_css,
        ".nav a.active,\n.nav a:hover,\n.nav a:focus-visible",
    )

    assert '{ href: "/", label: "Dashboard" }' in app_js
    assert nav_body.index("gap: 8px;") >= 0
    assert "border: 0;" in nav_link_body
    assert "border-color" not in nav_state_body
    assert "rgba(255, 255, 255, 0.026)" in nav_state_body


def test_sidebar_profile_dropdown_stays_inside_sidebar() -> None:
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    dropdown_body = css_rule_body(styles_css, ".profile-dropdown")
    assert "width: 100%;" in dropdown_body
    assert "box-sizing: border-box;" in dropdown_body
    assert "overflow: hidden;" in dropdown_body


def test_settings_sections_have_local_save_actions_and_centered_toggles() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "renderSectionSave" in app_js
    assert 'data-action="save-settings"' in app_js
    assert 'renderSectionSave("URLs")' in app_js
    assert "translateY(-50%)" in styles_css
    assert "translate(18px, -50%)" in styles_css


def test_branding_settings_use_preset_color_box() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'type="color"' not in app_js
    assert "data-color-picker" not in app_js
    assert "renderColorPresetField" in app_js
    assert "color-preset-box" in styles_css
    assert "color-field" in styles_css


def test_template_color_picker_uses_native_presets_and_shared_theme() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "templateColorPresets" in app_js
    assert "renderColorPresetButtons" in app_js
    assert 'list="template-color-presets"' not in app_js
    assert 'id="template-color-presets"' not in app_js
    assert "data-color-preset" in app_js
    assert "closestPresetColor" in app_js
    assert "color-preset-grid" in styles_css
    assert "color-preset-swatch" in styles_css
    assert "--email-surface" in styles_css


def test_completed_setup_route_is_removed_from_signed_in_dashboard() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    assert '{ href: "/setup", label: "Setup" }' not in app_js
    assert "renderSetupComplete" not in app_js
    assert "Onboarding complete" not in app_js
    assert '{ href: "/templates", label: "Templates" }' in app_js


def test_dashboard_contains_email_templates_page() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "renderTemplates" in app_js
    assert "email_templates" in app_js
    assert "Magic link" in app_js
    assert "Password reset OTP" in app_js
    assert "template-preview" in styles_css
    assert "template-tabs" in styles_css


def test_email_template_cards_have_individual_save_actions() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'data-action="save-template"' in app_js
    assert "handleTemplateSave" in app_js
    assert "Save Magic link" in app_js
    assert "Save One-time passcode" in app_js
    assert "Save Password reset OTP" in app_js
    assert "Save templates" not in app_js
    assert "template-card-actions" in styles_css


def test_dashboard_email_template_previews_have_footer_and_contact_visuals() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "footer_text" in app_js
    assert "support_label" in app_js
    assert "support_url" in app_js
    assert "email-preview-footer" in app_js
    assert "email-safe-note" in styles_css
    assert "email-contact-row" in styles_css
    assert "text-align: center" in styles_css
