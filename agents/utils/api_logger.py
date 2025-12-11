"""
API调用日志工具
统一打印外部API调用的入参、响应和耗时
"""
import time
import json
from functools import wraps
from typing import Any, Callable, Optional


def log_api_call(api_name: str, log_request: bool = True, log_response: bool = True, max_response_length: int = 1000):
    """
    装饰器：记录API调用的入参、响应和耗时
    
    Args:
        api_name: API名称（用于日志标识）
        log_request: 是否记录请求参数
        log_response: 是否记录响应数据
        max_response_length: 响应数据的最大长度（超过会截断）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # 记录请求参数
            if log_request:
                request_info = {
                    "args": [str(arg)[:200] for arg in args] if args else [],
                    "kwargs": {k: str(v)[:200] if not isinstance(v, (dict, list)) else v for k, v in kwargs.items()}
                }
                print(f"\n[API Call] {api_name}")
                print(f"[Request] {json.dumps(request_info, indent=2, ensure_ascii=False)[:500]}")
            
            try:
                # 执行API调用
                result = func(*args, **kwargs)
                
                # 计算耗时
                elapsed_time = time.time() - start_time
                
                # 记录响应
                if log_response:
                    result_str = str(result)
                    if len(result_str) > max_response_length:
                        result_str = result_str[:max_response_length] + f"... (truncated, total length: {len(str(result))})"
                    print(f"[Response] {result_str}")
                
                print(f"[Duration] {elapsed_time:.3f}s")
                
                return result
                
            except Exception as e:
                # 计算耗时
                elapsed_time = time.time() - start_time
                
                # 记录错误
                print(f"[Error] {str(e)}")
                print(f"[Duration] {elapsed_time:.3f}s (failed)")
                
                raise
        
        return wrapper
    return decorator


def log_http_request(method: str, url: str, params: Optional[dict] = None, data: Optional[dict] = None):
    """
    记录HTTP请求（用于httpx调用）
    
    Args:
        method: HTTP方法
        url: URL
        params: 查询参数
        data: 请求体数据
    """
    print(f"\n[HTTP Request] {method} {url}")
    if params:
        print(f"[Params] {json.dumps(params, indent=2, ensure_ascii=False)[:500]}")
    if data:
        print(f"[Data] {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")


def log_http_response(status_code: int, response_data: Any, elapsed_time: float, max_length: int = 1000):
    """
    记录HTTP响应
    
    Args:
        status_code: HTTP状态码
        response_data: 响应数据
        elapsed_time: 耗时（秒）
        max_length: 响应数据最大长度
    """
    response_str = str(response_data)
    if len(response_str) > max_length:
        response_str = response_str[:max_length] + f"... (truncated, total length: {len(str(response_data))})"
    
    print(f"[HTTP Response] Status: {status_code}")
    print(f"[HTTP Response] Data: {response_str}")
    print(f"[HTTP Response] Duration: {elapsed_time:.3f}s")


