"""Loopback JSON API for the 3D client. Standard library only; binds to 127.0.0.1.

Run from prototypes/3d-datacenter-001:  python -m engine.server   (or: npm run engine)
Saves go to ./saves (or SRS3D_SAVE_DIR) — never to the user's Python game saves.

  GET  /api/health                     engine status
  GET  /api/saves                      3D saves (tutorial / story / free)
  POST /api/games          {mode}      start a NEW game (new file, nothing overwritten)
  GET  /api/games/<id>                 snapshot (opens a saved game if needed)
  POST /api/games/<id>/actions {type,...}  one GameAction -> {ok, message, hint, result, game}
  POST /api/games/<id>/close           save and release the file lock
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from engine.adapter import GameHost, ActionError, API_VERSION  # noqa: E402

MAX_BODY = 64 * 1024
ALLOWED_HOSTS = re.compile(r'(127\.0\.0\.1|localhost)(:\d+)?')
ALLOWED_ORIGINS = re.compile(r'http://(127\.0\.0\.1|localhost)(:\d+)?')
class NotFound(Exception):
    pass


def lookup(host, gid):
    """Only a missing save becomes 404; any other KeyError is an internal error (500)."""
    try:
        return host.get(gid)
    except KeyError:
        raise NotFound(gid) from None


GAME_PATH = re.compile(r'/api/games/([A-Za-z0-9_]+)(/actions|/close)?')


def make_handler(host: GameHost, log=None):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'SRS3DEngine/1'

        def log_message(self, fmt, *args):  # quiet by default; QA passes a log callback
            if log:
                log(fmt % args)

        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _guard(self):
            # Loopback only, and no cross-site browser requests (DNS-rebinding / CSRF hardening).
            if not ALLOWED_HOSTS.fullmatch(self.headers.get('Host', '')):
                self._send(HTTPStatus.FORBIDDEN, {'ok': False, 'message': 'loopback only'})
                return False
            origin = self.headers.get('Origin')
            if origin and not ALLOWED_ORIGINS.fullmatch(origin):
                self._send(HTTPStatus.FORBIDDEN, {'ok': False, 'message': 'origin not allowed'})
                return False
            return True

        def _body(self):
            length = int(self.headers.get('Content-Length') or 0)
            if length < 0 or length > MAX_BODY:
                raise ValueError('body too large')
            if length and 'application/json' not in (self.headers.get('Content-Type') or ''):
                raise ValueError('JSON body required')
            raw = self.rfile.read(length) if length else b'{}'
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('JSON object required')
            return data

        def do_GET(self):
            if not self._guard():
                return
            path = self.path.split('?')[0]
            try:
                if path == '/api/health':
                    return self._send(200, {'ok': True, 'api': API_VERSION, 'engine': 'python:session.GameSession',
                                            'saveDir': host.dir.name})
                if path == '/api/saves':
                    return self._send(200, {'ok': True, 'saves': host.run(host.saves)})
                m = GAME_PATH.fullmatch(path)
                if m and not m[2]:
                    return self._send(200, {'ok': True, 'game': host.run(lambda: lookup(host, m[1]).snapshot())})
                return self._send(404, {'ok': False, 'message': 'not found'})
            except NotFound:
                return self._send(404, {'ok': False, 'message': '저장된 게임을 찾을 수 없습니다.'})
            except ValueError as exc:
                return self._send(409, {'ok': False, 'message': str(exc), 'hint': getattr(exc, 'hint', '')})
            except Exception:
                traceback.print_exc()
                return self._send(500, {'ok': False, 'message': '엔진 내부 오류'})

        def do_POST(self):
            if not self._guard():
                return
            path = self.path.split('?')[0]
            try:
                data = self._body()
            except (ValueError, UnicodeDecodeError) as exc:
                return self._send(400, {'ok': False, 'message': f'잘못된 요청: {exc}'})
            try:
                if path == '/api/games':
                    return self._send(200, {'ok': True, 'game': host.run(lambda: host.new_game(data.get('mode')).snapshot())})
                m = GAME_PATH.fullmatch(path)
                if m and m[2] == '/actions':
                    def act():
                        game = lookup(host, m[1])
                        try:
                            result = game.act(data)
                        except ValueError as exc:   # engine rule or adapter rejection: nothing changed
                            return {'ok': False, 'message': str(exc), 'hint': getattr(exc, 'hint', ''), 'game': game.snapshot()}
                        return {'ok': True, 'message': result.pop('info', ''), 'hint': result.pop('hint', ''),
                                'result': result, 'game': game.snapshot()}
                    return self._send(200, host.run(act))
                if m and m[2] == '/close':
                    host.close(m[1])
                    return self._send(200, {'ok': True})
                return self._send(404, {'ok': False, 'message': 'not found'})
            except NotFound:
                return self._send(404, {'ok': False, 'message': '저장된 게임을 찾을 수 없습니다.'})
            except ActionError as exc:
                return self._send(400, {'ok': False, 'message': str(exc), 'hint': exc.hint})
            except ValueError as exc:
                return self._send(409, {'ok': False, 'message': str(exc)})
            except Exception:
                traceback.print_exc()
                return self._send(500, {'ok': False, 'message': '엔진 내부 오류'})

    return Handler


def serve(port=8765, save_dir=None, ready=None):
    save_dir = Path(save_dir or os.environ.get('SRS3D_SAVE_DIR') or HERE.parent / 'saves')
    host = GameHost(save_dir, worker=True)
    httpd = ThreadingHTTPServer(('127.0.0.1', port), make_handler(host))
    print(f'SRS 3D engine ready on http://127.0.0.1:{httpd.server_address[1]}  (saves: {host.dir})', flush=True)
    if ready:
        ready(httpd)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        host.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Server Room Survival 3D engine adapter (loopback only)')
    parser.add_argument('--port', type=int, default=int(os.environ.get('SRS3D_ENGINE_PORT', 8765)))
    parser.add_argument('--save-dir', default=None)
    args = parser.parse_args()
    serve(args.port, args.save_dir)
