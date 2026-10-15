"""Run the Docker + SQLite learner acceptance gate without Cloudflare.

This gate deliberately uses an explicit, reviewed test allowlist rather than
implicitly selecting the SDK's legacy Cloudflare/Wrangler test suite.
It does NOT replace the SDK's wider quality suite or the browser owner UAT.

Usage (Python 3.12):
    python scripts/run_selfhost_gate.py
    python scripts/run_selfhost_gate.py --scope selfhost
    python scripts/run_selfhost_gate.py --scope sdk
    python scripts/run_selfhost_gate.py --live-url http://127.0.0.1:18085 \
        --sqlite-db /path/to/isolated/learning-kernel.sqlite3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SELFHOST_TESTS = (
    "tests/test_feedback_runtime.py",
    "tests/test_learning_map.py",
    "tests/test_migrations.py",
    "tests/test_runtime_http_host.py",
    "tests/test_sdk_sqlite_migrations.py",
    "tests/test_seed_u1.py",
    "tests/test_sqlite_d1.py",
    "tests/test_u1_compound_pool_plan.py",
    "tests/test_u1_compound_refill_continuity.py",
    "tests/test_u1_compound_surface_runtime.py",
    "tests/test_u1_full_supply_runtime.py",
    "tests/test_u1_pool_replenishment.py",
    "tests/test_u1_spaced_review_runtime.py",
)
# Only portable LK semantics: validation, trusted feedback, protected Pool,
# Surface, compound evidence, and review. No Cloudflare deployment/mocks.
CANONICAL_SDK_TESTS = (
    "tests/test_runtime_vnext_activity_pool.py",
    "tests/test_runtime_vnext_service_binding_security.py",
    "tests/test_runtime_vnext_surface_compiler.py",
    "tests/test_runtime_vnext_trusted_evaluation.py",
    "tests/test_runtime_spaced_review.py",
    "tests/test_math_u1_vnext_compound_square_cutting.py",
    "tests/test_math_u1_vnext_supply_continuity.py",
)
EXPECTED_SCHEMA_FAMILY = "learning-kernel-runtime-vnext"
EXPECTED_SCHEMA_REVISION = "4"
MIN_PLACES = 17


def validate_test_contract(sdk: Path) -> None:
    """Fail if a safety test silently disappears or a root test is unclassified."""
    if not (sdk / "learning_kernel" / "__init__.py").is_file():
        raise RuntimeError(f"Pinned SDK is missing: {sdk}")
    for directory, selected in ((ROOT, SELFHOST_TESTS), (sdk, CANONICAL_SDK_TESTS)):
        missing = [entry for entry in selected if not (directory / entry).is_file()]
        if missing:
            raise RuntimeError(f"Mandatory test files missing from {directory}: {missing}")
    actual = {path.relative_to(ROOT).as_posix() for path in (ROOT / "tests").glob("test_*.py")}
    unclassified = sorted(actual - set(SELFHOST_TESTS))
    if unclassified:
        raise RuntimeError(
            "New selfhost tests require explicit gate classification: "
            + ", ".join(unclassified)
        )
    forbidden = ("wrangler", "cloudflare", "test_runtime_vnext_worker.py", "test_runtime_vnext_d1_migrations.py")
    if any(term in entry.casefold() for entry in (*SELFHOST_TESTS, *CANONICAL_SDK_TESTS) for term in forbidden):
        raise RuntimeError("Cloudflare deployment tests must not enter the selfhost gate.")


def run_group(label: str, root: Path, paths: tuple[str, ...], sdk: Path) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT), str(sdk), env.get("PYTHONPATH", ""))
    )
    command = [
        sys.executable, "-m", "pytest",
        "-q", "-ra", "-o", "addopts=", "--tb=short", *paths,
    ]
    print(f"=== {label} ({len(paths)} required files) ===", flush=True)
    result = subprocess.run(
        command, cwd=root, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    summary = result.stdout.splitlines()[-1] if result.stdout.splitlines() else ""
    skipped = bool(re.search(r"\b\d+ skipped\b", result.stdout))
    passed = result.returncode == 0 and not skipped
    if skipped:
        print(f"{label}: skipped tests are NOT a passing gate.", flush=True)
    return {"name": label, "passed": passed, "exitCode": result.returncode,
            "summary": summary, "skipped": skipped, "testFiles": len(paths)}


def _json_get(url: str) -> dict[str, object]:
    try:
        with urlopen(url, timeout=7) as response:  # noqa: S310 - caller-provided local acceptance origin
            if response.status != 200:
                raise RuntimeError(f"{url}: HTTP {response.status}")
            result = json.loads(response.read(2_000_000))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Selfhost HTTP readiness failed: {url}: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{url}: expected JSON object")
    return result


def check_live_service(url: str, database_path: Path) -> dict[str, object]:
    """Read-only checks; never seed, migrate, issue, or write learner data."""
    origin = url.rstrip("/")
    ready = _json_get(origin + "/api/ready")
    if ready.get("ready") is not True:
        raise RuntimeError("Selfhost /api/ready is not ready.")
    map_data = _json_get(origin + "/api/learning-map")
    places = map_data.get("places")
    if not isinstance(places, list) or len(places) < MIN_PLACES:
        raise RuntimeError(f"Selfhost learning map has fewer than {MIN_PLACES} Places.")
    if not database_path.is_file():
        raise RuntimeError(f"SQLite DB missing: {database_path}")
    database_uri = "file:" + database_path.resolve().as_posix() + "?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick != ("ok",):
            raise RuntimeError(f"SQLite integrity failed: {quick!r}")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"SQLite foreign key violations: {len(violations)}")
        metadata = dict(connection.execute("SELECT key, value FROM vnext_runtime_metadata"))
        if metadata.get("schema_family") != EXPECTED_SCHEMA_FAMILY:
            raise RuntimeError("SQLite schema family differs from Runtime.")
        if metadata.get("schema_revision") != EXPECTED_SCHEMA_REVISION:
            raise RuntimeError("SQLite schema revision is not 4.")
        migrations = {
            name for (name,) in connection.execute(
                "SELECT migration_name FROM selfhosted_migrations"
            )
        }
        if len(migrations) != 4:
            raise RuntimeError("Selfhost must contain four recorded, checksum-pinned migrations.")
    return {"name": "isolated-live-http-and-sqlite", "passed": True,
            "places": len(places), "sqliteIntegrity": "ok",
            "schemaRevision": EXPECTED_SCHEMA_REVISION, "migrations": 4}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-dir", type=Path, default=ROOT / "vendor" / "learning-kernel-sdk")
    parser.add_argument("--scope", choices=("both", "selfhost", "sdk"), default="both")
    parser.add_argument("--live-url", help="Explicit isolated Docker URL, e.g. http://127.0.0.1:18085")
    parser.add_argument("--sqlite-db", type=Path, help="SQLite file belonging to that isolated Docker instance")
    parser.add_argument("--report", type=Path, help="Optional JSON report path (never writes to learner DB)")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("The pinned SDK acceptance gate requires Python 3.12 or newer.")
    if bool(args.live_url) != bool(args.sqlite_db):
        parser.error("--live-url and --sqlite-db must be provided together.")
    sdk = args.sdk_dir.resolve()
    validate_test_contract(sdk)
    results: list[dict[str, object]] = []
    if args.scope in {"both", "selfhost"}:
        results.append(run_group("selfhost-sqlite", ROOT, SELFHOST_TESTS, sdk))
    if args.scope in {"both", "sdk"}:
        results.append(run_group("lk-canonical-portable", sdk, CANONICAL_SDK_TESTS, sdk))
    if args.live_url:
        try:
            results.append(check_live_service(args.live_url, args.sqlite_db))
        except RuntimeError as exc:
            results.append({"name": "isolated-live-http-and-sqlite", "passed": False, "error": str(exc)})
    success = all(result["passed"] for result in results)
    report = {
        "schemaVersion": "bailian.selfhost-acceptance@1",
        "gate": "docker-sqlite-core",
        "passed": success,
        "cloudflareDeploymentTestsExecuted": False,
        "liveCheckPerformed": bool(args.live_url),
        "browserUatIncluded": False,
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SELFHOST_GATE=" + json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
