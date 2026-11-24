// Port check for `npm run play` (Issue #6): find out whether a loopback port is already taken WITHOUT touching the
// process that holds it. The launcher only reports; it never kills anything.
import net from 'node:net';

export function portFree(port, host = '127.0.0.1') {
  return new Promise(resolve => {
    const srv = net.createServer();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => srv.close(() => resolve(true)));
    srv.listen(port, host);
  });
}
export function busyMessage(name, port, envName) {
  return `[play] ${name} 포트 ${port}를 이미 다른 프로그램(예: 이전에 띄운 Vite/엔진)이 사용 중입니다.\n` +
    `       이 스크립트는 다른 프로세스를 종료하지 않습니다. 그 터미널을 직접 종료하거나,\n` +
    `       다른 포트로 실행하세요:  $env:${envName} = '${port + 7}'; npm.cmd run play`;
}
