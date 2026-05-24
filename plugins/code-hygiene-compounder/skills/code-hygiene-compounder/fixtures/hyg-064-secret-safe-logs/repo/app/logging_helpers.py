def failure_log(error, context):
    payload = {"level": "error", "message": str(error)}
    payload.update(context)
    return payload
