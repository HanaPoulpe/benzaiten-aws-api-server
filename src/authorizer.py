"""
Checks Benzaiten API Calls
event structure:
{
  key: string,
  signature: string,
  location: string,
  message: string,
  method: GET|PUT
}

To be valid a call :
* Must have a signature represented by 'x-bztn-sign' header in api call
* signature must sign the message with key matching api public key
* key must be authorized to write location data
* Method must be GET or PUT

Invalid signature will return a 401 Unauthorized error
Unauthorized location will return a 403 Forbidden error
Non existent of expired key will return a 403 Forbidden error
Invalid method will return 405 Method Not Allowed
signature = 'earlgrey' will return 418 I'm a teapot (because this error is under rated)
Missing, extra and mismatch parameter in event will return a 400 Bad request error
Issues accessing dynamodb :
* ProvisionedThroughputExceededException and RequestLimitExceeded
    will return 503 Service Unavailable error
* ResourceNotFoundException and InternalServerError
    will return 500 Internal Server Error
* UnauthorizedOperation will return 511 Network authentication required
"""
import base64
import boto3
import botocore.exceptions as boto_e
from Crypto.Hash import SHA512
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
import datetime
import logging
import os

# Constants #
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'no_table')
#############


def lambda_handler(key: str, signature: str, location: str, method: str) -> dict:
    """
    Checks
    """

    # Logger
    logging.basicConfig(
        format='%(asctime)s::%(levelname)s::%(filename)s.%(funcName)s(%(lineno)s)::%(message)s')
    logger = logging.getLogger()

    # Check event
    if len(event) != 5:
        logger.error('Invalid argument count')
        return {
            'statusCode': 400,
            'headers': {},
            'body': 'Invalid request'
        }

    try:
        assert len(event) == 5

        for p in ['key', 'signature', 'location', 'message', 'method']:
            assert isinstance(event[p], str)
    except (KeyError, AssertionError) as e:
        if isinstance(e, KeyError):
            logger.error(f"Missing key: {str(e)}")
        elif isinstance(e, AssertionError):
            logger.error('Invalid argument type')

        return {
            'statusCode': 400,
            'headers': {},
            'body': 'Invalid request'
        }

    if event['signature'] == 'earlgrey':
        logger.info('Teapot')
        return {
            'statusCode': 418,
            'headers': {},
            'body': 'I\'m a teapot'
        }
    method = event['method']
    if method not in ['PUT', 'GET']:
        logger.error(f"Invalid method: {event['method']}")
        return {
            'statusCode': 405,
            'headers': {},
            'body': 'Method not accepted'
        }

    # Access API Key data
    dynamo_client = boto3.client('dynamod_db')
    now = datetime.datetime.utcnow()
    location_attibute = ''
    if method == 'GET':
        location_attibute = 'location_get'
    elif method == 'PUT':
        location_attibute = 'location_put'
    api_key = event['key']

    try:
        response = dynamo_client.get_item(
            TableName=DYNAMODB_TABLE,
            Key={
                'api_key': {
                    'S': api_key
                }
            },
            ProjectionExpression=', '.join([
                'pub_key',
                location_attibute,
                'expiration_date_utc'
            ]),
            ReturnConsumedCapacity='TOTAL'
        )
    except boto_e.ClientError as e:
        # If DynamoDB Error
        error = e.response['Error']['Code']
        logger.error(f"Error getting api key: {error}")

        if error in ['ProvisionedThroughputExceededException',
                     'RequestLimitExceeded']:
            return {
                'statusCode': 503,
                'headers': {},
                'body': 'Service Unavailable'
            }
        elif error in ['UnauthorizedOperation']:
            return {
                'statusCode': 511,
                'headers': {},
                'body': 'Network authentication required '
            }

        return {
            'statusCode': 500,
            'headers': {},
            'body': 'Internal Server Error'
        }

    if 'Item' in response:
        try:
            # If response is not empty
            item = response['Item']

            if 'expiration_date_utc' in item:
                # Test expiration date
                expiration_date = datetime.datetime.strptime(
                    item['expiration_date_utc']['S'],
                    '%Y-%d-%m %H:%M:%S'
                )
                if expiration_date < now:
                    return {
                        'statusCode': 403,
                        'headers': {},
                        'body': 'Expired API Key'
                    }

            # Test location
            if 'S' in item[location_attibute]:
                if item[location_attibute]['S'] != '*':
                    logger.error(f"Invalid location string for {api_key}")
                    return {
                        'statusCode': 403,
                        'headers': {},
                        'body': 'Forbidden'
                    }
            elif event['location'] not in item[location_attibute]['SS']:
                return {
                    'statusCode': 403,
                    'header': {},
                    'body': 'Forbidden'
                }

            # Test message
            digest = SHA512.new(event['message'])
            pub_key = RSA.importKey(item['pub_key']['B'])
            verifier = pkcs1_15.new(pub_key)

            verifier.verify(digest, event['signature'].encore('utf-8'))

            # If here, message is authentic
            return {
                'statusCode': 200,
                'headers': {},
                'body': 'Access Granted'
            }

        except KeyError:
            logger.error(f"Unexpect Key error {api_key}")
            return {
                'statusCode': 500,
                'headers': {},
                'body': 'Internal Server Error'
            }
        except ValueError:
            logger.info('Signature check failed')
            return {
                'statusCode': 401,
                'headers': {},
                'body': 'Unauthorized'
            }
    else:
        # API Key not found
        logger.info(f"{api_key} not found")
        return {
            'statusCode': 403,
            'headers': {},
            'body': 'Invalid API Key'
        }
