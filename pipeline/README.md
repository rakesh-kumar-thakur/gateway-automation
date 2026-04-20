# Infrastructure Automation Pipeline

## Quick Start

This directory contains the complete CI/CD pipeline infrastructure for deploying AWS resources across multiple environments (Dev, QA, Production) in the **ap-south-1** region.

## 🎯 Key Features

✅ **Separate Pipelines per Environment** - Independent dev, qa, and prod pipelines  
✅ **Automatic Change Detection** - Deploys only modified modules  
✅ **Manual Approval for Production** - Safety gate before prod deployments  
✅ **Comprehensive Testing** - API, integration, and load tests  
✅ **SNS Notification Ready** - Infrastructure provisioned for future alerts  
✅ **Single Region Deployment** - All resources in ap-south-1 (Mumbai)

## 📁 Directory Structure

```
pipeline/
├── README.md                          # This file
├── DEPLOYMENT.md                      # Detailed deployment guide
│
├── dev-pipeline.yaml                  # Dev environment pipeline
├── qa-pipeline.yaml                   # QA environment pipeline  
├── prod-pipeline.yaml                 # Production pipeline (with approval)
│
├── params-dev.json                    # Dev parameters
├── params-qa.json                     # QA parameters
├── params-prod.json                   # Production parameters
│
├── buildspec-deploy.yml               # Deployment with change detection
├── buildspec-api-tests.yml            # API endpoint tests
├── buildspec-integration-tests.yml    # Integration tests
├── buildspec-load-tests.yml           # Load/performance tests
│
└── modules/                           # Module manifests
    ├── api-gateway.yml                # API Gateway module
    ├── alb.yml                        # Application Load Balancer
    └── ecs.yml                        # ECS cluster and services
```

## 🚀 Quick Deployment

### Deploy All Pipelines

```bash
# Deploy Dev pipeline
aws cloudformation deploy \
  --template-file pipeline/dev-pipeline.yaml \
  --stack-name dev-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Deploy QA pipeline
aws cloudformation deploy \
  --template-file pipeline/qa-pipeline.yaml \
  --stack-name qa-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-qa.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Deploy Production pipeline
aws cloudformation deploy \
  --template-file pipeline/prod-pipeline.yaml \
  --stack-name prod-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

### View Pipeline URLs

```bash
# Get all pipeline URLs
for env in dev qa prod; do
  echo "=== ${env^^} Pipeline ==="
  aws cloudformation describe-stacks \
    --stack-name ${env}-infra-pipeline-stack \
    --query "Stacks[0].Outputs[?OutputKey=='PipelineConsoleUrl'].OutputValue" \
    --output text \
    --region ap-south-1
  echo
done
```

## 🔄 Pipeline Flow

### Development Pipeline
```
GitHub (develop) → Deploy Changed Modules → API Tests → Integration Tests → Load Tests
```

### QA Pipeline
```
GitHub (qa) → Deploy Changed Modules → API Tests → Integration Tests → Load Tests
```

### Production Pipeline
```
GitHub (main) → ⚠️ MANUAL APPROVAL → Deploy Changed Modules → API Tests → Integration Tests → Load Tests
```

## 📋 Configuration

### Branch Mapping

| Environment | Branch    | Auto-Deploy | Approval Required |
|-------------|-----------|-------------|-------------------|
| Dev         | `develop` | ✅ Yes      | ❌ No             |
| QA          | `qa`      | ✅ Yes      | ❌ No             |
| Production  | `main`    | ✅ Yes      | ✅ **YES**        |

### Module Status

| Module      | Enabled | Description                    |
|-------------|---------|--------------------------------|
| api-gateway | ✅ Yes  | REST API with Swagger          |
| alb         | ❌ No   | Application Load Balancer      |
| ecs         | ❌ No   | ECS Cluster and Services       |

To enable a module, edit `pipeline/modules/<module>.yml` and set `enabled: true`.

## 🧪 Testing

Each pipeline includes three automated test stages:

1. **API Tests** - Validates endpoints, response codes, CORS
2. **Integration Tests** - Cross-service communication, AWS connectivity
3. **Load Tests** - Performance under load, response time thresholds

Test results are available in CodeBuild logs and as HTML reports in artifacts.

## 🔔 Notifications (Optional Setup)

SNS topics are provisioned but not subscribed by default:

```bash
# Subscribe to production approval notifications
APPROVAL_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name prod-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApprovalTopicArn'].OutputValue" \
  --output text \
  --region ap-south-1)

aws sns subscribe \
  --topic-arn $APPROVAL_TOPIC \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region ap-south-1
```

## 🎛️ Change Detection

The pipeline automatically detects which modules have changed:

1. Compares git diff between commits
2. Matches changed files against module `changePaths`
3. Deploys only affected modules

### Manual Override

Force deployment of specific modules:

```bash
# Set in CodeBuild environment variables
DEPLOY_MODULES=api-gateway,alb
```

## 📊 Monitoring

### View Pipeline Status

```bash
# List recent executions
aws codepipeline list-pipeline-executions \
  --pipeline-name dev-infra-pipeline \
  --max-results 5 \
  --region ap-south-1
```

### View Build Logs

```bash
# Get latest build
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name dev-infra-deploy \
  --max-items 1 \
  --query 'ids[0]' \
  --output text \
  --region ap-south-1)

# View logs
aws codebuild batch-get-builds \
  --ids $BUILD_ID \
  --region ap-south-1
```

### CloudWatch Alarms

Each pipeline has a CloudWatch alarm for failures:
- `dev-infra-pipeline-failure`
- `qa-infra-pipeline-failure`
- `prod-infra-pipeline-failure`

## 🔧 Troubleshooting

### Pipeline Not Triggering

Check EventBridge rule:
```bash
aws events describe-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1
```

Manually trigger:
```bash
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

### Module Not Deploying

1. Verify module is enabled in `pipeline/modules/<module>.yml`
2. Check if changed files match `changePaths`
3. Review CodeBuild logs for errors
4. Use manual override if needed

### Test Failures

1. Check API endpoint exists in CloudFormation outputs
2. Verify security groups allow traffic
3. Review test logs in CodeBuild
4. Adjust test thresholds if needed

## 📚 Documentation

- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Complete deployment guide with detailed instructions
- **Module Manifests** - See `pipeline/modules/*.yml` for module configurations
- **BuildSpec Files** - See `buildspec-*.yml` for build and test configurations

## 🔐 Security

- All artifact buckets use AES256 encryption
- IAM roles follow least privilege principle
- Public access blocked on all S3 buckets
- Manual approval required for production
- CloudFormation drift detection recommended

## 🧹 Cleanup

To remove all pipelines:

```bash
# Delete pipeline stacks
for env in dev qa prod; do
  aws cloudformation delete-stack \
    --stack-name ${env}-infra-pipeline-stack \
    --region ap-south-1
done

# Manually delete artifact buckets if needed
aws s3 rb s3://381492219337-dev-pipeline-artifacts --force
aws s3 rb s3://381492219337-qa-pipeline-artifacts --force
aws s3 rb s3://381492219337-prod-pipeline-artifacts --force
```

## 📝 Workflow Example

### Deploying a New Feature

```bash
# 1. Create feature branch
git checkout -b feature/new-endpoint develop

# 2. Make changes
vim aws/api-gateway/swagger.yaml

# 3. Commit and push
git add .
git commit -m "Add new API endpoint"
git push origin feature/new-endpoint

# 4. Create PR to develop
# 5. Merge PR → Dev pipeline auto-triggers
# 6. After testing, merge develop → qa
# 7. After QA validation, merge qa → main
# 8. Approve production deployment in AWS Console
```

## 🤝 Adding New AWS Components

The pipeline is designed to be modular and extensible. You can easily add new AWS services (Lambda, DynamoDB, S3, RDS, etc.) without modifying pipeline templates.

### Quick Steps:
1. Create CloudFormation template in `aws/<component>/template.yaml`
2. Create module manifest in `pipeline/modules/<component>.yml`
3. Set `enabled: true` and define `changePaths`
4. Commit and push to trigger deployment

**📖 See [ADDING_NEW_COMPONENTS.md](./ADDING_NEW_COMPONENTS.md) for detailed examples including:**
- Lambda functions
- DynamoDB tables
- S3 buckets
- RDS databases
- Cross-component references
- Dependency management

## 📚 Documentation

- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Complete deployment guide with detailed instructions
- **[ADDING_NEW_COMPONENTS.md](./ADDING_NEW_COMPONENTS.md)** - Step-by-step guide for adding Lambda, DynamoDB, S3, RDS, etc.
- **Module Manifests** - See `pipeline/modules/*.yml` for module configurations
- **BuildSpec Files** - See `buildspec-*.yml` for build and test configurations

##  Support

For issues:
1. Check CloudWatch Logs
2. Review CodeBuild logs
3. Verify IAM permissions
4. Consult [DEPLOYMENT.md](./DEPLOYMENT.md) or [ADDING_NEW_COMPONENTS.md](./ADDING_NEW_COMPONENTS.md)

## 🎯 Roadmap

Future enhancements:
- [ ] Enable SNS email notifications
- [ ] Add Slack integration
- [ ] Implement blue-green deployments
- [ ] Add canary deployments for production
- [ ] Multi-region support
- [ ] Automated rollback on test failures

---

**Region**: ap-south-1 (Mumbai)  
**Version**: 1.0  
**Last Updated**: 2026-04-20