const $ = selector => document.querySelector(selector);
const state = {
  token: localStorage.getItem('shield_token') || '',
  user: null,
  conversations: [],
  activeId: null,
  busy: false,
  authMode: 'login',
  registrationOpen: false,
  abortController: null,
  renderTimer: null,
  stopped: false
};
state.team = [];
state.tasks = [];
state.departments = [];
state.uploading = false;

const form = $('#chatForm');
const input = $('#messageInput');
const sendButton = $('#sendBtn');
const stopButton = $('#stopBtn');
const messages = $('#messages');
const messageList = $('#messageList');
const welcome = $('#welcome');
const sidebar = $('#sidebar');
const overlay = $('#overlay');

function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[char]);
}

function renderMarkdown(source = '') {
  const blocks = [];
  let text = escapeHtml(source).replace(/```([\w-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const index = blocks.push(`<pre><div class="code-head"><span>${lang || 'code'}</span><button class="copy-code" type="button">Sao chép</button></div><code>${code.trim()}</code></pre>`) - 1;
    return `@@CODE${index}@@`;
  });
  text = text
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/^[-*] (.+)$/gm, '<span class="list-line">• $1</span>')
    .replace(/\n/g, '<br>');
  blocks.forEach((block, index) => { text = text.replace(`@@CODE${index}@@`, block); });
  return text;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof Blob) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (response.status === 401 && !path.startsWith('/auth/')) {
    signOut(false);
    throw new Error('Phiên đăng nhập đã hết hạn');
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    let securityReport = null;
    try {
      const error = await response.json();
      detail = typeof error.detail === 'string' ? error.detail : error.detail?.message || detail;
      securityReport = error.detail?.security_report || null;
    } catch (_) { /* response was not JSON */ }
    const error = new Error(detail);
    error.status = response.status;
    error.securityReport = securityReport;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.remove('show'), 2600);
}

function showConversation() {
  welcome.hidden = true;
  messageList.classList.add('active');
}

function resetMessages() {
  messageList.innerHTML = '';
  messageList.classList.remove('active');
  welcome.hidden = false;
}

const BLOCKED_DECISIONS = new Set(['block', 'human_review']);
const APPEAL_LABELS = { pending: 'Kháng cáo đang chờ duyệt', accepted: 'Kháng cáo được chấp nhận', rejected: 'Kháng cáo bị từ chối' };

function percent(value) {
  return `${Math.round(Number(value) * 100)}%`;
}

/* Guard risk, shown per stage rather than as one number.
 * `risk_score` is the maximum weight of the rules a stage matched, so it is
 * labelled as a rule-based risk score — not a model confidence, and not a
 * probability. A stage that did not run is omitted entirely instead of
 * being drawn as 0%, because "not evaluated" is not "evaluated as safe". */
function riskStripHtml(message) {
  const stages = [
    ['Input', message.risk_input],
    ['RAG', message.risk_rag],
    ['Output', message.risk_output]
  ].filter(([, value]) => typeof value === 'number');
  if (!stages.length) return '';
  const peak = Math.max(...stages.map(([, value]) => value));
  const detail = stages.map(([name, value]) => `${name} ${value.toFixed(2)}`).join(' · ');
  return `<span class="score-chip risk" title="Điểm rủi ro theo luật (trọng số rule cao nhất mỗi tầng) — ${escapeHtml(detail)}">
    <span>Rủi ro (luật)</span><b>${peak.toFixed(2)}</b>
    <span class="meter"><i style="--value:${percent(peak)}"></i></span>
  </span>`;
}

/* Retrieval scores. Semantic (cosine) and lexical (BM25) are shown as two
 * distinct facts, never merged into one bar: the backend fuses them by rank
 * (RRF) precisely because the two scales are not comparable, and collapsing
 * them in the UI would re-imply a shared scale the system does not have. */
function retrievalStripHtml(message) {
  const sources = message.sources || [];
  const scored = sources.filter(source => typeof source.semantic_score === 'number');
  const mode = sources.find(source => source.retrieval)?.retrieval;
  const chips = [];
  if (mode) {
    chips.push(`<span class="score-chip mode" title="${mode === 'hybrid'
      ? 'Hybrid: BM25 từ khoá + embedding ngữ nghĩa, hợp nhất bằng Reciprocal Rank Fusion'
      : 'Chỉ BM25 từ khoá — mô hình embedding không khả dụng hoặc đang tắt'}">◎ ${escapeHtml(mode === 'hybrid' ? 'Hybrid RRF' : 'BM25')}</span>`);
  }
  if (scored.length) {
    const best = Math.max(...scored.map(source => source.semantic_score));
    chips.push(`<span class="score-chip" title="Cosine similarity giữa câu hỏi và tài liệu, tính bằng mô hình embedding cục bộ">
      <span>Ngữ nghĩa</span><b>${best.toFixed(2)}</b>
      <span class="meter"><i style="--value:${percent(best)}"></i></span>
    </span>`);
  } else if (mode === 'bm25' && sources.length) {
    chips.push('<span class="score-chip muted" title="Không có điểm ngữ nghĩa cho lượt này">Ngữ nghĩa: không có</span>');
  }
  return chips.join('');
}

function scoreStripHtml(message) {
  const chips = [riskStripHtml(message), retrievalStripHtml(message)].filter(Boolean).join('');
  return chips ? `<div class="score-strip">${chips}</div>` : '';
}

function sourcesHtml(message) {
  if (!message.sources?.length) return '';
  const items = message.sources.map(source => {
    const semantic = typeof source.semantic_score === 'number'
      ? `<span class="sem" title="Điểm ngữ nghĩa (cosine)">${source.semantic_score.toFixed(2)}</span>` : '';
    const rank = source.lexical_rank
      ? `<span class="rank" title="Hạng theo BM25 từ khoá">#${source.lexical_rank}</span>` : '';
    return `<span class="source-item" title="${escapeHtml(source.scope || '')}">▤ ${escapeHtml(source.filename)}${semantic}${rank}</span>`;
  }).join('');
  return `<div class="sources"><span>Tham khảo</span>${items}</div>`;
}

function appealHtml(message) {
  if (message.role !== 'assistant' || !message.id) return '';
  if (message.appeal_status) {
    const label = APPEAL_LABELS[message.appeal_status] || message.appeal_status;
    const note = message.appeal_note ? ` — ${message.appeal_note}` : '';
    return `<span class="appeal-state ${escapeHtml(message.appeal_status)}">⚖ ${escapeHtml(label)}${escapeHtml(note)}</span>`;
  }
  if (!BLOCKED_DECISIONS.has(message.decision)) return '';
  return `<button type="button" class="appeal-btn" data-action="appeal" title="Yêu cầu superadmin xem xét lại">⚖ Kháng cáo</button>`;
}

function messageActions(message) {
  if (message.role !== 'assistant' || !message.id) return '';
  const up = message.feedback === 1 ? 'active' : '';
  const down = message.feedback === -1 ? 'active' : '';
  return `<div class="message-actions">
    <button type="button" data-action="copy" title="Sao chép">⧉</button>
    <button type="button" data-action="feedback" data-value="1" class="${up}" title="Hữu ích">♡</button>
    <button type="button" data-action="feedback" data-value="-1" class="${down}" title="Chưa tốt">♢</button>
    ${message.latency_ms != null ? `<span>${(message.latency_ms / 1000).toFixed(1)} giây</span>` : ''}
    ${appealHtml(message)}
  </div>`;
}

function addMessage(message, animate = false) {
  showConversation();
  const node = document.createElement('article');
  node.className = `message ${message.role}`;
  node.dataset.messageId = message.id || '';
  node.dataset.raw = message.content || '';
  const note = message.decision
    ? `<span class="guard-note">◈ Guardrail: ${escapeHtml(message.decision)}</span>` : '';
  const sources = sourcesHtml(message);
  node.innerHTML = message.role === 'assistant'
    ? `<span class="message-bot-icon">✦</span><div class="message-content"><div class="bubble markdown"></div>${sources}${scoreStripHtml(message)}${note}${messageActions(message)}</div>`
    : `<div class="bubble">${escapeHtml(message.content)}</div>`;
  messageList.appendChild(node);
  if (message.role === 'assistant') {
    const bubble = node.querySelector('.bubble');
    if (animate) return animateAnswer(bubble, message.content);
    bubble.innerHTML = renderMarkdown(message.content);
  }
  messages.scrollTop = messages.scrollHeight;
  return Promise.resolve(node);
}

function addUploadStatus(file) {
  showConversation();
  const node = document.createElement('article');
  node.className = 'message assistant upload-status scanning';
  node.innerHTML = `<span class="message-bot-icon">&#128737;</span>
    <div class="message-content"><div class="bubble upload-status-bubble">
      <div class="upload-status-head"><strong>Đang kiểm tra tài liệu</strong><span>SCANNING</span></div>
      <p>${escapeHtml(file.name)} · ${formatFileSize(file.size)}</p>
      <small>Upload Scanner và RAG Guard đang kiểm tra tệp trước khi lưu.</small>
    </div></div>`;
  messageList.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function securityReportHtml(report) {
  if (!report?.stages?.length) return '';
  const labels = { upload_scanner: 'Upload Scanner', antivirus: 'Antivirus', rag_guard: 'RAG Guard' };
  return `<details class="security-report" open><summary>Chi tiết kiểm tra</summary>${report.stages.map(stage => {
    const rules = stage.rule_ids?.length ? stage.rule_ids.join(', ') : 'không có rule khớp';
    const reasons = stage.reasons?.length ? stage.reasons.join('; ') : 'không phát hiện dấu hiệu nguy hiểm';
    return `<div class="security-stage"><b>${escapeHtml(labels[stage.stage] || stage.stage)}</b><span class="decision ${escapeHtml(stage.decision)}">${escapeHtml(stage.decision)}</span><small>Engine: ${escapeHtml(stage.engine || 'unknown')} · ${escapeHtml(rules)}</small><small>${escapeHtml(reasons)}</small></div>`;
  }).join('')}</details>`;
}

function finishUploadStatus(node, kind, file, detail, decision = '', securityReport = null) {
  node.className = `message assistant upload-status ${kind}`;
  const labels = {
    allow: ['Tài liệu an toàn và đã được lưu', 'ALLOW'],
    sanitize: ['Tài liệu đã được làm sạch và lưu', 'SANITIZE'],
    blocked: ['Tài liệu bị từ chối', 'BLOCKED'],
    error: ['Không thể kiểm tra tài liệu', 'ERROR']
  };
  const [title, badge] = labels[kind] || labels.error;
  node.querySelector('.upload-status-bubble').innerHTML = `
    <div class="upload-status-head"><strong>${title}</strong><span>${badge}</span></div>
    <p>${escapeHtml(file.name)} · ${formatFileSize(file.size)}</p>
    <small>${escapeHtml(detail)}</small>
    ${decision ? `<em>Guard decision: ${escapeHtml(decision)}</em>` : ''}
    ${securityReportHtml(securityReport)}`;
  messages.scrollTop = messages.scrollHeight;
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function animateAnswer(bubble, content) {
  state.stopped = false;
  let index = 0;
  return new Promise(resolve => {
    const step = () => {
      if (state.stopped || index >= content.length) {
        bubble.innerHTML = renderMarkdown(content.slice(0, index));
        bindCodeCopy(bubble);
        state.renderTimer = null;
        resolve();
        return;
      }
      index += 1;
      bubble.innerHTML = renderMarkdown(content.slice(0, index));
      messages.scrollTop = messages.scrollHeight;
      state.renderTimer = setTimeout(step, 7);
    };
    step();
  });
}

function bindCodeCopy(root = document) {
  root.querySelectorAll('.copy-code').forEach(button => {
    if (button.dataset.bound) return;
    button.dataset.bound = '1';
    button.addEventListener('click', () => {
      navigator.clipboard.writeText(button.closest('pre').querySelector('code').textContent);
      toast('Đã sao chép đoạn mã');
    });
  });
}

function addTyping() {
  showConversation();
  const node = document.createElement('article');
  node.className = 'message assistant typing-message';
  node.innerHTML = '<span class="message-bot-icon">✦</span><div class="bubble"><span class="typing"><i></i><i></i><i></i></span><small class="thinking-label">Đang tạo và kiểm tra câu trả lời…</small></div>';
  messageList.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function setBusy(value) {
  state.busy = value;
  sendButton.disabled = value;
  stopButton.hidden = !value;
  sendButton.hidden = value;
}

async function ensureConversation() {
  if (state.activeId) return state.activeId;
  const conversation = await api('/conversations', {
    method: 'POST', body: JSON.stringify({ title: 'Cuộc trò chuyện mới' })
  });
  state.activeId = conversation.id;
  await loadConversations();
  return state.activeId;
}

async function sendMessage(text) {
  const prompt = text.trim();
  if (!prompt || state.busy || !state.user) return;
  const conversationId = await ensureConversation();
  setBusy(true);
  addMessage({ role: 'user', content: prompt });
  input.value = '';
  resizeInput();
  const typing = addTyping();
  state.abortController = new AbortController();

  try {
    const isUnguarded = window.location.pathname.includes('unguarded.html');
    const endpoint = `/conversations/${conversationId}/messages${isUnguarded ? '_unguarded' : ''}`;
    const data = await api(endpoint, {
      method: 'POST',
      body: JSON.stringify({ content: prompt }),
      signal: state.abortController.signal
    });
    typing.remove();
    const message = data.assistant_message;
    await addMessage(message, true);
    bindCodeCopy(messageList);
    await loadConversations();
  } catch (error) {
    typing.remove();
    if (error.name === 'AbortError') {
      toast('Đã dừng hiển thị. Hội thoại sẽ đồng bộ khi mở lại.');
    } else {
      addMessage({ role: 'assistant', content: `Không thể hoàn tất yêu cầu: ${error.message}`, decision: 'error' });
    }
  } finally {
    state.abortController = null;
    setBusy(false);
    input.focus();
  }
}

function stopGeneration() {
  state.stopped = true;
  if (state.abortController) state.abortController.abort();
  setBusy(false);
}

async function loadConversations() {
  state.conversations = await api('/conversations');
  renderHistory();
}

function renderHistory() {
  const list = $('#historyList');
  if (!state.conversations.length) {
    list.innerHTML = '<p class="empty-state">Chưa có cuộc trò chuyện</p>';
    return;
  }
  list.innerHTML = state.conversations.map(item => `
    <div class="history-row ${item.id === state.activeId ? 'active' : ''}" data-id="${item.id}">
      <button class="history-main" type="button"><span class="history-icon">✦</span><span><strong>${escapeHtml(item.title)}</strong><small>${state.user?.role === 'superadmin' ? `${escapeHtml(item.owner_username)} · ${escapeHtml(item.owner_department)} · ` : ''}${item.message_count} tin nhắn</small></span></button>
      <button class="history-delete" type="button" title="Xóa">×</button>
    </div>`).join('');
}

async function openConversation(id) {
  if (state.busy) stopGeneration();
  state.activeId = id;
  resetMessages();
  const conversation = state.conversations.find(item => item.id === id);
  $('#conversationTitle').textContent = conversation?.title || 'Shield Assistant';
  renderHistory();
  const items = await api(`/conversations/${id}/messages`);
  items.forEach(item => addMessage(item));
  bindCodeCopy(messageList);
  closeMobileSidebar();
}

async function createNewConversation() {
  const conversation = await api('/conversations', {
    method: 'POST', body: JSON.stringify({ title: 'Cuộc trò chuyện mới' })
  });
  await loadConversations();
  state.activeId = conversation.id;
  $('#conversationTitle').textContent = conversation.title;
  resetMessages();
  renderHistory();
  input.focus();
  closeMobileSidebar();
}

async function renameActive() {
  if (!state.activeId) return;
  const current = state.conversations.find(item => item.id === state.activeId);
  const title = window.prompt('Tên mới cho cuộc trò chuyện:', current?.title || '');
  if (!title?.trim()) return;
  await api(`/conversations/${state.activeId}`, {
    method: 'PATCH', body: JSON.stringify({ title: title.trim().slice(0, 80) })
  });
  await loadConversations();
  $('#conversationTitle').textContent = title.trim();
}

async function deleteConversation(id) {
  const conversation = state.conversations.find(item => item.id === id);
  if (!window.confirm(`Xóa “${conversation?.title || 'cuộc trò chuyện'}”?`)) return;
  await api(`/conversations/${id}`, { method: 'DELETE' });
  if (state.activeId === id) {
    state.activeId = null;
    resetMessages();
    $('#conversationTitle').textContent = 'Shield Assistant';
  }
  await loadConversations();
}

async function submitFeedback(button) {
  const article = button.closest('.message');
  const value = Number(button.dataset.value);
  await api(`/messages/${article.dataset.messageId}/feedback`, {
    method: 'PUT', body: JSON.stringify({ value })
  });
  article.querySelectorAll('[data-action="feedback"]').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  toast('Cảm ơn phản hồi của bạn');
}

function updateProfile() {
  $('#profileName').textContent = state.user.username;
  $('#profileMeta').textContent = `${state.user.department} · ${state.user.role}`;
  $('#profileAvatar').textContent = state.user.username.slice(0, 2).toUpperCase();
  $('#adminBtn').hidden = state.user.role !== 'superadmin';
  $('#documentScope').querySelector('option[value="department"]').disabled = state.user.role === 'member';
  $('#documentScope').querySelector('option[value="global"]').disabled = state.user.role !== 'superadmin';
  $('#documentAudience').querySelector('option[value="superadmin"]').disabled = state.user.role !== 'superadmin';
}

async function bootstrapSession() {
  try {
    const authStatus = await api('/auth/status');
    state.registrationOpen = authStatus.registration_open;
    $('#authToggle').hidden = !state.registrationOpen;
  } catch (_) { /* login will report backend connectivity */ }
  if (!state.token) return showAuth();
  try {
    state.user = await api('/auth/me');
    updateProfile();
    hideAuth();
    await loadConversations();
    if (state.conversations.length) await openConversation(state.conversations[0].id);
  } catch (_) {
    signOut(false);
  }
}

function showAuth() { $('#authScreen').classList.remove('hidden'); }
function hideAuth() { $('#authScreen').classList.add('hidden'); }

function signOut(callApi = true) {
  if (callApi && state.token) api('/auth/logout', { method: 'POST' }).catch(() => {});
  localStorage.removeItem('shield_token');
  Object.assign(state, { token: '', user: null, conversations: [], activeId: null });
  resetMessages();
  $('#historyList').innerHTML = '';
  showAuth();
}

function setAuthMode(mode) {
  if (mode === 'register' && !state.registrationOpen) return;
  state.authMode = mode;
  const register = mode === 'register';
  $('#authTitle').textContent = register ? 'Tạo tài khoản' : 'Đăng nhập Shield AI';
  $('#authCopy').textContent = register ? 'Tài khoản đầu tiên sẽ là quản trị viên.' : 'Tiếp tục cuộc trò chuyện của bạn trên thiết bị này.';
  $('#departmentField').hidden = !register;
  $('#authSubmit').textContent = register ? 'Đăng ký' : 'Đăng nhập';
  $('#authToggle').textContent = register ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký';
  $('#authError').textContent = '';
}

async function submitAuth(event) {
  event.preventDefault();
  const payload = { username: $('#authUsername').value.trim(), password: $('#authPassword').value };
  if (state.authMode === 'register') payload.department = $('#authDepartment').value.trim() || 'general';
  try {
    const result = await api(`/auth/${state.authMode}`, { method: 'POST', body: JSON.stringify(payload) });
    state.token = result.token;
    state.user = result.user;
    localStorage.setItem('shield_token', result.token);
    updateProfile();
    hideAuth();
    await loadConversations();
    if (state.conversations.length) await openConversation(state.conversations[0].id);
    else await createNewConversation();
  } catch (error) {
    $('#authError').textContent = error.message;
  }
}

async function openDocuments() {
  $('#documentsDialog').showModal();
  await loadDocuments();
}

async function loadDocuments() {
  const documents = await api('/documents');
  $('#documentList').innerHTML = documents.length ? documents.map(doc => `
    <div class="document-row"><span>▤</span><div><strong>${escapeHtml(doc.filename)}</strong><small>${doc.scope} · ${doc.audience_role} · ${(doc.size_bytes / 1024).toFixed(1)} KB · ${doc.guard_decision} · quyền: ${escapeHtml(doc.access_reason || 'scope')}</small>${doc.allowed_users?.length || doc.allowed_groups?.length ? `<small>Chia sẻ: ${escapeHtml([...(doc.allowed_users || []), ...(doc.allowed_groups || [])].join(', '))}</small>` : ''}</div><button type="button" data-document-delete="${doc.id}">×</button></div>
  `).join('') : '<p class="empty-state">Chưa có tài liệu trong phạm vi của bạn.</p>';
}

async function prepareUpload(file) {
  if (!file) return;
  if (!$('#documentDepartment').options.length) {
    const departments = await api('/departments');
    $('#documentDepartment').innerHTML = departments.map(item => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join('');
    if (state.user?.department) $('#documentDepartment').value = state.user.department;
  }
  $('#chatUploadName').textContent = file.name;
  $('#chatUploadSize').textContent = `${formatFileSize(file.size)} · kiểm tra trước khi lưu`;
  $('#chatUploadPanel').hidden = false;
}

function clearUploadSelection() {
  $('#documentFile').value = '';
  $('#documentAllowedUsers').value = '';
  $('#documentAllowedGroups').value = '';
  $('#chatUploadPanel').hidden = true;
}

async function uploadDocument() {
  const file = $('#documentFile').files[0];
  if (!file || state.uploading) return;
  await ensureConversation();
  state.uploading = true;
  $('#uploadDocumentBtn').disabled = true;
  $('#clearUploadBtn').disabled = true;
  const statusNode = addUploadStatus(file);
  try {
    const query = new URLSearchParams({
      scope: $('#documentScope').value,
      audience: $('#documentAudience').value,
      department: $('#documentDepartment').value,
      allowed_users: $('#documentAllowedUsers').value,
      allowed_groups: $('#documentAllowedGroups').value
    });
    const result = await api(`/documents?${query}`, {
      method: 'POST', body: file,
      headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) }
    });
    const systemCode = result.upload_scan?.detected_type === 'system-code';
    finishUploadStatus(
      statusNode,
      'allow',
      file,
      systemCode
        ? 'Đã nhận diện mã script/hệ thống, nhưng không phát hiện hành vi nguy hiểm. Tệp được phép lưu.'
        : 'Không phát hiện nội dung nguy hiểm. Tệp đã được thêm vào kho tài liệu.',
      result.guard_decision,
      result.security_report
    );
    clearUploadSelection();
    if ($('#documentsDialog').open) await loadDocuments();
  } catch (error) {
    const blocked = [400, 413, 415, 422].includes(error.status);
    finishUploadStatus(
      statusNode,
      blocked ? 'blocked' : 'error',
      file,
      blocked ? `${error.message} Tệp không được lưu.` : error.message,
      error.securityReport?.final_decision || '',
      error.securityReport
    );
  } finally {
    state.uploading = false;
    $('#uploadDocumentBtn').disabled = false;
    $('#clearUploadBtn').disabled = false;
  }
}

function openAppeal(article) {
  const messageId = article?.dataset.messageId;
  const dialog = $('#appealDialog');
  if (!messageId || !dialog) return;
  $('#appealMessageId').value = messageId;
  $('#appealReason').value = '';
  $('#appealError').textContent = '';
  const decision = article.querySelector('.guard-note')?.textContent?.trim() || '';
  $('#appealContext').textContent = decision
    ? `${decision} · Tin nhắn #${messageId}`
    : `Tin nhắn #${messageId}`;
  dialog.showModal();
}

async function submitAppeal(event) {
  event.preventDefault();
  const messageId = $('#appealMessageId').value;
  const reason = $('#appealReason').value.trim();
  if (!reason) { $('#appealError').textContent = 'Bạn cần nêu lý do kháng cáo'; return; }
  try {
    await api(`/messages/${messageId}/appeal`, { method: 'POST', body: JSON.stringify({ reason }) });
    $('#appealDialog').close();
    toast('Đã gửi kháng cáo. Superadmin sẽ xem xét.');
    // Re-render from the server so the button becomes the real stored
    // state rather than an optimistic guess.
    if (state.activeId) await openConversation(state.activeId);
  } catch (error) {
    $('#appealError').textContent = error.message;
  }
}

function renderAppealQueue(appeals) {
  const node = $('#appealQueue');
  if (!node) return;
  if (!appeals.length) {
    node.innerHTML = '<p class="empty-state">Chưa có kháng cáo nào.</p>';
    return;
  }
  node.innerHTML = appeals.map(appeal => {
    const quote = (appeal.message_content || '').slice(0, 240);
    const pending = appeal.status === 'pending';
    return `<article class="appeal-card" data-appeal="${escapeHtml(appeal.id)}">
      <div class="appeal-card-head">
        <span class="appeal-badge ${escapeHtml(appeal.status)}">${escapeHtml(appeal.status)}</span>
        <strong>${escapeHtml(appeal.username)}</strong>
        <small>${escapeHtml(appeal.department || '')} · ${escapeHtml(appeal.message_decision || '')} · ${escapeHtml(appeal.request_id || '')}</small>
      </div>
      <p class="appeal-reason">${escapeHtml(appeal.reason)}</p>
      <p class="appeal-quote">${escapeHtml(quote)}</p>
      ${pending ? `<div class="appeal-actions">
        <input data-note placeholder="Ghi chú xử lý (không bắt buộc)" maxlength="1000">
        <button type="button" class="accept" data-resolve="accepted">Chấp nhận</button>
        <button type="button" class="reject" data-resolve="rejected">Từ chối</button>
      </div>` : `<small>Xử lý bởi ${escapeHtml(appeal.resolved_by_username || '—')}${appeal.resolution_note ? ` · ${escapeHtml(appeal.resolution_note)}` : ''}</small>`}
    </article>`;
  }).join('');
}

async function resolveAppeal(card, status) {
  const note = card.querySelector('[data-note]')?.value || '';
  await api(`/admin/appeals/${card.dataset.appeal}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, note })
  });
  toast(status === 'accepted' ? 'Đã chấp nhận kháng cáo' : 'Đã từ chối kháng cáo');
  renderAppealQueue(await api('/admin/appeals'));
}

async function openAdmin() {
  const data = await api('/admin/stats');
  $('#adminDialog').showModal();
  const stats = { ...data.workspace, audit_events: data.audit.total, blocked: data.audit.decisions.block || 0 };
  $('#statGrid').innerHTML = Object.entries(stats).map(([name, value]) => `<div><strong>${value}</strong><span>${escapeHtml(name.replaceAll('_', ' '))}</span></div>`).join('');
  const departments = data.departments.filter(department => department.code !== 'WORKSPACE');
  if (data.users.some(user => user.role === 'superadmin')) departments.unshift({ code: 'WORKSPACE', name: 'Workspace' });
  $('#orgList').innerHTML = departments.map(department => {
    const users = data.users.filter(user => department.code === 'WORKSPACE'
      ? user.role === 'superadmin'
      : user.department === department.code && user.role !== 'superadmin');
    return `<div class="org-department"><strong>${escapeHtml(department.name)} (${escapeHtml(department.code)})</strong><div class="org-users">${users.map(user => `<span class="org-user ${user.role}"><b>${escapeHtml(user.role)}</b>${escapeHtml(user.username)}</span>`).join('') || '<span class="empty-state">Chưa có người dùng</span>'}</div></div>`;
  }).join('');
  // Appeals share the admin console but are fetched separately: a failure
  // to load the review queue must not blank out the security statistics.
  try { renderAppealQueue(await api('/admin/appeals')); }
  catch (error) {
    const node = $('#appealQueue');
    if (node) node.innerHTML = `<p class="empty-state">Không tải được kháng cáo: ${escapeHtml(error.message)}</p>`;
  }
  $('#auditList').innerHTML = data.audit.recent.length ? data.audit.recent.map(event => `
    <div class="audit-row"><span class="decision ${event.decision}">${event.decision}</span><div><strong>${escapeHtml(event.request_id || '')}</strong><small>${escapeHtml(event.timestamp || '')}</small></div><small>${escapeHtml((event.matched_rules || []).join(', '))}</small></div>
  `).join('') : '<p class="empty-state">Chưa có sự kiện audit.</p>';
}

function taskStatusLabel(status) {
  return ({ todo: 'Chưa bắt đầu', in_progress: 'Đang thực hiện', done: 'Hoàn thành' })[status] || status;
}

function renderTasks() {
  $('#taskList').innerHTML = state.tasks.length ? state.tasks.map(task => {
    const canDelegate = state.user.role !== 'member' && !task.parent_task_id;
    const canProgress = state.user.role === 'superadmin' || task.assigned_user_id === state.user.id;
    return `<article class="task-card ${task.parent_task_id ? 'child-task' : ''}">
      <div class="task-head"><span class="task-status ${task.status}">${taskStatusLabel(task.status)}</span><small>${escapeHtml(task.department)} · ${escapeHtml(task.assigned_username)}</small></div>
      <strong>${escapeHtml(task.title)}</strong><p>${escapeHtml(task.description || 'Không có mô tả')}</p>
      <div class="progress-track"><i style="width:${task.progress}%"></i></div>
      <div class="task-actions"><span>${task.progress}%${task.child_count ? ` · ${task.child_count} phần việc` : ''}</span>
        ${canDelegate ? `<button type="button" data-delegate="${task.id}">Giao xuống</button>` : ''}
        ${canProgress ? `<select data-progress="${task.id}" aria-label="Cập nhật tiến độ"><option value="">Cập nhật</option><option value="0">0%</option><option value="25">25%</option><option value="50">50%</option><option value="75">75%</option><option value="100">100%</option></select>` : ''}
      </div></article>`;
  }).join('') : '<p class="empty-state">Chưa có công việc được giao.</p>';
}

function renderTeam() {
  $('#teamList').innerHTML = state.team.map(person => `<span class="team-person ${person.role}"><b>${escapeHtml(person.username)}</b><small>${person.role === 'leader' ? 'Leader' : 'Nhân viên'}</small></span>`).join('') || '<p class="empty-state">Chưa có nhân sự.</p>';
}

async function openTasks() {
  state.departments = await api('/departments');
  state.tasks = await api('/tasks');
  $('#departmentTaskForm').hidden = state.user.role !== 'superadmin';
  $('#teamSection').hidden = state.user.role === 'member';
  $('#taskRoleHelp').textContent = state.user.role === 'superadmin'
    ? 'Bạn giao việc cho phòng ban; leader của phòng sẽ nhận và chia việc cho nhân viên.'
    : state.user.role === 'leader'
      ? 'Bạn thấy toàn bộ nhân sự và công việc trong phòng, sau đó giao phần việc xuống nhân viên.'
      : 'Bạn chỉ thấy công việc được giao cho chính mình và cập nhật tiến độ tại đây.';
  $('#taskDepartment').innerHTML = state.departments.filter(d => d.code !== 'WORKSPACE').map(d => `<option value="${escapeHtml(d.code)}">${escapeHtml(d.name)}</option>`).join('');
  if (state.user.role !== 'member') {
    state.team = await api(`/team${state.user.role === 'superadmin' ? `?department=${encodeURIComponent($('#taskDepartment').value || '')}` : ''}`);
    renderTeam();
  }
  renderTasks();
  $('#tasksDialog').showModal();
}

async function createDepartmentTask(event) {
  event.preventDefault();
  await api('/tasks/department', { method: 'POST', body: JSON.stringify({ title: $('#taskTitle').value, description: $('#taskDescription').value, department: $('#taskDepartment').value, due_at: $('#taskDueAt').value || null }) });
  event.target.reset(); state.tasks = await api('/tasks'); renderTasks(); toast('Đã giao việc cho leader phòng ban');
}

async function openDelegate(parentId) {
  $('#delegateParentId').value = parentId;
  const parent = state.tasks.find(task => task.id === parentId);
  if (state.user.role === 'superadmin' && parent) {
    state.team = await api(`/team?department=${encodeURIComponent(parent.department)}`);
  }
  const members = state.team.filter(person => person.role === 'member' && (!parent || person.department === parent.department));
  $('#delegateUser').innerHTML = members.map(person => `<option value="${person.id}">${escapeHtml(person.username)}</option>`).join('');
  $('#delegateDialog').showModal();
}

async function submitDelegate(event) {
  event.preventDefault(); const parentId = $('#delegateParentId').value;
  await api(`/tasks/${parentId}/delegate`, { method: 'POST', body: JSON.stringify({ assigned_user_id: Number($('#delegateUser').value), title: $('#delegateTitle').value, description: $('#delegateDescription').value, due_at: $('#delegateDueAt').value || null }) });
  $('#delegateDialog').close(); event.target.reset(); state.tasks = await api('/tasks'); renderTasks(); toast('Đã giao việc cho nhân viên');
}

function resizeInput() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
}

function closeMobileSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.remove('show');
}

form.addEventListener('submit', event => { event.preventDefault(); sendMessage(input.value); });
input.addEventListener('input', resizeInput);
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
});
messageList.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  const article = button.closest('.message');
  if (button.dataset.action === 'copy') {
    navigator.clipboard.writeText(article.dataset.raw); toast('Đã sao chép câu trả lời');
  }
  if (button.dataset.action === 'feedback') submitFeedback(button).catch(error => toast(error.message));
  if (button.dataset.action === 'appeal') openAppeal(article);
});
// Optional chaining, not a convenience: unguarded.html loads this same
// script but has no appeal dialog, and addEventListener on null would throw
// at parse time and take the whole chat UI down with it.
$('#appealForm')?.addEventListener('submit', event => submitAppeal(event));
$('#appealQueue')?.addEventListener('click', event => {
  const button = event.target.closest('[data-resolve]');
  if (!button) return;
  resolveAppeal(button.closest('.appeal-card'), button.dataset.resolve).catch(error => toast(error.message));
});
$('#historyList').addEventListener('click', event => {
  const row = event.target.closest('.history-row');
  if (!row) return;
  if (event.target.closest('.history-delete')) deleteConversation(row.dataset.id);
  else openConversation(row.dataset.id);
});
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => sendMessage(button.dataset.prompt)));
$('#newChatBtn').addEventListener('click', () => createNewConversation().catch(error => toast(error.message)));
$('#renameBtn').addEventListener('click', () => renameActive().catch(error => toast(error.message)));
$('#stopBtn').addEventListener('click', stopGeneration);
$('#logoutBtn').addEventListener('click', () => signOut(true));
$('#authForm').addEventListener('submit', submitAuth);
$('#authToggle').addEventListener('click', () => setAuthMode(state.authMode === 'login' ? 'register' : 'login'));
$('#documentsBtn').addEventListener('click', () => openDocuments().catch(error => toast(error.message)));
$('#tasksBtn').addEventListener('click', () => openTasks().catch(error => toast(error.message)));
$('#departmentTaskForm').addEventListener('submit', event => createDepartmentTask(event).catch(error => toast(error.message)));
$('#delegateForm').addEventListener('submit', event => submitDelegate(event).catch(error => toast(error.message)));
$('#taskDepartment').addEventListener('change', async event => {
  if (state.user?.role !== 'superadmin') return;
  state.team = await api(`/team?department=${encodeURIComponent(event.target.value)}`); renderTeam();
});
$('#taskList').addEventListener('click', event => { const button = event.target.closest('[data-delegate]'); if (button) openDelegate(button.dataset.delegate).catch(error => toast(error.message)); });
$('#taskList').addEventListener('change', async event => {
  const select = event.target.closest('[data-progress]'); if (!select || select.value === '') return;
  await api(`/tasks/${select.dataset.progress}/progress`, { method: 'PATCH', body: JSON.stringify({ progress: Number(select.value) }) });
  state.tasks = await api('/tasks'); renderTasks(); toast('Đã cập nhật tiến độ');
});
$('#attachBtn').addEventListener('click', () => $('#documentFile').click());
$('#documentFile').addEventListener('change', event => prepareUpload(event.target.files[0]).catch(error => {
  clearUploadSelection();
  addMessage({ role: 'assistant', content: `Không thể chuẩn bị tải tệp: ${error.message}`, decision: 'error' });
}));
$('#clearUploadBtn').addEventListener('click', clearUploadSelection);
$('#uploadDocumentBtn').addEventListener('click', () => uploadDocument());
$('#documentList').addEventListener('click', async event => {
  const button = event.target.closest('[data-document-delete]');
  if (!button || !confirm('Xóa tài liệu này?')) return;
  await api(`/documents/${button.dataset.documentDelete}`, { method: 'DELETE' });
  await loadDocuments();
});
$('#adminBtn').addEventListener('click', () => openAdmin().catch(error => toast(error.message)));
document.addEventListener('click', event => {
  const button = event.target.closest('[data-close]');
  if (!button) return;
  const dialog = document.getElementById(button.dataset.close);
  if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close();
});
$('#menuBtn').addEventListener('click', () => { sidebar.classList.add('open'); overlay.classList.add('show'); });
overlay.addEventListener('click', closeMobileSidebar);

setAuthMode('login');
bootstrapSession();
