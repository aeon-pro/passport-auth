from pathlib import Path

WEB_DIR = Path(__file__).parents[2] / "web"


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
    assert "2026-06-02-control-room" in index_html
    assert "shell-rail" in app_js
    assert "command-surface" in app_js
    assert "settings-matrix" in app_js
    assert "obsidian-grid" in styles_css
    assert "kinetic-line" in styles_css


def test_settings_sections_have_local_save_actions_and_centered_toggles() -> None:
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")

    assert "renderSectionSave" in app_js
    assert 'data-action="save-settings"' in app_js
    assert 'renderSectionSave("URLs")' in app_js
    assert "translateY(-50%)" in styles_css
    assert "translate(18px, -50%)" in styles_css
