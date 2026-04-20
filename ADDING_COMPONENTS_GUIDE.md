# Adding New Components Guide

## Quick Answer

To provision **ALB, NLB, ECS Fargate, and Lambda**, you need to add **2 files per component**:

1. **CloudFormation template** in `aws/{component}/template.yaml`
2. **Module manifest** in `pipeline/modules/{component}.yml`

**No pipeline changes needed!** The existing [`pipeline/buildspec-deploy.yml`](pipeline/buildspec-deploy.yml) automatically discovers and deploys new modules.

## Current Structure

```
aws/
  api-gateway/          ✅ Already exists
    template.yaml
    swagger.yaml
  alb/                  ⚠️ Stub exists (disabled)
    template.yaml
  ecs/                  ⚠️ Stub exists (disabled)
    template.yaml

pipeline/
  modules/
    api-gateway.yml     ✅ Enabled
    alb.yml             ⚠️ Disabled (enabled: false)
    ecs.yml             ⚠️ Disabled (enabled: false)
```

## Adding Your Components

### 1. ALB (Application Load Balancer)

#### Step 1.1: Complete the Template
```bash
# File already exists: aws/alb/template.yaml
# You need to complete it with your ALB configuration
```

**Example ALB Template:**
```yaml
# aws/alb/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Application Load Balancer

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  
  VpcId:
    Type: AWS::EC2::VPC::Id
  
  PublicSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>

Resources:
  AlbSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: !Sub "${Environment}-alb-sg"
      GroupDescription: Allow HTTP/HTTPS
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0

  ApplicationLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: !Sub "${Environment}-alb"
      Type: application
      Scheme: internet-facing
      IpAddressType: ipv4
      Subnets: !Ref PublicSubnetIds
      SecurityGroups:
        - !Ref AlbSecurityGroup
      Tags:
        - Key: Environment
          Value: !Ref Environment

  AlbTargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: !Sub "${Environment}-alb-tg"
      Port: 80
      Protocol: HTTP
      VpcId: !Ref VpcId
      TargetType: ip
      HealthCheckEnabled: true
      HealthCheckPath: /health
      HealthCheckProtocol: HTTP

  AlbListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref ApplicationLoadBalancer
      Port: 80
      Protocol: HTTP
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref AlbTargetGroup

Outputs:
  AlbArn:
    Value: !Ref ApplicationLoadBalancer
    Export:
      Name: !Sub "${Environment}-AlbArn"
  
  AlbDnsName:
    Value: !GetAtt ApplicationLoadBalancer.DNSName
    Export:
      Name: !Sub "${Environment}-AlbDnsName"
  
  TargetGroupArn:
    Value: !Ref AlbTargetGroup
    Export:
      Name: !Sub "${Environment}-AlbTargetGroupArn"
```

#### Step 1.2: Update the Manifest
```yaml
# pipeline/modules/alb.yml
module:
  name: alb
  description: Application Load Balancer
  enabled: true              # ← Change to true
  order: 10                  # ← Add explicit order
  dependsOn: []              # ← No dependencies

stack:
  name: alb-stack
  templatePath: aws/alb/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: value
    value: dev               # TODO: Make environment-neutral later
  - key: VpcId
    source: ssm
    path: /pipeline/dev/vpc_id
  - key: PublicSubnetIds
    source: ssm
    path: /pipeline/dev/public_subnet_ids

tags:
  - key: Module
    value: alb

changePaths:
  - aws/alb/**
  - pipeline/modules/alb.yml
```

#### Step 1.3: Create SSM Parameters
```bash
# Store VPC and subnet IDs in SSM
aws ssm put-parameter \
  --name /pipeline/dev/vpc_id \
  --value vpc-xxxxx \
  --type String

aws ssm put-parameter \
  --name /pipeline/dev/public_subnet_ids \
  --value subnet-xxx,subnet-yyy \
  --type StringList
```

#### Step 1.4: Commit and Deploy
```bash
git add aws/alb/ pipeline/modules/alb.yml
git commit -m "Enable ALB module"
git push origin develop
# Pipeline automatically deploys ALB
```

---

### 2. NLB (Network Load Balancer)

#### Step 2.1: Create Template
```bash
mkdir -p aws/nlb
```

```yaml
# aws/nlb/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Network Load Balancer

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  
  VpcId:
    Type: AWS::EC2::VPC::Id
  
  PublicSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>

Resources:
  NetworkLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: !Sub "${Environment}-nlb"
      Type: network
      Scheme: internet-facing
      IpAddressType: ipv4
      Subnets: !Ref PublicSubnetIds
      Tags:
        - Key: Environment
          Value: !Ref Environment

  NlbTargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: !Sub "${Environment}-nlb-tg"
      Port: 80
      Protocol: TCP
      VpcId: !Ref VpcId
      TargetType: ip
      HealthCheckEnabled: true
      HealthCheckProtocol: TCP

  NlbListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref NetworkLoadBalancer
      Port: 80
      Protocol: TCP
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref NlbTargetGroup

Outputs:
  NlbArn:
    Value: !Ref NetworkLoadBalancer
    Export:
      Name: !Sub "${Environment}-NlbArn"
  
  NlbDnsName:
    Value: !GetAtt NetworkLoadBalancer.DNSName
    Export:
      Name: !Sub "${Environment}-NlbDnsName"
  
  NlbTargetGroupArn:
    Value: !Ref NlbTargetGroup
    Export:
      Name: !Sub "${Environment}-NlbTargetGroupArn"
```

#### Step 2.2: Create Manifest
```yaml
# pipeline/modules/nlb.yml
module:
  name: nlb
  description: Network Load Balancer
  enabled: true
  order: 15                  # After ALB
  dependsOn: []

stack:
  name: nlb-stack
  templatePath: aws/nlb/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: value
    value: dev
  - key: VpcId
    source: ssm
    path: /pipeline/dev/vpc_id
  - key: PublicSubnetIds
    source: ssm
    path: /pipeline/dev/public_subnet_ids

tags:
  - key: Module
    value: nlb

changePaths:
  - aws/nlb/**
  - pipeline/modules/nlb.yml
```

#### Step 2.3: Deploy
```bash
git add aws/nlb/ pipeline/modules/nlb.yml
git commit -m "Add NLB module"
git push origin develop
```

---

### 3. ECS Fargate

#### Step 3.1: Complete the Template
```yaml
# aws/ecs/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: ECS Fargate Cluster and Service

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  
  ClusterName:
    Type: String
    Default: app-cluster
  
  ContainerImage:
    Type: String
    Description: ECR image URI
  
  VpcId:
    Type: AWS::EC2::VPC::Id
  
  PrivateSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
  
  TargetGroupArn:
    Type: String
    Description: ALB Target Group ARN

Resources:
  EcsCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub "${Environment}-${ClusterName}"
      CapacityProviders:
        - FARGATE
        - FARGATE_SPOT
      DefaultCapacityProviderStrategy:
        - CapacityProvider: FARGATE
          Weight: 1
      Tags:
        - Key: Environment
          Value: !Ref Environment

  TaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub "${Environment}-ecs-task-execution-role"
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

  TaskRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub "${Environment}-ecs-task-role"
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole

  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub "${Environment}-app-task"
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: 256
      Memory: 512
      ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn
      TaskRoleArn: !GetAtt TaskRole.Arn
      ContainerDefinitions:
        - Name: app
          Image: !Ref ContainerImage
          PortMappings:
            - ContainerPort: 80
              Protocol: tcp
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref LogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

  LogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/ecs/${Environment}-app"
      RetentionInDays: 7

  ServiceSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: !Sub "${Environment}-ecs-service-sg"
      GroupDescription: ECS Service Security Group
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          SourceSecurityGroupId: !ImportValue
            Fn::Sub: "${Environment}-AlbSecurityGroupId"

  EcsService:
    Type: AWS::ECS::Service
    Properties:
      ServiceName: !Sub "${Environment}-app-service"
      Cluster: !Ref EcsCluster
      TaskDefinition: !Ref TaskDefinition
      DesiredCount: 2
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          AssignPublicIp: DISABLED
          Subnets: !Ref PrivateSubnetIds
          SecurityGroups:
            - !Ref ServiceSecurityGroup
      LoadBalancers:
        - ContainerName: app
          ContainerPort: 80
          TargetGroupArn: !Ref TargetGroupArn

Outputs:
  ClusterArn:
    Value: !GetAtt EcsCluster.Arn
    Export:
      Name: !Sub "${Environment}-EcsClusterArn"
  
  ServiceArn:
    Value: !Ref EcsService
    Export:
      Name: !Sub "${Environment}-EcsServiceArn"
```

#### Step 3.2: Update Manifest
```yaml
# pipeline/modules/ecs.yml
module:
  name: ecs
  description: ECS Fargate Cluster and Service
  enabled: true              # ← Change to true
  order: 20                  # ← After ALB (depends on it)
  dependsOn:
    - alb                    # ← Explicit dependency

stack:
  name: ecs-stack
  templatePath: aws/ecs/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: value
    value: dev
  - key: ClusterName
    source: value
    value: app-cluster
  - key: ContainerImage
    source: ssm
    path: /pipeline/dev/ecs_container_image
  - key: VpcId
    source: ssm
    path: /pipeline/dev/vpc_id
  - key: PrivateSubnetIds
    source: ssm
    path: /pipeline/dev/private_subnet_ids
  - key: TargetGroupArn
    source: ssm
    path: /pipeline/dev/alb_target_group_arn

tags:
  - key: Module
    value: ecs

changePaths:
  - aws/ecs/**
  - pipeline/modules/ecs.yml
```

#### Step 3.3: Create SSM Parameters
```bash
aws ssm put-parameter \
  --name /pipeline/dev/ecs_container_image \
  --value 123456789.dkr.ecr.ap-south-1.amazonaws.com/myapp:latest \
  --type String

aws ssm put-parameter \
  --name /pipeline/dev/private_subnet_ids \
  --value subnet-aaa,subnet-bbb \
  --type StringList

# After ALB is deployed, store its target group ARN
aws ssm put-parameter \
  --name /pipeline/dev/alb_target_group_arn \
  --value arn:aws:elasticloadbalancing:... \
  --type String
```

#### Step 3.4: Deploy
```bash
git add aws/ecs/ pipeline/modules/ecs.yml
git commit -m "Enable ECS Fargate module"
git push origin develop
```

---

### 4. Lambda Functions

#### Step 4.1: Create Template
```bash
mkdir -p aws/lambda
```

```yaml
# aws/lambda/template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Lambda Functions

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
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
        - arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole

  ProcessorFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${Environment}-processor"
      Runtime: python3.12
      Handler: index.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Timeout: 30
      MemorySize: 256
      Code:
        ZipFile: |
          import json
          def handler(event, context):
              print(f"Processing event: {json.dumps(event)}")
              return {
                  'statusCode': 200,
                  'body': json.dumps({'message': 'Success'})
              }
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment
      Tags:
        - Key: Environment
          Value: !Ref Environment

  WorkerFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${Environment}-worker"
      Runtime: python3.12
      Handler: index.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Timeout: 60
      MemorySize: 512
      Code:
        ZipFile: |
          import json
          def handler(event, context):
              print(f"Worker processing: {json.dumps(event)}")
              return {'status': 'completed'}
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment

  # Lambda Log Groups
  ProcessorLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${ProcessorFunction}"
      RetentionInDays: 7

  WorkerLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${WorkerFunction}"
      RetentionInDays: 7

Outputs:
  ProcessorFunctionArn:
    Value: !GetAtt ProcessorFunction.Arn
    Export:
      Name: !Sub "${Environment}-ProcessorFunctionArn"
  
  WorkerFunctionArn:
    Value: !GetAtt WorkerFunction.Arn
    Export:
      Name: !Sub "${Environment}-WorkerFunctionArn"
```

#### Step 4.2: Create Manifest
```yaml
# pipeline/modules/lambda.yml
module:
  name: lambda
  description: Lambda Functions
  enabled: true
  order: 5                   # Early in deployment (no dependencies)
  dependsOn: []

stack:
  name: lambda-stack
  templatePath: aws/lambda/template.yaml
  capabilities:
    - CAPABILITY_NAMED_IAM

parameters:
  - key: Environment
    source: value
    value: dev

tags:
  - key: Module
    value: lambda

changePaths:
  - aws/lambda/**
  - pipeline/modules/lambda.yml
```

#### Step 4.3: Deploy
```bash
git add aws/lambda/ pipeline/modules/lambda.yml
git commit -m "Add Lambda functions module"
git push origin develop
```

---

## Deployment Order with Dependencies

With the recommended `order` and `dependsOn` fields:

```
Order 5:  lambda        (no dependencies)
Order 10: alb           (no dependencies)
Order 15: nlb           (no dependencies)
Order 20: ecs           (depends on alb)
Order 30: api-gateway   (might depend on lambda)
```

The enhanced buildspec (from [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) Phase 4) will:
1. Sort by `order`
2. Resolve `dependsOn` chains
3. Deploy in correct sequence

---

## Summary: Where to Add Components

| Component | Template Location | Manifest Location | Dependencies |
|-----------|------------------|-------------------|--------------|
| **ALB** | `aws/alb/template.yaml` | `pipeline/modules/alb.yml` | None |
| **NLB** | `aws/nlb/template.yaml` | `pipeline/modules/nlb.yml` | None |
| **ECS Fargate** | `aws/ecs/template.yaml` | `pipeline/modules/ecs.yml` | ALB (for target group) |
| **Lambda** | `aws/lambda/template.yaml` | `pipeline/modules/lambda.yml` | None |

## Quick Checklist

For each component:
- [ ] Create CloudFormation template in `aws/{component}/template.yaml`
- [ ] Create module manifest in `pipeline/modules/{component}.yml`
- [ ] Set `enabled: true` in manifest
- [ ] Add `order` field (lower = earlier)
- [ ] Add `dependsOn` if needed
- [ ] Create required SSM parameters
- [ ] Commit and push to trigger deployment

**No pipeline changes needed!** The buildspec automatically discovers new modules.