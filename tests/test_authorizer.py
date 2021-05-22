"""
Test case for api authorizer

author: hana
update: 2021-05-22
"""

import botocore.exceptions as boto_e
import base64
import Crypto.PublicKey.RSA
from Crypto.Hash import SHA512
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from unittest import TestCase
from unittest.mock import MagicMock, patch

import src.authorizer as authorizer
import src.response as response


# MockClasses #
class MockBoto3Client:
    """
    Mock boto3.client() return
    """
    def __init__(self):
        self.exception = None
        self.values = None

    def get_item(self, **kwargs):
        if self.exception:
            raise self.exception

        return self.values
###############


# Testcase #
class TestIsAllowed(TestCase):
    """
    Tests authorizer.is_allowed
    """

    ProvisionedThroughputExceededException = boto_e.ClientError(
        {'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'get_item')
    RequestLimitExceeded = boto_e.ClientError({'Error': {'Code': 'RequestLimitExceeded'}}, 'get_item')
    UnauthorizedOperation = boto_e.ClientError({'Error': {'Code': 'UnauthorizedOperation'}}, 'get_item')
    UnknownError = boto_e.ClientError({'Error': {'Code': 'OtherException'}}, 'get_item')

    valid_key = Crypto.PublicKey.RSA.generate(2048)
    invalid_key = Crypto.PublicKey.RSA.generate(2048)

    ret_ok = response.BaseResponse(
        statusCode=response.HTTPCodes.Success.OK,
        headers={},
        body='Access Granted'
    )
    ret_teapot = response.BaseResponse(
        statusCode=418,
        headers={},
        body='I\'m a teapot'
    )
    ret_invalid_method = response.BaseResponse(
        statusCode=405,
        headers={},
        body='Method not accepted'
    )
    ret_unavailable = response.BaseResponse(
        statusCode=503,
        headers={},
        body='Service Unavailable'
    )
    ret_net_auth =  response.BaseResponse(
        statusCode=511,
        headers={},
        body='Network authentication required '
    )
    ret_boto_err_other = response.BaseResponse(
        statusCode=500,
        headers={},
        body='Internal Server Error'
    )
    ret_expired_key = response.BaseResponse(
        statusCode=403,
        headers={},
        body='Expired API Key'
    )
    ret_internal = response.BaseResponse(
        statusCode=500,
        headers={},
        body='Internal Server Error'
    )
    ret_forbidden = response.BaseResponse(
        statusCode=403,
        headers={},
        body='Forbidden'
    )
    ret_unauthorized = response.BaseResponse(
        statusCode=401,
        headers={},
        body='Unauthorized'
    )
    ret_invalid_api = response.BaseResponse(
        statusCode=403,
        headers={},
        body='Invalid API Key'
    )

    @patch('boto3.client')
    def test_not_issues(self, m_boto_client):
        """
        Test a normal call
        """
        key = 'mock_key'
        message = 'mock_message'
        location = 'mock_location'
        method = 'GET'
        digest = SHA512.new(message.encode('utf-8'))
        signer = Crypto.Signature.pkcs1_15.new(TestIsAllowed.valid_key)
        signed = signer.sign(digest)
        signature = base64.b64encode(signed).decode('utf-8')

        boto_r = MockBoto3Client()
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_get': {
                    'S': '*'
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }

        m_boto_client.return_value = boto_r

        out = authorizer.is_allowed(key, message, signature, location, method)
        self.assertEqual(TestIsAllowed.ret_ok, out)

        method = 'PUT'
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_put': {
                    'SS': [location, 'mock_else']
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }

        out = authorizer.is_allowed(key, message, signature, location, method)
        self.assertEqual(TestIsAllowed.ret_ok, out)

    @patch('boto3.client')
    def test_teapot(self, m_boto_client):
        """
        Test easter egg
        """
        boto_r = MockBoto3Client()
        boto_r.exception = NotImplementedError('Should not be here')

        m_boto_client.return_value = boto_r
        out = authorizer.is_allowed('mock_key', 'mock_message', 'earlgrey', 'mock_signature', 'GET')
        self.assertEqual(TestIsAllowed.ret_teapot, out)

    @patch('boto3.client')
    def test_invalid_method(self, m_boto_client):
        """
        Test invalid method
        """
        boto_r = MockBoto3Client()
        boto_r.exception = NotImplementedError('Should not be here')

        m_boto_client.return_value = boto_r
        out = authorizer.is_allowed('mock_key', 'mock_message', 'earlgrey', 'mock_signature',
                                    'INVALID')
        self.assertEqual(TestIsAllowed.ret_invalid_method, out)

    @patch('boto3.client')
    def test_dynamodb_exceptions(self, m_boto_client):
        params = {
            'key': 'mock_key',
            'message': 'mock_message',
            'signature': 'mock_signature',
            'location': 'mock_location',
            'method': 'GET'
        }

        boto_r = MockBoto3Client()
        m_boto_client.return_value = boto_r

        # Throughput Error
        boto_r.exception = TestIsAllowed.ProvisionedThroughputExceededException
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_unavailable, out)

        # RequestLimit Error
        boto_r.exception = TestIsAllowed.RequestLimitExceeded
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_unavailable, out)

        # Network Issue
        boto_r.exception = TestIsAllowed.UnauthorizedOperation
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_net_auth, out)

        # Other Issues
        boto_r.exception = TestIsAllowed.UnknownError
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_boto_err_other, out)

    @patch('boto3.client')
    def test_invalid_expiration_date(self, m_boto_client):
        params = {
            'key': 'mock_key',
            'message': 'mock_message',
            'signature': 'mock_signature',
            'location': 'mock_location',
            'method': 'GET'
        }

        boto_r = MockBoto3Client()
        m_boto_client.return_value = boto_r

        # Test expired key
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '1999-12-31 23:59:59'
                },
                'location_get': {
                    'S': '*'
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_expired_key, out)

        # Test invalid date
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': 'invalid date'
                },
                'location_get': {
                    'S': '*'
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_internal, out)

        # Test invalid type
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'X': 'invalid date'
                },
                'location_get': {
                    'S': '*'
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_internal, out)

    @patch('boto3.client')
    def test_invalid_location(self, m_boto_client):
        params = {
            'key': 'mock_key',
            'message': 'mock_message',
            'signature': 'mock_signature',
            'location': 'mock_location',
            'method': 'GET'
        }

        boto_r = MockBoto3Client()
        m_boto_client.return_value = boto_r

        # Invalid S
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_get': {
                    'S': 'invalid'
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_forbidden, out)

        # Invalid SS
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_get': {
                    'SS': ['invalid', 'disney land']
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_forbidden, out)

        # Invalid Type
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_get': {
                    'X': ['invalid', 'disney land']
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_internal, out)

    @patch('boto3.client')
    def test_invalid_signature(self, m_boto_client):
        key = 'mock_key'
        message = 'mock_message'
        location = 'mock_location'
        method = 'GET'
        digest = SHA512.new(message.encode('utf-8'))
        signer = Crypto.Signature.pkcs1_15.new(TestIsAllowed.valid_key)
        signed = signer.sign(digest)
        signature = base64.b64encode(signed).decode('utf-8')

        digest = SHA512.new(message.encode('utf-8'))
        signer = Crypto.Signature.pkcs1_15.new(TestIsAllowed.invalid_key)
        signed = signer.sign(digest)
        signature_invalid_sign = base64.b64encode(signed).decode('utf-8')

        digest = SHA512.new('invalid message'.encode('utf-8'))
        signed = signer.sign(digest)
        signature_invalid_msg_sign = base64.b64encode(signed).decode('utf-8')

        signer = Crypto.Signature.pkcs1_15.new(TestIsAllowed.valid_key)
        signed = signer.sign(digest)
        signature_invalid_msg = base64.b64encode(signed).decode('utf-8')

        boto_r = MockBoto3Client()
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_get': {
                    'S': '*'
                },
                'pub_key': {
                    "B": TestIsAllowed.valid_key.public_key().exportKey()
                }
            }
        }
        m_boto_client.return_value = boto_r

        # Test wrong sign
        out = authorizer.is_allowed(key, message, signature_invalid_sign, location, method)
        self.assertEqual(TestIsAllowed.ret_unauthorized, out)

        # Test wrong sign, wrong msg
        out = authorizer.is_allowed(key, message, signature_invalid_msg_sign, location, method)
        self.assertEqual(TestIsAllowed.ret_unauthorized, out)

        # Test wrong message
        out = authorizer.is_allowed(key, message, signature_invalid_msg, location, method)
        self.assertEqual(TestIsAllowed.ret_unauthorized, out)

        # Test invalid sign
        out = authorizer.is_allowed(key, message, 'a' * 100000000, location, method)
        self.assertEqual(TestIsAllowed.ret_unauthorized, out)

        # Test invalid key store
        boto_r.values = {
            'Item': {
                'expiration_date_utc': {
                    'S': '2999-12-31 23:59:59'
                },
                'location_get': {
                    'S': '*'
                },
                'pub_key': {
                    "B": 'a' * 100000000
                }
            }
        }
        out = authorizer.is_allowed(key, message, signature, location, method)
        self.assertEqual(TestIsAllowed.ret_unauthorized, out)

    @patch("boto3.client")
    def test_invalid_api_key(self, m_boto_client):
        params = {
            'key': 'mock_key',
            'message': 'mock_message',
            'signature': 'mock_signature',
            'location': 'mock_location',
            'method': 'GET'
        }

        boto_r = MockBoto3Client()
        m_boto_client.return_value = boto_r

        # Invalid S
        boto_r.values = {}
        out = authorizer.is_allowed(**params)
        self.assertEqual(TestIsAllowed.ret_invalid_api, out)
