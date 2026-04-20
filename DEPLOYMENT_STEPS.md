# Step-by-Step Deployment Guide

## 🎯 Goal
Deploy the Dev pipeline that will automatically trigger when you commit changes to API Gateway endpoints in the `develop` branch.

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- [ ] AWS CLI installed and configured
- [ ] AWS credentials with admin access (or CloudFormation, CodePipeline, CodeBuild, IAM permissions)
- [ ] GitHub repository: `rakesh-kumar-thakur/gateway-automation`
- [ ] GitHub connection already created in AWS (ARN: `arn:aws:codeconnections:ap-south-1:381492219337:connection/7a96c5e3-3fe4-443e-99c3-881818fa83c4`)
- [ ] Git installed locally
- [ ] Access to AWS Console

## 🚀 Deployment Steps

### Step 1: Commit All Changes to Git

```bash
# Navigate to your project directory
cd c:/Users/0048EQ744/Kiro/Infra-automation-sample

# Check current status
git status

# Add all new pipeline files
git add pipeline/

# Commit the changes
git commit -m "Add multi-environment pipeline infrastructure with change detection"

# Push to your current branch (likely master or main)
git push origin master
```

### Step 2: Create Development Branch

The dev pipeline monitors the `develop` branch, so we need to create it:

```bash
# Create and checkout develop branch from master
git checkout -b develop

# Push develop branch to GitHub
git push -u origin develop
```

### Step 3: Deploy the Development Pipeline

```bash
# Deploy the dev pipeline stack
aws cloudformation deploy \
  --template-file pipeline/dev-pipeline.yaml \
  --stack-name dev-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1

# This will take 3-5 minutes
```

**Expected Output:**
```
Waiting for changeset to be created..
Waiting for stack create/update to complete
Successfully created/updated stack - dev-infra-pipeline-stack
```

### Step 4: Verify Pipeline Creation

```bash
# Get the pipeline console URL
aws cloudformation describe-stacks \
  --stack-name dev-infra-pipeline-stack \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineConsoleUrl'].OutputValue" \
  --output text \
  --region ap-south-1
```

**Copy the URL and open it in your browser** to see the pipeline in AWS Console.

### Step 5: Verify Pipeline Components

Check that all resources were created:

```bash
# Check pipeline exists
aws codepipeline get-pipeline \
  --name dev-infra-pipeline \
  --region ap-south-1

# Check CodeBuild project exists
aws codebuild batch-get-projects \
  --names dev-infra-deploy \
  --region ap-south-1

# Check S3 artifact bucket exists
aws s3 ls | grep dev-pipeline-artifacts
```

### Step 6: Trigger Initial Pipeline Run

The pipeline should auto-trigger when you push to `develop`, but let's do a manual trigger first:

```bash
# Manually start the pipeline
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

**Monitor in AWS Console:**
1. Go to the pipeline URL from Step 4
2. Watch the pipeline execute through stages:
   - Source (pulls from GitHub)
   - Deploy (deploys API Gateway)
   - Test (runs API, integration, load tests)

### Step 7: Verify API Gateway Deployment

After the pipeline completes successfully:

```bash
# Get API Gateway endpoint
aws cloudformation describe-stacks \
  --stack-name dev-api-gateway-stack \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text \
  --region ap-south-1
```

**Test the API:**
```bash
# Replace <API_ENDPOINT> with the URL from above
curl <API_ENDPOINT>
```

## ✅ Verification Checklist

After deployment, verify:

- [ ] Pipeline visible in AWS Console
- [ ] Pipeline execution completed successfully
- [ ] API Gateway stack created (`dev-api-gateway-stack`)
- [ ] API endpoint accessible
- [ ] All test stages passed (API, Integration, Load)

## 🔄 Testing Automatic Triggers

Now test that changes automatically trigger the pipeline:

### Test 1: Add a New API Endpoint

```bash
# Make sure you're on develop branch
git checkout develop

# Edit the Swagger file
# Open aws/api-gateway/swagger.yaml in your editor
# Add a new endpoint (example below)

# Commit and push
git add aws/api-gateway/swagger.yaml
git commit -m "Add new /hello endpoint"
git push origin develop
```

**What happens:**
1. GitHub push triggers EventBridge rule
2. EventBridge starts the pipeline
3. Pipeline detects changes in `aws/api-gateway/**`
4. Deploys only the API Gateway module
5. Runs tests
6. Updates complete in 5-10 minutes

**Monitor:**
- Go to pipeline URL in AWS Console
- Watch new execution start automatically
- Check CloudWatch Logs for details

### Example: Adding a New Endpoint to Swagger

Edit `aws/api-gateway/swagger.yaml` and add:

```yaml
paths:
  /hello:
    get:
      summary: Hello endpoint
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: string
      x-amazon-apigateway-integration:
        type: mock
        requestTemplates:
          application/json: '{"statusCode": 200}'
        responses:
          default:
            statusCode: 200
            responseTemplates:
              application/json: '{"message": "Hello from API Gateway!"}'
```

## 🎛️ Optional: Deploy QA and Production Pipelines

Once dev is working, deploy other environments:

### Deploy QA Pipeline

```bash
# Create qa branch
git checkout -b qa develop
git push -u origin qa

# Deploy QA pipeline
aws cloudformation deploy \
  --template-file pipeline/qa-pipeline.yaml \
  --stack-name qa-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-qa.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

### Deploy Production Pipeline

```bash
# Create main branch (if not exists)
git checkout -b main develop
git push -u origin main

# Deploy Production pipeline
aws cloudformation deploy \
  --template-file pipeline/prod-pipeline.yaml \
  --stack-name prod-infra-pipeline-stack \
  --parameter-overrides file://pipeline/params-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

## 🔍 Monitoring and Logs

### View Pipeline Executions

```bash
# List recent pipeline runs
aws codepipeline list-pipeline-executions \
  --pipeline-name dev-infra-pipeline \
  --max-results 5 \
  --region ap-south-1
```

### View Build Logs

```bash
# Get latest build ID
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name dev-infra-deploy \
  --max-items 1 \
  --query 'ids[0]' \
  --output text \
  --region ap-south-1)

# View build details
aws codebuild batch-get-builds \
  --ids $BUILD_ID \
  --region ap-south-1
```

### View Logs in Console

1. **Pipeline Logs**: CodePipeline → dev-infra-pipeline → Execution history
2. **Build Logs**: CodeBuild → Build projects → dev-infra-deploy → Build history
3. **CloudWatch Logs**: CloudWatch → Log groups → `/aws/codebuild/dev-infra-deploy`

## 🐛 Troubleshooting

### Pipeline Not Triggering Automatically

**Problem**: Push to develop but pipeline doesn't start

**Solution**:
```bash
# Check EventBridge rule
aws events describe-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1

# Verify rule is ENABLED
# If disabled, enable it:
aws events enable-rule \
  --name dev-infra-pipeline-trigger \
  --region ap-south-1

# Manually trigger to test
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

### Build Fails with Permission Error

**Problem**: CodeBuild fails with "Access Denied"

**Solution**: Check IAM role has necessary permissions
```bash
# View CodeBuild role
aws iam get-role \
  --role-name dev-codebuild-deploy-role \
  --region ap-south-1
```

### API Gateway Not Deploying

**Problem**: Pipeline succeeds but API Gateway not updated

**Solution**: Check module is enabled
```bash
# Verify api-gateway.yml has enabled: true
cat pipeline/modules/api-gateway.yml | grep enabled

# Check if changes match changePaths
git diff HEAD~1 HEAD --name-only
```

### Tests Failing

**Problem**: Test stage fails

**Solution**: 
1. Check API endpoint exists in CloudFormation outputs
2. Verify security groups allow traffic
3. Review test logs in CodeBuild
4. Tests may fail on first run if API not ready - retry pipeline

## 🧹 Cleanup (If Needed)

To remove everything:

```bash
# Delete pipeline stack
aws cloudformation delete-stack \
  --stack-name dev-infra-pipeline-stack \
  --region ap-south-1

# Delete API Gateway stack (if exists)
aws cloudformation delete-stack \
  --stack-name dev-api-gateway-stack \
  --region ap-south-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name dev-infra-pipeline-stack \
  --region ap-south-1

# Manually delete artifact bucket
aws s3 rb s3://381492219337-dev-pipeline-artifacts --force
```

## 📞 Support

If you encounter issues:

1. **Check CloudWatch Logs**: Most detailed error information
2. **Review CodeBuild Logs**: Shows deployment steps and errors
3. **Check CloudFormation Events**: Shows stack creation/update issues
4. **Verify IAM Permissions**: Ensure roles have necessary access

## 🎉 Success Criteria

You'll know everything is working when:

✅ Pipeline visible in AWS Console  
✅ Pipeline executes successfully  
✅ API Gateway deployed and accessible  
✅ Tests pass (API, Integration, Load)  
✅ Pushing to `develop` automatically triggers pipeline  
✅ New endpoints deploy automatically  

## 📚 Next Steps

After successful deployment:

1. **Add more endpoints**: Edit `aws/api-gateway/swagger.yaml`
2. **Enable other modules**: Set `enabled: true` in `pipeline/modules/alb.yml` or `ecs.yml`
3. **Add new components**: Follow [`pipeline/ADDING_NEW_COMPONENTS.md`](pipeline/ADDING_NEW_COMPONENTS.md)
4. **Deploy to QA/Prod**: Follow optional steps above
5. **Set up notifications**: Subscribe to SNS topics (see [`pipeline/DEPLOYMENT.md`](pipeline/DEPLOYMENT.md))

---

**Region**: ap-south-1 (Mumbai)  
**Environment**: Development  
**Branch**: develop  
**Pipeline**: dev-infra-pipeline