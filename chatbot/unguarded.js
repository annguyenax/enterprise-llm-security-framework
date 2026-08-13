const token = localStorage.getItem('shield_token') || '';
const state = { user: null, history: [], documents: [], busy: false };
const $ = selector => document.querySelector(selector);

function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;' })[char]);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof Blob) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...options, headers });
  const body = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail?.message || `HTTP ${response.status}`);
  return body;
}

function toast(message) {
  const node = $('#toast'); node.textContent = message; node.classList.add('show');
  clearTimeout(node.timer); node.timer = setTimeout(() => node.classList.remove('show'), 2400);
}

function formatSize(bytes) { return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`; }

function renderDocuments() {
  $('#documentCount').textContent = `${state.documents.length} tài liệu`;
  $('#documentList').innerHTML = state.documents.length ? state.documents.map(document => `<div class="document-row"><span>▤</span><div><strong title="${escapeHtml(document.filename)}">${escapeHtml(document.filename)}</strong><small>${formatSize(document.size_bytes)} · kho dùng chung · không kiểm tra upload</small></div><button type="button" data-delete-document="${escapeHtml(document.id)}" aria-label="Xóa ${escapeHtml(document.filename)}">×</button></div>`).join('') : '<p class="empty">Chưa có file trong kho tri thức dùng chung.</p>';
}

async function loadDocuments() { state.documents = await api('/unguarded/documents'); renderDocuments(); }

function showMessages() { $('#welcome').hidden = true; $('#messageList').classList.add('active'); }

function addMessage(role, content, sources = [], latency = null) {
  showMessages();
  const article = document.createElement('article'); article.className = `message ${role}`;
  if (role === 'user') article.innerHTML = `<div class="bubble">${escapeHtml(content)}</div>`;
  else article.innerHTML = `<div class="assistant-wrap"><div class="bubble">${escapeHtml(content)}</div>${sources.length ? `<div class="source-list">${sources.map(source => `<span>▤ ${escapeHtml(source.filename)}</span>`).join('')}</div>` : ''}<span class="baseline-note">Guards disabled${latency != null ? ` · ${(latency / 1000).toFixed(1)} giây` : ''}</span></div>`;
  $('#messageList').appendChild(article); $('#messages').scrollTop = $('#messages').scrollHeight; return article;
}

function addTyping() { const node = addMessage('assistant', ''); node.querySelector('.bubble').innerHTML = '<span class="typing"><i></i><i></i><i></i></span>'; return node; }

async function sendMessage(text) {
  const prompt = text.trim(); if (!prompt || state.busy) return;
  state.busy = true; $('#sendBtn').disabled = true; addMessage('user', prompt); $('#messageInput').value = '';
  const typing = addTyping();
  try {
    const result = await api('/unguarded/chat', { method:'POST', body:JSON.stringify({ content:prompt, history:state.history.slice(-12) }) });
    typing.remove(); addMessage('assistant', result.response, result.sources, result.latency_ms);
    state.history.push({ role:'user', content:prompt }, { role:'assistant', content:result.response });
  } catch (error) { typing.remove(); addMessage('assistant', `Không thể hoàn tất yêu cầu: ${error.message}`); }
  finally { state.busy = false; $('#sendBtn').disabled = false; $('#messageInput').focus(); }
}

async function uploadDocument() {
  const file = $('#documentFile').files[0]; if (!file) return;
  $('#uploadError').textContent = ''; $('#uploadDocumentBtn').disabled = true;
  try {
    await api('/unguarded/documents', { method:'POST', body:file, headers:{ 'Content-Type':'application/octet-stream', 'X-Filename':encodeURIComponent(file.name) } });
    $('#uploadDialog').close(); $('#documentFile').value = ''; await loadDocuments(); toast('Đã tải trực tiếp vào kho dùng chung, không qua Guard');
  } catch (error) { $('#uploadError').textContent = error.message; }
  finally { $('#uploadDocumentBtn').disabled = false; }
}

function resetSession() { state.history = []; $('#messageList').innerHTML = ''; $('#messageList').classList.remove('active'); $('#welcome').hidden = false; toast('Đã tạo phiên baseline mới'); }

async function bootstrap() {
  if (!token) { $('#accessScreen').hidden = false; $('#accessMessage').textContent = 'Hãy đăng nhập Shield AI trước khi mở môi trường so sánh.'; return; }
  try {
    state.user = await api('/auth/me');
    $('#profileName').textContent = state.user.username; $('#profileMeta').textContent = `${state.user.department} · ${state.user.role}`; $('#profileAvatar').textContent = state.user.username.slice(0,2).toUpperCase();
    await loadDocuments();
  } catch (error) { $('#accessScreen').hidden = false; $('#accessMessage').textContent = error.message; }
}

$('#chatForm').addEventListener('submit', event => { event.preventDefault(); sendMessage($('#messageInput').value); });
$('#messageInput').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('#chatForm').requestSubmit(); } });
$('#messageInput').addEventListener('input', event => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight,140)}px`; });
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => sendMessage(button.dataset.prompt)));
$('#newSessionBtn').addEventListener('click', resetSession); $('#uploadBtn').addEventListener('click', () => $('#uploadDialog').showModal()); $('#attachBtn').addEventListener('click', () => $('#uploadDialog').showModal());
$('#closeUploadBtn').addEventListener('click', () => $('#uploadDialog').close()); $('#uploadDocumentBtn').addEventListener('click', uploadDocument);
$('#documentList').addEventListener('click', async event => { const button = event.target.closest('[data-delete-document]'); if (!button) return; await api(`/unguarded/documents/${button.dataset.deleteDocument}`, { method:'DELETE' }); await loadDocuments(); toast('Đã xóa tài liệu khỏi kho dùng chung'); });

// Log out so the demo can switch roles without going back to the guarded
// page. The token is shared with Shield AI via localStorage, so this
// invalidates the session server-side, clears it locally, and returns to
// index.html where the login form lives (this page has no login form of its
// own). `keepalive` lets the POST finish even though we navigate away.
$('#logoutBtn')?.addEventListener('click', async () => {
  try { await api('/auth/logout', { method: 'POST', keepalive: true }); } catch (_) { /* log out locally regardless */ }
  localStorage.removeItem('shield_token');
  window.location.href = 'index.html';
});

bootstrap();
