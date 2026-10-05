"""Sending one request on to a service and streaming its answer back, without holding either body in memory (an SSE stream or a 15 MB spoken answer
passes through the same way a small JSON call does)."""

from collections.abc import AsyncIterator

import httpx
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.core.config import Settings
from app.core.exceptions import BadGatewayError, BadRequestError, GatewayTimeoutError, PayloadTooLargeError
from app.proxy.headers import request_headers, response_headers


def safe_path(path: str) -> bool:
    """A path is forwarded only if it is what it looks like: no dot segments, no empty segments, no backslashes or control characters that a service's own
    normalisation might read differently from the gateway's routing."""
    if not path.startswith("/") or "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return False
    parts = path.split("/")[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]  # one trailing slash is fine
    return all(part not in {"", ".", ".."} for part in parts)


async def _limited(stream: AsyncIterator[bytes], limit: int) -> AsyncIterator[bytes]:
    seen = 0
    async for chunk in stream:
        seen += len(chunk)
        if seen > limit:
            raise PayloadTooLargeError
        yield chunk


async def _relay(upstream: httpx.Response) -> AsyncIterator[bytes]:
    # A real upstream call streams lazily here. A response built with its content already in hand (every test's
    # MockTransport) counts as already read, and .aiter_raw() would refuse a second read of the same bytes.
    if upstream.is_stream_consumed:
        yield upstream.content
        return
    async for chunk in upstream.aiter_raw():
        yield chunk


def _timeout(settings: Settings, path: str) -> httpx.Timeout:
    read = settings.STREAM_READ_TIMEOUT_SECONDS if path.rstrip("/").endswith("/stream") else settings.UPSTREAM_READ_TIMEOUT_SECONDS
    return httpx.Timeout(connect=settings.UPSTREAM_CONNECT_TIMEOUT_SECONDS, read=read, write=read, pool=settings.UPSTREAM_CONNECT_TIMEOUT_SECONDS)


async def forward(
    request: Request, *, base_url: str, path: str, client: httpx.AsyncClient, settings: Settings, request_id: str, client_ip: str, forwarded_for: str | None
) -> StreamingResponse:
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise BadRequestError("The Content-Length header is not valid.", code="BAD_CONTENT_LENGTH")
        if int(declared) > settings.MAX_BODY_BYTES:
            raise PayloadTooLargeError
    has_body = declared not in (None, "0") or "transfer-encoding" in request.headers
    headers = request_headers(request.headers.items(), client_ip=client_ip, forwarded_for=forwarded_for, scheme=request.url.scheme, request_id=request_id)
    url = httpx.URL(base_url).copy_with(path=path, query=request.url.query.encode() if request.url.query else None)
    upstream_request = client.build_request(
        request.method, url, headers=headers, content=_limited(request.stream(), settings.MAX_BODY_BYTES) if has_body else None, timeout=_timeout(settings, path)
    )
    try:
        upstream = await client.send(upstream_request, stream=True)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError from exc
    except httpx.HTTPError as exc:
        raise BadGatewayError from exc
    response = StreamingResponse(_relay(upstream), status_code=upstream.status_code, background=BackgroundTask(upstream.aclose))
    response.raw_headers = [(name.lower().encode("latin-1"), value.encode("latin-1")) for name, value in response_headers(upstream.headers.multi_items())]
    return response
