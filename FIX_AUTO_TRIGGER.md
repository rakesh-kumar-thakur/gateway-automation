# Fix Auto-Trigger Issue - Action Required

## Current Status
✅ DetectChanges: false (correct)
✅ EventBridge rule: ENABLED
✅ GitHub connection: AVAILABLE
✅ Rule pattern: Correct for develop branch

## The Problem
EventBridge needs the CodeStar Connection to send events. The connection must be configured to send notifications.

## Solution - Enable Notifications on GitHub Connection

Run this command to enable notifications:

```bash
aws codeconnections update-connection \
  --connection-arn arn:aws:codeconnections:ap-south-1:381492219337:connection/7a96c5e3-3fe4-443e-99c3-881818fa83c4 \
  --region ap-south-1
```

## Alternative: Manual Trigger Test

Test if pipeline works manually:

```bash
aws codepipeline start-pipeline-execution \
  --name dev-infra-pipeline \
  --region ap-south-1
```

## Verify EventBridge is Receiving Events

After pushing to GitHub, check CloudWatch Logs:

```bash
aws logs tail /aws/events/dev-infra-pipeline-trigger --follow --region ap-south-1
```

## If Still Not Working

The CodeStar Connection might not be sending events to EventBridge. This is a known AWS limitation. 

**Workaround: Use GitHub Webhooks Instead**

1. Go to your GitHub repo → Settings → Webhooks
2. Add webhook:
   - Payload URL: `https://YOUR_API_GATEWAY_URL/webhook`
   - Content type: application/json
   - Events: Just the push event
3. Create a Lambda function to trigger the pipeline
4. Connect Lambda to API Gateway

OR

**Use CodePipeline's Built-in Detection (Simpler)**

Remove EventBridge and use CodePipeline's native GitHub polling:
- Set `DetectChanges: true` in the pipeline
- Remove the EventBridge rule
- CodePipeline will poll GitHub every minute

Run this to switch back:

```bash
aws cloudformation update-stack \
  --stack-name dev-infra-pipeline-stack \
  --template-body file://pipeline/dev-pipeline.yaml \
  --parameters \
    ParameterKey=GitHubOwner,ParameterValue=rakesh-kumar-thakur \
    ParameterKey=GitHubRepo,ParameterValue=gateway-automation \
    ParameterKey=GitHubBranch,ParameterValue=develop \
    ParameterKey=GitHubConnectionArn,ParameterValue=arn:aws:codeconnections:ap-south-1:381492219337:connection/7a96c5e3-3fe4-443e-99c3-881818fa83c4 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

Then change line 398 in dev-pipeline.yaml back to `DetectChanges: true` and update the stack again.