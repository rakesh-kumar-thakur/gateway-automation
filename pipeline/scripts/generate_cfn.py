#!/usr/bin/env python3
"""
generate_cfn.py
---------------
Reads aws/api-gateway/endpoints.yaml and renders a fully expanded
CloudFormation template into aws/api-gateway/template.yaml.

Usage:
    python pipeline/scripts/generate_cfn.py

The pipeline runs this automatically before cfn-lint / deploy.
You can also run it locally after editing endpoints.yaml.
"""

import yaml
import re
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENDPOINTS_FILE = ROOT / "aws/api-gateway/endpoints.yaml"
TEMPLATE_FILE  = ROOT / "aws/api-gateway/template.yaml"

# ── Helpers ──────────────────────────────────────────────────────────────────

def pascal(text: str) -> str:
    """Convert 'my-path_name' -> 'MyPathName' for use as CFN logical IDs."""
    return re.sub(r'[^a-zA-Z0-9]', ' ', text).title().replace(' ', '')

def method_title(method: str) -> str:
    return method.capitalize()

def indent(text: str, spaces: int) -> str:
    pad = ' ' * spaces
    return '\n'.join(pad + line if line.strip() else line for line in text.splitlines())

# ── Resource block builders ───────────────────────────────────────────────────

def lambda_resource(ep: dict) -> str:
    p       = pascal(ep['path'])
    desc    = ep['description']
    runtime = ep['runtime']
    handler = ep['handler']
    method  = ep['method'].upper()
    code    = indent(ep['code'].rstrip(), 10)

    return f"""\
  # Lambda: {desc}  ({method} /{ep['path']})
  Lambda{p}:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${{Environment}}-{desc}"
      Runtime: {runtime}
      Handler: {handler}
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        ZipFile: |
{code}
      Tags:
        - Key: Environment
          Value: !Ref Environment
        - Key: Endpoint
          Value: {method} /{ep['path']}
"""

def resource_block(ep: dict) -> str:
    p = pascal(ep['path'])
    return f"""\
  Resource{p}:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RestApi
      ParentId: !GetAtt RestApi.RootResourceId
      PathPart: {ep['path']}
"""

def method_block(ep: dict) -> str:
    p      = pascal(ep['path'])
    m      = ep['method'].upper()
    mt     = method_title(ep['method'])
    return f"""\
  Method{p}{mt}:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RestApi
      ResourceId: !Ref Resource{p}
      HttpMethod: {m}
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub
          - "arn:aws:apigateway:${{AWS::Region}}:lambda:path/2015-03-31/functions/${{Fn}}/invocations"
          - Fn: !GetAtt Lambda{p}.Arn
"""

def permission_block(ep: dict) -> str:
    p = pascal(ep['path'])
    m = ep['method'].upper()
    mt = method_title(ep['method'])
    return f"""\
  Permission{p}{mt}:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt Lambda{p}.Arn
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub "arn:aws:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:${{RestApi}}/*/{m}/{ep['path']}"
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Reading endpoints from: {ENDPOINTS_FILE}")
    with open(ENDPOINTS_FILE) as f:
        data = yaml.safe_load(f)

    endpoints = data.get('Endpoints', [])
    if not endpoints:
        print("ERROR: No endpoints found in endpoints.yaml", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(endpoints)} endpoint(s): " +
          ", ".join(f"{e['method'].upper()} /{e['path']}" for e in endpoints))

    # Build generated block
    blocks = []
    depends_on = []
    for ep in endpoints:
        p  = pascal(ep['path'])
        mt = method_title(ep['method'])
        depends_on.append(f"Method{p}{mt}")
        blocks.append(lambda_resource(ep))
        blocks.append(resource_block(ep))
        blocks.append(method_block(ep))
        blocks.append(permission_block(ep))

    generated = '\n'.join(blocks)

    # Read current template
    with open(TEMPLATE_FILE) as f:
        template = f.read()

    # Replace generated section
    pattern = r'(  # GENERATED_RESOURCES_START\n).*?(  # GENERATED_RESOURCES_END)'
    replacement = r'\g<1>' + generated + r'  # GENERATED_RESOURCES_END'
    new_template, count = re.subn(pattern, replacement, template, flags=re.DOTALL)

    if count == 0:
        print("ERROR: Could not find GENERATED_RESOURCES_START/END markers in template.yaml",
              file=sys.stderr)
        sys.exit(1)

    # Inject/replace DependsOn into ApiDeployment (handles both first-run and re-run)
    depends_str = '\n'.join(f'      - {d}' for d in depends_on)
    new_template = re.sub(
        r'(  ApiDeployment:\n    Type: AWS::ApiGateway::Deployment\n)'
        r'(?:    # DependsOn list is injected by generate_cfn\.py|    DependsOn:\n(?:      - \S+\n)*)',
        f'\\1    DependsOn:\n{depends_str}\n',
        new_template
    )

    with open(TEMPLATE_FILE, 'w') as f:
        f.write(new_template)

    print(f"template.yaml updated with {len(endpoints)} endpoint(s).")
    print("DependsOn injected:", depends_on)

if __name__ == '__main__':
    main()
