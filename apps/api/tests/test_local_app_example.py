from pathlib import Path

ROOT = Path(__file__).parents[3]
LOCAL_APP_DIR = ROOT / "examples" / "local-app"


def test_local_app_example_contains_hosted_auth_integration() -> None:
    app_js = (LOCAL_APP_DIR / "app.js").read_text(encoding="utf-8")
    server_js = (LOCAL_APP_DIR / "server.mjs").read_text(encoding="utf-8")
    readme = (LOCAL_APP_DIR / "README.md").read_text(encoding="utf-8")

    assert "http://localhost:5173" in readme
    assert "http://localhost:8000" in app_js
    assert "/login" in app_js
    assert "/register" in app_js
    assert "/verify" in app_js
    assert "/api/v1/auth/token" in app_js
    assert "/api/v1/auth/me" in app_js
    assert "/api/v1/auth/refresh" in app_js
    assert "/api/v1/auth/logout" in app_js
    assert "/api/v1/auth/google/start" in app_js
    assert "code_challenge" in app_js
    assert "code_verifier" in app_js
    assert 'pathname === "/auth/callback"' in server_js


def test_local_app_persists_pkce_for_magic_link_callbacks() -> None:
    app_js = (LOCAL_APP_DIR / "app.js").read_text(encoding="utf-8")

    assert "PKCE_VERIFIER_TTL_MS" in app_js
    assert "readStoredPkceVerifier" in app_js
    assert "clearStoredPkceVerifier" in app_js
    assert "localStorage.setItem(" in app_js
    assert "PKCE_VERIFIER_KEY," in app_js
    assert "sessionStorage.setItem(PKCE_VERIFIER_KEY" not in app_js
