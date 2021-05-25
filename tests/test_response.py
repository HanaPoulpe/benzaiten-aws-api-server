import base64
import json
import unittest

import src.layer.benzaiten_api.response as response


class TestBaseResponse(unittest.TestCase):
    def test_is_ok(self):
        t_resp = response.BaseResponse(
            statusCode=response.HTTPCodes.Success.OK,
            headers={},
            body=""
        )

        self.assertTrue(t_resp.is_ok(), 'Test code OK')
        t_resp.statusCode = response.HTTPCodes.Success.ACCEPTED
        self.assertTrue(t_resp.is_ok(), 'Test code ACCEPTED')
        t_resp.statusCode = response.HTTPCodes.ClientError.BAD_REQUEST
        self.assertFalse(t_resp.is_ok(), 'Test code BAD REQUEST')
        t_resp.statusCode = response.HTTPCodes.ClientError.CONFLICT
        self.assertFalse(t_resp.is_ok(), 'Test code CONFLICT')
        t_resp.statusCode = response.HTTPCodes.Information.SWITCHING_PROTOCOLS
        self.assertFalse(t_resp.is_ok(), 'Test code SWITCHING PROTOCOLS')
        t_resp.statusCode = response.HTTPCodes.Redirection.MULTIPLE_CHOICES
        self.assertFalse(t_resp.is_ok(), 'Test code Multiple Choices')
        t_resp.statusCode = response.HTTPCodes.Redirection.TEMPORARY_REDIRECT
        self.assertFalse(t_resp.is_ok(), 'Test code Temporary Redirect')

    def test_get_response(self):
        status = response.HTTPCodes.Success.OK
        headers = {
            "test_h": "test_v"
        }
        body = "teststring"

        t_resp = response.BaseResponse(
            statusCode=status,
            headers=headers,
            body=body
        )

        headers['Content-Type'] = 'application/json'

        out = t_resp.get_response()
        self.assertDictEqual(out,
                             {
                                 "isBase64Encoded": False,
                                 "statusCode": status,
                                 "headers": headers,
                                 "body": body
                             })

        out = t_resp.get_response(encode_base64=True)
        self.assertDictEqual(out,
                             {
                                 "isBase64Encoded": True,
                                 "statusCode": status,
                                 "headers": headers,
                                 "body": base64.b64encode(body.encode('UTF-8'))
                             })

        body = "not_encoded".encode("utf-8")
        t_resp.body = body
        out = t_resp.get_response()
        self.assertDictEqual(out,
                             {
                                 "isBase64Encoded": False,
                                 "statusCode": status,
                                 "headers": headers,
                                 "body": body
                             })

        body = base64.b64encode("encoded".encode('UTF-8'))
        t_resp.body = body
        out = t_resp.get_response()
        self.assertDictEqual(out,
                             {
                                 "isBase64Encoded": True,
                                 "statusCode": status,
                                 "headers": headers,
                                 "body": body
                             })

    def test_set_body_from_dict(self):
        status = response.HTTPCodes.Success.OK
        headers = {
            "test_h": "test_v"
        }
        body = {
            "test": 'me',
            "json": "decode",
            'float': 1.23
        }
        t_resp = response.BaseResponse(
            statusCode=status,
            headers=headers,
        )
        t_resp.set_body_from_dict(body)

        self.assertDictEqual(body,
                             json.loads(t_resp.body))
