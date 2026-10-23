"""Fork change 16: a real daemon records what started a session ("Started by").

Both client routes that create sessions for a terminal command are driven end to end against a
stand-in model server: the classic CLI (``hermes chat -q``, the route agents' commands take) and
``run_gateway_chat`` with a titled create (the route the nightly update script takes).
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.gateway.fixtures.local_recovery_probe import daemon

NIGHTLY_TITLE = 'Nightly update 1 Jan 01:00: triage'

_NIGHTLY_RUN = '''
import argparse, asyncio, sys
from hermes_cli.gateway_chat import run_gateway_chat

class Result:
    result = {}
    def bind_session(self, _): pass
    def on_text_delta(self, _): pass
    def on_tool_progress(self, *a, **k): pass
    def emit_result(self, result, session_id="", exit_code=0):
        self.result = dict(result or {})
        return exit_code

out = Result()
args = argparse.Namespace(oneshot="PROBE_NIGHTLY", provider="custom", model="probe-model", toolsets="",
                          max_turns=1, yolo=True, safe_mode=True, source="tool",
                          continue_last=sys.argv[1], create_if_missing=True, launched_by="Nightly update",
                          in_dir=sys.argv[2], quiet=True, reasoning=None, api_key="probe-key",
                          base_url=sys.argv[3])
asyncio.run(run_gateway_chat(args, emitter=out))
print("REPLY:" + str(out.result.get("final_response") or out.result.get("error") or ""))
'''


class Model(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if not body.get('messages'):
            self.send_error(404)
            return
        choice = {'index': 0, 'message': {'role': 'assistant', 'content': 'PROVENANCE_OK'}, 'finish_reason': 'stop'}
        kind = 'application/json'
        payload = json.dumps({'id': 'local', 'choices': [choice], 'model': body['model'],
                              'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}).encode()
        if body.get('stream'):
            choice['delta'] = choice.pop('message')
            payload = ('data: ' + json.dumps({'id': 'local', 'choices': [choice]}) + '\n\ndata: [DONE]\n\n').encode()
            kind = 'text/event-stream'
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def probe(tmp_path):
    root = Path(__file__).resolve().parents[3]
    home, user, work = tmp_path / 'state', tmp_path / 'user', tmp_path / 'work'
    home.mkdir(mode=0o700)
    user.mkdir()
    work.mkdir()
    peer = ThreadingHTTPServer(('127.0.0.1', 0), Model)
    thread = threading.Thread(target=peer.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{peer.server_port}/v1'
    cfg = {'model': {'provider': 'custom', 'default': 'probe-model', 'base_url': origin},
           'auxiliary': {'title_generation': {'enabled': False}}, 'platform_toolsets': {'cli': []},
           'memory': {'memory_enabled': False, 'user_profile_enabled': False}}
    (home / 'config.yaml').write_text(json.dumps(cfg))
    env = {k: os.environ[k] for k in ('PATH', 'LANG', 'TZ', 'SYSTEMROOT') if k in os.environ}
    env.update(HOME=str(user), USERPROFILE=str(user), HERMES_HOME=str(home), PYTHONPATH=str(root))
    if os.name == 'nt':
        # Without LOCALAPPDATA, the Windows Python install manager behind a bare `python` installs a
        # whole runtime into the working directory (here the checkout); keep it inside tmp, and off.
        env.update(LOCALAPPDATA=str(user / 'AppData' / 'Local'), APPDATA=str(user / 'AppData' / 'Roaming'),
                   PYTHON_MANAGER_AUTOMATIC_INSTALL='false')

    def classic(query, **extra):
        result = subprocess.run([sys.executable, '-c', 'import cli; cli.main(**' + repr({'query': query, 'quiet': True}) + ')'],
                                cwd=work, env={**env, **extra}, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=90, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'PROVENANCE_OK' in result.stdout, result.stdout + result.stderr
        found = re.search(r'^session_id: (\S+)$', result.stderr, re.MULTILINE)
        assert found, result.stderr
        return found.group(1)

    try:
        with daemon(root, home, env, barrier=False):
            started = classic('PROBE_STARTED', HERMES_SESSION_ID='parent-session-1', HERMES_LAUNCHED_BY='Probe program')
            plain = classic('PROBE_PLAIN')
            nightly = subprocess.run([sys.executable, '-c', _NIGHTLY_RUN, NIGHTLY_TITLE, str(work), origin],
                                     cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                     timeout=90, check=False)
            assert nightly.returncode == 0, nightly.stdout + nightly.stderr
            assert 'REPLY:PROVENANCE_OK' in nightly.stdout, nightly.stdout + nightly.stderr
            # Read while the daemon still runs: Windows releases a stopped daemon's file locks late,
            # and the rows (provenance included) are committed before each client returns.
            return _read_rows(home / 'state.db', started, plain)
    finally:
        peer.shutdown()
        peer.server_close()
        thread.join(timeout=5)


def _read_rows(path, started, plain, budget=15.0):
    deadline = time.monotonic() + budget
    while True:
        try:
            conn = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True, timeout=5)
            try:
                def row(where, value):
                    found = conn.execute(f'SELECT source, title, model_config FROM sessions WHERE {where} = ?',
                                         (value,)).fetchall()
                    assert len(found) == 1, (where, value, found)
                    source, title, model_config = found[0]
                    config = json.loads(model_config or '{}')
                    return {'source': source, 'title': title,
                            'launched_from': config.get('_launched_from'), 'launched_by': config.get('_launched_by')}

                return {'started': row('id', started), 'plain': row('id', plain),
                        'nightly': row('title', NIGHTLY_TITLE)}
            finally:
                conn.close()
        except sqlite3.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(.2)
