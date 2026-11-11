import React, { useState, useRef, useEffect } from 'react';
import { Snackbar, Alert } from '@mui/material';
import { API_BASE, api } from './services/http';
import {
  SERVER_DATA_VERSION_KEY, activeChatKey, chatListKey, clearAppCaches,
  clearAppStorage, createId, getDeviceState,
} from './services/deviceStorage';
import { Icon } from './components/Icons';
import { isGifRequest, isImageRequest } from './utils/chat';
import './styles/App.css';
import PrimaryScreen from './components/PrimaryScreen';
import ConversationScreen from './components/ConversationScreen';

// ── COMPONENT ─────────────────────────────────────────────────────────────────
export default function App({ onLogout }) {
  const [sidebarView, setSidebarView] = useState('chats');
  const [activeTab, setActiveTab] = useState('chats');
  const [chatScreen, setChatScreen] = useState('list');
  const [deviceState, setDeviceState] = useState(getDeviceState);
  const { deviceId, chats, activeChatId } = deviceState;
  const activeChat = chats.find(chat => chat.id === activeChatId) || chats[0];
  const sessionId = activeChat.sessionId;

  // settings fields
  const [avatarPrompt, setAvatarPrompt] = useState('');
  const [personality,  setPersonality]  = useState('friendly');
  const [avatarSrc,    setAvatarSrc]    = useState(`${API_BASE}/media/avatars/${sessionId}.png?t=${Date.now()}`);

  // loading per action
  const [loadingAvatar,      setLoadingAvatar]      = useState(false);
  const [uploadingAvatar,    setUploadingAvatar]    = useState(false);
  const [loadingPersonality, setLoadingPersonality]  = useState(false);
  const [loadingChat,        setLoadingChat]         = useState(false);
  const [loadingReset,       setLoadingReset]        = useState(false);

  // chat
  const [messages,  setMessages]  = useState([]);
  const [message,   setMessage]   = useState('');
  const [isTyping,  setIsTyping]  = useState(false);
  const [isGenImg,  setIsGenImg]  = useState(false);
  const [isGenGif,  setIsGenGif]  = useState(false);
  const [genProgress, setGenProgress] = useState(0);  // 0-100

  // lightbox
  const [lightbox, setLightbox] = useState(null);

  // snackbar
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'error' });

  // server status
  const [isServerOnline, setIsServerOnline] = useState(false);
  const [collection, setCollection] = useState([]);
  const [loadingCollection, setLoadingCollection] = useState(false);
  const [collectionRefreshNonce, setCollectionRefreshNonce] = useState(0);

  // voice (Web Speech API — fully offline, no backend needed)
  const [voices,       setVoices]       = useState([]);
  const [currentVoice, setCurrentVoice] = useState(null); // SpeechSynthesisVoice object
  const [ttsEnabled,   setTtsEnabled]   = useState(true);

  const chatEndRef  = useRef(null);
  const inputRef    = useRef(null);
  const fileInputRef = useRef(null);
  const conversationSnapshotRef = useRef(null);
  const conversationSyncInFlight = useRef(false);
  const conversationSyncFailed = useRef(false);
  const activeSessionIdRef = useRef(sessionId);
  activeSessionIdRef.current = sessionId;

  const resetLocalConversationState = async (version, broadcast = true) => {
    if (broadcast && window.localStorage.getItem(SERVER_DATA_VERSION_KEY) === version) return true;
    let cacheCleared = true;
    clearAppStorage();
    window.localStorage.setItem(SERVER_DATA_VERSION_KEY, version);
    const nextState = getDeviceState();
    setDeviceState(nextState);
    setMessages([]);
    setMessage('');
    setAvatarPrompt('');
    setPersonality('friendly');
    setAvatarSrc(`${API_BASE}/media/avatars/${nextState.chats[0].sessionId}.png?t=${Date.now()}`);
    setLoadingAvatar(false);
    setUploadingAvatar(false);
    setLoadingPersonality(false);
    setLoadingChat(false);
    setLoadingReset(false);
    setIsTyping(false);
    setIsGenImg(false);
    setIsGenGif(false);
    setGenProgress(0);
    setActiveTab('chats');
    setChatScreen('list');
    setSidebarView('chats');
    setCollection([]);
    if (broadcast) {
      window.localStorage.setItem('ai-friend-reset-event', String(Date.now()));
    }
    try {
      await clearAppCaches();
    } catch (error) {
      console.error('Could not clear the app cache:', error);
      setSnack({ open: true, msg: 'Chat data was deleted, but some browser cache could not be cleared.', severity: 'warning' });
      cacheCleared = false;
    }
    return cacheCleared;
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, isGenImg, isGenGif, genProgress]);

  useEffect(() => {
    let active = true;
    conversationSnapshotRef.current = null;
    const syncConversation = async () => {
      if (!active || document.hidden || conversationSyncInFlight.current) return;
      conversationSyncInFlight.current = true;
      try {
        const res = await api.get('/conversation', { params: { session_id: sessionId } });
        if (!active) return;
        conversationSyncFailed.current = false;
        const data = res.data;
        const snapshot = JSON.stringify(data);
        if (snapshot !== conversationSnapshotRef.current) {
          conversationSnapshotRef.current = snapshot;
          setMessages((data.messages || []).map(item => ({
            ...item,
            time: new Date(item.time),
          })));
          setAvatarPrompt(data.avatar_prompt || '');
          setPersonality(data.personality || 'friendly');
          setAvatarSrc(data.avatar_url || `${API_BASE}/media/avatars/${sessionId}.png`);
        }
      } catch (error) {
        if (active && !conversationSyncFailed.current) {
          console.error('Conversation sync failed:', error);
          conversationSyncFailed.current = true;
        }
      } finally {
        conversationSyncInFlight.current = false;
      }
    };

    const syncWhenVisible = () => {
      if (!document.hidden) syncConversation();
    };

    syncConversation();
    const interval = setInterval(syncWhenVisible, 3000);
    document.addEventListener('visibilitychange', syncWhenVisible);
    window.addEventListener('focus', syncWhenVisible);
    window.addEventListener('pageshow', syncWhenVisible);
    return () => {
      active = false;
      clearInterval(interval);
      document.removeEventListener('visibilitychange', syncWhenVisible);
      window.removeEventListener('focus', syncWhenVisible);
      window.removeEventListener('pageshow', syncWhenVisible);
    };
  }, [sessionId]);

  useEffect(() => {
    const handleStorage = event => {
      if (event.key === 'ai-friend-reset-event') {
        resetLocalConversationState(
          window.localStorage.getItem(SERVER_DATA_VERSION_KEY) || '',
          false
        );
        return;
      }
      if (event.key === chatListKey(deviceId) || event.key === activeChatKey(deviceId)) {
        setDeviceState(getDeviceState());
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [deviceId]);

  useEffect(() => {
    if (activeTab !== 'collection') return undefined;
    let active = true;
    setLoadingCollection(true);
    api.get('/collection')
      .then(response => {
        if (active) setCollection(response.data.items || []);
      })
      .catch(error => {
        if (active) {
          console.error('Could not load image collection:', error);
          showError('Could not load the image collection.');
        }
      })
      .finally(() => {
        if (active) setLoadingCollection(false);
      });
    return () => { active = false; };
  }, [activeTab, collectionRefreshNonce]);

  // Check server connectivity on mount and periodically.
  // Uses native fetch + AbortController instead of axios — axios timeout is
  // unreliable in browsers for connection-refused errors and can hang silently.
  // fetch throws a TypeError immediately when the server is not running.
  useEffect(() => {
    const checkServer = async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3000); // hard 3s timeout
      try {
        const res = await fetch(`${API_BASE}/health?t=${Date.now()}`, {
          signal: controller.signal,
          cache: 'no-store',
          credentials: 'include',
        });
        clearTimeout(timer);
        setIsServerOnline(res.ok);
        if (res.ok) {
          const health = await res.json();
          const serverVersion = health.server_data_version;
          if (typeof serverVersion === 'string' && serverVersion) {
            const localVersion = window.localStorage.getItem(SERVER_DATA_VERSION_KEY);
            if (localVersion && localVersion !== serverVersion) {
              const cacheCleared = await resetLocalConversationState(serverVersion);
              if (cacheCleared) {
                setSnack({ open: true, msg: 'Server data was deleted. This device’s chat cache was cleared.', severity: 'success' });
              }
            } else if (!localVersion) {
              window.localStorage.setItem(SERVER_DATA_VERSION_KEY, serverVersion);
            }
          }
        }
      } catch {
        clearTimeout(timer);
        setIsServerOnline(false);
      }
    };

    checkServer();
    const interval = setInterval(checkServer, 5000);
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

  const startProgressPolling = (requestId, expectedSessionId) => {
    let timeoutId;
    let stopped = false;
    let loggedError = false;

    const poll = async () => {
      try {
        const response = await api.get(`/progress/${requestId}`);
        if (stopped) return;
        const progress = Number(response.data.progress) || 0;
        if (activeSessionIdRef.current === expectedSessionId) setGenProgress(progress);
        if (progress >= 100) return;
      } catch (error) {
        if (!loggedError) {
          console.error('Progress polling failed:', error);
          loggedError = true;
        }
      }
      if (!stopped) timeoutId = setTimeout(poll, 250);
    };

    timeoutId = setTimeout(poll, 0);
    return () => {
      stopped = true;
      clearTimeout(timeoutId);
    };
  };

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

  const saveDeviceState = (nextState) => {
    window.localStorage.setItem(chatListKey(deviceId), JSON.stringify(nextState.chats));
    window.localStorage.setItem(activeChatKey(deviceId), nextState.activeChatId);
    setDeviceState(nextState);
  };

  const handleNewChat = () => {
    const id = createId();
    const nextChat = {
      id,
      sessionId: `device-${deviceId}-chat-${id}`,
      name: `Chat ${chats.length + 1}`,
    };
    saveDeviceState({
      deviceId,
      chats: [nextChat, ...chats],
      activeChatId: id,
    });
    setMessages([]);
    setMessage('');
    setAvatarPrompt('');
    setPersonality('friendly');
    setAvatarSrc(`${API_BASE}/media/avatars/${nextChat.sessionId}.png?t=${Date.now()}`);
    setLoadingChat(false);
    setLoadingAvatar(false);
    setUploadingAvatar(false);
    setLoadingPersonality(false);
    setIsTyping(false);
    setIsGenImg(false);
    setIsGenGif(false);
    setGenProgress(0);
    setLoadingReset(false);
    setSidebarView('chats');
  };

  const handleSelectChat = (chat) => {
    if (chat.id === activeChatId) {
      setActiveTab('chats');
      setChatScreen('conversation');
      return;
    }
    window.localStorage.setItem(activeChatKey(deviceId), chat.id);
    setDeviceState({ ...deviceState, activeChatId: chat.id });
    setMessages([]);
    setMessage('');
    setAvatarPrompt('');
    setPersonality('friendly');
    setAvatarSrc(`${API_BASE}/media/avatars/${chat.sessionId}.png?t=${Date.now()}`);
    setLoadingChat(false);
    setLoadingAvatar(false);
    setUploadingAvatar(false);
    setLoadingPersonality(false);
    setIsTyping(false);
    setIsGenImg(false);
    setIsGenGif(false);
    setGenProgress(0);
    setLoadingReset(false);
    setActiveTab('chats');
    setChatScreen('conversation');
    setSidebarView('chats');
  };

  const handleRenameChat = (name) => {
    const nextChats = chats.map(chat =>
      chat.id === activeChatId ? { ...chat, name } : chat
    );
    saveDeviceState({ ...deviceState, chats: nextChats });
  };

  // ── Avatar ─────────────────────────────────────────────────
  const handleSetAvatar = async () => {
    if (!avatarPrompt.trim()) return showError('Describe your avatar first.');
    setLoadingAvatar(true);
    try {
      const res = await api.post('/setavatar', { prompt: avatarPrompt, session_id: sessionId });
      if (activeSessionIdRef.current !== sessionId) return;
      const imageUrl = res.data.avatar ? res.data.avatar : `${API_BASE}/media/avatars/${sessionId}.png`;
      setAvatarSrc(`${imageUrl}?t=${Date.now()}`);
      if (typeof res.data.avatar_prompt === 'string') setAvatarPrompt(res.data.avatar_prompt);

      showInfo('Avatar updated ✨');
      setChatScreen('conversation');
    } catch {
      if (activeSessionIdRef.current === sessionId) showError('Failed to create avatar.');
    }
    finally  {
      if (activeSessionIdRef.current === sessionId) setLoadingAvatar(false);
    }
  };

  const handleUploadAvatar = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const supportedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!supportedTypes.includes(file.type)) {
      showError('Choose a JPEG, PNG, or WebP picture.');
      event.target.value = '';
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showError('Choose a picture that is 10 MB or smaller.');
      event.target.value = '';
      return;
    }

    setUploadingAvatar(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    formData.append('avatar_prompt', avatarPrompt);
    try {
      const res = await api.post('/uploadavatar', formData);
      if (activeSessionIdRef.current !== sessionId) return;
      setAvatarSrc(`${res.data.avatar}?t=${Date.now()}`);
      if (typeof res.data.avatar_prompt === 'string') setAvatarPrompt(res.data.avatar_prompt);
      showInfo('Your picture is now the avatar ✨');
      setChatScreen('conversation');
    } catch (error) {
      if (activeSessionIdRef.current === sessionId) {
        showError(error.response?.data?.detail || 'Could not upload this picture.');
      }
    } finally {
      if (activeSessionIdRef.current === sessionId) setUploadingAvatar(false);
      event.target.value = '';
    }
  };

  // ── Personality ─────────────────────────────────────────────
  const handleChangePersonality = async () => {
    if (!personality.trim()) return showError('Enter a personality.');
    setLoadingPersonality(true);
    try {
      const res = await api.post('/setpersonality', { personality, session_id: sessionId });
      if (activeSessionIdRef.current !== sessionId) return;
      addMessage('ai', res.data.reply);
      setChatScreen('conversation');
    } catch {
      if (activeSessionIdRef.current === sessionId) showError('Failed to set personality.');
    }
    finally  {
      if (activeSessionIdRef.current === sessionId) setLoadingPersonality(false);
    }
  };

  // ── Reset all data ──────────────────────────────────────────
  const handleReset = async () => {
    if (!window.confirm('Delete all chats, avatars, settings, and generated media from the server? This affects every device connected to this server and cannot be undone. Downloaded AI models will be kept.')) return;
    setLoadingReset(true);
    try {
      const response = await api.post('/delete-all-data');
      const version = response.data.server_data_version;
      if (typeof version !== 'string' || !version) {
        throw new Error('The server did not return the new data version.');
      }
      const cacheCleared = await resetLocalConversationState(version);
      if (cacheCleared) showInfo('All server data and this browser’s chat cache were deleted.');
    } catch {
      showError('Delete failed. The server may not have removed all data.');
    }
    finally { setLoadingReset(false); }
  };
  const handleSend = async () => {
    const text = message.trim();
    if (!text || loadingChat) return;

    addMessage('user', text);
    setMessage('');
    setLoadingChat(true);

    const willGenGif = isGifRequest(text);
    const willGenImage = isImageRequest(text);
    const requestId = willGenGif || willGenImage ? createId() : null;
    const stopProgressPolling = requestId
      ? startProgressPolling(requestId, sessionId)
      : () => {};
    if (willGenGif)   setIsGenGif(true);
    else if (willGenImage) setIsGenImg(true);
    else              setIsTyping(true);

    try {
      const res = await api.post('/chat', {
        message: text,
        session_id: sessionId,
        request_id: requestId,
      });
      if (activeSessionIdRef.current !== sessionId) return;
      setIsTyping(false);
      setIsGenImg(false);
      setIsGenGif(false);
      const imageUrl = res.data.image ? `${res.data.image}?t=${Date.now()}` : null;
      const gifUrl = res.data.gif ? `${res.data.gif}?t=${Date.now()}` : null;
      addMessage('ai', res.data.reply, imageUrl, gifUrl);
      speakText(res.data.reply);
    } catch (error) {
      if (activeSessionIdRef.current !== sessionId) return;
      setIsTyping(false);
      setIsGenImg(false);
      setIsGenGif(false);
      showError(error.response?.data?.detail || 'Failed to get a reply. Is the server running?');
    } finally {
      stopProgressPolling();
      if (activeSessionIdRef.current === sessionId) {
        setLoadingChat(false);
        setGenProgress(0);
        inputRef.current?.focus();
      }
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
      {/* Lightbox */}
      {lightbox && (
        <div className="lightbox" onClick={() => setLightbox(null)}>
          <button className="lightbox-close" onClick={() => setLightbox(null)}>
            <Icon.Close />
          </button>
          <img src={lightbox} alt="Full size" onClick={e => e.stopPropagation()} />
        </div>
      )}

      <div className="wa-shell app-shell">
        <PrimaryScreen
          {...{
            activeTab, chatScreen, setChatScreen, setCollectionRefreshNonce,
            chats, activeChatId, handleSelectChat, API_BASE,
            loadingCollection, collection, setLightbox, sidebarView, activeChat,
            handleRenameChat, avatarPrompt, setAvatarPrompt, fileInputRef,
            handleUploadAvatar, uploadingAvatar, loadingAvatar, handleSetAvatar,
            personality, setPersonality, handleChangePersonality, loadingPersonality,
            isServerOnline, voices, currentVoice, setCurrentVoice, ttsEnabled,
            setTtsEnabled, speakText, loadingReset, handleReset, handleNewChat,
            setActiveTab, setSidebarView,
            onLogout,
          }}
        />
        <ConversationScreen
          {...{
            activeTab, chatScreen, setChatScreen, avatarSrc, activeChat, isGenGif,
            isGenImg, isTyping, isServerOnline, setSidebarView, messages,
            setLightbox, genProgress, chatEndRef, message, setMessage, inputRef,
            handleInputResize, handleKeyDown, loadingChat, handleSend,
          }}
        />
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
