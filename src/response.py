"""
Manages response for api calls
"""
import base64
import binascii
import dataclasses
import json
import logging
import typing


@dataclasses.dataclass
class BaseResponse:
    """Represent a response to an API call

    @statusCode: int
        HTTP Response code

    @headers: dict
        Dictionary of headers

    @body: Union[str, bytes]
        Body of the response

    @is_ok(): bool
        Is the response an HTTP OK

    @get_response(is_base64_encoded=False, encode_base64=False): dict
        Generate the response to be returned

    @set_set_body_from_dict(body):
        Set the body to the json string matching a dictionary
    """
    statusCode: int
    headers: dict
    body: typing.Union[str, bytes] = ""

    def is_ok(self) -> bool:
        """
        Check is the statusCode is in the 200

        Returns
        -------
        bool
        """
        return self.statusCode // 100 == 2

    def get_response(self, encode_base64: bool = False) -> dict:
        """
        Dict to return at the end of lambda function


        Parameters
        ----------
        encode_base64 : bool, optional
            Encode body str to base64

        Returns
        -------
        dict
        """
        # Prepare
        logger = logging.getLogger()

        is_base64_encoded = False
        if isinstance(self.body, bytes):
            # For bytes, check encoding
            try:
                if base64.b64encode(base64.b64decode(self.body)) == self.body:
                    is_base64_encoded = True
            except binascii.Error:
                pass

        # Encode to base64 if needed
        if encode_base64:
            logger.debug("Encoding to base64")
            body = base64.b64encode(
                self.body if isinstance(self.body, bytes) else self.body.encode('UTF-8')
            )
            is_base64_encoded = True
        else:
            body = self.body

        return {
            "isBase64Encoded": is_base64_encoded,
            "statusCode": self.statusCode,
            "headers": self.headers,
            "body": body
        }

    def set_body_from_dict(self, body: dict):
        """
        Set the body to the json string matching a dictionary

        Parameters
        ----------
        body : dict
            Dictionary to convert to body

        Returns
        -------
        None
        """
        self.body = json.dumps(body)


class HTTPCodes:
    """Collection of HTTP Codes"""
    class Information:
        """Information class HTTP Codes"""
        CONTINUE = 100
        SWITCHING_PROTOCOLS = 101
        PROCESSING = 102
        EARLY_HINTS = 103

    class Success:
        """Success class HTTP Codes"""
        OK = 200
        CREATED = 201
        ACCEPTED = 202
        NON_AUTHORITATIVE_INFORMATION = 203
        NO_CONTENT = 204
        RESET_CONTENT = 205
        PARTIAL_CONTENT = 206

    class Redirection:
        """Redirection class HTTP Codes"""
        MULTIPLE_CHOICES = 300
        MOVED_PERMANENTLY = 301
        FOUND = 302
        SEE_OTHER = 303
        NOT_MODIFIED = 304
        USE_PROXY = 305
        SWITCH_PROXY = 306
        TEMPORARY_REDIRECT = 307
        PERMANENT_REDIRECT = 308
        TOO_MANY_REDIRECTS = 310

    class ClientError:
        """Client Error class HTTP Codes"""
        BAD_REQUEST = 400
        UNAUTHORIZED = 401
        PAYMENT_REQUIRED = 402
        FORBIDDEN = 403
        NOT_FOUND = 404
        METHOD_NOT_ALLOWED = 405
        NOT_ACCEPTABLE = 406
        PROXY_AUTHENTICATION_REQUIRED = 407
        REQUEST_TIME_OUT = 408
        CONFLICT = 409
        GONE = 410
        LENGTH_REQUIRED = 411
        PRECONDITION_FAILED = 412
        REQUEST_ENTRY_TOO_LARGE = 413
        REQUEST_URI_TOO_LONG = 414
        UNSUPPORTED_MEDIA_TYPE = 415
        REQUEST_RANGE_UNSATISFIABLE = 416
        EXPECTATION_FAILED = 417
        I_M_A_TEAPOT = 418
        BAD_MAPPING = 421
        TOO_EARLY = 425
        UPGRADE_REQUIRED = 426
        TOO_MANY_REQUESTS = 429
        UNAVAILABLE_FOR_LEGAL_REASONS = 451

    class ApplicationError:
        """Server/Application Error class HTTP Codes"""
        INTERNAL_SERVER_ERROR = 500
        NOT_IMPLEMENTED = 501
        BAD_GATEWAY = 502
        SERVICE_UNAVAILABLE = 503
        GATEWAY_TIME_OUT = 504
        HTTP_VERSION_NOT_SUPPORTED = 505
        BANDWIDTH_LIMIT_EXCEEDED = 509
