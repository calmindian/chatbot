import { render, screen } from '@testing-library/react';
import PrimaryScreen from './PrimaryScreen';

test('renders chats and the primary navigation', () => {
  render(
    <PrimaryScreen
      activeTab="chats"
      chatScreen="list"
      chats={[{ id: 'chat-1', sessionId: 'session-1', name: 'Chat 1' }]}
      activeChatId="chat-1"
      handleSelectChat={jest.fn()}
      API_BASE=""
      setCollectionRefreshNonce={jest.fn()}
      loadingCollection={false}
      collection={[]}
      setLightbox={jest.fn()}
      sidebarView="globalSettings"
      handleNewChat={jest.fn()}
      setActiveTab={jest.fn()}
      setSidebarView={jest.fn()}
    />
  );

  expect(screen.getByRole('heading', { name: 'Chats' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Chat 1 Your companion is ready' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'New chat' })).toBeInTheDocument();
  expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
});

test('chat settings do not expose a separate outfit control', () => {
  render(
    <PrimaryScreen
      activeTab="chats"
      chatScreen="chatSettings"
      setChatScreen={jest.fn()}
      chats={[{ id: 'chat-1', sessionId: 'session-1', name: 'Chat 1' }]}
      activeChatId="chat-1"
      activeChat={{ id: 'chat-1', sessionId: 'session-1', name: 'Chat 1' }}
      sidebarView="chatSettings"
      handleRenameChat={jest.fn()}
      avatarPrompt=""
      setAvatarPrompt={jest.fn()}
      fileInputRef={{ current: null }}
      handleUploadAvatar={jest.fn()}
      uploadingAvatar={false}
      loadingAvatar={false}
      handleSetAvatar={jest.fn()}
      personality="friendly"
      setPersonality={jest.fn()}
      handleChangePersonality={jest.fn()}
      loadingPersonality={false}
      setActiveTab={jest.fn()}
      setSidebarView={jest.fn()}
    />
  );

  expect(screen.queryByPlaceholderText(/outfit/i)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /change outfit/i })).not.toBeInTheDocument();
});
