"""The request log's lines (week 10): one per request, with a short id that
also tags the events logged inside it; never the cookie."""

import asyncio
import json

from app import requestlog
from app.activity import visitor_label

COOKIE_VALUE = "s3cret-cookie-value"


def call(app, path="/api/thing", method="POST", cookie=True):
    """Run one request through the middleware; return (messages sent, stdout lines)."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": b'{"password": "hunter2"}', "more_body": False}

    async def send(message):
        sent.append(message)

    headers = [(b"cookie", f"visitor={COOKIE_VALUE}".encode())] if cookie else []
    scope = {"type": "http", "method": method, "path": path, "query_string": b"key=abc", "headers": headers}
    wrapped = requestlog.RequestLog(app, cookie="visitor", label=visitor_label)
    asyncio.run(wrapped(scope, receive, send))
    return sent


def lines(capsys) -> list[dict]:
    return [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]


def plain(status=200, content_type=b"application/json", seen=None):
    async def app(scope, receive, send):
        if seen is not None:
            seen.append(requestlog.request_id.get())
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", content_type)]})
        await send({"type": "http.response.body", "body": b"{}"})

    return app


def test_one_line_per_request_with_method_path_status_ms_and_who(capsys):
    seen = []
    sent = call(plain(204, seen=seen))
    [line] = lines(capsys)
    assert line["event"] == "request"
    assert line["method"] == "POST" and line["path"] == "/api/thing" and line["status"] == 204
    assert isinstance(line["ms"], int) and line["ms"] >= 0
    assert line["visitor"] == visitor_label(COOKIE_VALUE)
    assert len(line["request"]) == 8
    # the same id is in the response header and visible to the handler
    assert dict(sent[0]["headers"])[b"x-request-id"] == line["request"].encode()
    assert seen == [line["request"]]


def test_never_logs_the_cookie_the_body_or_the_query(capsys):
    call(plain())
    out = capsys.readouterr().out
    assert COOKIE_VALUE not in out
    assert "hunter2" not in out and "key=abc" not in out


def test_a_visitor_without_a_cookie_is_logged_as_nobody(capsys):
    call(plain(), cookie=False)
    assert lines(capsys)[0]["visitor"] is None


def test_static_files_get_no_line(capsys):
    sent = call(plain(), path="/static/game.js", method="GET")
    assert lines(capsys) == []
    assert b"x-request-id" in dict(sent[0]["headers"])


def test_a_live_stream_logs_when_it_opens_and_closes_not_each_keep_alive(capsys):
    async def stream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/event-stream")]})
        for _ in range(5):
            await send({"type": "http.response.body", "body": b": keep-alive\n\n", "more_body": True})
        await send({"type": "http.response.body", "body": b""})

    call(stream, path="/arena/events", method="GET")
    got = lines(capsys)
    assert [x["event"] for x in got] == ["stream_open", "stream_close"]
    assert got[0]["request"] == got[1]["request"]


def test_an_unhandled_error_logs_one_line_and_answers_500(capsys):
    async def broken(scope, receive, send):
        raise ValueError("the thing broke")

    sent = call(broken)
    [line] = lines(capsys)
    assert line["event"] == "request_error" and line["status"] == 500
    assert line["error"] == "ValueError" and line["message"] == "the thing broke"
    assert line["path"] == "/api/thing" and len(line["request"]) == 8
    assert 1 <= len(line["trace"]) <= 3 and "test_requestlog.py" in line["trace"][-1]
    assert sent[0]["status"] == 500
    assert line["request"].encode() in sent[1]["body"]
    assert COOKIE_VALUE not in json.dumps(line)


def test_an_event_logged_during_a_request_carries_its_id(capsys, tmp_path, monkeypatch):
    from app import activity, db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "app.db")
    db.migrate()

    async def logs(scope, receive, send):
        with db.connect() as conn:
            activity.record(conn, "visit", COOKIE_VALUE)
        await plain()(scope, receive, send)

    call(logs, path="/", method="GET")
    visit, request = lines(capsys)
    assert visit["event"] == "visit" and request["event"] == "request"
    assert visit["request"] == request["request"]
    # outside a request (the ticker), an event has no id
    with db.connect() as conn:
        activity.record(conn, "visit", COOKIE_VALUE)
    assert "request" not in lines(capsys)[0]
