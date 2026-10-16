"""One log line per request, with a short id (week 10).

Each request gets a short random id. The response carries it in the
`x-request-id` header, the server prints one JSON line for the request
(method, path, status, ms, who), and every event logged while the request runs
carries the same id (`request`), so a narrator can tie a "pause" line to the
request that caused it. Who is the public label, never the cookie; bodies,
query strings and headers are not logged.

The live event streams stay open for minutes: they get a line when they open
and one when they close, and nothing for their keep-alives. Static files get
no line. An exception nobody handled gets one line with the id, the path, the
error and a short traceback, and the visitor gets a plain 500.

This is plain ASGI, not Starlette's BaseHTTPMiddleware, so a streaming
response is passed through untouched and the id (a context variable) is seen
by everything the request runs, including work it schedules with call_soon or
in a thread. The ticker runs outside any request, so tick-time events have no
id and nothing here touches a turn.
"""

import json
import secrets
import time
import traceback
from contextvars import ContextVar
from http.cookies import SimpleCookie

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

HEADER = b"x-request-id"


def new_id() -> str:
    return secrets.token_hex(4)


def emit(line: dict) -> None:
    print(json.dumps(line), flush=True)


def cookie_from(scope, name: str) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"cookie":
            jar = SimpleCookie()
            try:
                jar.load(value.decode("latin-1"))
            except Exception:
                return None
            return jar[name].value if name in jar else None
    return None


class RequestLog:
    def __init__(self, app, cookie: str, label, skip: tuple[str, ...] = ("/static/",)):
        self.app = app
        self.cookie = cookie  # read only to make the public label
        self.label = label  # visitor id -> public label
        self.skip = skip

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = new_id()
        token = request_id.set(rid)
        path = scope.get("path", "")
        quiet = path.startswith(self.skip)
        began = time.perf_counter()
        visitor = cookie_from(scope, self.cookie)
        base = {"request": rid, "method": scope.get("method"), "path": path,
                "visitor": self.label(visitor) if visitor else None}
        state = {"status": None, "stream": False}

        def line(event: str, **more) -> dict:
            ms = round((time.perf_counter() - began) * 1000)
            out = {"event": event, **base, "status": state["status"], "ms": ms, "at": int(time.time()), **more}
            out["text"] = f"{out['method']} {path} {state['status']} in {ms} ms"
            return out

        async def tagged_send(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                headers = list(message.get("headers", [])) + [(HEADER, rid.encode())]
                message = {**message, "headers": headers}
                kind = dict(headers).get(b"content-type", b"")
                if kind.startswith(b"text/event-stream"):
                    state["stream"] = True
                    if not quiet:
                        opened = line("stream_open")
                        opened["text"] = f"{opened['method']} {path} opened a live stream"
                        emit(opened)
            await send(message)

        try:
            await self.app(scope, receive, tagged_send)
        except Exception as err:
            answered = state["status"] is not None
            if not answered:
                state["status"] = 500
            frames = traceback.extract_tb(err.__traceback__)[-3:]
            emit({**line("request_error"), "error": type(err).__name__, "message": str(err)[:200],
                  "trace": [f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} in {f.name}" for f in frames],
                  "text": f"{base['method']} {path} failed: {type(err).__name__}"})
            if not answered:  # nothing sent yet: answer with a plain 500
                await send({"type": "http.response.start", "status": 500,
                            "headers": [(b"content-type", b"text/plain; charset=utf-8"), (HEADER, rid.encode())]})
                await send({"type": "http.response.body", "body": f"Something went wrong (request {rid}).".encode()})
            return
        finally:
            request_id.reset(token)
        if quiet:
            return
        if state["stream"]:
            closed = line("stream_close")
            closed["text"] = f"{closed['method']} {path} closed after {round(closed['ms'] / 1000)} s"
            emit(closed)
        else:
            emit(line("request"))
