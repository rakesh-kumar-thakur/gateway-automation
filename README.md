# AWS Infra Automation

Modular CloudFormation infrastructure with a generic CodePipeline orchestrator.

## Structure

```
aws/                    # Core AWS resources (no pipeline logic)
  api-gateway/          # API Gateway + Lambda endpoints
  alb/                  # ALB (disabled - stub)
  ecs/                  # ECS (disabled - stub)

pipeline/               # CI/CD only (no AWS resource logic)
  codepipeline.yaml     # Pipeline stack
  buildspec.yml         # Generic build orchestrator
  params.json           # Pipeline deploy parameters
  modules/              # One manifest per module
  scripts/              # deploy_module.py, generate_cfn.py
```

## First-time setup

### 1. Create GitHub CodeStar Connection
AWS Console → Developer Tools → Connections → Create connection → GitHub

### 2. Update pipeline/params.json
Fill in `GitHubOwner`, `GitHubRepo`, `GitHubConnectionArn`.

### 3. Deploy the pipeline stack
```bash
aws cloudformation deploy \
  --template-file pipeline/codepipeline.yaml \
  --stack-name prod-infra-pipeline \
  --parameter-overrides file://pipeline/params.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

After this, every push to `main` triggers the pipeline automatically.

## Adding a new module (e.g. ALB)

1. Set `enabled: true` in `pipeline/modules/alb.yml`
2. Fill in `aws/alb/template.yaml`
3. Push — pipeline detects the change and deploys only ALB

## Deploying a single module manually

```bash
# Via AWS CLI (triggers CodeBuild directly)
aws codebuild start-build \
  --project-name prod-infra-deploy \
  --environment-variables-override name=DEPLOY_MODULES,value=api-gateway,type=PLAINTEXT

# Locally
DEPLOY_MODULES=api-gateway python pipeline/scripts/deploy_module.py
```
