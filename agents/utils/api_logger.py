"""
API call logging utilities
Uniformly print external API call inputs, responses, and timing
"""
import time
import json
from functools import wraps
from typing import Any, Callable, Optional


def log_api_call(api_name: str, log_request: bool = True, log_response: bool = True, max_response_length: int = 1000):
    """
    Decorator: log API call inputs, outputs, and timing.

    Args:
        api_name: API name (used for log labeling)
        log_request: Whether to log request parameters
        log_response: Whether to log response data
        max_response_length: Max response length (truncated if exceeded)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # Log request parameters
            if log_request:
                request_info = {
                    "args": [str(arg)[:200] for arg in args] if args else [],
                    "kwargs": {k: str(v)[:200] if not isinstance(v, (dict, list)) else v for k, v in kwargs.items()}
                }
                print(f"\n[API Call] {api_name}")
                print(f"[Request] {json.dumps(request_info, indent=2, ensure_ascii=False)[:500]}")

            try:
                # Execute API call
                result = func(*args, **kwargs)

                # Compute duration
                elapsed_time = time.time() - start_time

                # Log response
                if log_response:
                    result_str = str(result)
                    if len(result_str) > max_response_length:
                        result_str = result_str[:max_response_length] + f"... (truncated, total length: {len(str(result))})"
                    print(f"[Response] {result_str}")

                print(f"[Duration] {elapsed_time:.3f}s")

                return result

            except Exception as e:
                # Compute duration
                elapsed_time = time.time() - start_time

                # Log error
                print(f"[Error] {str(e)}")
                print(f"[Duration] {elapsed_time:.3f}s (failed)")

                raise

        return wrapper
    return decorator


def log_http_request(method: str, url: str, params: Optional[dict] = None, data: Optional[dict] = None):
    """
    Log HTTP request (for httpx calls).

    Args:
        method: HTTP method
        url: URL
        params: Query parameters
        data: Request body data
    """
    print(f"\n[HTTP Request] {method} {url}")
    if params:
        print(f"[Params] {json.dumps(params, indent=2, ensure_ascii=False)[:500]}")
    if data:
        print(f"[Data] {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")


def log_http_response(status_code: int, response_data: Any, elapsed_time: float, max_length: int = 1000):
    """
    Log HTTP response.

    Args:
        status_code: HTTP status code
        response_data: Response data
        elapsed_time: Duration (seconds)
        max_length: Max response length
    """
    response_str = str(response_data)
    if len(response_str) > max_length:
        response_str = response_str[:max_length] + f"... (truncated, total length: {len(str(response_data))})"

    print(f"[HTTP Response] Status: {status_code}")
    print(f"[HTTP Response] Data: {response_str}")
    print(f"[HTTP Response] Duration: {elapsed_time:.3f}s")
