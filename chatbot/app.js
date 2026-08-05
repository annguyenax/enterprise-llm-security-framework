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
    try {
      const error = await response.json();
      detail = typeof error.detail === 'string' ? error.detail : error.detail?.message || detail;
    } catch (_) { /* response was not JSON */ }
    throw new Error(detail);
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

function messageActions(message) {
  if (message.role !== 'assistant' || !message.id) return '';
  const up = message.feedback === 1 ? 'active' : '';
  const down = message.feedback === -1 ? 'active' : '';
  return `<div class="message-actions">
    <button type="button" data-action="copy" title="Sao chép">⧉</button>
    <button type="button" data-action="feedback" data-value="1" class="${up}" title="Hữu ích">♡</button>
    <button type="button" data-action="feedback" data-value="-1" class="${down}" title="Chưa tốt">♢</button>
    ${message.latency_ms != null ? `<span>${(message.latency_ms / 1000).toFixed(1)} giây</span>` : ''}
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
  const sources = message.sources?.length
    ? `<div class="sources"><span>Tham khảo</span>${message.sources.map(source => `<b title="${escapeHtml(source.scope)}">▤ ${escapeHtml(source.filename)}</b>`).join('')}</div>`
    : '';
  node.innerHTML = message.role === 'assistant'
    ? `<span class="message-bot-icon">✦</span><div class="message-content"><div class="bubble markdown"></div>${sources}${note}${messageActions(message)}</div>`
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
    const data = await api(`/conversations/${conversationId}/messages`, {
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
  const departments = await api('/departments');
  $('#documentDepartment').innerHTML = departments.map(item => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join('');
  await loadDocuments();
}

async function loadDocuments() {
  const documents = await api('/documents');
  $('#documentList').innerHTML = documents.length ? documents.map(doc => `
    <div class="document-row"><span>▤</span><div><strong>${escapeHtml(doc.filename)}</strong><small>${doc.scope} · ${doc.audience_role} · ${(doc.size_bytes / 1024).toFixed(1)} KB · ${doc.guard_decision}</small></div><button type="button" data-document-delete="${doc.id}">×</button></div>
  `).join('') : '<p class="empty-state">Chưa có tài liệu trong phạm vi của bạn.</p>';
}

async function uploadDocument(event) {
  event.preventDefault();
  const file = $('#documentFile').files[0];
  if (!file) return;
  $('#uploadError').textContent = '';
  try {
    await api(`/documents?scope=${encodeURIComponent($('#documentScope').value)}&audience=${encodeURIComponent($('#documentAudience').value)}&department=${encodeURIComponent($('#documentDepartment').value)}`, {
      method: 'POST', body: file,
      headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) }
    });
    event.target.reset();
    toast('Tài liệu đã qua kiểm tra và được lưu');
    await loadDocuments();
  } catch (error) { $('#uploadError').textContent = error.message; }
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
$('#uploadForm').addEventListener('submit', uploadDocument);
$('#documentList').addEventListener('click', async event => {
  const button = event.target.closest('[data-document-delete]');
  if (!button || !confirm('Xóa tài liệu này?')) return;
  await api(`/documents/${button.dataset.documentDelete}`, { method: 'DELETE' });
  await loadDocuments();
});
$('#adminBtn').addEventListener('click', () => openAdmin().catch(error => toast(error.message)));
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => $(`#${button.dataset.close}`).close()));
$('#menuBtn').addEventListener('click', () => { sidebar.classList.add('open'); overlay.classList.add('show'); });
overlay.addEventListener('click', closeMobileSidebar);

setAuthMode('login');
bootstrapSession();
