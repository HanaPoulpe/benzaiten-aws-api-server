import base64
import datetime
import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

import src.layer.benzaiten_api.response as response
import src.aws_lambda.api_metrics_put.put as put


# Metric test
class TestMetric(TestCase):
    def test_metric_system_key(self):
        m = {
            'metric_name': 'mock_metric',
            'time_span': '5min',
            'location_name': 'mock_loc',
            'metric_date': datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            'metric_value': 12.34,
            'metric_source': 'test_case'
        }

        out = put.Metric(**m)
        self.assertEqual(
            f"{m['metric_name']}@{m['location_name']}#{m['time_span']}",
            out.metric_system_key
        )

    def test_eq(self):
        m = {
            'metric_name': 'mock_metric',
            'time_span': '5min',
            'location_name': 'mock_loc',
            'metric_date': datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            'metric_value': 12.34,
            'metric_source': 'test_case'
        }
        m1 = put.Metric(**m)

        m['metric_value'] = 45.67
        m2 = put.Metric(**m)

        self.assertEqual(m1, m2)
        self.assertEqual(m1, m)

        m['metric_name'] = 'mock_else'
        m2 = put.Metric(**m)
        self.assertNotEqual(m1, m2)
        self.assertNotEqual(m1, m)

        self.assertNotEqual(m1, {'bleh': 'nope'})
        self.assertNotEqual(m1, 456)

    def test_hash(self):
        m1 = put.Metric(
            'mock_metric',
            '5min',
            'mock_loc',
            datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            12.34,
            'test_case'
        )
        m2 = put.Metric(
            'mock_metric',
            '5min',
            'mock_loc2',
            datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            12.34,
            'test_case'
        )
        m3 = put.Metric(
            'mock_metric',
            '5min',
            'mock_loc',
            datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            42.34,
            'test_case'
        )

        self.assertNotEqual(hash(m1), hash(m2))
        self.assertEqual(hash(m1), hash(m3))

    def test_get_from_dict(self):
        m = {
            'metric_name': 'mock_metric',
            'time_span': '5min',
            'location_name': 'mock_loc',
            'metric_date': datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            'metric_value': 12.34,
            'metric_source': 'test_case'
        }
        m1 = put.Metric(**m)

        self.assertEqual(m1, put.Metric.get_from_dict(m))
        m['test'] = 'test'
        self.assertEqual(m1, put.Metric.get_from_dict(m))

        m['metric_date'] = '2021-06-02 12:34:56'
        self.assertEqual(m1, put.Metric.get_from_dict(m))

        m['metric_date'] = 'bleh'
        self.assertRaises(ValueError, put.Metric.get_from_dict, m)

        m['metric_date'] = 5
        self.assertRaises(TypeError, put.Metric.get_from_dict, m)

        self.assertRaises(KeyError, put.Metric.get_from_dict, {'mock': 'else'})

    def test_to_message(self):
        m = {
            'metric_name': 'mock_metric',
            'time_span': '5min',
            'location_name': 'mock_loc',
            'metric_date': datetime.datetime.strptime(
                '2021-06-02 12:34:56',
                '%Y-%m-%d %H:%M:%S'
            ),
            'metric_value': 12.34,
            'metric_source': 'test_case'
        }
        m1 = put.Metric(**m)

        out = m1.to_message()
        out_v = json.loads(out)

        m['metric_date'] = '2021-06-02 12:34:56'
        self.assertIn('msg_send_date_utc', out_v)
        m['msg_send_date_utc'] = out_v['msg_send_date_utc']

        self.assertDictEqual(m, out_v)


class TestRequest(TestCase):
    def test_add(self):
        rq = put.Request(
            api_key='mock_k',
            signature='mock_sig',
            location='mock_loc',
            message='mock_msg',
            headers=dict(),
            method='PUT',
            host='mock.host'
        )

        m1 = put.Metric(
            'metric_1',
            '5min',
            'mock_loc',
            datetime.datetime.now(),
            12.34,
            'mock_src'
        )
        m2 = put.Metric(
            'metric_2',
            '5min',
            'mock_loc',
            datetime.datetime.now(),
            12.34,
            'mock_src'
        )

        self.assertIsNone(rq.metrics)
        rq.add(m1)
        self.assertSetEqual({m1}, rq.metrics)
        rq.add(m2)
        self.assertSetEqual({m1, m2}, rq.metrics)
        self.assertRaises(KeyError, rq.add, m1)

        rq = put.Request(
            api_key='mock_k',
            signature='mock_sig',
            location='mock_loc',
            message='mock_msg',
            headers=dict(),
            method='PUT',
            host='mock.host',
            metrics=5
        )

        rq.add(m1)
        self.assertSetEqual({m1}, rq.metrics)


class TestEventError(TestCase):
    def test_init(self):
        put.EventError(put.response.BaseResponse(200, {}, ''))
        self.assertRaises(TypeError, put.EventError, 'wrong_type')


class TestParseEvent(TestCase):
    def test_bad_resource(self):
        event = {
            'resource': 'none',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_bad_method(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'GET',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_body_too_long(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': 'a' * 30000000,
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_query_string_parameters(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': {'kill': 'me'},
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_bad_body(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': 'not json',
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_bad_body_content(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo_power_rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_metrics_issue(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': 555
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        self.assertRaises(put.EventError, put.parse_event, event)

    def test_parse_ok(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        put.parse_event(event)

        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': base64.b64encode(json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }).encode('utf-8')),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': True,
        }
        put.parse_event(event)


class TestLambdaHandler(TestCase):
    def test_wrong_event(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        out = put.lambda_handler(event, None)
        self.assertNotEqual(out['statusCode']//100, 2)

    @patch('src.layer.benzaiten_api.authorizer.is_allowed',
           MagicMock(return_value=response.BaseResponse(
               statusCode=response.HTTPCodes.ClientError.FORBIDDEN,
               headers={},
               body=''
           )))
    def test_unauthorized(self):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        out = put.lambda_handler(event, None)
        self.assertNotEqual(out['statusCode'] // 100, 2)

    @patch('src.layer.benzaiten_api.authorizer.is_allowed',
           MagicMock(return_value=response.BaseResponse(
               statusCode=response.HTTPCodes.Success.OK,
               headers={},
               body=''
           )))
    @patch('boto3.resource')
    def test_ok(self, m_boto3_resource):
        event = {
            'resource': 'metric',
            'httpMethod': 'PUT',
            'body': json.dumps({
                'location_name': 'chez_borris',
                'metrics': [
                    {
                        'metric_name': 'soiree_disco',
                        'time_span': '5min',
                        'metric_date': '1995-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                    {
                        'metric_name': 'gogo power rangers',
                        'time_span': '1h',
                        'metric_date': '1993-05-08 12:34:56',
                        'metric_value': 12.34,
                        'metric_source': 'test_case'
                    },
                ]
            }),
            'headers': {
                'Host': 'mock',
                'X-Bztn-Key': 'mock_key',
                'X-Bztn-Sign': 'mock_sign'
            },
            'queryStringParameters': None,
            'isBase64Encoded': False,
        }
        out = put.lambda_handler(event, None)
        self.assertEqual(out['statusCode'] // 100, 2)
