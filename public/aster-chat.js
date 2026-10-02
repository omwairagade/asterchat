(() => {
  const byId = (id) => document.getElementById(id);
  const authPanel = byId('auth-panel');
  const chatPanel = byId('chat-panel');
  const authNotice = byId('auth-notice');
  const chatNotice = byId('chat-notice');
  const loginButton = byId('login-button');
  const logoutButton = byId('logout-button');
  const sessionStatus = byId('session-status');
  const quotaCount = byId('quota-count');
  const chatForm = byId('chat-form');
  const chatInput = byId('chat-input');
  const sendButton = byId('send-button');
  const messagesNode = byId('chat-messages');
  const emptyMessage = byId('chat-empty');
  const dailyLimit = 100;

  let signedIn = false;
  let sending = false;
  let activeChatController = null;
  let remaining = dailyLimit;
  let conversation = [];

  function showNotice(node, message) {
    node.textContent = message || '';
  }

  function setUsage(data) {
    const used = Number.isFinite(data.used) ? data.used : 0;
    const limit = Number.isFinite(data.dailyLimit) ? data.dailyLimit : dailyLimit;
    remaining = Number.isFinite(data.remaining) ? Math.max(0, data.remaining) : Math.max(0, limit - used);
    quotaCount.textContent = `${remaining} of ${limit} left`;
    updateControls();
  }

  function updateControls() {
    const blocked = !signedIn || sending || remaining <= 0;
    chatInput.disabled = blocked;
    sendButton.disabled = blocked || !chatInput.value.trim();
    loginButton.disabled = sending;
  }

  function setAuthenticated(data) {
    signedIn = Boolean(data.authenticated);
    authPanel.hidden = signedIn;
    chatPanel.hidden = !signedIn;
    logoutButton.hidden = !signedIn;
    sessionStatus.innerHTML = '<span class="status-dot" aria-hidden="true"></span>' + (signedIn ? 'Signed in with Manus' : 'Sign in to chat');
    if (signedIn) setUsage(data);
    else {
      remaining = dailyLimit;
      quotaCount.textContent = 'Sign in to see your count';
      chatInput.value = '';
      updateControls();
    }
  }

  function clearConversation() {
    conversation = [];
    messagesNode.replaceChildren();
    if (emptyMessage) {
      emptyMessage.textContent = 'Start with the messy version. Aster is listening.';
      messagesNode.appendChild(emptyMessage);
    }
  }

  function appendMessage(role, text) {
    if (emptyMessage && emptyMessage.isConnected) emptyMessage.remove();
    const bubble = document.createElement('article');
    bubble.className = `message message-${role}`;
    bubble.setAttribute('aria-label', role === 'user' ? 'You' : 'Aster');
    const content = document.createElement('div');
    content.className = 'message-body';
    content.textContent = text || '';
    bubble.appendChild(content);
    messagesNode.appendChild(bubble);
    messagesNode.scrollTop = messagesNode.scrollHeight;
    return { bubble, content };
  }

  async function loadSession() {
    try {
      const response = await fetch('/api/auth/session', { credentials: 'same-origin', cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) {
        setAuthenticated({ authenticated: false });
        showNotice(authNotice, data.error || 'The account service is unavailable. Please try again shortly.');
        return;
      }
      setAuthenticated(data);
    } catch (_) {
      setAuthenticated({ authenticated: false });
      showNotice(authNotice, 'Could not check your sign-in. Please refresh and try again.');
    }
    if (new URLSearchParams(window.location.search).get('auth') === 'failed') {
      showNotice(authNotice, 'Sign-in did not complete. Please try again.');
      window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
    }
  }

  loginButton.addEventListener('click', async () => {
    showNotice(authNotice, '');
    loginButton.disabled = true;
    try {
      const response = await fetch('/api/auth/start', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ origin: window.location.origin }),
      });
      const data = await response.json();
      if (!response.ok || !data.authorizationUrl) throw new Error(data.detail || 'Sign-in is unavailable.');
      if (window.top && window.top !== window) window.top.location.assign(data.authorizationUrl);
      else window.location.assign(data.authorizationUrl);
    } catch (error) {
      showNotice(authNotice, typeof error.message === 'string' ? error.message : 'Could not start sign-in.');
      loginButton.disabled = false;
    }
  });

  logoutButton.addEventListener('click', async () => {
    logoutButton.disabled = true;
    if (activeChatController) activeChatController.abort();
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ origin: window.location.origin }),
      });
    } finally {
      clearConversation();
      setAuthenticated({ authenticated: false });
      logoutButton.disabled = false;
      showNotice(chatNotice, '');
    }
  });

  chatInput.addEventListener('input', updateControls);
  chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = chatInput.value.trim();
    if (!text || !signedIn || sending || remaining <= 0) return;
    if (text.length > 4000) {
      showNotice(chatNotice, 'Please keep each message under 4,000 characters.');
      return;
    }

    showNotice(chatNotice, '');
    if (emptyMessage && emptyMessage.isConnected) emptyMessage.remove();
    conversation.push({ role: 'user', content: text });
    appendMessage('user', text);
    chatInput.value = '';
    sending = true;
    updateControls();
    const assistant = appendMessage('assistant', 'Thinking…');
    assistant.content.setAttribute('aria-label', 'Aster is thinking');
    let assistantText = '';
    let gotError = false;
    let completed = false;
    const controller = new AbortController();
    activeChatController = controller;

    try {
      const requestHistory = conversation.slice(-23);
      while (requestHistory.length && requestHistory[0].role !== 'user') requestHistory.shift();
      const response = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify({ messages: requestHistory }),
        signal: controller.signal,
      });
      if (response.status === 401) {
        clearConversation();
        setAuthenticated({ authenticated: false });
        showNotice(authNotice, 'Your sign-in expired. Sign in again to continue.');
        return;
      }
      if (response.status === 429) {
        const body = await response.json();
        const detail = body.detail || {};
        if (typeof detail === 'object') setUsage(detail);
        conversation.pop();
        assistant.bubble.remove();
        showNotice(chatNotice, detail.message || 'You have reached today’s message limit.');
        return;
      }
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => ({}));
        conversation.pop();
        assistant.bubble.remove();
        showNotice(chatNotice, body.detail || 'Aster could not start a reply. Please try again.');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const handleEvent = (raw) => {
        let eventName = 'message';
        const dataLines = [];
        raw.split('\n').forEach((line) => {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        });
        if (!dataLines.length) return;
        let data;
        try { data = JSON.parse(dataLines.join('\n')); } catch (_) { return; }
        if (eventName === 'usage') setUsage(data);
        if (eventName === 'delta' && typeof data.text === 'string') {
          assistantText += data.text;
          assistant.content.textContent = assistantText;
          messagesNode.scrollTop = messagesNode.scrollHeight;
        }
        if (eventName === 'done') {
          if (typeof data.html === 'string') assistant.content.innerHTML = data.html;
          completed = true;
        }
        if (eventName === 'error') {
          gotError = true;
          showNotice(chatNotice, data.message || 'Aster could not complete that reply.');
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() || '';
        chunks.forEach(handleEvent);
      }
      buffer += decoder.decode();
      if (buffer.trim()) handleEvent(buffer);
      if (assistantText) conversation.push({ role: 'assistant', content: assistantText });
      else if (gotError) assistant.bubble.remove();
      else if (!completed) assistant.bubble.remove();
    } catch (error) {
      if (error && error.name === 'AbortError') {
        assistant.bubble.remove();
        return;
      }
      if (assistantText) conversation.push({ role: 'assistant', content: assistantText });
      else assistant.bubble.remove();
      showNotice(chatNotice, 'The connection stopped before Aster could finish. Your submitted message used one daily message.');
    } finally {
      if (activeChatController === controller) activeChatController = null;
      sending = false;
      updateControls();
      if (signedIn) chatInput.focus();
    }
  });

  byId('year').textContent = new Date().getFullYear();
  loadSession();
})();
