#!/usr/bin/env python3
"""
deploy_module.py
----------------
Generic module deployer. Reads a module manifest from pipeline/modules/<name>.yml
and executes: preDeploy → validate → package → deploy.

Usage:
    # Deploy a specific module
    python pipeline/scripts/deploy_module.py api-gateway

    # Force-deploy specific modules (comma-separated), bypassing change detection
    DEPLOY_MODULES=api-gateway,alb python pipeline/scripts/deploy_module.py

    # Deploy all changed modules (used by buildspec.yml in CI)
    python pipeline/scripts/deploy_module.py --changed-only
"""

import os
import sys
import subprocess
import yaml
import boto3
import fnmatch
import argparse
from pathlib import Path

ROOT          = Path(__file__).resolve().parents[2]
MODULES_DIR   = ROOT / "pipeline/modules"
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "")
ENVIRONMENT   = os.environ.get("ENVIRONMENT", "dev")

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd: str, check: bool = True):
    """Run a shell command, stream output, raise on failure."""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT)
    if check and result.returncode != 0:
        print(f"ERROR: Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode

def get_ssm_value(path: str) -> str:
    """Fetch a value from SSM Parameter Store."""
    ssm = boto3.client("ssm")
    try:
        return ssm.get_parameter(Name=path)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        print(f"WARNING: SSM parameter not found: {path}", file=sys.stderr)
        return ""

def resolve_parameters(params: list) -> list:
    """Resolve parameter values from SSM and return as CFN override strings."""
    overrides = []
    for p in params:
        if p["source"] == "ssm":
            value = get_ssm_value(p["path"])
            if value:
                overrides.append(f"{p['key']}={value}")
        elif p["source"] == "env":
            value = os.environ.get(p["env"], "")
            if value:
                overrides.append(f"{p['key']}={value}")
    return overrides

def get_changed_files() -> list[str]:
    """
    Return list of changed files in this build.
    In CodeBuild, uses git diff against previous commit.
    Falls back to all files if git is unavailable.
    """
    try:
        result = subprocess.run(
            "git diff --name-only HEAD~1 HEAD",
            shell=True, capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()
    except Exception:
        pass
    # Fallback: treat everything as changed
    print("WARNING: Could not determine changed files, deploying all modules.")
    return ["**"]

def module_has_changes(manifest: dict, changed_files: list[str]) -> bool:
    """Check if any changed file matches this module's changePaths patterns."""
    patterns = manifest.get("changePaths", ["**"])
    for changed in changed_files:
        for pattern in patterns:
            if fnmatch.fnmatch(changed, pattern):
                return True
    return False

def load_manifest(module_name: str) -> dict:
    """Load and parse a module manifest YAML."""
    manifest_path = MODULES_DIR / f"{module_name}.yml"
    if not manifest_path.exists():
        print(f"ERROR: No manifest found for module '{module_name}' at {manifest_path}", file=sys.stderr)
        sys.exit(1)
    with open(manifest_path) as f:
        return yaml.safe_load(f)

def is_enabled(manifest: dict) -> bool:
    """Return False if the module manifest has enabled: false."""
    return manifest.get("module", {}).get("enabled", True)

# ── Core deploy logic ─────────────────────────────────────────────────────────

def deploy(module_name: str):
    manifest     = load_manifest(module_name)

    if not is_enabled(manifest):
        print(f"  Module '{module_name}' is disabled (enabled: false in manifest). Skipping.")
        return
    stack_cfg    = manifest["stack"]
    stack_name   = stack_cfg["name"]
    template_src = ROOT / stack_cfg["templatePath"]
    capabilities = " ".join(stack_cfg.get("capabilities", ["CAPABILITY_NAMED_IAM"]))
    packaged     = f"/tmp/packaged-{module_name}.yaml"

    print(f"\n{'='*60}")
    print(f"  MODULE : {module_name}")
    print(f"  STACK  : {stack_name}")
    print(f"  ENV    : {ENVIRONMENT}")
    print(f"{'='*60}\n")

    # 1. Pre-deploy hook
    pre = manifest.get("preDeploy")
    if pre and isinstance(pre, dict) and pre.get("script"):
        print(f"[1/4] Pre-deploy: {pre['description']}")
        run(pre["script"])
    else:
        print("[1/4] Pre-deploy: skipped (none defined)")

    # 2. Validate
    print(f"\n[2/4] Validating {template_src.relative_to(ROOT)} ...")
    run(f"cfn-lint {template_src}")
    run(f"aws cloudformation validate-template --template-body file://{template_src}")

    # 3. Package
    print(f"\n[3/4] Packaging to s3://{ARTIFACT_BUCKET}/cfn-artifacts/{module_name}/ ...")
    run(
        f"aws cloudformation package"
        f" --template-file {template_src}"
        f" --s3-bucket {ARTIFACT_BUCKET}"
        f" --s3-prefix cfn-artifacts/{module_name}"
        f" --output-template-file {packaged}"
    )

    # 4. Deploy
    print(f"\n[4/4] Deploying stack: {stack_name} ...")
    params   = resolve_parameters(manifest.get("parameters", []))
    tags_raw = manifest.get("tags", [])
    tags     = " ".join(f"{t['key']}={t['value']}" for t in tags_raw)
    tags    += f" Environment={ENVIRONMENT}"

    param_str = " ".join(params) if params else ""
    run(
        f"aws cloudformation deploy"
        f" --template-file {packaged}"
        f" --stack-name {stack_name}"
        f" --capabilities {capabilities}"
        f" --no-fail-on-empty-changeset"
        + (f" --parameter-overrides {param_str}" if param_str else "")
        + (f" --tags {tags}" if tags else "")
    )

    # Print outputs
    print(f"\n  Stack outputs:")
    run(
        f"aws cloudformation describe-stacks"
        f" --stack-name {stack_name}"
        f" --query 'Stacks[0].Outputs'"
        f" --output table",
        check=False
    )
    print(f"\n  Module '{module_name}' deployed successfully.\n")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("module", nargs="?", help="Module name to deploy (e.g. api-gateway)")
    parser.add_argument("--changed-only", action="store_true",
                        help="Auto-detect changed modules from git diff")
    args = parser.parse_args()

    # Priority 1: explicit env var override (manual trigger / CLI)
    force_modules = os.environ.get("DEPLOY_MODULES", "").strip()
    if force_modules:
        modules = [m.strip() for m in force_modules.split(",") if m.strip()]
        print(f"DEPLOY_MODULES override: {modules}")
        for m in modules:
            deploy(m)
        return

    # Priority 2: single module passed as argument
    if args.module:
        deploy(args.module)
        return

    # Priority 3: changed-only detection (used by buildspec in CI)
    if args.changed_only:
        changed = get_changed_files()
        print(f"Changed files detected: {len(changed)}")
        all_manifests = sorted(MODULES_DIR.glob("*.yml"))
        deployed = []
        for manifest_path in all_manifests:
            name = manifest_path.stem
            manifest = load_manifest(name)
            if not is_enabled(manifest):
                print(f"  -> '{name}' is disabled, skipping")
                continue
            if module_has_changes(manifest, changed):
                print(f"  -> '{name}' has changes, queuing for deploy")
                deployed.append(name)
            else:
                print(f"  -> '{name}' no changes, skipping")
        if not deployed:
            print("\nNo modules changed. Nothing to deploy.")
            return
        for m in deployed:
            deploy(m)
        return

    parser.print_help()
    sys.exit(1)

if __name__ == "__main__":
    main()
