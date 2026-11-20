"""Read-only GPU/WebGL probe using an isolated, temporary Chrome profile."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import websocket

OUT = Path(__file__).resolve().parent
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

def main():
    report = {'mode': 'headless diagnostic; visible browser interaction is unverified'}
    with tempfile.TemporaryDirectory(prefix='srs-browser-probe-') as profile:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        proc = subprocess.Popen([CHROME, '--headless=new', '--no-first-run',
            '--no-default-browser-check', '--remote-debugging-port=0',
            '--user-data-dir='+profile, 'about:blank'], startupinfo=startup,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sockets = []
        try:
            port_file = Path(profile)/'DevToolsActivePort'
            deadline = time.monotonic()+20
            while not port_file.exists():
                if time.monotonic()>deadline:
                    raise TimeoutError('Chrome debugging endpoint unavailable')
                time.sleep(.1)
            port = port_file.read_text().splitlines()[0]
            def endpoint(path):
                with urllib.request.urlopen('http://127.0.0.1:'+port+path, timeout=5) as response:
                    return json.load(response)
            def connect(url):
                sock = websocket.create_connection(url, timeout=15, suppress_origin=True)
                sockets.append(sock)
                return sock
            counter = 0
            def call(sock, method, params=None):
                nonlocal counter
                counter += 1
                request_id = counter
                sock.send(json.dumps({'id':request_id, 'method':method, 'params':params or {}}))
                while True:
                    data = json.loads(sock.recv())
                    if data.get('id') == request_id:
                        if 'error' in data:
                            raise RuntimeError(data['error'])
                        return data['result']
            browser = connect(endpoint('/json/version')['webSocketDebuggerUrl'])
            report['browser'] = call(browser, 'Browser.getVersion')
            report['gpu'] = call(browser, 'SystemInfo.getInfo')['gpu']
            page = connect(next(t for t in endpoint('/json/list') if t['type']=='page')['webSocketDebuggerUrl'])
            expression = '''JSON.stringify((()=>{
                const result={userAgent:navigator.userAgent,devicePixelRatio,
                    screen:{width:screen.width,height:screen.height}};
                for(const kind of ['webgl','webgl2']) {
                    const gl=document.createElement('canvas').getContext(kind);
                    if(!gl){result[kind]={supported:false};continue;}
                    const ext=gl.getExtension('WEBGL_debug_renderer_info');
                    result[kind]={supported:true,version:gl.getParameter(gl.VERSION),
                        renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null,
                        maxTextureSize:gl.getParameter(gl.MAX_TEXTURE_SIZE),
                        attributes:gl.getContextAttributes()};
                } return result;})())'''
            report['webgl'] = json.loads(call(page, 'Runtime.evaluate', {'expression':expression,'returnByValue':True})['result']['value'])
            OUT.joinpath('browser-gpu.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            call(browser, 'Browser.close')
        finally:
            for sock in sockets:
                sock.close()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)
    print(json.dumps(report['webgl'],indent=2))

if __name__ == '__main__':
    main()
