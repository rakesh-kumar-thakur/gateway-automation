# BuildSpec Explanation

## What is `pipeline/buildspec-deploy.yml`?

This is a **single, shared deployment orchestrator** used by **all environments** (dev/qa/prod) and **all AWS components** (api-gateway, alb, ecs, etc.).

## Key Characteristics

### ✅ Common for All Environments
- Same buildspec file used by dev, qa, and prod pipelines
- Environment is passed via `ENVIRONMENT` variable (line 14)
- Each pipeline's CodeBuild project references this same file

### ✅ Common for All Components
- Generic orchestrator that reads module manifests from [`pipeline/modules/*.yml`](pipeline/modules/)
- Deploys any component (api-gateway, alb, ecs, rds, etc.)
- No component-specific logic in the buildspec itself

### ✅ You Do NOT Need Separate Buildspecs

**One buildspec handles everything** because:
1. Component-specific details are in module manifests (not buildspec)
2. Environment-specific values come from environment variables
3. The Python script dynamically reads manifests and deploys accordingly

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ pipeline/buildspec-deploy.yml (SINGLE FILE)                 │
│                                                              │
│  1. Reads ENVIRONMENT variable (dev/qa/prod)                │
│  2. Scans pipeline/modules/*.yml for enabled modules        │
│  3. For each enabled module:                                │
│     - Reads its manifest (template path, parameters, etc.)  │
│     - Validates CloudFormation template                     │
│     - Packages if needed (swagger.yaml, etc.)               │
│     - Deploys CloudFormation stack                          │
│  4. Reports success/failure                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   pipeline/modules/ (MODULE MANIFESTS)  │
        ├─────────────────────────────────────────┤
        │  api-gateway.yml  ← Component details   │
        │  alb.yml          ← Component details   │
        │  ecs.yml          ← Component details   │
        │  rds.yml          ← Component details   │
        └─────────────────────────────────────────┘
```

## Current Flow (Per Environment)

### Dev Pipeline
```yaml
# pipeline/dev-pipeline.yaml (line 178-206)
CodeBuildDeployProject:
  Environment:
    EnvironmentVariables:
      - Name: ENVIRONMENT
        Value: dev              # ← Sets environment
      - Name: ARTIFACT_BUCKET
        Value: !Ref ArtifactBucket
  Source:
    BuildSpec: pipeline/buildspec-deploy.yml  # ← Same file
```

### QA Pipeline (Future)
```yaml
# pipeline/qa-pipeline.yaml
CodeBuildDeployProject:
  Environment:
    EnvironmentVariables:
      - Name: ENVIRONMENT
        Value: qa               # ← Different environment
      - Name: ARTIFACT_BUCKET
        Value: !Ref ArtifactBucket
  Source:
    BuildSpec: pipeline/buildspec-deploy.yml  # ← Same file
```

### Prod Pipeline (Future)
```yaml
# pipeline/prod-pipeline.yaml
CodeBuildDeployProject:
  Environment:
    EnvironmentVariables:
      - Name: ENVIRONMENT
        Value: prod             # ← Different environment
      - Name: ARTIFACT_BUCKET
        Value: !Ref ArtifactBucket
  Source:
    BuildSpec: pipeline/buildspec-deploy.yml  # ← Same file
```

## What the BuildSpec Does (Line by Line)

### Phase 1: Install (lines 18-24)
```yaml
install:
  runtime-versions:
    python: 3.12
  commands:
    - pip install pyyaml boto3 cfn-lint
```
**Purpose:** Install Python dependencies needed for deployment

### Phase 2: Pre-Build (lines 26-263)
```yaml
pre_build:
  commands:
    - echo "==> Environment $ENVIRONMENT"
    - cat > /tmp/deploy_modules.py << 'DEPLOY_SCRIPT'
    # ... Python script embedded here ...
```
**Purpose:** 
- Create deployment orchestrator script
- Script reads module manifests
- Script determines what to deploy

### Phase 3: Build (lines 265-268)
```yaml
build:
  commands:
    - python3 /tmp/deploy_modules.py
```
**Purpose:** Execute the deployment orchestrator

### Phase 4: Post-Build (lines 270-279)
```yaml
post_build:
  commands:
    - if [ $CODEBUILD_BUILD_SUCCEEDING -eq 1 ]; then
        echo "✓ All deployments successful"
      fi
```
**Purpose:** Report final status

## The Embedded Python Script

The buildspec contains a **generic deployment orchestrator** (lines 33-261) that:

### 1. Loads Module Manifests (lines 204-212)
```python
modules_dir = Path('pipeline/modules')
manifests = {}

for manifest_file in sorted(modules_dir.glob('*.yml')):
    manifest = load_module_manifest(manifest_file)
    module_name = manifest['module']['name']
    manifests[module_name] = manifest
```

### 2. Determines What to Deploy (lines 214-226)
```python
if deploy_modules_override:
    # Manual: DEPLOY_MODULES=api-gateway,alb
    modules_to_deploy = [m.strip() for m in deploy_modules_override.split(',')]
else:
    # Auto: Deploy all enabled modules
    for module_name, manifest in manifests.items():
        if manifest.get('module', {}).get('enabled', False):
            modules_to_deploy.append(module_name)
```

### 3. Deploys Each Module (lines 95-194)
```python
def deploy_module(manifest, environment, artifact_bucket):
    module_name = manifest['module']['name']
    stack_name = f"{environment}-{stack_config['name']}"  # dev-api-gateway-stack
    template_path = stack_config['templatePath']          # aws/api-gateway/template.yaml
    
    # Validate template
    run_command(f"cfn-lint {template_path}")
    
    # Package if needed (swagger.yaml, etc.)
    if needs_packaging:
        run_command(f"aws cloudformation package ...")
    
    # Build parameters from manifest
    params = []
    for param in manifest.get('parameters', []):
        if param['source'] == 'ssm':
            value = get_ssm_parameter(param['path'])
        elif param['source'] == 'value':
            value = param['value']
        params.append(f"{param['key']}={value}")
    
    # Deploy CloudFormation stack
    run_command(f"aws cloudformation deploy ...")
```

## Why This Design is Powerful

### ✅ Single Source of Truth
- One buildspec for all environments and components
- Changes apply everywhere automatically

### ✅ Component Isolation
- Each component's details in its own manifest
- Adding new component = add manifest file only
- No buildspec changes needed

### ✅ Environment Flexibility
- Same logic works for dev/qa/prod
- Environment passed as variable
- Stack names automatically prefixed (dev-*, qa-*, prod-*)

### ✅ Easy Testing
- Can test locally: `ENVIRONMENT=dev python deploy_modules.py`
- Can override: `DEPLOY_MODULES=api-gateway python deploy_modules.py`

## Example: Adding a New Component (RDS)

### Step 1: Create Template
```bash
# Create aws/rds/template.yaml
# (CloudFormation template for RDS)
```

### Step 2: Create Manifest
```yaml
# pipeline/modules/rds.yml
module:
  name: rds
  enabled: true

stack:
  name: rds-stack
  templatePath: aws/rds/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: value
    value: dev
  - key: DBName
    source: value
    value: mydb

changePaths:
  - aws/rds/**
  - pipeline/modules/rds.yml
```

### Step 3: Commit and Push
```bash
git add aws/rds/ pipeline/modules/rds.yml
git commit -m "Add RDS module"
git push
```

### Result
- **Buildspec unchanged** ✅
- Pipeline automatically:
  1. Detects new manifest
  2. Reads RDS configuration
  3. Deploys RDS stack
  4. Works in dev/qa/prod

## Current Limitations (To Be Fixed)

### 1. No Dependency Ordering
```python
# Line 233: Deploys in alphabetical order
for module_name in modules_to_deploy:
    deploy_module(manifest, environment, artifact_bucket)
```
**Problem:** If ECS depends on ALB, might deploy in wrong order

**Solution:** Add dependency resolution (see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md))

### 2. Hardcoded Environment Values
```yaml
# pipeline/modules/api-gateway.yml (line 21)
parameters:
  - key: Environment
    source: value
    value: dev  # ← Hardcoded!
```
**Problem:** Same manifest can't work for qa/prod

**Solution:** Use `source: environment` and load from `pipeline/env/*.json`

### 3. No Change Detection
```python
# Line 59: Always deploys all enabled modules
return None  # CodeBuild doesn't preserve git history
```
**Problem:** Deploys everything even if only one component changed

**Solution:** Use S3 to track previous commit or accept this limitation

## Summary

| Question | Answer |
|----------|--------|
| **Common for all environments?** | ✅ Yes - same buildspec for dev/qa/prod |
| **Common for all components?** | ✅ Yes - reads manifests dynamically |
| **Need separate buildspecs?** | ❌ No - one buildspec handles everything |
| **Where is component logic?** | In [`pipeline/modules/*.yml`](pipeline/modules/) manifests |
| **Where is environment logic?** | In `ENVIRONMENT` variable + future `pipeline/env/*.json` |
| **Can I add new components?** | ✅ Yes - just add manifest, no buildspec changes |

## Recommended Enhancements

See [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) Phase 4 for:
- Dependency graph resolution
- Environment config loading
- Topological sort for deployment order
- Dynamic parameter resolution with multiple sources