from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_dashboard_toggle_css_keeps_knobs_centered() -> None:
    css = (ROOT / "apps" / "web" / "styles.css").read_text(encoding="utf-8")

    assert "top: 50%;" in css
    assert "transform: translateY(-50%);" in css
    assert "transform: translate(16px, -50%);" in css


def test_onboarding_requires_real_sign_in_method() -> None:
    app_js = (ROOT / "apps" / "web" / "app.js").read_text(encoding="utf-8")

    assert "const signInMethodKeys = [" in app_js
    sign_in_keys_block = app_js.split("const signInMethodKeys = [", 1)[1].split("];", 1)[0]
    assert "password_reset_otp_enabled" not in sign_in_keys_block
    assert "const hasMethod = signInMethodKeys.some((key) => state.onboarding[key]);" in app_js


def test_dashboard_static_assets_have_cache_busted_ui_version() -> None:
    index_html = (ROOT / "apps" / "web" / "index.html").read_text(encoding="utf-8")

    assert "2026-06-26-toggle-ui" in index_html
