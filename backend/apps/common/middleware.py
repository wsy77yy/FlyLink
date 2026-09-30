import logging
import time
from uuid import uuid4


logger = logging.getLogger('flylink.request')


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get('X-Request-ID') or uuid4().hex
        request.request_id = request_id
        started = time.perf_counter()

        try:
            response = self.get_response(request)
        except Exception:
            logger.exception(
                'request_failed',
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.path,
                    'duration_ms': round((time.perf_counter() - started) * 1000, 2),
                    'user_id': getattr(getattr(request, 'user', None), 'pk', None),
                },
            )
            raise

        response['X-Request-ID'] = request_id
        logger.info(
            'request_completed',
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': round((time.perf_counter() - started) * 1000, 2),
                'user_id': getattr(getattr(request, 'user', None), 'pk', None),
            },
        )
        return response
