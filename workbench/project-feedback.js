/* Project-local autosave. Browser storage and the original exporter remain independent backups. */
(function (global) {
  'use strict';
  const endpoint = '/api/workbench/feedback';
  const clone = value => JSON.parse(JSON.stringify(value));
  const signature = value => JSON.stringify(value);
  const meaningful = store => Object.keys(store.records || {}).length || Object.keys(store.legacy || {}).length ||
    store.workbench?.journal?.length || Object.keys(store.workbench?.frameEditor?.drafts || {}).length;
  const dataURL = blob => new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(reader.error); reader.readAsDataURL(blob);
  });

  function connect(adapter) {
    const metaKey = adapter.storageKey + ':project-files-v1';
    let revision = 0, token = '', initialized = false, dirty = false, busy = false, blocked = false;
    let timer = 0, retryTimer = 0, lastError = '', savedAt = '', inflight = null;
    const blobs = new WeakMap(), uploaded = new Map();
    const badge = document.createElement('span');
    badge.id = 'wb-project-save'; badge.className = 'wb-hint'; badge.setAttribute('role', 'status');
    document.querySelector('#wb-save').parentNode.append(badge);
    const status = (text, error = false) => { badge.textContent = '项目文件：' + text; badge.style.color = error ? '#a33830' : ''; };
    const state = () => ({initialized, dirty, busy, blocked, revision, savedAt, error: lastError, path: 'feedback/latest.json'});

    async function request(path, body) {
      const response = await fetch(path, body === undefined ? {cache: 'no-store'} : {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-Workbench-Token': token}, body: JSON.stringify(body)
      });
      const result = await response.json();
      if (!response.ok) {
        const error = new Error(result.error || 'HTTP ' + response.status);
        error.status = response.status; error.result = result; throw error;
      }
      return result;
    }

    function packBlob(blob, name, mimeType) {
      if (!blobs.has(blob)) {
        const job = (async () => {
          const bytes = await blob.arrayBuffer();
          const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2, '0')).join('');
          if (uploaded.has(sha256)) return uploaded.get(sha256);
          const result = await request(endpoint + '/assets', {sha256, name, mimeType: mimeType || blob.type,
            dataUrl: await dataURL(blob)});
          uploaded.set(sha256, result); return result;
        })();
        blobs.set(blob, job);
        job.catch(() => blobs.delete(blob));
      }
      return blobs.get(blob);
    }

    async function packAsset(asset) {
      const result = {...asset}; delete result.url; delete result.blob;
      if (asset.kind === 'folder') {
        result.files = await Promise.all(asset.files.map(async file => {
          const item = {...file}; delete item.blob; delete item.url;
          item.file = await packBlob(file.blob, file.name, file.type); return item;
        }));
      } else result.file = await packBlob(asset.blob, asset.name, asset.type);
      return result;
    }

    async function unpackAsset(asset) {
      async function unpack(item) {
        const response = await fetch('/' + item.file.path, {cache: 'no-store'});
        if (!response.ok) throw new Error('项目附件读取失败：' + item.name);
        const bytes = await response.arrayBuffer();
        const sha = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2, '0')).join('');
        if (sha !== item.file.sha256) throw new Error('项目附件校验失败：' + item.name);
        uploaded.set(sha, item.file);
        return {...item, blob: new Blob([bytes], {type: item.type || item.file.mimeType})};
      }
      return asset.kind === 'folder' ? {...asset, files: await Promise.all(asset.files.map(unpack))} : unpack(asset);
    }

    function later() {
      clearTimeout(retryTimer);
      retryTimer = setTimeout(() => (initialized ? flush() : initialize()).catch(() => {}), 4000);
    }

    async function initialize() {
      if (initialized) return;
      status('正在连接本机保存服务…');
      try {
        await adapter.ready;
        const remote = await request(endpoint);
        if (remote.projectId !== adapter.projectId) throw new Error('保存服务对应另一个项目');
        token = remote.writeToken;
        const snapshot = remote.snapshot, local = adapter.store();
        let needsSave = !snapshot, acceptedRemote = false;
        let meta = {};
        try { meta = JSON.parse(localStorage.getItem(metaKey) || '{}'); } catch {}
        if (snapshot) {
          revision = snapshot.revision;
          const same = signature(snapshot.store) === signature(local);
          const clean = meta.signature === signature(local);
          needsSave = signature(snapshot.context) !== signature(adapter.context);
          if (!same && (!meaningful(local) || clean)) {
            const restored = await Promise.all(snapshot.assets.map(unpackAsset));
            if (signature(adapter.store()) !== signature(local)) {
              // A person started typing while attachment recovery was in flight.
              revision = -1; needsSave = true;
            } else {
              await adapter.restore(snapshot.store, restored); acceptedRemote = true;
            }
          } else if (!same && meta.revision !== revision) {
            // Preserve a legacy/offline branch on disk; never silently overwrite the other browser.
            revision = -1; needsSave = true;
          } else if (!same) {
            needsSave = true;
          }
          for (const asset of snapshot.assets) {
            for (const item of asset.kind === 'folder' ? asset.files : [asset]) uploaded.set(item.file.sha256, item.file);
          }
          if (same || acceptedRemote) {
            localStorage.setItem(metaKey, JSON.stringify({revision: snapshot.revision, signature: signature(adapter.store())}));
          }
        }
        initialized = true; lastError = '';
        // The initial save also migrates old browser-only notes, history and all IndexedDB assets.
        dirty = needsSave;
        if (needsSave) schedule();
        else { savedAt = snapshot.savedAt; status('已从本期目录恢复，修改后自动保存'); }
      } catch (error) {
        lastError = error.message;
        status('尚未同步，原浏览器记录保留；' + error.message, true); later();
      }
    }

    function schedule() {
      dirty = true;
      if (blocked) return;
      status('待保存…');
      if (!initialized || busy || timer) return;
      timer = setTimeout(() => { timer = 0; flush().catch(() => {}); }, 650);
    }

    async function flush() {
      if (!initialized) { await initialize(); if (!initialized) throw new Error(lastError || '保存服务未连接'); }
      if (blocked) throw new Error(lastError || '存在意见版本冲突');
      if (busy) { await inflight; if (dirty) return flush(); return state(); }
      if (!dirty) return state();
      clearTimeout(timer); timer = 0; busy = true; dirty = false;
      status('正在保存…');
      inflight = (async () => {
        try {
          await adapter.waitPending();
          const store = clone(adapter.store());
          const assets = await Promise.all(adapter.assets().map(packAsset));
          const result = await request(endpoint, {projectId: adapter.projectId, baseRevision: revision,
            context: adapter.context, store, assets});
          revision = result.revision; savedAt = result.savedAt; lastError = '';
          localStorage.setItem(metaKey, JSON.stringify({revision, signature: signature(store)}));
          status('已自动保存到本期目录');
        } catch (error) {
          dirty = true; lastError = error.message;
          if (error.status === 409) {
            blocked = true;
            status('版本冲突已另存 ' + error.result.conflictPath + '；浏览器记录保留', true);
          } else {
            if (error.status === 403) initialized = false;
            status('保存失败，原浏览器记录保留；' + error.message, true); later();
          }
          throw error;
        } finally { busy = false; if (dirty && !blocked && !lastError) schedule(); }
        return state();
      })();
      return inflight;
    }

    document.addEventListener('workbench-persist', schedule);
    global.addEventListener('online', () => { if (!blocked) (initialized ? flush() : initialize()).catch(() => {}); });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden' && dirty && !blocked) flush().catch(() => {}); });
    global.addEventListener('beforeunload', event => {
      if (dirty || busy) { event.preventDefault(); event.returnValue = ''; }
    });
    initialize().catch(() => {});
    return {getState: state, flush};
  }
  global.WorkbenchProjectSync = {connect};
})(window);
