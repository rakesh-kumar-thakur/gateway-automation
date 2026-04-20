# Troubleshooting Guide

## Issue 1: API Gateway Not Created

### Diagnosis Steps

Run these commands to check the status:

```bash
# 1. Check if pipeline executed
aws codepipeline list-pipeline-executions \
  --pipeline-name dev-infra-pipeline \
  --max-results 1 \
  --region ap-south-1

# 2. Check if API Gateway stack exists
aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --region ap-south-1

# 3. Check CodeBuild logs
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name dev-infra-deploy \
  --max-items 1 \
  --query 'ids[0]' \
  --output text \
  --region ap-south-1)

aws logs tail /aws/codebuild/dev-infra-deploy --follow
```

### Solution: Manually Trigger Pipeline

The pipeline needs to run at least once to deploy API Gateway:

```bash
# Trigger the pipeline manually
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

**Monitor the execution:**
1. Go to AWS Console → CodePipeline → dev-infra-pipeline
2. Watch it progress through: Source → Deploy → Test
3. Wait 5-10 minutes for completion

**After completion, verify API Gateway:**
```bash
aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --query "Stacks[0].Outputs" \
  --region ap-south-1
```

---

## Issue 2: Pipeline Not Auto-Triggering on Push

### Root Cause

EventBridge rule needs the GitHub connection to be properly configured and the repository to send webhook events.

### Solution Steps

#### Step 1: Verify EventBridge Rule

```bash
# Check if rule exists and is enabled
aws events describe-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1

# Output should show: "State": "ENABLED"
```

If disabled, enable it:
```bash
aws events enable-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1
```

#### Step 2: Verify GitHub Connection

```bash
# Check connection status
aws codeconnections get-connection \
  --connection-arn arn:aws:codeconnections:ap-south-1:381492219337:connection/7a96c5e3-3fe4-443e-99c3-881818fa83c4 \
  --region ap-south-1

# Status should be "AVAILABLE"
```

If status is "PENDING", you need to complete the connection:
1. Go to AWS Console → Developer Tools → Connections
2. Find your connection
3. Click "Update pending connection"
4. Complete GitHub authorization

#### Step 3: Configure Source Action to Detect Changes

The pipeline Source action must have `DetectChanges: true`. Let's verify:

```bash
# Get pipeline definition
aws codepipeline get-pipeline \
  --name dev-infra-pipeline \
  --region ap-south-1 \
  --query 'pipeline.stages[0].actions[0].configuration.DetectChanges'

# Should return: "true"
```

#### Step 4: Test Auto-Trigger

After verifying above, test the trigger:

```bash
# Make a change to swagger file
echo "# Test change" >> aws/api-gateway/swagger.yaml

# Commit and push to develop branch
git add aws/api-gateway/swagger.yaml
git commit -m "Test auto-trigger"
git push origin develop

# Wait 1-2 minutes, then check if pipeline started
aws codepipeline list-pipeline-executions \
  --pipeline-name dev-infra-pipeline \
  --max-results 1 \
  --region ap-south-1
```

#### Step 5: Alternative - Use GitHub Webhook (If EventBridge Not Working)

If EventBridge continues to have issues, you can set up a GitHub webhook:

1. **In GitHub:**
   - Go to your repository → Settings → Webhooks
   - Click "Add webhook"
   - Payload URL: Get from AWS Console (CodePipeline → Settings → Webhook URL)
   - Content type: `application/json`
   - Events: Select "Just the push event"
   - Active: ✓

2. **Update Pipeline to use Webhook instead of EventBridge:**

This requires modifying the pipeline, but for now, **manual triggering works**:

```bash
# Manual trigger command (use this until auto-trigger is fixed)
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

---

## Quick Fix: Manual Workflow

Until auto-trigger is fully working, use this workflow:

```bash
# 1. Make changes to API Gateway
vim aws/api-gateway/swagger.yaml

# 2. Commit and push
git add aws/api-gateway/swagger.yaml
git commit -m "Add new endpoint"
git push origin develop

# 3. Manually trigger pipeline
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1

# 4. Monitor execution
aws codepipeline get-pipeline-state \
  --name dev-infra-pipeline \
  --region ap-south-1
```

---

## Common Issues and Solutions

### Issue: "No changes detected, skipping deployment"

**Cause:** No files matching `changePaths` were modified.

**Solution:** Ensure you're modifying files in `aws/api-gateway/**`

```bash
# Check what files changed
git diff HEAD~1 HEAD --name-only

# Should show files like:
# aws/api-gateway/swagger.yaml
# aws/api-gateway/template.yaml
```

### Issue: Pipeline fails at Deploy stage

**Cause:** CloudFormation deployment error.

**Solution:** Check CodeBuild logs:

```bash
# Get latest build logs
aws logs tail /aws/codebuild/dev-infra-deploy \
  --follow \
  --region ap-south-1
```

Common errors:
- **IAM permissions**: CodeBuild role needs CloudFormation permissions
- **Template syntax**: Validate with `cfn-lint aws/api-gateway/template.yaml`
- **Parameter mismatch**: Check SSM parameters exist

### Issue: Tests fail after deployment

**Cause:** API Gateway not ready or security groups blocking traffic.

**Solution:**
1. Wait 2-3 minutes after deployment
2. Retry pipeline execution
3. Check API Gateway endpoint is accessible:

```bash
# Get endpoint
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text \
  --region ap-south-1)

# Test endpoint
curl $ENDPOINT
```

---

## Verification Checklist

After troubleshooting, verify everything works:

- [ ] Pipeline exists: `aws codepipeline get-pipeline --name dev-infra-pipeline --region ap-south-1`
- [ ] EventBridge rule enabled: `aws events describe-rule --name dev-infra-pipeline-trigger --region ap-south-1`
- [ ] GitHub connection active: Check AWS Console → Developer Tools → Connections
- [ ] Pipeline can be triggered manually: `aws codepipeline start-pipeline-execution --name dev-infra-pipeline --region ap-south-1`
- [ ] API Gateway stack created: `aws cloudformation describe-stacks --stack-name dev-api-gateway-stack --region ap-south-1`
- [ ] API endpoint accessible: `curl <API_ENDPOINT>`

---

## Getting Help

If issues persist:

1. **Check CloudWatch Logs:**
   ```bash
   aws logs tail /aws/codebuild/dev-infra-deploy --follow --region ap-south-1
   ```

2. **Check CloudFormation Events:**
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name dev-api-gateway-stack \
     --max-items 10 \
     --region ap-south-1
   ```

3. **Check Pipeline Execution Details:**
   ```bash
   EXECUTION_ID=$(aws codepipeline list-pipeline-executions \
     --pipeline-name dev-infra-pipeline \
     --max-results 1 \
     --query 'pipelineExecutionSummaries[0].pipelineExecutionId' \
     --output text \
     --region ap-south-1)
   
   aws codepipeline get-pipeline-execution \
     --pipeline-name dev-infra-pipeline \
     --pipeline-execution-id $EXECUTION_ID \
     --region ap-south-1
   ```

---

## Working Configuration

For reference, here's what should be working:

**Branch:** `develop`  
**Pipeline:** `dev-infra-pipeline`  
**Region:** `ap-south-1`  
**Trigger:** Push to `develop` branch  
**Modules:** API Gateway (enabled)  

**Expected Flow:**
1. Push to `develop` → EventBridge detects
2. EventBridge triggers pipeline
3. Pipeline pulls code from GitHub
4. CodeBuild detects changed modules
5. Deploys API Gateway stack
6. Runs tests
7. Complete in 5-10 minutes