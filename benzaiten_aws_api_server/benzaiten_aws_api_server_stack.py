from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core, aws_apigateway, aws_lambda, aws_kms, aws_iam, aws_dynamodb


class BenzaitenAwsApiServerStack(cdk.Stack):

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

        api_lambda = aws_lambda.Function(
            self,
            'benzaiten-auth-lambda',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            code=aws_lambda.Code.from_asset('src/'),
            handler='app.lambda_handler',
            environment_encryption=kms,
            role=api_lambda_role
        )

        api = aws_apigateway.LambdaRestApi(
            self,
            'benzaiten-rest-api',
            handler=api_lambda,
            rest_api_name="benzaiten_rest_api",
        )
