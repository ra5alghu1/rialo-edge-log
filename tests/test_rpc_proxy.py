import io
import json
import unittest
from unittest.mock import patch
from archive.rpc_proxy import validate_request, forward_read, ProxyUnavailable, MAX_RESPONSE_BYTES


def request():
    return {'jsonrpc': '2.0', 'id': 1, 'method': 'getAccountInfo',
            'params': [{'address': '1'*32, 'encoding': 'base64'}]}


class ProxyTests(unittest.TestCase):
    def test_allowed(self):
        validate_request(request())
        v=request(); v.update(method='getTransaction', params=[{'signature':'2'*88}])
        validate_request(v)

    def test_rejects_writes_batches_and_extra_fields(self):
        cases=[[], request()|{'method':'sendTransaction'}, request()|{'url':'http://localhost'},
               request()|{'params':[{'address':'https://evil.test','encoding':'base64'}]},
               request()|{'params':[{'address':'1'*32,'encoding':'jsonParsed'}]},
               request()|{'params':[{'address':'1'*32,'encoding':'base64','extra':1}]}]
        for v in cases:
            with self.subTest(v=v), self.assertRaises(ValueError): validate_request(v)

    def test_forward_and_limits(self):
        for raw, succeeds in [(json.dumps({'jsonrpc':'2.0','id':1,'result':None}).encode(),True),
                              (b'x'*(MAX_RESPONSE_BYTES+1),False), (b'bad json',False),
                              (b'{"jsonrpc":"2.0","id":2,"result":null}',False)]:
            with patch('archive.rpc_proxy.build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(raw)
                if succeeds:
                    self.assertIsNone(forward_read(request(),'https://rpc.example')['result'])
                    args=opener.return_value.open.call_args
                    self.assertEqual(args.kwargs['timeout'],8)
                    self.assertEqual(args.args[0].full_url,'https://rpc.example')
                else:
                    with self.assertRaises(ProxyUnavailable): forward_read(request(),'https://rpc.example')

    def test_busy_and_network_failure(self):
        with patch('archive.rpc_proxy._SLOTS') as slots:
            slots.acquire.return_value=False
            with self.assertRaises(ProxyUnavailable): forward_read(request(),'https://rpc.example')
            slots.release.assert_not_called()
        with patch('archive.rpc_proxy.build_opener',side_effect=OSError('private upstream detail')):
            with self.assertRaisesRegex(ProxyUnavailable,'temporarily unavailable'):
                forward_read(request(),'https://rpc.example')

    def test_http_route(self):
        import tempfile
        import threading
        import urllib.request
        import urllib.error
        from pathlib import Path
        from http.server import ThreadingHTTPServer
        from types import SimpleNamespace
        from archive.server import handler_factory
        with tempfile.TemporaryDirectory() as tmp:
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_factory(
                SimpleNamespace(rpc_url='https://fixed.example'), Path(tmp), 'secret'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = 'http://127.0.0.1:%s/api/rpc' % server.server_port
            try:
                with patch('archive.rpc_proxy.build_opener') as opener:
                    opener.return_value.open.return_value = io.BytesIO(
                        b'{"jsonrpc":"2.0","id":1,"result":null}')
                    with urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(request()).encode())) as r:
                        self.assertEqual(r.status, 200)
                    opener.reset_mock()
                    for data in [b'[]', b'x'*4097, json.dumps(request()|{'method':'sendTransaction'}).encode()]:
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(urllib.request.Request(url, data=data))
                        self.assertEqual(error.exception.code,400)
                        error.exception.close()
                    opener.assert_not_called()
            finally:
                server.shutdown(); server.server_close(); thread.join()
