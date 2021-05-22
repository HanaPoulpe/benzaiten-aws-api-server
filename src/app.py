import response


def lambda_handler(event, context):
    resp = response.BaseResponse(
        headers={},
        statusCode=response.HTTPCodes.ApplicationError.SERVICE_UNAVAILABLE,
        body="Not implemented Yet"
    )

    return resp.get_response()
