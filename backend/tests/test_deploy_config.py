"""Static checks of the Docker files. They need no Docker: they catch the mistakes that
only show up at `docker compose up --build` time (wrong COPY path, an env var the app
ignores, mismatched ports, a file excluded by .dockerignore).

These tests do NOT build or run any image. Skipped automatically if the repository root
files are not present (e.g. when running inside the backend image itself).
"""
import fnmatch
import re
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not (ROOT / "docker-compose.yml").exists(), reason="repository root files not available"
)


def instructions(dockerfile: Path) -> list[tuple[str, str]]:
    """(INSTRUCTION, arguments) pairs with line continuations joined and comments dropped."""
    text = re.sub(r"\\\n", " ", dockerfile.read_text())
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cmd, _, rest = line.partition(" ")
            out.append((cmd.upper(), rest.strip()))
    return out


def dockerignore_patterns() -> list[str]:
    lines = (ROOT / ".dockerignore").read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def is_ignored(rel: str) -> bool:
    """Simplified .dockerignore matching: root-level names and **/name at any depth."""
    parts = rel.strip("/").split("/")
    for pat in dockerignore_patterns():
        if pat.startswith("**/"):
            if any(fnmatch.fnmatch(p, pat[3:]) for p in parts):
                return True
        elif rel.strip("/") == pat or rel.strip("/").startswith(pat + "/"):
            return True
    return False


def copy_sources(dockerfile: Path) -> list[str]:
    srcs = []
    for cmd, args in instructions(dockerfile):
        if cmd == "COPY" and "--from=" not in args:
            tokens = args.split()
            srcs.extend(tokens[:-1])           # last token is the destination
    return srcs


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


# ---------------------------------------------------------------- Dockerfiles
@pytest.mark.parametrize("name", ["backend", "frontend"])
def test_every_copy_source_exists_and_is_not_dockerignored(name):
    dockerfile = ROOT / name / "Dockerfile"
    sources = copy_sources(dockerfile)
    assert sources
    for src in sources:                                    # build context = repository root
        assert (ROOT / src).exists(), f"{name}/Dockerfile COPY source missing: {src}"
        assert not is_ignored(src), f"{src} is excluded by .dockerignore"


def test_files_the_images_need_at_runtime_are_not_excluded():
    needed = [
        "backend/app/main.py", "backend/alembic.ini", "backend/alembic/env.py",
        "backend/scripts/docker-entrypoint.sh", "backend/requirements.txt",
        "knowledge_base/nutrition_seed.json",
        "frontend/package.json", "frontend/package-lock.json", "frontend/index.html",
        "frontend/vite.config.ts", "frontend/src/main.tsx", "frontend/nginx.conf",
    ]
    for rel in needed:
        assert (ROOT / rel).exists(), rel
        assert not is_ignored(rel), f"{rel} would be excluded from the build context"


def test_secrets_and_local_environments_are_excluded_from_images():
    for rel in [".env", ".git", "backend/.venv", "frontend/node_modules", "frontend/dist",
                "backend/app/__pycache__"]:
        assert is_ignored(rel), f"{rel} must be in .dockerignore"


def test_backend_dockerfile_wiring():
    ins = instructions(ROOT / "backend" / "Dockerfile")
    flat = " ".join(f"{c} {a}" for c, a in ins)
    assert ins[0][0] == "FROM" and "python:3" in ins[0][1]
    assert any(c == "USER" and a != "root" for c, a in ins)                 # not running as root
    assert "KNOWLEDGE_BASE_PATH=/app/knowledge_base/nutrition_seed.json" in flat
    assert "COPY knowledge_base/ ./knowledge_base/" in flat                  # where that path points
    assert ("EXPOSE", "8000") in ins
    cmd = next(a for c, a in ins if c == "CMD")
    assert "scripts/docker-entrypoint.sh" in cmd
    entry = (ROOT / "backend" / "scripts" / "docker-entrypoint.sh").read_text()
    assert "--port 8000" in entry                                            # matches EXPOSE


def test_frontend_dockerfile_wiring():
    ins = instructions(ROOT / "frontend" / "Dockerfile")
    flat = " ".join(f"{c} {a}" for c, a in ins)
    assert "npm ci" in flat and "npm run build" in flat
    assert any(c == "ARG" and a.startswith("VITE_API_BASE_URL") for c, a in ins)
    assert "COPY --from=build /app/dist /usr/share/nginx/html" in flat
    assert ("EXPOSE", "80") in ins
    assert "listen 80;" in (ROOT / "frontend" / "nginx.conf").read_text()


# ---------------------------------------------------------------- compose
def test_compose_services_and_build_contexts(compose):
    assert set(compose["services"]) == {"db", "backend", "frontend"}
    for name in ("backend", "frontend"):
        build = compose["services"][name]["build"]
        assert build["context"] == "."                                       # repo root
        assert (ROOT / build["dockerfile"]).exists()


def test_compose_ports_are_localhost_only_and_match_the_images(compose):
    svc = compose["services"]
    for name, s in svc.items():
        for port in s["ports"]:
            assert port.startswith("127.0.0.1:"), f"{name} publishes {port} to all interfaces"
    assert svc["backend"]["ports"] == ["127.0.0.1:8000:8000"]                 # EXPOSE 8000
    assert svc["frontend"]["ports"] == ["127.0.0.1:5173:80"]                  # EXPOSE 80, CORS origin :5173
    assert "http://localhost:5173" in svc["backend"]["environment"]["CORS_ORIGINS"]


def test_compose_startup_ordering_and_healthchecks(compose):
    svc = compose["services"]
    assert svc["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert svc["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "pg_isready" in " ".join(svc["db"]["healthcheck"]["test"])
    assert "/health" in " ".join(svc["backend"]["healthcheck"]["test"])


def test_every_backend_env_var_is_a_real_setting(compose):
    fields = {n.upper() for n in Settings.model_fields}
    for var in compose["services"]["backend"]["environment"]:
        assert var in fields, f"{var} is passed to the container but Settings ignores it"


def test_backend_container_talks_to_the_db_service_not_localhost(compose):
    url = compose["services"]["backend"]["environment"]["DATABASE_URL"]
    assert "@db:5432/" in url and "localhost" not in url


def test_frontend_build_arg_matches_the_dockerfile_and_env_example(compose):
    args = compose["services"]["frontend"]["build"]["args"]
    assert list(args) == ["VITE_API_BASE_URL"]
    env = (ROOT / ".env.example").read_text()
    assert "VITE_API_BASE_URL=http://localhost:8000" in env
    assert "http://localhost:8000" in args["VITE_API_BASE_URL"]


def test_env_example_covers_every_setting_compose_substitutes():
    env_keys = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", (ROOT / ".env.example").read_text(), re.M))
    lines = (ROOT / "docker-compose.yml").read_text().splitlines()
    compose_text = "\n".join(l for l in lines if not l.lstrip().startswith("#"))   # ignore comments
    for var in set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", compose_text)):
        assert var in env_keys, f"docker-compose.yml uses ${{{var}}} but .env.example does not document it"


def test_env_example_has_no_real_looking_secrets():
    text = (ROOT / ".env.example").read_text()
    assert not re.search(r"sk-[A-Za-z0-9_-]{16,}", text)
    assert re.search(r"^ANTHROPIC_API_KEY=\s*$", text, re.M)               # shipped blank
