import json
import os
import socket
import time
import urllib.error
import urllib.request


DEFAULT_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


class NemotronError(Exception):
    def __init__(self, message, *, code="provider_error", retriable=False):
        super().__init__(message)
        self.code = code
        self.retriable = retriable


def is_nemotron_configured():
    return bool(os.getenv("NVIDIA_API_KEY", "").strip())


def nemotron_model():
    return os.getenv("PET_AGENT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _bounded_int(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _content_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for part in value:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def _completion_from_json(payload):
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise NemotronError(
            "NVIDIA returned an incomplete response.", code="invalid_response", retriable=True
        ) from exc
    text = _content_text(content).strip()
    if not text:
        raise NemotronError("NVIDIA returned an empty response.", code="empty_response", retriable=True)
    return text


def _tool_message_from_json(payload):
    try:
        choice = payload["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise NemotronError(
            "NVIDIA returned an incomplete response.", code="invalid_response", retriable=True
        ) from exc
    content = _content_text(message.get("content")).strip()
    raw_tool_calls = message.get("tool_calls") or []
    tool_calls = []
    for index, call in enumerate(raw_tool_calls):
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            continue
        function = call["function"]
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        arguments = function.get("arguments", "{}")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        tool_calls.append(
            {
                "id": str(call.get("id") or f"call_{index}"),
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    if not content and not tool_calls:
        raise NemotronError("NVIDIA returned an empty response.", code="empty_response", retriable=True)
    return {
        "content": content,
        "tool_calls": tool_calls,
        "finish_reason": str(choice.get("finish_reason") or ""),
    }


def _stream_completion(response):
    chunks = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
            delta = event.get("choices", [{}])[0].get("delta", {})
        except (json.JSONDecodeError, IndexError, TypeError, AttributeError):
            continue
        content = _content_text(delta.get("content"))
        if content:
            chunks.append(content)
    text = "".join(chunks).strip()
    if not text:
        raise NemotronError(
            "NVIDIA returned an empty streamed response.", code="empty_response", retriable=True
        )
    return text


def _request_completion(messages, timeout_seconds, *, tools=None, tool_choice=None):
    structured = bool(tools)
    stream = os.getenv("PET_AGENT_STREAM", "1") != "0" and not structured
    payload = {
        "model": nemotron_model(),
        "messages": messages,
        "temperature": 0.4,
        "top_p": 0.9,
        "max_tokens": _bounded_int("PET_AGENT_MAX_TOKENS", 700, 64, 2048),
        "stream": stream,
        "chat_template_kwargs": {
            "enable_thinking": os.getenv("PET_AGENT_THINKING", "0") == "1"
        },
    }
    if structured:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice or "auto"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        os.getenv("NVIDIA_API_URL", DEFAULT_API_URL),
        data=body,
        headers={
            "Authorization": f"Bearer {os.environ['NVIDIA_API_KEY'].strip()}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": "PixelVault-Pet-Agent/5.12",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if stream and "text/event-stream" in content_type:
                return _stream_completion(response)
            response_payload = json.loads(response.read().decode("utf-8"))
            if structured:
                return _tool_message_from_json(response_payload)
            return _completion_from_json(response_payload)
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            nested_error = error_payload.get("error") if isinstance(error_payload, dict) else None
            detail = str(
                error_payload.get("detail")
                or error_payload.get("message")
                or (nested_error.get("message") if isinstance(nested_error, dict) else "")
                or ""
            ).strip()
        except (json.JSONDecodeError, AttributeError, OSError):
            detail = ""
        if exc.code in {401, 403}:
            message = "NVIDIA rejected the API key. Check NVIDIA_API_KEY and restart the server."
            code = "authentication"
        elif exc.code == 429:
            message = "NVIDIA is rate-limiting requests right now."
            code = "rate_limited"
        elif exc.code >= 500:
            message = "NVIDIA is temporarily unavailable."
            code = "provider_unavailable"
        else:
            message = detail[:240] or f"NVIDIA rejected the request ({exc.code})."
            code = "request_rejected"
        raise NemotronError(
            message,
            code=code,
            retriable=exc.code == 429 or exc.code >= 500,
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise NemotronError(
            "NVIDIA took too long to begin or continue the response.",
            code="timeout",
            retriable=True,
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            code = "timeout"
            message = "NVIDIA took too long to begin or continue the response."
        else:
            code = "connection"
            message = "PixelVault could not reach NVIDIA."
        raise NemotronError(message, code=code, retriable=True) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise NemotronError(
            "NVIDIA returned an unreadable response.", code="invalid_response", retriable=True
        ) from exc


def ask_nemotron(messages, *, tools=None, tool_choice=None):
    if not is_nemotron_configured():
        return None
    base_timeout = _bounded_int("PET_AGENT_TIMEOUT_SECONDS", 60, 10, 120)
    retries = _bounded_int("PET_AGENT_RETRIES", 1, 0, 2)
    last_error = None
    for attempt in range(retries + 1):
        try:
            timeout = base_timeout if attempt == 0 else min(base_timeout, 20)
            return _request_completion(
                messages,
                timeout,
                tools=tools,
                tool_choice=tool_choice,
            )
        except NemotronError as exc:
            last_error = exc
            if not exc.retriable or attempt >= retries:
                raise
            time.sleep(0.4 * (attempt + 1))
    raise last_error or NemotronError("NVIDIA did not return a response.")
