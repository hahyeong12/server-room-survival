// Browser client for the loopback engine adapter (engine/server.py) behind the Vite /api proxy.
// Calls are serialized so that clicks reach the engine in the order the player made them.
export function createEngineClient(base = '/api', fetchImpl = (...a) => fetch(...a)) {
  let chain = Promise.resolve();
  async function call(path, body) {
    let res;
    try {
      res = await fetchImpl(base + path, body === undefined ? { cache: 'no-store' }
        : { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    } catch {
      return { ok: false, offline: true, message: 'Python 엔진에 연결할 수 없습니다. npm run play 로 엔진을 실행하세요.' };
    }
    let data;
    try { data = await res.json(); } catch { data = { ok: false, message: `엔진 응답을 읽을 수 없습니다 (HTTP ${res.status}).` }; }
    if (!res.ok && data.ok !== false) data.ok = false;
    if (res.status === 502 || res.status === 504) { data.offline = true; data.message ||= 'Python 엔진이 응답하지 않습니다.'; }
    return { ...data, status: res.status };
  }
  const queued = (path, body) => (chain = chain.then(() => call(path, body), () => call(path, body)));
  return {
    health: () => call('/health'),
    saves: () => call('/saves'),
    create: (mode, chapter, options) => queued('/games', { mode, ...(chapter === undefined ? {} : {chapter}), ...(options ? {options} : {}) }),
    // Phase 5: a retry / chapter start is always a NEW save made from a chapter-start checkpoint (source unchanged).
    retry: id => queued(`/games/${encodeURIComponent(id)}/retry`, {}),
    checkpoint: (id, chapter) => queued(`/games/${encodeURIComponent(id)}/checkpoint`, { chapter }),
    load: id => queued(`/games/${encodeURIComponent(id)}`),
    act: (id, action) => queued(`/games/${encodeURIComponent(id)}/actions`, action),
    close: id => queued(`/games/${encodeURIComponent(id)}/close`, {}),
    idle: () => chain,
  };
}
