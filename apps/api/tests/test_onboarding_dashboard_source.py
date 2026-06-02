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
