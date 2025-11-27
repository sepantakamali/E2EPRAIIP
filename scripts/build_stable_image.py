#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
import tomllib

ARTIFACTS_DIR = Path("artifacts")
STABLE_PATH = ARTIFACTS_DIR / "model_stable.joblib"
RUNLOG_CANDIDATES = [
    ARTIFACTS_DIR / "runs.jsonl",
    ARTIFACTS_DIR / "runs.model",
]


def sh(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def image_id(ref: str) -> str | None:
    """Return the local image ID for a given ref (repo:tag) or None if missing."""
    try:
        out = sh(["docker", "images", "-q", ref], check=False).stdout.strip()
        return out or None
    except Exception:
        return None


def baked_pointer(ref: str) -> str | None:
    """Return baked MODEL_POINTER value for an image ref, if present."""
    try:
        out = sh(["docker", "image", "inspect", ref, "--format", "{{json .Config.Env}}"], check=False).stdout
        envs = json.loads(out or "[]")
        for env in envs:
            if isinstance(env, str) and env.startswith("MODEL_POINTER="):
                return env.split("=", 1)[1]
        return None
    except Exception:
        return None


def docker_tag(src: str, dst: str, dry_run: bool) -> None:
    print(f"$ docker tag {src} {dst}")
    if not dry_run:
        sh(["docker", "tag", src, dst])


def docker_build(tags: list[str], version: str, git_sha: str, build_date: str, dry_run: bool) -> None:
    cmd = [
        "docker", "build",
        "--build-arg", "MODEL_POINTER=stable",
        "--build-arg", f"VERSION={version}",
        "--build-arg", f"VCS_REF={git_sha}",
        "--build-arg", f"BUILD_DATE={build_date}",
        *tags,
        ".",
    ]
    print("$", " ".join(cmd))
    if not dry_run:
        sh(cmd)


def try_read_meta_from_runlog(stable_name: str) -> dict | None:
    for candidate in RUNLOG_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            with candidate.open() as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    # support either key name
                    path_val = entry.get("artifact") or entry.get("path")
                    if str(path_val).endswith(stable_name):
                        return entry
        except Exception:
            continue
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Build or re-tag a Docker image that serves the STABLE model pointer by default.")
    p.add_argument("--image", default="textclf-api", help="Base image name to tag (default: textclf-api)")
    p.add_argument("--stable-tag", default="stable", help="Human-friendly stable tag (default: stable)")
    p.add_argument("--no-stable", action="store_true", help="Do not apply the stable tag (e.g., :stable)")
    p.add_argument("--no-version-stable", action="store_true", help="Do not apply the version-stable tag (e.g., :0.1.0-stable)")
    p.add_argument("--also-latest", action="store_true", help="Also tag :latest for convenience")
    p.add_argument("--force-rebuild", action="store_true", help="Force a rebuild even if a suitable stable-baked image exists")
    p.add_argument("--dry-run", action="store_true", help="Print actions instead of executing")
    args = p.parse_args()

    if not STABLE_PATH.exists():
        raise FileNotFoundError(
            f"{STABLE_PATH} not found. Promote a model first, e.g.\n"
            "  python -m textclf.promote artifacts/<your-model>.joblib"
        )

    version = tomllib.load(open("pyproject.toml", "rb"))["project"]["version"]

    try:
        git_sha = sh(["git", "rev-parse", "--short", "HEAD"], check=False).stdout.strip() or "local"
    except Exception:
        git_sha = "local"
    build_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    meta = try_read_meta_from_runlog(STABLE_PATH.name)
    if meta and (meta.get("artifact") or meta.get("path")):
        print(f"Preparing stable image for model: {meta.get('artifact') or meta.get('path')}")
    else:
        print(f"Preparing stable image for pointer: {STABLE_PATH}")

    # Desired tags
    stable_ref = f"{args.image}:{args.stable_tag}"
    ver_stable_ref = f"{args.image}:{version}-stable"
    latest_ref = f"{args.image}:latest"

    want_stable = not args.no_stable
    want_ver_stable = not args.no_version_stable
    want_latest = args.also_latest

    # Existing local images
    have_stable = image_id(stable_ref)
    have_ver_stable = image_id(ver_stable_ref)
    have_latest = image_id(latest_ref)

    # Re-tag only from images that are ALREADY baked with MODEL_POINTER=stable
    can_retag_from_stable = False
    src_ref = None
    for candidate in (stable_ref, ver_stable_ref):
        if image_id(candidate):
            if baked_pointer(candidate) == "stable":
                can_retag_from_stable = True
                src_ref = candidate
                break

    if not args.force_rebuild and can_retag_from_stable:
        print("Found stable-baked image locally; re-tagging without rebuild.")
        if want_stable and not have_stable:
            docker_tag(src_ref, stable_ref, args.dry_run)
        if want_ver_stable and not have_ver_stable:
            docker_tag(src_ref, ver_stable_ref, args.dry_run)
        if want_latest and not have_latest:
            docker_tag(src_ref, latest_ref, args.dry_run)
        print("✅ Tagging complete")
        return 0

    # Otherwise build once and apply tags
    tags: list[str] = []
    if want_stable:
        tags += ["-t", stable_ref]
    if want_ver_stable:
        tags += ["-t", ver_stable_ref]
    if want_latest:
        tags += ["-t", latest_ref]

    docker_build(tags, version, git_sha, build_date, args.dry_run)
    print("✅ Build complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())