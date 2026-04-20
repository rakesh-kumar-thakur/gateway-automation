# Infra Pipeline Plan

## Current review

Current structure is a good start because infrastructure templates are already separated under [`aws/`](aws/) and deployment logic is grouped under [`pipeline/`](pipeline/). The manifest-driven idea in [`pipeline/modules/api-gateway.yml`](pipeline/modules/api-gateway.yml:5), [`pipeline/modules/alb.yml`](pipeline/modules/alb.yml:8), and [`pipeline/modules/ecs.yml`](pipeline/modules/ecs.yml:7) is the right direction for extensibility.

Main gaps in the current design:

- [`pipeline/dev-pipeline.yaml`](pipeline/dev-pipeline.yaml) is dev-specific and hardcodes names like `dev-infra-pipeline`, `dev-codebuild-deploy-role`, SSM paths under `/pipeline/dev/*`, and artifact bucket naming.
- [`pipeline/modules/api-gateway.yml`](pipeline/modules/api-gateway.yml:18) hardcodes `dev` values, so the same module manifest cannot be reused cleanly for qa and prod.
- Module ordering is only implied by filename comments in [`pipeline/modules/alb.yml`](pipeline/modules/alb.yml:4), which is fragile when more components are added.
- [`pipeline/buildspec-deploy.yml`](pipeline/buildspec-deploy.yml:220) currently deploys all enabled modules because change detection is not really effective in CodeBuild.
- Parameter files exist for three environments, but there is only one actual pipeline template: [`pipeline/params-dev.json`](pipeline/params-dev.json), [`pipeline/params-qa.json`](pipeline/params-qa.json), [`pipeline/params-prod.json`](pipeline/params-prod.json).

## Recommended target design

Use **one reusable pipeline template** for all environments:

- [`pipeline/pipeline.yaml`](pipeline/pipeline.yaml) → one generic CodePipeline/CodeBuild CloudFormation template
- deploy this same template 3 times:
  - `dev-infra-pipeline`
  - `qa-infra-pipeline`
  - `prod-infra-pipeline`

Each stack should differ only by input parameters such as:

- `EnvironmentName` = dev / qa / prod
- `GitHubBranch` = develop / qa / main
- `ApprovalRequired` = false for dev, true for qa/prod if needed
- `NotificationEmail` or SNS target
- optional environment-specific stack config

This is cleaner than maintaining separate templates like [`pipeline/dev-pipeline.yaml`](pipeline/dev-pipeline.yaml).

## Desired pipeline flow

Recommended CodePipeline stages:

1. **Source**
   - GitHub via CodeConnections
   - branch per environment:
     - dev → `develop`
     - qa → `qa`
     - prod → `main`

2. **Validate**
   - run [`cfn-lint`](pipeline/buildspec-deploy.yml:110)
   - validate manifest schema
   - detect dependency graph and impacted modules

3. **Deploy-Shared/Components**
   - deploy modules in dependency order
   - example order:
     - api-gateway
     - alb
     - ecs
   - future components should plug in without changing the pipeline template

4. **Approval** (optional)
   - not needed in dev
   - recommended for qa and prod

5. **Post-Deploy Verification**
   - smoke test / API test / health check
   - keep optional so the framework remains lightweight

## Extensibility model

Keep the pipeline generic and make modules self-describing.

Each component should have:

- infra template under [`aws/component-name/`](aws/)
- module manifest under [`pipeline/modules/`](pipeline/modules/)
- optional environment parameter file if the component needs overrides

Recommended manifest shape:

```yaml
module:
  name: api-gateway
  enabled: true
  order: 10
  dependsOn: []

stack:
  name: api-gateway
  templatePath: aws/api-gateway/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: environment
  - key: StageName
    source: environment
  - key: ApiName
    source: format
    value: "${EnvironmentName}-api-gateway"

changePaths:
  - aws/api-gateway/**
  - pipeline/modules/api-gateway.yml
```

Recommended rules:

- add explicit `order` and/or `dependsOn`
- remove hardcoded `dev` values from manifests
- support dynamic sources such as:
  - `environment`
  - `ssm`
  - `value`
  - `format`
- keep module-specific logic out of the pipeline template

That way, adding a new component becomes:

1. create [`aws/new-component/template.yaml`](aws/new-component/template.yaml)
2. create [`pipeline/modules/new-component.yml`](pipeline/modules/new-component.yml)
3. enable it
4. commit and let the same pipeline process it

## Environment strategy

Use environment-scoped config consistently.

Recommended structure:

```text
pipeline/
  pipeline.yaml
  buildspec-deploy.yml
  params-dev.json
  params-qa.json
  params-prod.json
  modules/
    api-gateway.yml
    alb.yml
    ecs.yml
  env/
    dev.json
    qa.json
    prod.json
```

Suggested responsibility split:

- [`pipeline/params-dev.json`](pipeline/params-dev.json), [`pipeline/params-qa.json`](pipeline/params-qa.json), [`pipeline/params-prod.json`](pipeline/params-prod.json)  
  only for pipeline stack deployment parameters
- `pipeline/env/*.json`  
  for environment values consumed by modules at deployment time
- [`pipeline/modules/*.yml`](pipeline/modules/)  
  only module metadata, dependency, template path, and parameter mapping

## Practical recommendations for your repo

1. Replace [`pipeline/dev-pipeline.yaml`](pipeline/dev-pipeline.yaml) with one generic [`pipeline/pipeline.yaml`](pipeline/pipeline.yaml).
2. Refactor manifests so they do not contain fixed dev values like in [`pipeline/modules/api-gateway.yml`](pipeline/modules/api-gateway.yml:21).
3. Add `order` or `dependsOn` to all manifests instead of relying on filename comments.
4. Store environment-specific values in environment config or SSM paths like:
   - `/pipeline/dev/...`
   - `/pipeline/qa/...`
   - `/pipeline/prod/...`
5. Update [`pipeline/buildspec-deploy.yml`](pipeline/buildspec-deploy.yml) so it:
   - reads environment-aware config
   - resolves dependency order
   - deploys selected modules in deterministic order
6. Keep test stages optional and attach them mainly to qa/prod first.

## Minimal next implementation plan

Phase 1:
- create one reusable [`pipeline/pipeline.yaml`](pipeline/pipeline.yaml)
- keep current module structure
- parameterize all dev-specific names

Phase 2:
- refactor manifests to be environment-neutral
- add `dependsOn` / `order`
- introduce `pipeline/env/dev.json`, `pipeline/env/qa.json`, `pipeline/env/prod.json`

Phase 3:
- improve deploy script to compute impacted modules plus dependencies
- add manual approval before prod deploy
- add smoke tests after deploy

## Recommendation summary

Best long-term approach:

- **one generic CloudFormation pipeline template**
- **three pipeline stacks: dev, qa, prod**
- **manifest-driven modules**
- **environment-neutral module definitions**
- **dependency-based deployment order**
- **easy onboarding of new components by adding one template + one manifest**

This gives you a scalable infra pipeline framework using CloudFormation and AWS CodePipeline without adding heavy documentation.