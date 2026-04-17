#!/usr/bin/env python3
"""
deploy_module.py
----------------
Generic module deployer. Reads manifests from pipeline/modules/*.yml
and deploys each enabled module via CloudFormation.

Usage:
    # Deploy all enabled modules (default - used by pipeline)
    python pipeline/scripts/deploy_module.py

    # Deploy a specific module only
    python pipeline/scripts/deploy_module.py api-gateway

    # Force specific modules via env var (manual trigger / CLI override)
    DEPLOY_MODULES=api-gateway python pipeline/scripts/deploy_module.py
"""

import os
import sys
import subprocess
import yaml
import boto3
import argparse
from pathlib import Path

ROOT            = Path(__file__).resolve().parents[2]
MODULES_DIR     = ROOT / "pipeline/modules"
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "")
ENVIRONMENT     = os.environ.get("ENVIRONMENT", "dev")


def run(cmd: str, check: bool = True):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT)
    if check and result.returncode != 0:
        print(f"ERROR: command failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode


def get_ssm_value(path: str) -> str:
    ssm = boto3.client("ssm")
    try:
        return ssm.get_parameter(Name=path)["Parameter"]["Value"]
    except Exception as e:
        print(f"WARNING: SSM {path} not found: {e}", file=sys.stderr)
        return ""


def resolve_parameters(params: list) -> list:
    overrides = []
    for p in params:
        if p["source"] == "ssm":
            value = get_ssm_value(p["path"])
            if value:
                overrides.append(f"{p['key']}={value}")
        elif p["source"] == "env":
            value = os.environ.get(p.get("env", ""), "")
            if value:
                overrides.append(f"{p['key']}={value}")
    return overrides


def load_manifest(module_name: str) -> dict:
    path = MODULES_DIR / f"{module_name}.yml"
    if not path.exists():
        print(f"ERROR: manifest not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def is_enabled(manifest: dict) -> bool:
    return manifest.get("module", {}).get("enabled", True)


def deploy(module_name: str):
    manifest = load_manifest(module_name)

    if not is_enabled(manifest):
        print(f"  [{module_name}] disabled — skipping")
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
        print("[1/4] Pre-deploy: skipped")

    # 2. Validate
    print(f"\n[2/4] Validating {stack_cfg['templatePath']} ...")
    run(f"cfn-lint {template_src}")
    run(f"aws cloudformation validate-template --template-body file://{template_src}")

    # 3. Package
    print(f"\n[3/4] Packaging → s3://{ARTIFACT_BUCKET}/cfn-artifacts/{module_name}/")
    run(
        f"aws cloudformation package"
        f" --template-file {template_src}"
        f" --s3-bucket {ARTIFACT_BUCKET}"
        f" --s3-prefix cfn-artifacts/{module_name}"
        f" --output-template-file {packaged}"
    )

    # 4. Deploy
    print(f"\n[4/4] Deploying stack: {stack_name} ...")
    params    = resolve_parameters(manifest.get("parameters", []))
    tags_raw  = manifest.get("tags", [])
    tags      = " ".join(f"{t['key']}={t['value']}" for t in tags_raw)
    tags     += f" Environment={ENVIRONMENT}"
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

    print(f"\n  Stack outputs:")
    run(
        f"aws cloudformation describe-stacks"
        f" --stack-name {stack_name}"
        f" --query 'Stacks[0].Outputs'"
        f" --output table",
        check=False
    )
    print(f"\n  [{module_name}] deployed successfully.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("module", nargs="?", help="Specific module to deploy")
    args = parser.parse_args()

    # Priority 1: DEPLOY_MODULES env var (manual override)
    force = os.environ.get("DEPLOY_MODULES", "").strip()
    if force:
        for m in [x.strip() for x in force.split(",") if x.strip()]:
            deploy(m)
        return

    # Priority 2: single module as CLI argument
    if args.module:
        deploy(args.module)
        return

    # Priority 3: deploy all enabled modules
    all_manifests = sorted(MODULES_DIR.glob("*.yml"))
    if not all_manifests:
        print("ERROR: no module manifests found in pipeline/modules/", file=sys.stderr)
        sys.exit(1)

    print(f"Deploying all enabled modules...\n")
    for manifest_path in all_manifests:
        name     = manifest_path.stem
        manifest = load_manifest(name)
        if not is_enabled(manifest):
            print(f"  [{name}] disabled — skipping")
            continue
        deploy(name)


if __name__ == "__main__":
    main()
