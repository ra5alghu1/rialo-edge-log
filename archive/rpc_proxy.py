"""Bounded, read-only Rialo RPC transport for the browser verifier."""
import json
import re
import threading
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 2_000_000
_SLOTS = threading.BoundedSemaphore(4)


class ProxyUnavailable(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_request(value):
    if not isinstance(value, dict) or set(value) != {'jsonrpc', 'id', 'method', 'params'}:
        raise ValueError('expected one JSON-RPC request')
    if value['jsonrpc'] != '2.0' or type(value['id']) not in (int, str):
        raise ValueError('invalid JSON-RPC version or id')
    method = value['method']
    params = value['params']
    if method not in ('getTransaction', 'getAccountInfo'):
        raise ValueError('only proof-reading methods are allowed')
    if not isinstance(params, list) or len(params) != 1 or not isinstance(params[0], dict):
        raise ValueError('expected one parameter object')
    p = params[0]
    field = 'signature' if method == 'getTransaction' else 'address'
    expected = {field} if method == 'getTransaction' else {field, 'encoding'}
    if set(p) != expected or not isinstance(p[field], str):
        raise ValueError('invalid proof parameters')
    lo, hi = (64, 88) if field == 'signature' else (32, 44)
    if not lo <= len(p[field]) <= hi or not re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]+', p[field]):
        raise ValueError('invalid base58 identifier')
    if method == 'getAccountInfo' and p['encoding'] != 'base64':
        raise ValueError('only base64 account encoding is allowed')
    return value


def forward_read(value, rpc_url):
    validate_request(value)
    if not _SLOTS.acquire(blocking=False):
        raise ProxyUnavailable('proof RPC is busy; retry shortly')
    try:
        request = Request(rpc_url, data=json.dumps(value).encode(),
                          headers={'Content-Type': 'application/json'})
        with build_opener(NoRedirect()).open(request, timeout=8) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError('response too large')
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0' or payload.get('id') != value['id']:
            raise ValueError('invalid RPC response')
        if ('result' in payload) == ('error' in payload):
            raise ValueError('invalid RPC result')
        return payload
    except Exception as exc:
        raise ProxyUnavailable('Rialo proof RPC is temporarily unavailable') from exc
    finally:
        _SLOTS.release()
