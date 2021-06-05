"""
api: PUT /metrics/
Body: application/json
Structure:
{
    location_name:str,
    metrics: [
        {
            metric_name: str
            time_span: str,
            metric_date: %y-%d-%d %H:%M:%S,
            metric_value: float,
            metric_source: str
        }, ...
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
import json
import logging
import os
import typing

try:
    import authorizer
except ModuleNotFoundError:
    import src.layer.benzaiten_api.authorizer as authorizer
try:
    import response
except ModuleNotFoundError:
    import src.layer.benzaiten_api.response as response

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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Metric):
            # If b is the same a Metric
            return (self.metric_name == other.metric_name and
                    self.time_span == other.time_span and
                    self.location_name == other.location_name and
                    self.metric_date == other.metric_date)
        elif hasattr(other, 'get') and callable(getattr(other, 'get')):
            # If b is a collection
            return (self.metric_name == other.get('metric_name') and
                    self.time_span == other.get('time_span') and
                    self.location_name == other.get('location_name') and
                    self.metric_date == other.get('metric_date'))

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
            metric_date = datetime.datetime.strptime(metric_date, '%Y-%m-%d %H:%M:%S')
        elif not isinstance(metric_date, datetime.datetime):
            raise TypeError(
                f"metric_date should be str with format %Y-%m-%d %H:%M:%S or datetime,"
                f" got {type(metric_date)}...")

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
            'msg_send_date_utc': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })

    def __hash__(self):
        return hash(f"{self.metric_date.strftime('%Y%m%d%H%M%S')}{self.metric_system_key}")


@dataclasses.dataclass
class Request:
    """Defines a request"""
    api_key: str
    signature: str
    location: str
    message: str
    headers: dict
    method: str
    host: str
    metrics: typing.Optional[typing.Set[Metric]] = None

    def add(self, metric: Metric):
        """
        Add a new metric to the metrics set

        @param metric: Metric to add
        @type metric: Metric
        @return: None
        """
        if not isinstance(self.metrics, set):
            self.metrics = set()

        if metric in self.metrics:
            # If the same metric have already been provided
            raise KeyError(f"Metric {metric.metric_system_key} already exists")

        self.metrics.add(metric)


class EventError(Exception):
    """Defines an exception while parsing lambda event"""
    def __init__(self, r: response.BaseResponse):
        if not isinstance(r, response.BaseResponse):
            raise TypeError(f"Invalid type, got {type(r)} instead of BaseResponse")
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
    ).get_response()


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
    headers = event['headers']

    if event['queryStringParameters']:
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

    for m in message['metrics']:
        try:
            resp.add(Metric.get_from_dict(m, location_name=location))
        except (TypeError, KeyError) as e:
            m = f"Invalid metric: {m}"
            logger.error(m)
            raise EventError(response.BaseResponse(
                statusCode=response.HTTPCodes.ClientError.BAD_REQUEST,
                headers={},
                body=m
            ))

    return resp
