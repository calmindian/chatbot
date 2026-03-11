import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  CircularProgress, Snackbar, Alert
} from '@mui/material';

// ── API ───────────────────────────────────────────────────────────────────────
const API_BASE = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';
const api = axios.create({ baseURL: API_BASE });

// ── ICONS (inline SVG — no extra deps) ───────────────────────────────────────
const Icon = {
  Send: () => (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
    </svg>
  ),
  Menu: () => (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
      <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
    </svg>
  ),
  Close: () => (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
    </svg>
  ),
  Camera: () => (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <path d="M12 15.2A3.2 3.2 0 1 0 12 8.8a3.2 3.2 0 0 0 0 6.4z"/><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/>
    </svg>
  ),
  Edit: () => (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
      <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
    </svg>
  ),
  Shirt: () => (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <path d="M16 4.1C16 2.39 14.21 1 12 1S8 2.39 8 4.1c-2.43.7-4.35 2.6-5 5.09l3 .81V21h12V10l3-.81c-.65-2.49-2.57-4.39-5-5.09zm-4-.1c.74 0 1.34.45 1.34 1S12.74 6 12 6s-1.34-.45-1.34-1S11.26 4 12 4z"/>
    </svg>
  ),
  Brain: () => (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <path d="M13 3c-4.42 0-8 3.58-8 8H3l3.89 3.89.07.14L11 11H9c0-2.21 1.79-4 4-4s4 1.79 4 4-1.79 4-4 4c-1.1 0-2.1-.45-2.83-1.17l-1.42 1.42C9.96 16.55 11.41 17 13 17c4.42 0 8-3.58 8-8s-3.58-8-8-8zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/>
    </svg>
  ),
  Image: () => (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
    </svg>
  ),
  Check: () => (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
    </svg>
  ),
  DoubleCheck: () => (
    <svg viewBox="0 0 18 18" width="16" height="16" fill="#53bdeb">
      <path d="M17.394 5.035l-.57-.444a.434.434 0 0 0-.609.076L8.97 13.901l-3.857-3.02a.434.434 0 0 0-.609.076l-.494.63a.434.434 0 0 0 .076.609l4.53 3.55a.434.434 0 0 0 .609-.076l7.246-9.25a.434.434 0 0 0-.076-.609zm-5.999 3.205l-.57-.444a.434.434 0 0 0-.609.076l-4.914 6.274-1.378-1.08a.434.434 0 0 0-.609.076l-.494.63a.434.434 0 0 0 .076.609l2.059 1.614a.434.434 0 0 0 .609-.076l5.906-7.55a.434.434 0 0 0-.076-.609z"/>
    </svg>
  ),
};

// ── STYLES ────────────────────────────────────────────────────────────────────
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg-deep:      #0a1014;
    --bg-sidebar:   #111b21;
    --bg-header:    #202c33;
    --bg-input:     #2a3942;
    --bg-user-msg:  #005c4b;
    --bg-ai-msg:    #202c33;
    --bg-panel:     #182229;
    --accent:       #00a884;
    --accent-hover: #06cf9c;
    --text-primary: #e9edef;
    --text-secondary:#8696a0;
    --text-time:    #8696a0;
    --border:       #2a3942;
    --divider:      #222d34;
    --sidebar-w:    360px;
    --header-h:     60px;
    --input-h:      62px;
    --radius-msg:   8px;
    --shadow:       0 1px 3px rgba(0,0,0,.4);
  }

  html, body, #root {
    height: 100%;
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg-deep);
    color: var(--text-primary);
    -webkit-font-smoothing: antialiased;
  }

  /* ── Layout shell ─────────────────────────────────────────── */
  .wa-shell {
    display: flex;
    height: 100dvh;
    overflow: hidden;
  }

  /* ── Sidebar ──────────────────────────────────────────────── */
  .wa-sidebar {
    width: var(--sidebar-w);
    min-width: var(--sidebar-w);
    background: var(--bg-sidebar);
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border);
    transition: transform .25s ease;
    z-index: 10;
  }

  .wa-sidebar-header {
    height: var(--header-h);
    background: var(--bg-header);
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 0 16px;
    flex-shrink: 0;
  }

  .wa-sidebar-header .avatar-wrap {
    position: relative;
    cursor: pointer;
  }

  .wa-avatar {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    object-fit: cover;
    background: var(--bg-input);
    display: block;
  }

  .wa-avatar-edit {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: rgba(0,0,0,.5);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity .2s;
    color: #fff;
  }
  .avatar-wrap:hover .wa-avatar-edit { opacity: 1; }

  .wa-sidebar-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;
  }

  .wa-sidebar-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
  }

  .wa-sidebar-body::-webkit-scrollbar { width: 6px; }
  .wa-sidebar-body::-webkit-scrollbar-track { background: transparent; }
  .wa-sidebar-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* ── Settings panels in sidebar ───────────────────────────── */
  .panel-section {
    padding: 12px 16px;
    border-bottom: 1px solid var(--divider);
  }

  .panel-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .8px;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 10px;
  }

  .wa-input {
    width: 100%;
    background: var(--bg-input);
    border: none;
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
    padding: 10px 14px;
    outline: none;
    resize: none;
    transition: box-shadow .15s;
  }
  .wa-input::placeholder { color: var(--text-secondary); }
  .wa-input:focus { box-shadow: 0 0 0 2px var(--accent); }

  .wa-btn {
    width: 100%;
    margin-top: 8px;
    padding: 9px 14px;
    border: none;
    border-radius: 8px;
    background: var(--accent);
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    transition: background .15s, opacity .15s;
  }
  .wa-btn:hover:not(:disabled) { background: var(--accent-hover); }
  .wa-btn:disabled { opacity: .5; cursor: not-allowed; }

  .wa-btn.secondary {
    background: var(--bg-input);
    color: var(--text-primary);
  }
  .wa-btn.secondary:hover:not(:disabled) { background: var(--border); }

  /* Status dot */
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    font-size: 13px;
    color: var(--text-secondary);
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
    box-shadow: 0 0 6px var(--accent);
  }

  /* ── Chat pane ─────────────────────────────────────────────── */
  .wa-chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    background: var(--bg-deep);
    position: relative;
  }

  /* Subtle tiled background like WhatsApp */
  .wa-chat::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(circle at 1px 1px, rgba(255,255,255,.03) 1px, transparent 0);
    background-size: 24px 24px;
    pointer-events: none;
  }

  /* ── Chat header ──────────────────────────────────────────── */
  .wa-chat-header {
    height: var(--header-h);
    background: var(--bg-header);
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 16px;
    flex-shrink: 0;
    z-index: 1;
    box-shadow: var(--shadow);
  }

  .menu-btn {
    display: none;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 6px;
    border-radius: 50%;
    transition: background .15s;
  }
  .menu-btn:hover { background: var(--bg-input); }

  .chat-header-info { flex: 1; min-width: 0; }
  .chat-header-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .chat-header-status {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 1px;
  }
  .chat-header-status.typing { color: var(--accent); }

  /* ── Messages area ─────────────────────────────────────────── */
  .wa-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px 4%;
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: relative;
    z-index: 1;
  }

  .wa-messages::-webkit-scrollbar { width: 6px; }
  .wa-messages::-webkit-scrollbar-track { background: transparent; }
  .wa-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .msg-row {
    display: flex;
    flex-direction: column;
    max-width: 68%;
    animation: fadeUp .2s ease;
  }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .msg-row.user  { align-self: flex-end; align-items: flex-end; }
  .msg-row.ai    { align-self: flex-start; align-items: flex-start; }

  .msg-bubble {
    padding: 8px 12px 6px;
    border-radius: var(--radius-msg);
    font-size: 14.5px;
    line-height: 1.5;
    position: relative;
    box-shadow: var(--shadow);
    word-break: break-word;
  }
  .msg-row.user  .msg-bubble {
    background: var(--bg-user-msg);
    color: var(--text-primary);
    border-bottom-right-radius: 2px;
  }
  .msg-row.ai    .msg-bubble {
    background: var(--bg-ai-msg);
    color: var(--text-primary);
    border-bottom-left-radius: 2px;
  }

  .msg-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    justify-content: flex-end;
    margin-top: 3px;
    font-size: 11px;
    color: var(--text-time);
    opacity: .8;
  }

  .msg-image {
    max-width: 100%;
    border-radius: 6px;
    margin-top: 6px;
    display: block;
    cursor: zoom-in;
  }

  .msg-gap { height: 6px; }

  /* Date pill */
  .date-pill {
    align-self: center;
    background: var(--bg-header);
    color: var(--text-secondary);
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 20px;
    margin: 8px 0;
  }

  /* Typing indicator */
  .typing-bubble {
    background: var(--bg-ai-msg);
    border-radius: var(--radius-msg);
    border-bottom-left-radius: 2px;
    padding: 12px 16px;
    display: flex;
    gap: 5px;
    align-items: center;
    align-self: flex-start;
    box-shadow: var(--shadow);
    animation: fadeUp .2s ease;
  }
  .typing-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-secondary);
    animation: bounce 1.2s infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: .2s; }
  .typing-dot:nth-child(3) { animation-delay: .4s; }
  @keyframes bounce {
    0%,60%,100% { transform: translateY(0); }
    30%          { transform: translateY(-5px); }
  }

  /* Image generation progress */
  .gen-bubble {
    background: var(--bg-ai-msg);
    border-radius: var(--radius-msg);
    border-bottom-left-radius: 2px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    align-self: flex-start;
    font-size: 13px;
    color: var(--text-secondary);
    box-shadow: var(--shadow);
    animation: fadeUp .2s ease;
  }

  /* ── Input bar ─────────────────────────────────────────────── */
  .wa-input-bar {
    height: var(--input-h);
    background: var(--bg-header);
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 16px;
    flex-shrink: 0;
    z-index: 1;
  }

  .wa-chat-input {
    flex: 1;
    background: var(--bg-input);
    border: none;
    border-radius: 24px;
    color: var(--text-primary);
    font-size: 15px;
    font-family: inherit;
    padding: 10px 18px;
    outline: none;
    resize: none;
    max-height: 120px;
    line-height: 1.4;
  }
  .wa-chat-input::placeholder { color: var(--text-secondary); }

  .send-btn {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    border: none;
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background .15s, transform .1s;
  }
  .send-btn:hover:not(:disabled) { background: var(--accent-hover); }
  .send-btn:active:not(:disabled) { transform: scale(.92); }
  .send-btn:disabled { background: var(--bg-input); color: var(--text-secondary); cursor: not-allowed; }

  /* ── Mobile overlay ────────────────────────────────────────── */
  .sidebar-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.6);
    z-index: 9;
  }

  /* ── Image lightbox ────────────────────────────────────────── */
  .lightbox {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.92);
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: zoom-out;
    animation: fadeIn .15s ease;
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  .lightbox img {
    max-width: 92vw;
    max-height: 92vh;
    border-radius: 8px;
    box-shadow: 0 8px 48px rgba(0,0,0,.8);
  }
  .lightbox-close {
    position: absolute;
    top: 16px;
    right: 16px;
    background: rgba(255,255,255,.15);
    border: none;
    color: #fff;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background .15s;
  }
  .lightbox-close:hover { background: rgba(255,255,255,.3); }

  /* ── Empty state ───────────────────────────────────────────── */
  .empty-chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: var(--text-secondary);
    font-size: 14px;
  }
  .empty-icon {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    background: var(--bg-header);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
  }

  /* ── Responsive ────────────────────────────────────────────── */
  @media (max-width: 768px) {
    .wa-sidebar {
      position: fixed;
      top: 0; left: 0; bottom: 0;
      transform: translateX(-100%);
    }
    .wa-sidebar.open {
      transform: translateX(0);
      box-shadow: 4px 0 24px rgba(0,0,0,.5);
    }
    .sidebar-overlay.open { display: block; }
    .menu-btn { display: flex; }
    .msg-row { max-width: 85%; }
  }

  @media (min-width: 769px) {
    .menu-btn { display: none !important; }
  }
`;

// ── HELPERS ───────────────────────────────────────────────────────────────────
function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function isImageRequest(msg) {
  return ['image','picture','photo','pic','selfie','show me','draw']
    .some(k => msg.toLowerCase().includes(k));
}

function isGifRequest(msg) {
  return ['gif','animate','dancing','walking','moving','motion','video','action']
    .some(k => msg.toLowerCase().includes(k));
}

// ── COMPONENT ─────────────────────────────────────────────────────────────────
export default function App() {
  // sidebar
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // settings fields
  const [avatarPrompt, setAvatarPrompt] = useState('');
  const [outfit,       setOutfit]       = useState('');
  const [personality,  setPersonality]  = useState('friendly');
  const [avatarSrc,    setAvatarSrc]    = useState(`${API_BASE}/media/avatar.png?t=${Date.now()}`);

  // loading per action
  const [loadingAvatar,      setLoadingAvatar]      = useState(false);
  const [loadingOutfit,      setLoadingOutfit]       = useState(false);
  const [loadingPersonality, setLoadingPersonality]  = useState(false);
  const [loadingChat,        setLoadingChat]         = useState(false);

  // chat
  const [messages,  setMessages]  = useState([]);
  const [message,   setMessage]   = useState('');
  const [isTyping,  setIsTyping]  = useState(false);
  const [isGenImg,  setIsGenImg]  = useState(false);
  const [isGenGif,  setIsGenGif]  = useState(false);

  // lightbox
  const [lightbox, setLightbox] = useState(null);

  // snackbar
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'error' });

  // server status
  const [isServerOnline, setIsServerOnline] = useState(false);

  // voice (Web Speech API — fully offline, no backend needed)
  const [voices,       setVoices]       = useState([]);
  const [currentVoice, setCurrentVoice] = useState(null); // SpeechSynthesisVoice object
  const [ttsEnabled,   setTtsEnabled]   = useState(true);

  const chatEndRef  = useRef(null);
  const inputRef    = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, isGenImg, isGenGif]);

  // Check server connectivity on mount and periodically
  useEffect(() => {
    const checkServer = async () => {
      try {
        await api.get('/health', { timeout: 3000 });
        setIsServerOnline(true);
      } catch {
        setIsServerOnline(false);
      }
    };

    checkServer();
    const interval = setInterval(checkServer, 5000); // Check every 5 seconds
    return () => clearInterval(interval);
  }, []);

  // Load browser voices (Web Speech API)
  useEffect(() => {
    const load = () => {
      const all = window.speechSynthesis.getVoices();
      const en  = all.filter(v => v.lang.startsWith('en'));
      if (en.length === 0) return; // not ready yet
      setVoices(en);
      // Default: first Microsoft Online voice, else first English voice
      const preferred = en.find(v => v.name.includes('Microsoft') && v.name.includes('Online'))
                     || en.find(v => v.name.includes('Microsoft'))
                     || en[0];
      setCurrentVoice(preferred);
    };
    load();
    window.speechSynthesis.onvoiceschanged = load; // fires when voices finish loading
  }, []);

  const showError = (msg) => setSnack({ open: true, msg, severity: 'error' });
  const showInfo  = (msg) => setSnack({ open: true, msg, severity: 'success' });

  const speakText = (text) => {
    if (!ttsEnabled || !text) return;
    window.speechSynthesis.cancel(); // stop any current speech
    const utt = new SpeechSynthesisUtterance(text);
    if (currentVoice) utt.voice = currentVoice;
    utt.rate   = 1.0;
    utt.pitch  = 1.0;
    utt.volume = 1.0;
    window.speechSynthesis.speak(utt);
  };

  const addMessage = (role, text, image = null, gif = null) => {
    setMessages(prev => [...prev, { role, text, image, gif, time: new Date() }]);
  };

  // ── Avatar ─────────────────────────────────────────────────
  const handleSetAvatar = async () => {
    if (!avatarPrompt.trim()) return showError('Describe your avatar first.');
    setLoadingAvatar(true);
    try {
      const res = await api.post('/setavatar', { prompt: avatarPrompt });
      const imageUrl = res.data.avatar ? res.data.avatar : `${API_BASE}/media/avatar.png`;
      setAvatarSrc(`${imageUrl}?t=${Date.now()}`);
      showInfo('Avatar updated ✨');
      setSidebarOpen(false);
    } catch { showError('Failed to create avatar.'); }
    finally  { setLoadingAvatar(false); }
  };

  // ── Outfit ─────────────────────────────────────────────────
  const handleChangeOutfit = async () => {
    if (!outfit.trim()) return showError('Enter an outfit first.');
    setLoadingOutfit(true);
    try {
      const res = await api.post('/changeoutfit', { outfit });
      const imageUrl = res.data.image ? `${res.data.image}?t=${Date.now()}` : null;
      addMessage('ai', res.data.reply, imageUrl);
      setSidebarOpen(false);
    } catch { showError('Failed to change outfit.'); }
    finally  { setLoadingOutfit(false); }
  };

  // ── Personality ─────────────────────────────────────────────
  const handleChangePersonality = async () => {
    if (!personality.trim()) return showError('Enter a personality.');
    setLoadingPersonality(true);
    try {
      const res = await api.post('/setpersonality', { personality });
      addMessage('ai', res.data.reply);
      setSidebarOpen(false);
    } catch { showError('Failed to set personality.'); }
    finally  { setLoadingPersonality(false); }
  };

  // ── Send message ────────────────────────────────────────────
  const handleSend = async () => {
    const text = message.trim();
    if (!text || loadingChat) return;

    addMessage('user', text);
    setMessage('');
    setLoadingChat(true);

    const willGenGif = isGifRequest(text);
    const willGenImage = isImageRequest(text);
    if (willGenGif)   setIsGenGif(true);
    else if (willGenImage) setIsGenImg(true);
    else              setIsTyping(true);

    try {
      const res = await api.post('/chat', { message: text });
      setIsTyping(false);
      setIsGenImg(false);
      setIsGenGif(false);
      const imageUrl = res.data.image ? `${res.data.image}?t=${Date.now()}` : null;
      const gifUrl = res.data.gif ? `${res.data.gif}?t=${Date.now()}` : null;
      addMessage('ai', res.data.reply, imageUrl, gifUrl);
      speakText(res.data.reply);
    } catch {
      setIsTyping(false);
      setIsGenImg(false);
      setIsGenGif(false);
      showError('Failed to get a reply. Is the server running?');
    } finally {
      setLoadingChat(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputResize = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  // ── Render ──────────────────────────────────────────────────
  return (
    <>
      <style>{css}</style>

      {/* Lightbox */}
      {lightbox && (
        <div className="lightbox" onClick={() => setLightbox(null)}>
          <button className="lightbox-close" onClick={() => setLightbox(null)}>
            <Icon.Close />
          </button>
          <img src={lightbox} alt="Full size" onClick={e => e.stopPropagation()} />
        </div>
      )}

      <div className="wa-shell">

        {/* ── Sidebar overlay (mobile) ────────────────────── */}
        <div
          className={`sidebar-overlay ${sidebarOpen ? 'open' : ''}`}
          onClick={() => setSidebarOpen(false)}
        />

        {/* ── Sidebar ─────────────────────────────────────── */}
        <aside className={`wa-sidebar ${sidebarOpen ? 'open' : ''}`}>

          {/* Header */}
          <div className="wa-sidebar-header">
            <div className="avatar-wrap" onClick={() => fileInputRef.current?.click()}>
              <img className="wa-avatar" src={avatarSrc} alt="avatar"
                onError={e => { e.target.src = `https://ui-avatars.com/api/?name=AI&background=005c4b&color=fff`; }}
              />
              <div className="wa-avatar-edit"><Icon.Camera /></div>
            </div>
            <span className="wa-sidebar-title">AI Friend</span>
          </div>

          <div className="wa-sidebar-body">

            {/* Online status */}
            <div className="status-row">
              <div className="status-dot" style={{background: isServerOnline ? 'var(--accent)' : '#666'}}/>
              <span>{isServerOnline ? 'Online — ready to chat' : 'Offline — server not responding'}</span>
            </div>

            {/* Avatar section */}
            <div className="panel-section">
              <div className="panel-label">
                <span style={{marginRight:6}}>👤</span> Avatar
              </div>
              <textarea
                className="wa-input"
                rows={2}
                placeholder="e.g. young woman with brown hair, green eyes…"
                value={avatarPrompt}
                onChange={e => setAvatarPrompt(e.target.value)}
              />
              <button
                className="wa-btn"
                onClick={handleSetAvatar}
                disabled={loadingAvatar}
              >
                {loadingAvatar
                  ? <><CircularProgress size={14} color="inherit" /> Creating…</>
                  : <><Icon.Camera /> Create Avatar</>
                }
              </button>
            </div>

            {/* Outfit section */}
            <div className="panel-section">
              <div className="panel-label">
                <span style={{marginRight:6}}>👗</span> Outfit
              </div>
              <input
                className="wa-input"
                placeholder="e.g. red summer dress, casual hoodie…"
                value={outfit}
                onChange={e => setOutfit(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleChangeOutfit()}
              />
              <button
                className="wa-btn secondary"
                onClick={handleChangeOutfit}
                disabled={loadingOutfit}
              >
                {loadingOutfit
                  ? <><CircularProgress size={14} color="inherit" /> Changing…</>
                  : <><Icon.Shirt /> Change Outfit</>
                }
              </button>
            </div>

            {/* Personality section */}
            <div className="panel-section">
              <div className="panel-label">
                <span style={{marginRight:6}}>🧠</span> Personality
              </div>
              <input
                className="wa-input"
                placeholder="e.g. shy, bubbly, sarcastic, caring…"
                value={personality}
                onChange={e => setPersonality(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleChangePersonality()}
              />
              <button
                className="wa-btn secondary"
                onClick={handleChangePersonality}
                disabled={loadingPersonality}
              >
                {loadingPersonality
                  ? <><CircularProgress size={14} color="inherit" /> Setting…</>
                  : <><Icon.Brain /> Set Personality</>
                }
              </button>
            </div>

            {/* Voice section */}
            <div className="panel-section">
              <div className="panel-label" style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                <span>🔊 Voice</span>
                <button onClick={() => { setTtsEnabled(e => !e); window.speechSynthesis.cancel(); }}
                  style={{background:'none',border:'none',color: ttsEnabled ? 'var(--accent)' : 'var(--text-secondary)',
                    cursor:'pointer',fontSize:12,fontWeight:600}}>
                  {ttsEnabled ? 'ON' : 'OFF'}
                </button>
              </div>
              <select className="wa-input" value={currentVoice?.name || ''}
                onChange={e => {
                  const v = voices.find(x => x.name === e.target.value);
                  if (v) setCurrentVoice(v);
                }}
                style={{cursor:'pointer'}}
                disabled={!ttsEnabled}
              >
                {voices.map(v => (
                  <option key={v.name} value={v.name}>
                    {v.name.replace('Microsoft ', '').replace(' Online (Natural) - English', '')}
                  </option>
                ))}
              </select>
              {currentVoice && (
                <button className="wa-btn secondary" style={{marginTop:6}}
                  onClick={() => speakText('Hello! This is how I sound.')}>
                  ▶ Test Voice
                </button>
              )}
            </div>

            {/* Tips */}
            <div className="panel-section" style={{fontSize:12, color:'var(--text-secondary)', lineHeight:1.6}}>
              <div className="panel-label">💡 Tips</div>
              Say <em>"show me a photo"</em> or <em>"take a selfie"</em> to generate an image.
              <br/><br/>
              Be descriptive when creating your avatar for best results.
            </div>

          </div>
        </aside>

        {/* ── Chat pane ────────────────────────────────────── */}
        <main className="wa-chat">

          {/* Chat header */}
          <div className="wa-chat-header">
            <button className="menu-btn" onClick={() => setSidebarOpen(o => !o)}>
              {sidebarOpen ? <Icon.Close /> : <Icon.Menu />}
            </button>
            <img
              className="wa-avatar"
              src={avatarSrc}
              alt="avatar"
              onError={e => { e.target.src = `https://ui-avatars.com/api/?name=AI&background=005c4b&color=fff`; }}
            />
            <div className="chat-header-info">
              <div className="chat-header-name">AI Friend</div>
              <div className={`chat-header-status ${(isTyping||isGenImg||isGenGif) ? 'typing' : ''}`}>
                {isGenGif  ? '🎬 Generating GIF…'
                 : isGenImg  ? '🎨 Generating image…'
                 : isTyping ? 'typing…'
                 : 'tap to see profile & settings'}
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="wa-messages">

            {messages.length === 0 && !isTyping && !isGenImg && !isGenGif && (
              <div className="empty-chat">
                <div className="empty-icon">
                  <svg viewBox="0 0 24 24" width="36" height="36" fill="currentColor">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                  </svg>
                </div>
                <span>Say hello to your AI Friend 👋</span>
                <span style={{fontSize:12, opacity:.6}}>Configure your friend in the settings panel</span>
              </div>
            )}

            <div className="date-pill" style={{display: messages.length ? 'block' : 'none'}}>
              Today
            </div>

            {messages.map((msg, i) => {
              const isUser = msg.role === 'user';
              // show gap between consecutive same-sender msgs
              const prevSame = i > 0 && messages[i-1].role === msg.role;
              return (
                <React.Fragment key={i}>
                  {prevSame && <div className="msg-gap" />}
                  <div className={`msg-row ${isUser ? 'user' : 'ai'}`}>
                    <div className="msg-bubble">
                      {msg.text}
                      {msg.gif && (
                        <img
                          className="msg-image"
                          src={msg.gif}
                          alt="animated GIF"
                          onClick={() => setLightbox(msg.gif)}
                          style={{cursor: 'pointer'}}
                        />
                      )}
                      {msg.image && (
                        <img
                          className="msg-image"
                          src={msg.image}
                          alt="generated"
                          onClick={() => setLightbox(msg.image)}
                        />
                      )}
                      <div className="msg-meta">
                        {formatTime(msg.time)}
                        {isUser && <Icon.DoubleCheck />}
                      </div>
                    </div>
                  </div>
                </React.Fragment>
              );
            })}

            {/* Typing indicator */}
            {isTyping && (
              <div className="typing-bubble">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            )}

            {/* Image generation indicator */}
            {isGenImg && (
              <div className="gen-bubble">
                <CircularProgress size={16} style={{color:'var(--accent)'}} />
                Generating image — this takes ~30 sec…
              </div>
            )}

            {/* GIF generation indicator */}
            {isGenGif && (
              <div className="gen-bubble">
                <CircularProgress size={16} style={{color:'var(--accent)'}} />
                Generating GIF — this takes ~60 sec…
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input bar */}
          <div className="wa-input-bar">
            <textarea
              ref={inputRef}
              className="wa-chat-input"
              rows={1}
              placeholder="Message"
              value={message}
              onChange={e => { setMessage(e.target.value); handleInputResize(e); }}
              onKeyDown={handleKeyDown}
              disabled={loadingChat}
            />
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={loadingChat || !message.trim()}
            >
              {loadingChat
                ? <CircularProgress size={18} style={{color:'inherit'}} />
                : <Icon.Send />
              }
            </button>
          </div>

        </main>
      </div>

      {/* Snackbar */}
      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={() => setSnack(s => ({...s, open: false}))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snack.severity} onClose={() => setSnack(s => ({...s, open: false}))}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </>
  );
}
