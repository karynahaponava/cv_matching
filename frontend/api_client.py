import requests


def api_error_message(
    response: requests.Response,
    fallback: str = "Ошибка сервера",
) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if not isinstance(payload, dict):
        return f"{fallback} (HTTP {response.status_code})"

    message = str(payload.get("message") or fallback)
    code = payload.get("code")
    trace_id = payload.get("trace_id")
    context = [f"HTTP {response.status_code}"]
    if code:
        context.append(f"код: {code}")
    if trace_id:
        context.append(f"trace_id: {trace_id}")
    return f"{message} ({', '.join(context)})"
