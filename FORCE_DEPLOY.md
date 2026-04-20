# Force Deploy API Gateway

## Problem
The pipeline's change detection found "No modules to deploy" because no files in `aws/api-gateway/**` were modified.

## Solution: Force Deploy API Gateway

### Option 1: Use Environment Variable Override (Recommended)

Trigger the pipeline with a manual override to deploy API Gateway:

```bash
# Start pipeline execution with override
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

Then immediately update the CodeBuild environment variable:

1. Go to AWS Console → CodePipeline → dev-infra-pipeline
2. Wait for the Deploy stage to start
3. Click "Stop execution" 
4. Go to CodeBuild → dev-infra-deploy → Edit → Environment
5. Add environment variable:
   - Name: `DEPLOY_MODULES`
   - Value: `api-gateway`
6. Save
7. Restart pipeline

### Option 2: Modify API Gateway File (Easier)

Make a small change to trigger deployment:

```bash
# Add a comment to trigger change detection
echo "# Force deploy" >> aws/api-gateway/swagger.yaml

# Commit and push
git add aws/api-gateway/swagger.yaml
git commit -m "Force deploy API Gateway"
git push origin develop

# Trigger pipeline
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

This will:
1. Detect changes in `aws/api-gateway/swagger.yaml`
2. Deploy the API Gateway module
3. Create the `dev-api-gateway-stack`

### Option 3: Deploy API Gateway Directly (Fastest)

Skip the pipeline and deploy directly:

```bash
# Navigate to project root
cd c:/Users/0048EQ744/Kiro/Infra-automation-sample

# Package the template (uploads swagger.yaml to S3)
aws cloudformation package \
  --template-file aws/api-gateway/template.yaml \
  --s3-bucket 381492219337-dev-pipeline-artifacts \
  --s3-prefix api-gateway \
  --output-template-file /tmp/packaged-api-gateway.yaml \
  --region ap-south-1

# Deploy the stack
aws cloudformation deploy \
  --template-file /tmp/packaged-api-gateway.yaml \
  --stack-name dev-api-gateway-stack \
  --parameter-overrides \
      Environment=dev \
      StageName=dev \
      ApiName=dev-api-gateway \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# Get the API endpoint
aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text \
  --region ap-south-1
```

## Recommended Approach

**Use Option 2** - it's the simplest and tests the full workflow:

```bash
# One-liner to force deploy
echo "# Deploy $(date)" >> aws/api-gateway/swagger.yaml && git add aws/api-gateway/swagger.yaml && git commit -m "Force deploy API Gateway" && git push origin develop && aws codepipeline start-pipeline-execution --name dev-infra-pipeline --region ap-south-1
```

## Verify Deployment

After running any option above, verify:

```bash
# Check stack exists
aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --region ap-south-1

# Get API endpoint
aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text \
  --region ap-south-1

# Test the API
curl $(aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text \
  --region ap-south-1)
```

## Why This Happened

The change detection logic compares git commits to find which files changed. On the first pipeline run after setup:
- No previous commit to compare against
- Or no files in `aws/api-gateway/**` were modified
- Result: "No modules to deploy"

## Future Deployments

After this initial deployment, the workflow will work correctly:

```bash
# 1. Edit swagger
vim aws/api-gateway/swagger.yaml

# 2. Commit and push
git add aws/api-gateway/swagger.yaml
git commit -m "Add new endpoint"
git push origin develop

# 3. Pipeline auto-detects changes and deploys ✅
```

## Quick Command Reference

```bash
# Force deploy via file change (recommended)
echo "# Deploy $(date)" >> aws/api-gateway/swagger.yaml
git add aws/api-gateway/swagger.yaml
git commit -m "Force deploy"
git push origin develop
aws codepipeline start-pipeline-execution --name dev-infra-pipeline --region ap-south-1

# Check deployment status
aws codepipeline get-pipeline-state --name dev-infra-pipeline --region ap-south-1

# View build logs
aws logs tail /aws/codebuild/dev-infra-deploy --follow --region ap-south-1

# Verify API Gateway created
aws cloudformation describe-stacks --stack-name dev-api-gateway-stack --region ap-south-1