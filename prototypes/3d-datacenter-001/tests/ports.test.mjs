import {test} from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import {portFree,busyMessage} from '../scripts/ports.mjs';

test('a taken port is reported, never taken over; the message names another port and does not kill anything',async()=>{
  const holder=net.createServer();await new Promise(r=>holder.listen(0,'127.0.0.1',r));const port=holder.address().port;
  assert.equal(await portFree(port),false);
  assert.equal(holder.listening,true,'the other program keeps its port');
  const msg=busyMessage('Vite(3D 화면)',port,'SRS3D_VITE_PORT');assert.match(msg,/종료하지 않습니다/);assert.match(msg,new RegExp(`SRS3D_VITE_PORT = '${port+7}'`));
  await new Promise(r=>holder.close(r));assert.equal(await portFree(port),true);
});
