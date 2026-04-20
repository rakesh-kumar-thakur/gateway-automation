# Simplified POC Pipeline Deployment Guide

This is a minimal version of the pipeline for quick POC testing. It includes only:
- ✅ Source stage (GitHub)
- ✅ Deploy stage (CodeBuild)
- ✅ EventBridge auto-trigger on push
- ❌ No test stages
- ❌ No SNS notifications
- ❌ No CloudWatch alarms

## Prerequisites

1. **GitHub Connection**: You need a CodeStar Connection to GitHub
   - Go to AWS Console → Developer Tools → Connections
   - Create a connection to GitHub
   - Note the ARN (format: `arn:aws:codeconnections:region:account:connection/xxxxx`)

## Deployment Steps

### Step 1: Deploy the Pipeline

```bash
aws cloudformation create-stack \
  --stack-name dev-pipeline-simple \
  --template-body file://pipeline/dev-pipeline-simple.yaml \
  --parameters \
    ParameterKey=GitHubOwner,ParameterValue=YOUR_GITHUB_USERNAME \
    ParameterKey=GitHubRepo,ParameterValue=YOUR_REPO_NAME \
    ParameterKey=GitHubBranch,ParameterValue=develop \
    ParameterKey=GitHubConnectionArn,ParameterValue=YOUR_CONNECTION_ARN \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

**Replace:**
- `YOUR_GITHUB_USERNAME` - Your GitHub username or organization
- `YOUR_REPO_NAME` - Your repository name
- `YOUR_CONNECTION_ARN` - The CodeStar Connection ARN from prerequisites

### Step 2: Wait for Stack Creation

```bash
aws cloudformation wait stack-create-complete \
  --stack-name dev-pipeline-simple \
  --region ap-south-1
```

### Step 3: Verify Pipeline

```bash
# Get pipeline URL
aws cloudformation describe-stacks \
  --stack-name dev-pipeline-simple \
  --query 'Stacks[0].Outputs[?OutputKey==`PipelineConsoleUrl`].OutputValue' \
  --output text \
  --region ap-south-1
```

Open the URL in your browser to see the pipeline.

## How It Works

### Auto-Trigger
The pipeline automatically triggers when you push to the `develop` branch:

1. Push code to GitHub develop branch
2. EventBridge detects the push event
3. Pipeline starts automatically
4. CodeBuild deploys enabled modules

### Manual Trigger
You can also trigger manually from AWS Console:
1. Go to CodePipeline console
2. Select `dev-infra-pipeline`
3. Click "Release change"

### Module Configuration

Modules are configured in `pipeline/modules/*.yml`:

**Example: `pipeline/modules/api-gateway.yml`**
```yaml
module:
  name: api-gateway
  enabled: true  # Set to false to skip deployment

stack:
  name: api-gateway-stack
  templatePath: aws/api-gateway/template.yaml

parameters:
  - key: Environment
    source: value
    value: dev
```

### Deploy Specific Modules Only

To deploy only specific modules, update the module manifest:
- Set `enabled: true` for modules you want to deploy
- Set `enabled: false` for modules you want to skip

Or override via environment variable in CodeBuild:
```yaml
DEPLOY_MODULES: "api-gateway,alb"  # Comma-separated list
```

## Troubleshooting

### Pipeline Not Triggering Automatically

**Check EventBridge Rule:**
```bash
aws events describe-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1
```

**Verify the rule is ENABLED and matches your branch name.**

### Deployment Failures

**Check CodeBuild Logs:**
1. Go to CodeBuild console
2. Select `dev-infra-deploy` project
3. View build history and logs

**Common Issues:**
- **Packaging errors**: Check that swagger.yaml exists in aws/api-gateway/
- **Permission errors**: Verify CodeBuild role has necessary permissions
- **Template errors**: Run `cfn-lint` locally to validate templates

### Manual Pipeline Execution

If auto-trigger isn't working, manually trigger:

```bash
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

## Cleanup

To delete everything:

```bash
# Delete the pipeline stack
aws cloudformation delete-stack \
  --stack-name dev-pipeline-simple \
  --region ap-south-1

# Delete deployed infrastructure stacks
aws cloudformation delete-stack \
  --stack-name api-gateway-stack \
  --region ap-south-1

# Note: S3 artifact bucket is retained by default
# Delete manually if needed:
aws s3 rb s3://YOUR_ACCOUNT_ID-dev-pipeline-artifacts --force
```

## Next Steps

Once POC is working:
1. Add test stages back (see `dev-pipeline.yaml` for full version)
2. Add SNS notifications
3. Add CloudWatch alarms
4. Deploy QA and Prod pipelines

## File Structure

```
pipeline/
├── dev-pipeline-simple.yaml      # Simplified pipeline (this POC)
├── dev-pipeline.yaml             # Full pipeline with tests
├── buildspec-deploy.yml          # Deployment logic
└── modules/
    ├── api-gateway.yml           # API Gateway config
    ├── alb.yml                   # ALB config
    └── ecs.yml                   # ECS config
```

## Support

If you encounter issues:
1. Check CodeBuild logs for detailed error messages
2. Verify all prerequisites are met
3. Ensure GitHub connection is active
4. Check IAM permissions

---
Made with Bob - Simplified POC Version