from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import (
    core,
    aws_apigateway,
    aws_lambda,
    aws_kms,
    aws_iam,
    aws_dynamodb,
    aws_lambda_python)


class BenzaitenAwsApiServerStack(cdk.Stack):
    """
    Benzaiten API stack
    """
    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Shared resources
        kms = aws_kms.Key(
            self,
            'benzaiten-kms'
        )

        api_keys_db = aws_dynamodb.Table(
            self,
            'benzaiten-apikey-table',
            partition_key=aws_dynamodb.Attribute(
                name='api_key',
                type=aws_dynamodb.AttributeType.STRING
            ),
            table_name='benzaiten_api_keys',
            encryption=aws_dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=kms,
        )

        # API Lambda
        api_keys = aws_apigateway.ApiKey()
        api = aws_apigateway.RestApi(
            self,
            'benzaiten-api',
            rest_api_name='benzaiten-api',
            default_cors_preflight_options=aws_apigateway.CorsOptions(
                allow_headers=[
                    'Content-Type',
                    'X-Amz-Date',
                    'Authorization',
                    'X-Api-Key',
                    'X-Bztn-Key',
                    'X-Bztn-Sign'
                ],
                allow_methods=['PUT', 'GET'],
                allow_credentials=True,
                allow_origins=['http://localhost:3000']
            )
        )

        api_lambda_role = aws_iam.Role(
            self,
            'benzaiten-auth-role',
            assumed_by=aws_iam.ServicePrincipal('lambda.awsamazon.com'),
            description='Role for benzaiten auth lambda',
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name('AWSLambdaBasicExecutionRole ')
            ],
            inline_policies={
                'read_dynamo': aws_iam.PolicyDocument(statements=[
                    aws_iam.PolicyStatement(
                        actions=[
                            'dynamodb:GetItem',
                        ],
                        resources=[
                            api_keys_db.table_arn
                        ]
                    )
                ]),
                'kms': aws_iam.PolicyDocument(statements=[
                    aws_iam.PolicyStatement(
                        actions=[
                            "kms:Decrypt",
                            "kms:GenerateDataKeyWithoutPlaintext",
                            "kms:GenerateDataKeyPairWithoutPlaintext",
                            "kms:GenerateDataKeyPair",
                            "kms:ReEncryptFrom",
                            "kms:Encrypt",
                            "kms:ReEncryptTo",
                            "kms:GenerateDataKey",
                            "kms:DescribeKey",
                        ],
                        resources=[
                            kms.key_arn
                        ]
                    )
                ])
            }
        )

        api_auth_lambda_layer = aws_lambda_python.PythonLayerVersion(
            self,
            'benzaiten-auth-lambda-layer',
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            entry='src/layer/benzaiten_api',
            description="Benzaiten API commons"
        )

        api_metrics_put_lambda = aws_lambda_python.PythonFunction(
            self,
            'benzaiten-metrics_put-lambda',
            entry='src/lambda/api_metrics_put',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            index='put.py',
            handler='lambda_handler',
            environment_encryption=kms,
            role=api_lambda_role,
            layers=[api_auth_lambda_layer],
            memory_size=128,
            timeout=cdk.Duration.seconds(15),
            function_name='benzaitent_api_metrics_get',
        )

        api_metrics = api.root.add_resource('metrics')
        api_metrics.add_method(
            'PUT',
            aws_apigateway.LambdaIntegration(
                api_metrics_put_lambda,
                proxy=True
            ),
            api_key_required=True
        )

        cdk.CfnOutput(self, 'api_endpoint', value=api.url)
