# Adding New AWS Components Guide

## Overview

The pipeline is designed to be **modular and extensible**. You can easily add new AWS components (Lambda, DynamoDB, S3, RDS, etc.) without modifying the pipeline templates. The system automatically detects and deploys changes.

## 📁 File Structure for New Components

```
project-root/
├── aws/                           # ← All AWS CloudFormation templates go here
│   ├── api-gateway/              # Existing module
│   │   ├── template.yaml
│   │   └── swagger.yaml
│   ├── alb/                      # Existing module
│   │   └── template.yaml
│   ├── ecs/                      # Existing module
│   │   └── template.yaml
│   │
│   ├── lambda/                   # ← NEW: Add Lambda functions here
│   │   ├── template.yaml         # CloudFormation template
│   │   └── src/                  # Lambda source code
│   │       └── handler.py
│   │
│   ├── dynamodb/                 # ← NEW: Add DynamoDB tables here
│   │   └── template.yaml
│   │
│   ├── s3/                       # ← NEW: Add S3 buckets here
│   │   └── template.yaml
│   │
│   └── rds/                      # ← NEW: Add RDS databases here
│       └── template.yaml
│
└── pipeline/
    └── modules/                   # ← Module manifests go here
        ├── api-gateway.yml       # Existing
        ├── alb.yml               # Existing
        ├── ecs.yml               # Existing
        ├── lambda.yml            # ← NEW: Add manifest for Lambda
        ├── dynamodb.yml          # ← NEW: Add manifest for DynamoDB
        ├── s3.yml                # ← NEW: Add manifest for S3
        └── rds.yml               # ← NEW: Add manifest for RDS
```

## 🔧 Step-by-Step: Adding a New Component

### Example 1: Adding Lambda Functions

#### Step 1: Create CloudFormation Template

Create `aws/lambda/template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Lambda Functions

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
  # Lambda Execution Role
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub "${Environment}-lambda-execution-role"
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: LambdaPermissions
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:Query
                Resource: "*"

  # Lambda Function
  MyFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${Environment}-my-function"
      Runtime: python3.12
      Handler: index.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        ZipFile: |
          def handler(event, context):
              return {
                  'statusCode': 200,
                  'body': 'Hello from Lambda!'
              }
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment
      Tags:
        - Key: Environment
          Value: !Ref Environment

Outputs:
  FunctionArn:
    Value: !GetAtt MyFunction.Arn
    Export:
      Name: !Sub "${Environment}-MyFunctionArn"
  
  FunctionName:
    Value: !Ref MyFunction
```

#### Step 2: Create Module Manifest

Create `pipeline/modules/lambda.yml`:

```yaml
# ============================================================
# Lambda Module Manifest
# ============================================================

module:
  name: lambda
  description: Lambda Functions
  enabled: true  # Set to true to enable deployment

stack:
  name: lambda-stack
  templatePath: aws/lambda/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

# No preDeploy script needed
preDeploy: ~

parameters:
  - key: Environment
    source: ssm
    path: /pipeline/{env}/environment

tags:
  - key: ManagedBy
    value: CodePipeline
  - key: Module
    value: lambda

# Define which file changes trigger deployment
changePaths:
  - aws/lambda/**
  - pipeline/modules/lambda.yml
```

#### Step 3: Commit and Deploy

```bash
# Add files
git add aws/lambda/
git add pipeline/modules/lambda.yml

# Commit
git commit -m "Add Lambda function module"

# Push to trigger pipeline
git push origin develop  # For dev environment
```

**That's it!** The pipeline will automatically:
1. Detect changes in `aws/lambda/**`
2. Deploy the Lambda module
3. Run tests
4. Show outputs

---

### Example 2: Adding DynamoDB Tables

#### Step 1: Create CloudFormation Template

Create `aws/dynamodb/template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: DynamoDB Tables

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "${Environment}-users"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: userId
          AttributeType: S
        - AttributeName: email
          AttributeType: S
      KeySchema:
        - AttributeName: userId
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: EmailIndex
          KeySchema:
            - AttributeName: email
              KeyType: HASH
          Projection:
            ProjectionType: ALL
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      Tags:
        - Key: Environment
          Value: !Ref Environment

Outputs:
  UsersTableName:
    Value: !Ref UsersTable
    Export:
      Name: !Sub "${Environment}-UsersTableName"
  
  UsersTableArn:
    Value: !GetAtt UsersTable.Arn
    Export:
      Name: !Sub "${Environment}-UsersTableArn"
```

#### Step 2: Create Module Manifest

Create `pipeline/modules/dynamodb.yml`:

```yaml
module:
  name: dynamodb
  description: DynamoDB Tables
  enabled: true

stack:
  name: dynamodb-stack
  templatePath: aws/dynamodb/template.yaml
  capabilities: []

preDeploy: ~

parameters:
  - key: Environment
    source: ssm
    path: /pipeline/{env}/environment

tags:
  - key: ManagedBy
    value: CodePipeline
  - key: Module
    value: dynamodb

changePaths:
  - aws/dynamodb/**
  - pipeline/modules/dynamodb.yml
```

---

### Example 3: Adding S3 Buckets

#### Step 1: Create CloudFormation Template

Create `aws/s3/template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: S3 Buckets

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "${AWS::AccountId}-${Environment}-data-bucket"
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      LifecycleConfiguration:
        Rules:
          - Id: DeleteOldVersions
            Status: Enabled
            NoncurrentVersionExpirationInDays: 90
      Tags:
        - Key: Environment
          Value: !Ref Environment

  BucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref DataBucket
      PolicyDocument:
        Statement:
          - Sid: DenyInsecureTransport
            Effect: Deny
            Principal: "*"
            Action: "s3:*"
            Resource:
              - !GetAtt DataBucket.Arn
              - !Sub "${DataBucket.Arn}/*"
            Condition:
              Bool:
                "aws:SecureTransport": false

Outputs:
  DataBucketName:
    Value: !Ref DataBucket
    Export:
      Name: !Sub "${Environment}-DataBucketName"
  
  DataBucketArn:
    Value: !GetAtt DataBucket.Arn
    Export:
      Name: !Sub "${Environment}-DataBucketArn"
```

#### Step 2: Create Module Manifest

Create `pipeline/modules/s3.yml`:

```yaml
module:
  name: s3
  description: S3 Buckets
  enabled: true

stack:
  name: s3-stack
  templatePath: aws/s3/template.yaml
  capabilities: []

preDeploy: ~

parameters:
  - key: Environment
    source: ssm
    path: /pipeline/{env}/environment

tags:
  - key: ManagedBy
    value: CodePipeline
  - key: Module
    value: s3

changePaths:
  - aws/s3/**
  - pipeline/modules/s3.yml
```

---

## 🔗 Connecting Components

### Example: Lambda + DynamoDB + API Gateway

When components need to reference each other, use CloudFormation exports:

#### 1. DynamoDB exports table name:
```yaml
Outputs:
  UsersTableName:
    Value: !Ref UsersTable
    Export:
      Name: !Sub "${Environment}-UsersTableName"
```

#### 2. Lambda imports and uses it:
```yaml
Parameters:
  Environment:
    Type: String

Resources:
  MyFunction:
    Type: AWS::Lambda::Function
    Properties:
      Environment:
        Variables:
          USERS_TABLE: !ImportValue 
            Fn::Sub: "${Environment}-UsersTableName"
```

#### 3. API Gateway invokes Lambda:
```yaml
Resources:
  ApiGatewayInvokeLambda:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !ImportValue 
        Fn::Sub: "${Environment}-MyFunctionArn"
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
```

---

## 📦 Complex Components with Dependencies

### Example: ECS Service (depends on ALB)

The ECS module already exists but is disabled. Here's how to enable it:

#### Step 1: Ensure ALB is deployed first

Edit `pipeline/modules/alb.yml`:
```yaml
module:
  name: alb
  enabled: true  # ← Change to true
```

#### Step 2: Enable ECS module

Edit `pipeline/modules/ecs.yml`:
```yaml
module:
  name: ecs
  enabled: true  # ← Change to true
```

#### Step 3: Deploy in order

The pipeline processes modules alphabetically by filename. To control order:

```bash
# Rename files with prefixes
mv pipeline/modules/alb.yml pipeline/modules/01-alb.yml
mv pipeline/modules/ecs.yml pipeline/modules/02-ecs.yml
```

Or deploy manually in order:
```bash
# Deploy ALB first
DEPLOY_MODULES=alb

# Then deploy ECS
DEPLOY_MODULES=ecs
```

---

## 🎯 Best Practices

### 1. **One Module = One CloudFormation Stack**
- Each component should be a separate module
- Makes updates and rollbacks easier
- Better separation of concerns

### 2. **Use Exports for Cross-Stack References**
```yaml
Outputs:
  MyResourceArn:
    Value: !GetAtt MyResource.Arn
    Export:
      Name: !Sub "${Environment}-MyResourceArn"
```

### 3. **Environment-Specific Naming**
Always prefix resources with environment:
```yaml
BucketName: !Sub "${AWS::AccountId}-${Environment}-my-bucket"
```

### 4. **Define Clear Change Paths**
Be specific about what triggers deployment:
```yaml
changePaths:
  - aws/lambda/**           # Any Lambda changes
  - aws/lambda/src/**       # Just source code
  - pipeline/modules/lambda.yml  # Manifest changes
```

### 5. **Add Appropriate IAM Permissions**
If your module needs special permissions, add them to CodeBuild role in pipeline templates.

---

## 🚀 Quick Reference

### Adding a New Component Checklist

- [ ] Create directory: `aws/<component-name>/`
- [ ] Create CloudFormation template: `aws/<component-name>/template.yaml`
- [ ] Create module manifest: `pipeline/modules/<component-name>.yml`
- [ ] Set `enabled: true` in manifest
- [ ] Define `changePaths` in manifest
- [ ] Add any required parameters
- [ ] Commit and push to trigger deployment
- [ ] Monitor pipeline in AWS Console

### Module Manifest Template

```yaml
module:
  name: <module-name>
  description: <description>
  enabled: true

stack:
  name: <stack-name>
  templatePath: aws/<module-name>/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM  # If creating IAM resources

preDeploy: ~

parameters:
  - key: Environment
    source: ssm
    path: /pipeline/{env}/environment

tags:
  - key: ManagedBy
    value: CodePipeline
  - key: Module
    value: <module-name>

changePaths:
  - aws/<module-name>/**
  - pipeline/modules/<module-name>.yml
```

---

## 🔍 Troubleshooting

### Module Not Deploying?

1. **Check if enabled**:
   ```yaml
   enabled: true  # Must be true
   ```

2. **Verify change paths match**:
   ```bash
   git diff --name-only HEAD~1 HEAD
   ```

3. **Check CloudFormation syntax**:
   ```bash
   cfn-lint aws/<module>/template.yaml
   ```

4. **Force deployment**:
   ```bash
   # Set in CodeBuild environment
   DEPLOY_MODULES=<module-name>
   ```

### Stack Creation Failed?

1. Check CloudWatch Logs in CodeBuild
2. Review CloudFormation events in AWS Console
3. Verify IAM permissions
4. Check resource limits (VPC limits, etc.)

---

## 📚 Additional Resources

- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)
- [Module Manifests](./modules/) - See existing examples
- [Deployment Guide](./DEPLOYMENT.md) - Full deployment instructions

---

## 💡 Examples Repository

Common components you might add:

| Component | Directory | Use Case |
|-----------|-----------|----------|
| Lambda | `aws/lambda/` | Serverless functions |
| DynamoDB | `aws/dynamodb/` | NoSQL database |
| S3 | `aws/s3/` | Object storage |
| RDS | `aws/rds/` | Relational database |
| SQS | `aws/sqs/` | Message queues |
| SNS | `aws/sns/` | Notifications |
| EventBridge | `aws/eventbridge/` | Event routing |
| Step Functions | `aws/stepfunctions/` | Workflow orchestration |
| CloudFront | `aws/cloudfront/` | CDN |
| WAF | `aws/waf/` | Web application firewall |

Each follows the same pattern: CloudFormation template + module manifest.