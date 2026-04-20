# Infrastructure Pipeline Implementation Plan

## Current State Analysis

### Strengths
- Clean separation: [`aws/`](aws/) for resources, [`pipeline/`](pipeline/) for CI/CD
- Manifest-driven approach in [`pipeline/modules/`](pipeline/modules/)
- Working dev pipeline with auto-detection in [`pipeline/buildspec-deploy.yml`](pipeline/buildspec-deploy.yml:220)
- Parameter files exist for all 3 environments

### Critical Issues
1. **Environment-specific hardcoding**
   - [`pipeline/dev-pipeline.yaml`](pipeline/dev-pipeline.yaml:107) has `dev-codebuild-deploy-role`, `dev-infra-pipeline`
   - [`pipeline/modules/api-gateway.yml`](pipeline/modules/api-gateway.yml:21) hardcodes `dev` values
   - SSM paths hardcoded to `/pipeline/dev/*`

2. **No dependency management**
   - [`pipeline/modules/alb.yml`](pipeline/modules/alb.yml:4) mentions order in comments only
   - [`pipeline/modules/ecs.yml`](pipeline/modules/ecs.yml:4) depends on ALB but no enforcement

3. **Limited extensibility**
   - Adding new component requires pipeline template changes
   - No approval stage for qa/prod
   - Test stages commented out

## Target Architecture

### Single Generic Pipeline Template
```
pipeline/
  pipeline.yaml              # Generic template for all environments
  buildspec-deploy.yml       # Enhanced with dependency resolution
  params-dev.json           # Pipeline stack parameters
  params-qa.json
  params-prod.json
  modules/                  # Environment-neutral manifests
    api-gateway.yml
    alb.yml
    ecs.yml
  env/                      # Environment-specific values
    dev.json
    qa.json
    prod.json
```

### Pipeline Flow
```
Source (GitHub) 
  → Validate (cfn-lint, manifest schema)
  → Deploy (dependency-ordered modules)
  → Approval (qa/prod only)
  → Post-Deploy Tests (optional)
```

## Implementation Phases

### Phase 1: Generic Pipeline Template
**Goal:** One template for dev/qa/prod

**Changes:**
1. Rename [`pipeline/dev-pipeline.yaml`](pipeline/dev-pipeline.yaml) → `pipeline/pipeline.yaml`
2. Add `EnvironmentName` parameter (dev/qa/prod)
3. Replace all hardcoded names:
   - `dev-infra-pipeline` → `${EnvironmentName}-infra-pipeline`
   - `dev-codebuild-deploy-role` → `${EnvironmentName}-codebuild-deploy-role`
   - `/pipeline/dev/*` → `/pipeline/${EnvironmentName}/*`
4. Add conditional approval stage:
   ```yaml
   - Name: Approval
     Condition: !Not [!Equals [!Ref EnvironmentName, dev]]
   ```

**Deploy:**
```bash
# Dev
aws cloudformation deploy \
  --template-file pipeline/pipeline.yaml \
  --stack-name dev-infra-pipeline \
  --parameter-overrides file://pipeline/params-dev.json \
  --capabilities CAPABILITY_NAMED_IAM

# QA
aws cloudformation deploy \
  --template-file pipeline/pipeline.yaml \
  --stack-name qa-infra-pipeline \
  --parameter-overrides file://pipeline/params-qa.json \
  --capabilities CAPABILITY_NAMED_IAM

# Prod
aws cloudformation deploy \
  --template-file pipeline/pipeline.yaml \
  --stack-name prod-infra-pipeline \
  --parameter-overrides file://pipeline/params-prod.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### Phase 2: Environment-Neutral Modules
**Goal:** Manifests work for any environment

**Module Manifest Schema:**
```yaml
module:
  name: api-gateway
  enabled: true
  order: 10                    # Explicit ordering
  dependsOn: []                # Dependency list

stack:
  name: api-gateway-stack
  templatePath: aws/api-gateway/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: environment        # From env/*.json
  - key: StageName
    source: environment
  - key: ApiName
    source: format
    value: "${EnvironmentName}-api-gateway"
  - key: VpcId
    source: ssm
    path: /pipeline/${EnvironmentName}/vpc_id

tags:
  - key: Module
    value: api-gateway

changePaths:
  - aws/api-gateway/**
  - pipeline/modules/api-gateway.yml
```

**Parameter Sources:**
- `environment` → from `pipeline/env/{env}.json`
- `ssm` → from SSM Parameter Store
- `value` → static value
- `format` → template string with `${EnvironmentName}`

**Changes:**
1. Update [`pipeline/modules/api-gateway.yml`](pipeline/modules/api-gateway.yml:18)
2. Update [`pipeline/modules/alb.yml`](pipeline/modules/alb.yml:8)
3. Update [`pipeline/modules/ecs.yml`](pipeline/modules/ecs.yml:7)
4. Add `order` and `dependsOn` fields

### Phase 3: Environment Config Files
**Goal:** Centralize environment-specific values

**Create `pipeline/env/dev.json`:**
```json
{
  "EnvironmentName": "dev",
  "StageName": "dev",
  "Region": "ap-south-1",
  "NotificationEmail": "dev-team@example.com"
}
```

**Create `pipeline/env/qa.json`:**
```json
{
  "EnvironmentName": "qa",
  "StageName": "qa",
  "Region": "ap-south-1",
  "NotificationEmail": "qa-team@example.com"
}
```

**Create `pipeline/env/prod.json`:**
```json
{
  "EnvironmentName": "prod",
  "StageName": "prod",
  "Region": "ap-south-1",
  "NotificationEmail": "ops-team@example.com"
}
```

### Phase 4: Enhanced Buildspec
**Goal:** Dependency-aware deployment

**Update [`pipeline/buildspec-deploy.yml`](pipeline/buildspec-deploy.yml:32):**

1. **Load environment config:**
   ```python
   env_config = json.load(open(f'pipeline/env/{environment}.json'))
   ```

2. **Build dependency graph:**
   ```python
   def build_dependency_graph(manifests):
       graph = {}
       for name, manifest in manifests.items():
           deps = manifest.get('module', {}).get('dependsOn', [])
           order = manifest.get('module', {}).get('order', 999)
           graph[name] = {'deps': deps, 'order': order}
       return graph
   ```

3. **Topological sort:**
   ```python
   def resolve_deploy_order(modules_to_deploy, graph):
       # Sort by order, then resolve dependencies
       ordered = []
       visited = set()
       
       def visit(module):
           if module in visited:
               return
           for dep in graph[module]['deps']:
               visit(dep)
           visited.add(module)
           ordered.append(module)
       
       for module in modules_to_deploy:
           visit(module)
       return ordered
   ```

4. **Parameter resolution:**
   ```python
   def resolve_parameter(param, env_config, environment):
       source = param.get('source', 'value')
       
       if source == 'environment':
           key = param['key']
           return env_config.get(key, '')
       elif source == 'ssm':
           path = param['path'].replace('${EnvironmentName}', environment)
           return get_ssm_parameter(path)
       elif source == 'format':
           template = param['value']
           return template.replace('${EnvironmentName}', environment)
       elif source == 'value':
           return param.get('value', '')
   ```

### Phase 5: Approval Stage
**Goal:** Manual approval for qa/prod

**Add to `pipeline/pipeline.yaml`:**
```yaml
- Name: Approval
  Actions:
    - Name: ManualApproval
      ActionTypeId:
        Category: Approval
        Owner: AWS
        Provider: Manual
        Version: '1'
      Configuration:
        CustomData: !Sub |
          Approve deployment to ${EnvironmentName}
          Review changes before proceeding
        NotificationArn: !Ref NotificationTopic
      RunOrder: 1
  # Only run for qa/prod
  Condition: !Not [!Equals [!Ref EnvironmentName, dev]]
```

## Adding New Components

### Example: Adding RDS Module

1. **Create template:**
   ```bash
   mkdir -p aws/rds
   # Create aws/rds/template.yaml
   ```

2. **Create manifest:**
   ```yaml
   # pipeline/modules/rds.yml
   module:
     name: rds
     enabled: true
     order: 5              # Before api-gateway (10)
     dependsOn: []
   
   stack:
     name: rds-stack
     templatePath: aws/rds/template.yaml
     capabilities:
       - CAPABILITY_NAMED_IAM
   
   parameters:
     - key: Environment
       source: environment
     - key: DBName
       source: format
       value: "${EnvironmentName}db"
   
   changePaths:
     - aws/rds/**
     - pipeline/modules/rds.yml
   ```

3. **Commit and push** - pipeline auto-deploys

## Deployment Commands

### Initial Pipeline Setup
```bash
# Deploy dev pipeline
aws cloudformation deploy \
  --template-file pipeline/pipeline.yaml \
  --stack-name dev-infra-pipeline \
  --parameter-overrides file://pipeline/params-dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Deploy qa pipeline
aws cloudformation deploy \
  --template-file pipeline/pipeline.yaml \
  --stack-name qa-infra-pipeline \
  --parameter-overrides file://pipeline/params-qa.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Deploy prod pipeline
aws cloudformation deploy \
  --template-file pipeline/pipeline.yaml \
  --stack-name prod-infra-pipeline \
  --parameter-overrides file://pipeline/params-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

### Manual Module Deployment
```bash
# Deploy specific module to dev
aws codebuild start-build \
  --project-name dev-infra-deploy \
  --environment-variables-override \
    name=DEPLOY_MODULES,value=api-gateway,type=PLAINTEXT

# Deploy multiple modules to qa
aws codebuild start-build \
  --project-name qa-infra-deploy \
  --environment-variables-override \
    name=DEPLOY_MODULES,value=alb,ecs,type=PLAINTEXT
```

## Migration Path

### Step 1: Backup
```bash
cp pipeline/dev-pipeline.yaml pipeline/dev-pipeline.yaml.backup
```

### Step 2: Create Generic Template
```bash
# Rename and parameterize
mv pipeline/dev-pipeline.yaml pipeline/pipeline.yaml
# Edit to add EnvironmentName parameter
```

### Step 3: Update Params Files
```bash
# Add EnvironmentName to each params file
# params-dev.json: "EnvironmentName": "dev"
# params-qa.json: "EnvironmentName": "qa"
# params-prod.json: "EnvironmentName": "prod"
```

### Step 4: Deploy New Pipelines
```bash
# Deploy all three environments
./deploy-pipelines.sh
```

### Step 5: Refactor Modules
```bash
# Update manifests to be environment-neutral
# Add order and dependsOn fields
```

### Step 6: Create Env Configs
```bash
mkdir -p pipeline/env
# Create dev.json, qa.json, prod.json
```

### Step 7: Update Buildspec
```bash
# Enhance with dependency resolution
# Add environment config loading
```

## Success Criteria

- ✅ Single `pipeline.yaml` deployed 3 times (dev/qa/prod)
- ✅ Module manifests have no hardcoded environment values
- ✅ Dependency ordering enforced automatically
- ✅ Approval required for qa/prod deployments
- ✅ Adding new component = 2 files (template + manifest)
- ✅ No pipeline template changes needed for new components

## Rollback Plan

If issues occur:
```bash
# Restore original dev pipeline
aws cloudformation deploy \
  --template-file pipeline/dev-pipeline.yaml.backup \
  --stack-name dev-infra-pipeline \
  --parameter-overrides file://pipeline/params-dev.json \
  --capabilities CAPABILITY_NAMED_IAM