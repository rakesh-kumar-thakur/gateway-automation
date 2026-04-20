# Multi-Environment Pipeline Deployment Guide

## Overview

This infrastructure automation solution provides separate CI/CD pipelines for **Dev**, **QA**, and **Production** environments in the **ap-south-1** region. Each pipeline automatically detects changed modules and deploys only those changes, with comprehensive testing and optional notifications.

## Architecture

### Pipeline Strategy
- **Separate Pipelines**: Independent pipelines per environment (dev-pipeline, qa-pipeline, prod-pipeline)
- **Single Region**: All deployments target ap-south-1 (Mumbai)
- **Change Detection**: Automatically deploys only modified modules
- **Automated Testing**: API tests, integration tests, and load tests after each deployment
- **Manual Approval**: Production deployments require manual approval before proceeding

### Pipeline Stages

#### Development Pipeline (`dev-pipeline.yaml`)
1. **Source** - Monitors `develop` branch
2. **Deploy** - Auto-deploys changed modules
3. **Test** - Runs API, integration, and load tests

#### QA Pipeline (`qa-pipeline.yaml`)
1. **Source** - Monitors `qa` branch
2. **Deploy** - Auto-deploys changed modules
3. **Test** - Runs API, integration, and load tests

#### Production Pipeline (`prod-pipeline.yaml`)
1. **Source** - Monitors `main` branch
2. **Manual Approval** - ⚠️ Requires manual approval before deployment
3. **Deploy** - Deploys changed modules after approval
4. **Test** - Runs API, integration, and load tests

## Prerequisites

### AWS Resources Required
1. **GitHub Connection**: CodeStar/CodeConnections connection to GitHub
   - Current ARN: `arn:aws:codeconnections:ap-south-1:381492219337:connection/7a96c5e3-3fe4-443e-99c3-881818fa83c4`

2. **IAM Permissions**: Deploying user needs:
   - CloudFormation full access
   - CodePipeline full access
   - CodeBuild full access
   - S3 access for artifact buckets
   - IAM role creation permissions
   - SNS topic creation permissions

### Git Branch Structure
- `develop` → Dev environment
- `qa` → QA environment
- `main` → Production environment

## Deployment Instructions

### Initial Setup

#### 1. Deploy Development Pipeline

```bash
# Navigate to project root
cd /path/to/Infra-automation-sample

# Deploy dev pipeline
aws cloudformation deploy \
  --template-file pipeline/dev-pipeline.yaml \
  --stack-name dev-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Get pipeline URL
aws cloudformation describe-stacks \
  --stack-name dev-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineConsoleUrl'].OutputValue" \
  --output text \
  --region ap-south-1
```

#### 2. Deploy QA Pipeline

```bash
# Deploy QA pipeline
aws cloudformation deploy \
  --template-file pipeline/qa-pipeline.yaml \
  --stack-name qa-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-qa.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Get pipeline URL
aws cloudformation describe-stacks \
  --stack-name qa-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineConsoleUrl'].OutputValue" \
  --output text \
  --region ap-south-1
```

#### 3. Deploy Production Pipeline

```bash
# Deploy production pipeline
aws cloudformation deploy \
  --template-file pipeline/prod-pipeline.yaml \
  --stack-name prod-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Get pipeline URL
aws cloudformation describe-stacks \
  --stack-name prod-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineConsoleUrl'].OutputValue" \
  --output text \
  --region ap-south-1
```

### Setting Up Approval Notifications (Optional)

To receive email notifications for production approvals:

```bash
# Get the approval SNS topic ARN
APPROVAL_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name prod-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApprovalTopicArn'].OutputValue" \
  --output text \
  --region ap-south-1)

# Subscribe your email
aws sns subscribe \
  --topic-arn $APPROVAL_TOPIC \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region ap-south-1

# Confirm subscription via email
```

## Module Configuration

### Enabling/Disabling Modules

Modules are configured in `pipeline/modules/*.yml`. Each module has an `enabled` flag:

```yaml
module:
  name: api-gateway
  enabled: true  # Set to false to disable
```

### Current Modules

1. **API Gateway** (`pipeline/modules/api-gateway.yml`)
   - Status: Enabled
   - Deploys REST API with Swagger definition
   - Change paths: `aws/api-gateway/**`

2. **ALB** (`pipeline/modules/alb.yml`)
   - Status: Disabled (set `enabled: true` to activate)
   - Deploys Application Load Balancer
   - Change paths: `aws/alb/**`

3. **ECS** (`pipeline/modules/ecs.yml`)
   - Status: Disabled (set `enabled: true` to activate)
   - Deploys ECS cluster and services
   - Change paths: `aws/ecs/**`

### Adding a New Module

1. Create module manifest: `pipeline/modules/my-module.yml`

```yaml
module:
  name: my-module
  description: My new module
  enabled: true

stack:
  name: my-module-stack
  templatePath: aws/my-module/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: ssm
    path: /pipeline/{env}/environment

tags:
  - key: ManagedBy
    value: CodePipeline
  - key: Module
    value: my-module

changePaths:
  - aws/my-module/**
  - pipeline/modules/my-module.yml
```

2. Create CloudFormation template: `aws/my-module/template.yaml`

3. Commit and push to trigger deployment

## Change Detection

The pipeline automatically detects which modules have changed by:

1. Comparing git diff between commits
2. Matching changed files against module `changePaths`
3. Deploying only modules with matching changes

### Manual Override

To force deployment of specific modules:

```bash
# In CodeBuild project, set environment variable:
DEPLOY_MODULES=api-gateway,alb

# Or trigger manually via AWS Console:
# CodeBuild → Project → Start build → Override environment variables
```

## Testing

### Test Stages

Each pipeline includes three test stages:

1. **API Tests** (`buildspec-api-tests.yml`)
   - Validates API endpoints are accessible
   - Checks response codes and headers
   - Verifies CORS configuration

2. **Integration Tests** (`buildspec-integration-tests.yml`)
   - Tests cross-service communication
   - Validates data flow between components
   - Checks AWS service connectivity

3. **Load Tests** (`buildspec-load-tests.yml`)
   - Simulates concurrent users
   - Measures response times under load
   - Validates performance thresholds

### Test Configuration

Adjust load test parameters in `buildspec-load-tests.yml`:

```yaml
env:
  variables:
    LOAD_TEST_DURATION: "60"  # seconds
    LOAD_TEST_USERS: "10"     # concurrent users
    LOAD_TEST_REQUESTS: "100" # total requests
```

## Notifications (Future Enhancement)

SNS topics are provisioned for future notification integration:

### Available Topics

- **Dev**: `dev-pipeline-notifications`
- **QA**: `qa-pipeline-notifications`
- **Prod**: `prod-pipeline-notifications`
- **Prod Approval**: `prod-pipeline-approval-required`

### Enabling Notifications

To enable notifications, subscribe to the topics:

```bash
# Get notification topic ARN
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name dev-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='NotificationTopicArn'].OutputValue" \
  --output text \
  --region ap-south-1)

# Subscribe email
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint team@example.com \
  --region ap-south-1

# Or subscribe Slack (requires Lambda integration)
# Or subscribe to EventBridge for custom workflows
```

## Workflow Examples

### Deploying a Change to Dev

```bash
# 1. Create feature branch from develop
git checkout develop
git pull
git checkout -b feature/my-change

# 2. Make changes to module
vim aws/api-gateway/swagger.yaml

# 3. Commit and push
git add .
git commit -m "Add new API endpoint"
git push origin feature/my-change

# 4. Create PR to develop branch
# 5. Merge PR → Pipeline auto-triggers
# 6. Monitor pipeline in AWS Console
```

### Promoting to QA

```bash
# 1. Merge develop to qa branch
git checkout qa
git pull
git merge develop
git push origin qa

# 2. Pipeline auto-triggers for QA
# 3. Tests run automatically
```

### Promoting to Production

```bash
# 1. Merge qa to main branch
git checkout main
git pull
git merge qa
git push origin main

# 2. Pipeline triggers and waits at approval gate
# 3. Review changes in GitHub
# 4. Approve in AWS Console:
#    CodePipeline → prod-infra-pipeline → Review
# 5. Deployment proceeds after approval
# 6. Tests run automatically
```

## Monitoring and Troubleshooting

### Viewing Pipeline Status

```bash
# List pipeline executions
aws codepipeline list-pipeline-executions \
  --pipeline-name dev-infra-pipeline \
  --region ap-south-1

# Get execution details
aws codepipeline get-pipeline-execution \
  --pipeline-name dev-infra-pipeline \
  --pipeline-execution-id <execution-id> \
  --region ap-south-1
```

### Viewing Build Logs

```bash
# List builds
aws codebuild list-builds-for-project \
  --project-name dev-infra-deploy \
  --region ap-south-1

# Get build logs
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region ap-south-1
```

### Common Issues

#### Pipeline Not Triggering

**Cause**: EventBridge rule not detecting changes

**Solution**:
```bash
# Check EventBridge rule status
aws events describe-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1

# Manually trigger pipeline
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

#### Module Not Deploying

**Cause**: Module disabled or change paths not matching

**Solution**:
1. Check module manifest: `enabled: true`
2. Verify change paths match modified files
3. Use manual override: `DEPLOY_MODULES=module-name`

#### Test Failures

**Cause**: API endpoint not available or performance issues

**Solution**:
1. Check CloudFormation stack outputs
2. Verify API Gateway deployment
3. Review test logs in CodeBuild
4. Adjust test thresholds if needed

## Cleanup

### Deleting a Pipeline

```bash
# Delete dev pipeline
aws cloudformation delete-stack \
  --stack-name dev-infra-pipeline-stack \
  --region ap-south-1

# Note: Artifact buckets are retained by default
# Delete manually if needed:
aws s3 rb s3://381492219337-dev-pipeline-artifacts --force
```

### Deleting All Pipelines

```bash
# Delete all pipeline stacks
for env in dev qa prod; do
  aws cloudformation delete-stack \
    --stack-name ${env}-infra-pipeline-stack \
    --region ap-south-1
done

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name dev-infra-pipeline-stack \
  --region ap-south-1
```

## Best Practices

1. **Branch Protection**: Enable branch protection on `main` and `qa` branches
2. **Code Review**: Require PR reviews before merging
3. **Testing**: Always test in Dev before promoting to QA
4. **Approval**: Review changes carefully before approving production deployments
5. **Monitoring**: Set up CloudWatch alarms for pipeline failures
6. **Notifications**: Subscribe to SNS topics for important events
7. **Rollback**: Keep previous versions in S3 for quick rollback if needed

## Support

For issues or questions:
1. Check CloudWatch Logs for detailed error messages
2. Review CodeBuild build logs
3. Verify IAM permissions
4. Check module manifests for configuration errors

## Version History

- **v1.0** - Initial multi-environment pipeline setup
  - Separate pipelines per environment
  - Change detection and selective deployment
  - Automated testing (API, integration, load)
  - Manual approval for production
  - SNS notification infrastructure