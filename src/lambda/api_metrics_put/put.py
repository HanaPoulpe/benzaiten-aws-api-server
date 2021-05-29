"""
api: PUT /metrics/
Body: application/json
Structure:
{
    location_name:str,
    metrics: [
        metric_name: str
        timestamp: str,
        metric_date: %y-%d-%d %H:%M:%S,
        metric_value: str,
        metric_source: str
    ]
}

Headers: {
    X-Bztn-Key: str,
    X-Bztn-Sign: str
}
"""
import base64
import boto3
import datetime
import dataclasses
import Crypto.Hash
import json
import logging
import os
import typing

import authorizer
import response

# Logger
logging.basicConfig(
    format='%(asctime)s::%(levelname)s::%(filename)s.%(funcName)s(%(lineno)s)::%(message)s')

# Const
MAX_BODY_LENGTH = 20 * 1024 * 1024
SQS_DESTINATION = os.getenv('SQS_DESTINATION', 'unset_sqs')


@dataclasses.dataclass(frozen=True, eq=False)
class Metric:
    """Defines a metric"""
    metric_name: str
    time_span: str
    location_name: str
    metric_date: datetime.datetime
    metric_value: float
    metric_source: str

    @property
    def metric_system_key(self) -> str:
        """
        Generate metric system key:
        MSK = metric_name@location#time_span

        @rtype: str
        """
        return f"{self.metric_name}@{self.location_name}#{self.time_span}"

    def __eq__(self, b: object) -> bool:
        if isinstance(b, Metric):
            # If b is the same a Metric
            return (self.metric_name == b.metric_name and
                    self.time_span == b.time_span and
                    self.location_name == b.location_name and
                    self.metric_date == b.metric_date)
        elif hasattr(b, 'get') and callable(getattr(b, 'get')):
            # If b is a collection
            try:
                return (self.metric_name == b.get('metric_name') and
                        self.time_span == b.get('time_span') and
                        self.location_name == b.get('location_name') and
                        self.metric_date == b.get('metric_date'))
            except:
                return False

        # For any other case
        return False

    @staticmethod
    def get_from_dict(d: dict, location_name: typing.Optional[str] = None):
        """
        Create a metric from dict

        @param d: source dict
        @param location_name: location_name, this will overwrite d['location_name'] value if any
        @rtype: Metric
        """
        metric_date = d['metric_date']
        if isinstance(metric_date, str):
            metric_date = datetime.datetime.strptime(metric_date, '%Y-%m-%d %H:%M-%S')
        elif not isinstance(metric_date, datetime.datetime):
            raise TypeError(f"metric_date should be str or datetime, got {type(metric_date)}...")

        if not location_name:
            location_name = d['location_name']

        return Metric(
            metric_name=d['metric_name'],
            time_span=d['time_span'],
            location_name=location_name,
            metric_date=metric_date,
            metric_value=d['metric_value'],
            metric_source=d['metric_source']
        )

    def to_message(self) -> str:
        """
        Returns a string to be sent in SQS for processing

        @rtype: str
        """
        return json.dumps({
            'metric_name': self.metric_name,
            'time_span': self.time_span,
            'location_name': self.location_name,
            'metric_date': self.metric_date.strftime('%Y-%m-%d %H:%M:%S'),
            'metric_value': self.metric_value,
            'metric_source': self.metric_source,
            'msg_received_date_utc': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })


@dataclasses.dataclass
class Request:
    """Defines a request"""
    api_key: str
    signature: str
    location: str
    metrics: typing.Optional[typing.Set[Metric]]
    message: str
    headers: dict
    method: str
    host: str

    def add(self, metric: Metric):
        """
        Add a new metric to the metrics set

        @param metric: Metric to add
        @type metric: Metric
        @return: None
        """
        if self.metrics is None:
            self.metrics = set()

        if metric in self.metrics:
            # If the same metric have already been provided
            raise KeyError(f"Metric {metric.metric_system_key} already exists")

        self.metrics.add(metric)


class EventError(RuntimeError):
    """Defines an exception while parsing lambda event"""
    def __init__(self, r: response.BaseResponse):
        super(r.body)
        self.response = r


def lambda_handler(event, context):
    """AWS Lambda handler"""
    # Parse event
    logger = logging.getLogger()
    try:
        logger.info("Parsing Event...")
        event = parse_event(event)
    except EventError as e:
        logger.error(f"Error parsing: {e.response.body}")
        return e.response.get_response()

    logger.info("Checking permissions...")
    ret = authorizer.is_allowed(
        key=event.api_key,
        message=event.message,
        signature=event.signature,
        location=event.location,
        method=event.method
    )

    if not ret.is_ok():
        logger.error(f"Access denied: {ret.body}")
        return ret.get_response()

    # Process messages
    sqs = boto3.resource('sqs').Queue(SQS_DESTINATION)
    logger.info(f"Sending metrics")
    for m in event.metrics:
        sqs.send_message(
            MessageBody=m.to_message()
        )

    logger.info('Done')
    return response.BaseResponse(
        statusCode=response.HTTPCodes.Success.CREATED,
        headers={'X-Bztn-Key': event.api_key},
        body=json.dumps({
            'status': 'success',
            'processed': len(event.metrics)
        })
    )


def parse_event(event) -> Request:
    """
    Parses aws lambda event parameter

    @param event: AWS Event
    @return: Parsed request
    """
    logger = logging.getLogger()

    # Value checks
    if event['resource'] != 'metric':
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.BAD_MAPPING,
            headers={},
            body=f"Bad resource: {event['resource']}"
        ))

    method = event['httpMethod']
    if method != 'PUT':
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.METHOD_NOT_ALLOWED,
            headers={},
            body=f"Method {method} not allowed"
        ))

    if len(event['body']) >= MAX_BODY_LENGTH:
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.REQUEST_ENTRY_TOO_LARGE,
            headers={},
            body='Message too big for being processed'
        ))

    host = event['headers']['Host']
    headers = {k: v for k, v in event['headers'].items()}

    if event['queryStringParameters'] is not None:
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.BAD_REQUEST,
            headers={},
            body=f"0 parameters excepted, got {len(event['queryStringParameters'])}"
        ))

    body = event['body']
    if event['isBase64Encoded']:
        body = base64.b64decode(body)

    try:
        message = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(e)
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.BAD_REQUEST,
            headers={},
            body="Invalid JSon object"
        ))

    try:
        location = message['location_name']
        signature = headers['X-Bztn-Sign']
        api_key = headers['X-Bztn-Key']
    except KeyError as e:
        logger.error(f"Invalid key: {e}")
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.BAD_REQUEST,
            headers={},
            body='Bad request'
        ))

    if 'metrics' not in message or not hasattr(message['metrics'], '__iter__'):
        raise EventError(response.BaseResponse(
            statusCode=response.HTTPCodes.ClientError.BAD_REQUEST,
            headers={},
            body='Metrics list is empty or not iterable'
        ))

    resp = Request(
        headers=headers,
        api_key=api_key,
        signature=signature,
        message=body,
        method=method,
        location=location,
        host=host
    )

    for m in event['metrics']:
        try:
            resp.add(Metric.get_from_dict(m))
        except (TypeError, KeyError) as e:
            m = f"Invalid metric: {m}"
            logger.error(m)
            raise EventError(response.BaseResponse(
                statusCode=response.HTTPCodes.ClientError.BAD_REQUEST,
                headers={},
                body=m
            ))

    return resp
