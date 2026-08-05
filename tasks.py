"""Invoke build tasks for jk-mcp-wsl.

Usage:
    uv run inv lint               # ruff check + format check       (alias: inv l)
    uv run inv lint --fix         # auto-fix violations and reformat
    uv run inv check-complexity   # cyclomatic complexity gate       (alias: inv cc)
    uv run inv test               # run pytest                       (alias: inv t)
    uv run inv coverage           # pytest + coverage report         (alias: inv v)
    uv run inv build              # build wheel + sdist              (alias: inv b)
    uv run inv build-image        # build Docker image               (alias: inv bi)
    uv run inv release            # semantic-release version bump    (alias: inv r)
    uv run inv dry-run            # preview next release version     (alias: inv dr)
    uv run inv clean              # remove build/coverage artifacts  (alias: inv c)
    uv run inv install            # install dependencies             (alias: inv i)
    uv run inv                    # list available tasks
"""

import re
import sys
from pathlib import Path

from invoke import Context, task

# =============================================================================
# CONFIGURATION — Single Source of Truth
# =============================================================================
MAX_COMPLEXITY = 7
COVERAGE_THRESHOLD = 90
IMAGE_NAME = "jk-mcp-wsl"


@task(aliases=["c"])
def clean(ctx: Context) -> None:
    """Remove transient build and coverage artifacts."""
    ctx.run("find . -name '*.pyc' -delete")
    ctx.run("find . -name '__pycache__' -type d -exec rm -r {} +", warn=True)
    ctx.run("find . -name '.pytest_cache' -type d -exec rm -r {} +", warn=True)
    ctx.run("rm -f .coverage coverage.xml junit.xml")
    ctx.run("rm -rf dist/ build/ *.egg-info/ htmlcov/")


@task(
    aliases=["l"],
    help={"fix": "Auto-fix lint violations and reformat files instead of just checking"},
)
def lint(ctx: Context, fix: bool = False) -> None:
    """Run ruff linter and formatter against src/ and tests/."""
    if fix:
        ctx.run("uv run ruff check --fix src/ tests/")
        ctx.run("uv run ruff format src/ tests/")
    else:
        ctx.run("uv run ruff check src/ tests/")
        ctx.run("uv run ruff format --check src/ tests/")


@task(
    aliases=["cc"],
    help={"max_complexity": f"Maximum allowed complexity (default: {MAX_COMPLEXITY})"},
)
def check_complexity(ctx: Context, max_complexity: int = MAX_COMPLEXITY) -> None:
    """Check cyclomatic complexity of the source code — fail if above MAX_COMPLEXITY.

    Only checks src/wsl, not tests/. Test files are excluded because
    setup/teardown logic in fixtures routinely exceeds the threshold without
    representing real application complexity.
    """
    ctx.run(f"uv run cyclo -m {max_complexity} src/wsl")


@task(
    aliases=["t"],
    help={
        "k": "Filter tests by expression (passed to pytest -k)",
        "v": "Increase verbosity (-v flag)",
        "x": "Stop after first failure (-x flag)",
    },
)
def test(ctx: Context, k: str | None = None, v: bool = False, x: bool = False) -> None:
    """Run the pytest suite."""
    cmd = "uv run pytest"
    if v:
        cmd += " -v"
    if x:
        cmd += " -x"
    if k:
        cmd += f" -k {k!r}"
    ctx.run(cmd)


@task(
    aliases=["v"],
    help={"report": "Coverage report format: term-missing (default), html, xml, json"},
)
def coverage(ctx: Context, report: str = "term-missing") -> None:
    """Run the pytest suite with coverage — fail if below COVERAGE_THRESHOLD."""
    result = ctx.run(
        f"uv run pytest --cov=src/wsl --cov-report={report} --cov-report=xml --cov-fail-under={COVERAGE_THRESHOLD}",
        warn=True,
    )
    if result and result.exited != 0:
        sys.exit(result.exited)


@task(aliases=["b"])
def build(ctx: Context) -> None:
    """Build the wheel and source distribution into dist/."""
    ctx.run("rm -rf dist/")
    ctx.run("uv build")


@task(
    aliases=["bi"],
    help={
        "tag": "Image tag — typically the semantic version (default: latest)",
        "name": f"Image name (default: {IMAGE_NAME})",
    },
)
def build_image(ctx: Context, tag: str = "latest", name: str = IMAGE_NAME) -> None:
    """Build and tag the Docker image."""
    ctx.run(f"docker build -t {name}:{tag} .")


@task(aliases=["dr"])
def dry_run(ctx: Context) -> None:
    """Preview the next release version without making any changes."""
    current = Path("VERSION").read_text().strip()
    major, minor, patch = (int(x) for x in current.split("."))

    last_tag = ctx.run("git tag --sort=-version:refname | head -1", hide=True, warn=True)
    tag = last_tag.stdout.strip() if last_tag and last_tag.ok else ""
    commit_range = f"{tag}..HEAD" if tag else "HEAD"

    log = ctx.run(f"git log {commit_range} --pretty=%s", hide=True, warn=True)
    commits = log.stdout.strip().splitlines() if log and log.ok else []

    bump = None
    for msg in commits:
        prefix = msg.split(":")[0]
        if "BREAKING CHANGE" in msg or prefix.endswith("!"):
            bump = "major"
            break
        if re.match(r"^feat(\(.+\))?$", prefix) and bump != "major":
            bump = "minor"
        elif re.match(r"^(fix|perf)(\(.+\))?$", prefix) and bump not in ("major", "minor"):
            bump = "patch"

    if bump is None:
        print(f"No release warranted by commits since {tag or 'beginning'}. Current version: {current}")
        return

    if bump == "major":
        next_version = f"{major + 1}.0.0"
    elif bump == "minor":
        next_version = f"{major}.{minor + 1}.0"
    else:
        next_version = f"{major}.{minor}.{patch + 1}"

    print(f"Next version: {next_version} ({bump} bump from {current})")


@task(
    aliases=["i"],
    help={"prod": "Install only production dependencies (omit dev group)"},
)
def install(ctx: Context, prod: bool = False) -> None:
    """Install project dependencies via uv sync."""
    if prod:
        ctx.run("uv sync --no-dev")
    else:
        ctx.run("uv sync")
