/* =============================================================
   ASTER & ROW — AI SUPPORT CHAT
   script.js
   Connects the frontend to the FastAPI /chat endpoint.
============================================================= */

'use strict';

// -----------------------------------------------------------
// CONFIG
// -----------------------------------------------------------

const API_BASE           = 'http://127.0.0.1:8000';
const REQUEST_TIMEOUT_MS = 60_000;   // 60 s — local LLM can be slow

// -----------------------------------------------------------
// FILENAME → READABLE LABEL MAP
// -----------------------------------------------------------

const SOURCE_LABELS = {
  '01-returns-policy-current.md':          'Returns Policy',
  '02-returns-policy-legacy.md':           'Legacy Returns Policy',
  '03-final-sale-and-promotions.md':       'Final Sale & Promotions Policy',
  '04-damaged-or-wrong-items.md':          'Damaged / Wrong Items Policy',
  '05-domestic-shipping.md':               'Domestic Shipping Policy',
  '06-international-shipping.md':          'International Shipping Policy',
  '07-warranty.md':                        'Warranty Policy',
  '08-order-changes-and-cancellations.md': 'Order Changes & Cancellations',
  '09-trailplus-membership.md':            'TrailPlus Membership',
  '10-gift-cards-and-price-adjustments.md':'Gift Cards & Price Adjustments',
  '11-product-care.md':                    'Product Care',
  '12-breeze-tumbler-product-card.md':     'Breeze Tumbler Product Info',
  '13-support-escalation.md':              'Support Escalation',
  '14-internal-content-migration-notes.md':'Support Notes',
};

function sourceLabel(filename) {
  if (!filename) return 'Policy Document';
  const key = filename.toLowerCase().trim();
  return SOURCE_LABELS[key] ||
    filename.replace(/^\d+-/, '').replace('.md', '').replace(/-/g, ' ');
}

// -----------------------------------------------------------
// SESSION ID
// -----------------------------------------------------------

function generateSessionId() {
  const ts  = Date.now();
  const rnd = Math.random().toString(36).slice(2, 8);
  return `frontend_${ts}_${rnd}`;
}

function getSessionId() {
  let id = sessionStorage.getItem('ar_session_id');
  if (!id) {
    id = generateSessionId();
    sessionStorage.setItem('ar_session_id', id);
  }
  return id;
}

function resetSession() {
  sessionStorage.removeItem('ar_session_id');
  return getSessionId();   // generates a fresh id
}

// -----------------------------------------------------------
// DOM REFS
// -----------------------------------------------------------

const messagesEl = document.getElementById('messages');
const inputEl    = document.getElementById('chat-input');
const btnSend    = document.getElementById('btn-send');
const btnNewChat = document.getElementById('btn-new-chat');
const welcomeEl  = document.getElementById('welcome-section');

// -----------------------------------------------------------
// STATE
// -----------------------------------------------------------

let isLoading     = false;
let sessionId     = getSessionId();
let typingLiEl    = null;   // reference to the current typing-indicator <li>
let _srcIdCounter = 0;      // unique counter for sources ARIA id pairing
let _reqSeq       = 0;      // monotonic request sequence number

// -----------------------------------------------------------
// HELPERS — DOM
// -----------------------------------------------------------

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function hideWelcome() {
  if (welcomeEl && !welcomeEl.hidden) welcomeEl.hidden = true;
}

function scrollToBottom() {
  const main = document.querySelector('.chat-main');
  if (!main) return;
  // requestAnimationFrame defers until after browser reflow so scrollHeight is accurate.
  requestAnimationFrame(() => { main.scrollTop = main.scrollHeight; });
}

// -----------------------------------------------------------
// RENDER — USER MESSAGE
// -----------------------------------------------------------

function appendUserMessage(text) {
  hideWelcome();

  const li = document.createElement('li');
  li.className = 'msg msg--user';
  li.setAttribute('role', 'listitem');

  li.innerHTML = `
    <div class="msg-body">
      <div class="bubble"><span class="bubble-text">${escapeHtml(text)}</span></div>
      <time class="msg-time" datetime="${new Date().toISOString()}">${formatTime(new Date())}</time>
    </div>
    <div class="avatar avatar--user" aria-hidden="true">You</div>
  `;

  messagesEl.appendChild(li);
  scrollToBottom();
}

// -----------------------------------------------------------
// RENDER — TYPING INDICATOR
// -----------------------------------------------------------

function showTypingIndicator() {
  const li = document.createElement('li');
  li.className = 'msg msg--ai';
  li.setAttribute('role', 'listitem');
  li.setAttribute('aria-label', 'Assistant is typing');

  li.innerHTML = `
    <div class="avatar avatar--ai" aria-hidden="true">A&R</div>
    <div class="bubble typing-indicator">
      <span class="typing-dot" aria-hidden="true"></span>
      <span class="typing-dot" aria-hidden="true"></span>
      <span class="typing-dot" aria-hidden="true"></span>
    </div>
  `;

  messagesEl.appendChild(li);
  typingLiEl = li;
  scrollToBottom();
}

function removeTypingIndicator() {
  if (typingLiEl) {
    typingLiEl.remove();
    typingLiEl = null;
  }
}

// -----------------------------------------------------------
// RENDER — AI MESSAGE
// -----------------------------------------------------------

function appendAiMessage(text, sources) {
  const li = document.createElement('li');
  li.className = 'msg msg--ai';
  li.setAttribute('role', 'listitem');

  // Build sources HTML — sources belong ONLY to this specific response
  let sourcesHtml = '';
  const seen   = new Set();
  const labels = [];
  for (const s of (sources || [])) {
    if (!s || !s.file) continue;
    const label = sourceLabel(s.file);
    if (!seen.has(label)) { seen.add(label); labels.push(label); }
  }

  if (labels.length > 0) {
    const srcId     = `src-${++_srcIdCounter}`;
    const listItems = labels.map(l => `<li>${escapeHtml(l)}</li>`).join('');
    sourcesHtml = `
      <div class="sources-section">
        <button class="sources-toggle" type="button"
                aria-expanded="false"
                aria-controls="${srcId}">
          <i class="sources-toggle-icon" aria-hidden="true">&#x203A;</i>
          Sources
        </button>
        <ul class="sources-list" id="${srcId}" hidden>${listItems}</ul>
      </div>`;
  }

  li.innerHTML = `
    <div class="avatar avatar--ai" aria-hidden="true">A&R</div>
    <div class="msg-body">
      <div class="bubble">
        <span class="bubble-text">${renderMarkdown(text)}</span>
        ${sourcesHtml}
      </div>
      <time class="msg-time" datetime="${new Date().toISOString()}">${formatTime(new Date())}</time>
    </div>
  `;

  // Attach sources toggle listener scoped to THIS message's li only
  const toggle = li.querySelector('.sources-toggle');
  const list   = li.querySelector('.sources-list');
  if (toggle && list) {
    toggle.addEventListener('click', () => {
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      list.hidden = expanded;
    });
  }

  messagesEl.appendChild(li);
  scrollToBottom();
}

// -----------------------------------------------------------
// RENDER — ERROR MESSAGE
// -----------------------------------------------------------

function appendErrorMessage(text) {
  const li = document.createElement('li');
  li.className = 'msg msg--ai msg--error';
  li.setAttribute('role', 'listitem');

  li.innerHTML = `
    <div class="avatar avatar--ai" aria-hidden="true">A&R</div>
    <div class="msg-body">
      <div class="bubble"><span class="bubble-text">${escapeHtml(text)}</span></div>
      <time class="msg-time" datetime="${new Date().toISOString()}">${formatTime(new Date())}</time>
    </div>
  `;

  messagesEl.appendChild(li);
  scrollToBottom();
}

// -----------------------------------------------------------
// HTML ESCAPE
// -----------------------------------------------------------

function escapeHtml(str) {
  return String(str)
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#039;');
}

// -----------------------------------------------------------
// MARKDOWN RENDERER  (AI responses only)
// Safe: escapeHtml runs FIRST so all user content is neutralised
// before any HTML tags are injected.
// -----------------------------------------------------------

function renderMarkdown(rawText) {
  // 1. Trim + HTML-escape — all special chars become entities
  let s = escapeHtml(rawText.trim());

  // 2. Bold  **text**
  s = s.replace(/\*\*([^*\r\n]+?)\*\*/g, '<strong>$1</strong>');

  // 3. Italic  *text*  (single asterisk, not adjacent to another)
  s = s.replace(/(?<!\*)\*(?!\*)([^*\r\n]+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

  // 4. Inline code  `text`
  s = s.replace(/`([^`\r\n]+?)`/g,
    '<code style="background:#f0f0f0;border-radius:3px;padding:1px 5px;' +
    'font-size:0.85em;font-family:monospace">$1</code>');

  // 5. Unordered list items  "- item" or "* item" at the start of a line
  s = s.replace(/((?:^|\n)[*\-] .+)+/g, (block) => {
    const items = block
      .split('\n')
      .filter(line => /^[*\-] /.test(line.trim()))
      .map(line   => `<li>${line.replace(/^[*\-] /, '').trim()}</li>`)
      .join('');
    return `<ul style="margin:.4em 0 .4em 1.2em;padding:0">${items}</ul>`;
  });

  return s;
}

// -----------------------------------------------------------
// SEND MESSAGE  — core request / response cycle
// -----------------------------------------------------------

async function sendMessage(text) {
  text = (text || '').trim();
  if (!text || isLoading) return;

  // ── 1. Snapshot all relevant state as local constants BEFORE any await ───
  //
  // isLoading already prevents concurrency, but using local constants means
  // that a later mutation of module-level variables (e.g. startNewConversation
  // called while the request is in-flight) cannot affect THIS request.
  //
  const currentMessage   = text;
  const currentSessionId = sessionId;
  const thisSeq          = ++_reqSeq;   // unique number identifying this request

  // ── 2. Lock UI ───────────────────────────────────────────────────────────
  isLoading         = true;
  inputEl.disabled  = true;
  btnSend.disabled  = true;
  inputEl.value     = '';
  autoResizeTextarea();

  // ── 3. Render the user's bubble immediately ──────────────────────────────
  appendUserMessage(currentMessage);
  showTypingIndicator();

  // ── 4. DevTools Console diagnostics ─────────────────────────────────────
  //    Open DevTools → Console to verify every request sends the right message
  //    and every response returns the matching answer.
  console.group(`[A&R] Request #${thisSeq}`);
  console.log('  sent message :', currentMessage);
  console.log('  session_id   :', currentSessionId);

  // ── 5. AbortController — prevents a hung request from blocking the UI ────
  const controller = new AbortController();
  const timeoutId  = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    // ── 6. POST — URL is unique every call; no cache layer can match it ─────
    const response = await fetch(
      `${API_BASE}/chat?_t=${Date.now()}&seq=${thisSeq}`, {
        method:  'POST',
        signal:  controller.signal,
        headers: {
          'Content-Type':  'application/json',
          'Cache-Control': 'no-store',
          'Pragma':        'no-cache',
        },
        cache: 'no-store',
        body:  JSON.stringify({
          session_id: currentSessionId,
          message:    currentMessage,     // ← always the CURRENT message
        }),
      }
    );

    clearTimeout(timeoutId);
    removeTypingIndicator();

    // ── 7. HTTP-level errors ─────────────────────────────────────────────────
    if (!response.ok) {
      let detail = `Server returned ${response.status}.`;
      try {
        const err = await response.json();
        if (err.detail) detail = err.detail;
      } catch (_) { /* ignore JSON parse errors on error body */ }

      console.error('  HTTP error:', response.status, detail);
      console.groupEnd();
      appendErrorMessage(
        'Sorry, I encountered a problem processing your request. ' +
        'Please try again in a moment.'
      );
      return;
    }

    // ── 8. Parse response body ───────────────────────────────────────────────
    const data = await response.json();

    // ── 9. Response integrity check ──────────────────────────────────────────
    //
    // The backend echoes  { message: request.message, answer: "...", ... }
    // in every response.  If data.message !== currentMessage it means some
    // caching layer (browser, OS proxy, service worker) returned a stale
    // response that was originally generated for a DIFFERENT question.
    // Reject it so the user never sees a wrong answer silently.
    //
    if (typeof data.message === 'string' && data.message !== currentMessage) {
      console.error('  STALE RESPONSE DETECTED');
      console.error('    expected :', currentMessage);
      console.error('    received :', data.message);
      console.groupEnd();
      appendErrorMessage(
        'A stale cached response was detected \u2014 the answer would ' +
        'belong to a different question. Please try again.'
      );
      return;
    }

    // ── 10. Validate shape ───────────────────────────────────────────────────
    if (!data || typeof data.answer !== 'string') {
      console.error('  unexpected response shape:', data);
      console.groupEnd();
      appendErrorMessage(
        'Sorry, I received an unexpected response. Please try again.'
      );
      return;
    }

    // ── 11. Out-of-order guard (belt-and-suspenders) ─────────────────────────
    //
    // isLoading prevents true concurrency, but this guard future-proofs
    // against any code path that might bypass that constraint.
    //
    if (thisSeq !== _reqSeq) {
      console.warn('  out-of-order: discarding seq', thisSeq,
                   '(current:', _reqSeq, ')');
      console.groupEnd();
      return;
    }

    // ── 12. Success — log and render ─────────────────────────────────────────
    console.log(
      '  answer       :',
      data.answer.length > 120
        ? data.answer.slice(0, 120) + '\u2026'
        : data.answer
    );
    console.log(
      '  sources      :',
      (data.sources || []).map(s => s.file).join(', ') || '(none)'
    );
    console.groupEnd();

    appendAiMessage(data.answer, data.sources || []);

  } catch (err) {
    clearTimeout(timeoutId);
    removeTypingIndicator();

    if (err.name === 'AbortError') {
      console.error(
        `  request #${thisSeq} timed out after ${REQUEST_TIMEOUT_MS / 1000}s`
      );
      console.groupEnd();
      appendErrorMessage(
        'The request timed out \u2014 the AI model may still be loading. ' +
        'Please wait a moment and try again.'
      );
    } else {
      console.error(`  network error on request #${thisSeq}:`, err);
      console.groupEnd();
      appendErrorMessage(
        'Sorry, I couldn\u2019t connect to the support server. ' +
        'Please make sure the backend is running and try again.'
      );
    }

  } finally {
    // Unlock UI — runs unconditionally (normal return, early return, or throw)
    isLoading         = false;
    inputEl.disabled  = false;
    btnSend.disabled  = false;
    inputEl.focus();
  }
}

// -----------------------------------------------------------
// NEW CONVERSATION
// -----------------------------------------------------------

function startNewConversation() {
  // Fresh session ID — backend creates a new conversation_store entry
  sessionId = resetSession();

  // Clear rendered messages
  messagesEl.innerHTML = '';

  // Show the welcome panel again
  if (welcomeEl) welcomeEl.hidden = false;

  // Reset textarea
  inputEl.value = '';
  autoResizeTextarea();
  inputEl.focus();
}

// -----------------------------------------------------------
// TEXTAREA AUTO-RESIZE
// -----------------------------------------------------------

function autoResizeTextarea() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
}

// -----------------------------------------------------------
// EVENT LISTENERS
// Each listener is registered exactly ONCE at module load time.
// There is no <form> element, so no native form-submit event fires.
// -----------------------------------------------------------

// Send button
btnSend.addEventListener('click', () => sendMessage(inputEl.value));

// Enter = send, Shift+Enter = new line
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(inputEl.value);
  }
});

// Auto-resize textarea as user types
inputEl.addEventListener('input', autoResizeTextarea);

// New conversation button
btnNewChat.addEventListener('click', startNewConversation);

// Suggestion chips — single delegated listener on the welcome section
if (welcomeEl) {
  welcomeEl.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    const msg = chip.dataset.message;
    if (msg) sendMessage(msg);
  });
}

// -----------------------------------------------------------
// INIT
// -----------------------------------------------------------

window.addEventListener('DOMContentLoaded', () => { inputEl.focus(); });
