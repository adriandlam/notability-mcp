"""Notability's private web API: the library over Socket.IO, note bundles and files over HTTP.

Unofficial and undocumented; mapped by notability-cli (docs/PROTOCOL.md at d49dc45). Requests
carry the web app's client-* headers, since the server forces updates on old client versions.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from importlib.metadata import version

from websockets.sync.client import connect

BASE = "https://notability.com"
SOCKET = "wss://notability.com/collab-api/socket.io/?EIO=4&transport=websocket"
NAMESPACE = "/metadata"
CLIENT_HEADERS = {
    "client-platform": "WEB",
    "client-version": os.environ.get("NOTABILITY_CLIENT_VERSION", "26.43.7"),
    "client-git-hash": "87273d83f7c62268c52d63d2ce48f16a4572e590",
    "client-build-time": "1792773738731",
}
USER_AGENT = f"notability-mcp/{version('notability-mcp')}"
MIN_INTERVAL = 0.25  # seconds between HTTP requests
RETRIES = 4


class ApiError(RuntimeError):
    pass


class AuthError(ApiError):
    pass


def fetch_library(token: str, timeout: float = 60) -> dict:
    """The whole library (folders, organizers, notes), as the web app receives it on connect."""
    headers = {"Origin": BASE, "Cookie": f"nb-auth-token={token}", "User-Agent": USER_AGENT}
    with connect(SOCKET, additional_headers=headers, max_size=2**28, open_timeout=timeout) as ws:
        if not str(ws.recv(timeout)).startswith("0"):
            raise ApiError("Unexpected Socket.IO handshake from Notability.")
        ws.send(f"40{NAMESPACE}," + json.dumps({"token": token, "query": CLIENT_HEADERS}))
        deadline = time.monotonic() + timeout
        while True:
            message = str(ws.recv(max(0.0, deadline - time.monotonic())))
            if message == "2":  # engine.io ping
                ws.send("3")
            elif message.startswith(f"44{NAMESPACE},"):
                raise AuthError("Notability rejected the token. Run `notability-mcp login` again.")
            elif message.startswith(f"42{NAMESPACE},"):
                event, *args = json.loads(message.removeprefix(f"42{NAMESPACE},"))
                if event == "partial-update":
                    return args[0]
                if event == "error":
                    raise ApiError(f"Notability library error: {args}")


def _auth(token: str) -> dict[str, str]:
    return {
        "Cookie": f"nb-auth-token={token}",
        "nb-auth-token": token,
        "User-Agent": USER_AGENT,
        **CLIENT_HEADERS,
    }


def fetch_bundle(token: str, note_id: str, device_id: str) -> bytes:
    """A note's full op log (FlatBuffers NoteBundle); empty for notes that have no ops yet."""
    uuid.UUID(note_id)  # ids come from the server; never put anything else in the URL
    request = urllib.request.Request(
        f"{BASE}/collab-api/note/{note_id}/bundle?deviceId={uuid.UUID(device_id)}",
        data=b"",
        method="POST",
        headers={**_auth(token), "Content-Type": "application/octet-stream"},
    )
    body = _send(request)
    return b"" if body.startswith(b"No ops found") else body


def fetch_asset(token: str, note_id: str, sha512: str) -> bytes:
    """A file a note uses (PDF, image, audio), by SHA-512, via a short-lived signed URL."""
    uuid.UUID(note_id)
    if not re.fullmatch(r"[0-9a-f]{128}", sha512):
        raise ValueError(f"Not a SHA-512 hex digest: {sha512[:20]!r}")
    signed = _send(
        urllib.request.Request(f"{BASE}/media/{sha512}?noteId={note_id}", headers=_auth(token))
    )
    url = json.loads(signed) if signed.startswith(b'"') else signed.decode().strip()
    if not url.startswith("https://"):
        raise ApiError("Notability returned an unexpected download link for a PDF.")
    try:  # the signed URL is the credential; the token must not go to the storage host
        return _send(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}))
    except AuthError as e:  # a refused link is this file's problem, not a bad token
        raise ApiError("Storage refused the download link for a PDF.") from e


def _send(request: urllib.request.Request) -> bytes:
    for attempt in range(RETRIES + 1):
        time.sleep(MIN_INTERVAL)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError("Notability rejected the token. Run `notability-mcp login`.") from e
            if (e.code != 429 and e.code < 500) or attempt == RETRIES:
                raise ApiError(f"Notability returned HTTP {e.code} for {request.full_url}") from e
            time.sleep(float(e.headers.get("Retry-After") or 2**attempt))
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == RETRIES:
                raise ApiError(f"Could not reach Notability: {e}") from e
            time.sleep(2**attempt)
    raise AssertionError("unreachable")
