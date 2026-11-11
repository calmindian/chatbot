export const DEVICE_ID_KEY = 'ai-friend-device-id';
export const LEGACY_SESSION_KEY = 'ai-friend-session-id';
export const SERVER_DATA_VERSION_KEY = 'ai-friend-server-data-version';
export const chatListKey = deviceId => `ai-friend-chats:${deviceId}`;
export const activeChatKey = deviceId => `ai-friend-active-chat:${deviceId}`;

export function clearAppStorage() {
  for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
    const key = window.localStorage.key(index);
    if (key?.startsWith('ai-friend-')) window.localStorage.removeItem(key);
  }
  for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = window.sessionStorage.key(index);
    if (key?.startsWith('ai-friend-')) window.sessionStorage.removeItem(key);
  }
}

export async function clearAppCaches() {
  if (!('caches' in window)) return;
  const cacheNames = await window.caches.keys();
  await Promise.all(cacheNames
    .filter(name => name.startsWith('ai-friend-'))
    .map(name => window.caches.delete(name)));
}

export function createId() {
  return window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function getDeviceId() {
  let deviceId = window.localStorage.getItem(DEVICE_ID_KEY);
  if (!deviceId) {
    deviceId = createId();
    window.localStorage.setItem(DEVICE_ID_KEY, deviceId);
  }
  return deviceId;
}

export function getDeviceState() {
  const deviceId = getDeviceId();
  const chatsStorageKey = chatListKey(deviceId);
  let chats = [];
  try {
    chats = JSON.parse(window.localStorage.getItem(chatsStorageKey) || '[]');
  } catch (error) {
    console.error('Could not read saved chat list:', error);
    window.localStorage.removeItem(chatsStorageKey);
  }
  chats = Array.isArray(chats)
    ? chats.filter(chat => chat && typeof chat.id === 'string' && typeof chat.sessionId === 'string')
    : [];
  chats = chats.map((chat, index) => ({
    ...chat,
    name: typeof chat.name === 'string' ? chat.name : `Chat ${index + 1}`,
  }));
  if (!Array.isArray(chats) || chats.length === 0) {
    const legacySessionId = window.sessionStorage.getItem(LEGACY_SESSION_KEY);
    const chatId = createId();
    chats = [{
      id: chatId,
      sessionId: legacySessionId || `device-${deviceId}-chat-${chatId}`,
      name: 'Chat 1',
    }];
    window.localStorage.setItem(chatsStorageKey, JSON.stringify(chats));
  }
  const storedActiveId = window.localStorage.getItem(activeChatKey(deviceId));
  const activeChatId = chats.some(chat => chat.id === storedActiveId) ? storedActiveId : chats[0].id;
  window.localStorage.setItem(activeChatKey(deviceId), activeChatId);
  return { deviceId, chats, activeChatId };
}
