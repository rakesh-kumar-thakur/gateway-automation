import json
import boto3
import os
from datetime import datetime

codepipeline = boto3.client('codepipeline')

def lambda_handler(event, context):
    """
    Polls for new commits and triggers pipeline if changes detected
    """
    try:
        pipeline_name = os.environ['PIPELINE_NAME']
        
        # Get the latest pipeline execution
        executions = codepipeline.list_pipeline_executions(
            pipelineName=pipeline_name,
            maxResults=1
        )
        
        # Get current source revision from pipeline state
        pipeline_state = codepipeline.get_pipeline_state(name=pipeline_name)
        
        source_stage = pipeline_state['stageStates'][0]
        if source_stage['stageName'] == 'Source':
            # Check if source action has new revision available
            for action in source_stage.get('actionStates', []):
                if action['actionName'] == 'GitHubSource':
                    current_revision = action.get('currentRevision', {})
                    latest_execution = action.get('latestExecution', {})
                    
                    # If there's a revision but no execution, or execution is old
                    if current_revision and latest_execution.get('status') != 'InProgress':
                        # Trigger pipeline
                        response = codepipeline.start_pipeline_execution(
                            name=pipeline_name
                        )
                        
                        print(f"Pipeline triggered: {response['pipelineExecutionId']}")
                        return {
                            'statusCode': 200,
                            'body': json.dumps({
                                'message': 'Pipeline triggered',
                                'executionId': response['pipelineExecutionId']
                            })
                        }
        
        print("No new changes detected")
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'No changes detected'})
        }
        
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# Made with Bob
