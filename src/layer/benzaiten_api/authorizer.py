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

try:
    import response
except ModuleNotFoundError:
    import src.layer.benzaiten_api.response as response

# Constants #
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'no_table')
#############


def is_allowed(key: str, message: str, signature: str, location: str, method: str) \
        -> response.BaseResponse:
    """
    Checks if parameters allows the request to be processed any further

    :param key: Client API Key
    :param message: Request complete message as str
    :param signature: Message signature
    :param location: Location ID
    :param method: HTTP Method
    :return: HTTP Response
    """

    logger = logging.getLogger()

    if method not in ['PUT', 'GET']:
        logger.error(f"Invalid method: {method}")
        return response.BaseResponse(
            statusCode=405,
            headers={},
            body='Method not accepted'
        )
    if signature == 'earlgrey':
        logger.info('Teapot')
        return response.BaseResponse(
            statusCode=418,
            headers={},
            body='I\'m a teapot'
        )

    # Access API Key data
    dynamo_client = boto3.client('dynamod_db')
    now = datetime.datetime.utcnow()
    location_attribute = ''
    if method == 'GET':
        location_attribute = 'location_get'
    elif method == 'PUT':
        location_attribute = 'location_put'

    try:
        resp = dynamo_client.get_item(
            TableName=DYNAMODB_TABLE,
            Key={
                'api_key': {
                    'S': key
                }
            },
            ProjectionExpression=', '.join([
                'pub_key',
                location_attribute,
                'expiration_date_utc'
            ]),
            ReturnConsumedCapacity='TOTAL'
        )
    except boto_e.ClientError as e:
        # If DynamoDB Error
        error = e.response['Error']['Code']
        logger.error(f"Error getting api key: {error}:{e.operation_name}")

        if error in ['ProvisionedThroughputExceededException',
                     'RequestLimitExceeded']:
            return response.BaseResponse(
                statusCode=503,
                headers={},
                body='Service Unavailable'
            )
        elif error in ['UnauthorizedOperation']:
            return response.BaseResponse(
                statusCode=511,
                headers={},
                body='Network authentication required '
            )

        return response.BaseResponse(
            statusCode=500,
            headers={},
            body='Internal Server Error'
        )

    if 'Item' in resp:
        try:
            # If response is not empty
            item = resp['Item']

            if 'expiration_date_utc' in item:
                # Test expiration date
                try:
                    expiration_date = datetime.datetime.strptime(
                        item['expiration_date_utc']['S'],
                        '%Y-%m-%d %H:%M:%S'
                    )
                    if expiration_date < now:
                        return response.BaseResponse(
                            statusCode=403,
                            headers={},
                            body='Expired API Key'
                        )
                except ValueError:
                    logger.error(f"Invalid date: {item['expiration_date_utc']['S']}")
                    return response.BaseResponse(
                        statusCode=500,
                        headers={},
                        body='Internal Server Error'
                    )

            # Test location
            if 'S' in item[location_attribute]:
                if item[location_attribute]['S'] != '*':
                    logger.error(f"Invalid location string for {key}")
                    return response.BaseResponse(
                        statusCode=403,
                        headers={},
                        body='Forbidden'
                    )
            elif location not in item[location_attribute]['SS']:
                return response.BaseResponse(
                    statusCode=403,
                    headers={},
                    body='Forbidden'
                )

            # Test message
            digest = SHA512.new(message.encode('utf-8'))
            pub_key = RSA.importKey(item['pub_key']['B'])
            verifier = pkcs1_15.new(pub_key)

            verifier.verify(digest, base64.b64decode(signature.encode('utf-8')))

            # If here, message is authentic
            return response.BaseResponse(
                statusCode=200,
                headers={},
                body='Access Granted'
            )

        except KeyError:
            logger.error(f"Unexpect Key error {key}")
            return response.BaseResponse(
                statusCode=500,
                headers={},
                body='Internal Server Error'
            )
        except ValueError:
            logger.info('Signature check failed')
            return response.BaseResponse(
                statusCode=401,
                headers={},
                body='Unauthorized'
            )
    else:
        # API Key not found
        logger.info(f"{key} not found")
        return response.BaseResponse(
            statusCode=403,
            headers={},
            body='Invalid API Key'
        )
