from urllib.parse import urlparse

LOCAL_DEVELOPMENT_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEVELOPMENT_ENVIRONMENTS = {"development", "local", "dev"}


def is_development_environment(app_env: str) -> bool:
    return app_env.strip().lower() in DEVELOPMENT_ENVIRONMENTS


def is_local_development_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    return parsed.scheme in {"http", "https"} and parsed.hostname in LOCAL_DEVELOPMENT_HOSTS
