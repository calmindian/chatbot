import React from 'react';
import { CircularProgress } from '@mui/material';
import { Icon } from './Icons';
import { formatTime } from '../utils/chat';

export default function ConversationScreen(props) {
  const { activeTab,
  chatScreen,
  setChatScreen,
  avatarSrc,
  activeChat,
  isGenGif,
  isGenImg,
  isTyping,
  isServerOnline,
  setSidebarView,
  messages,
  setLightbox,
  genProgress,
  chatEndRef,
  message,
  setMessage,
  inputRef,
  handleInputResize,
  handleKeyDown,
  loadingChat,
  handleSend } = props;

  return (
        <section className={`wa-chat app-chat-screen ${activeTab === 'chats' && chatScreen === 'conversation' ? '' : 'is-hidden'}`}>

          {/* Chat header */}
          <div className="wa-chat-header">
            <button
              className="chat-back-btn"
              onClick={() => setChatScreen('list')}
              aria-label="Back to chats"
            >
              <Icon.Back />
            </button>
            <img
              className="wa-avatar"
              src={avatarSrc}
              alt="avatar"
              onError={e => { e.target.src = `https://ui-avatars.com/api/?name=AI&background=005c4b&color=fff`; }}
            />
            <div className="chat-header-info">
              <div className="chat-header-name">{activeChat.name || 'AI Friend'}</div>
              <div className={`chat-header-status ${(isTyping||isGenImg||isGenGif) ? 'typing' : ''}`}>
                {isGenGif  ? '🎬 Generating GIF… (~20s)'
                 : isGenImg  ? '🎨 Generating image…'
                 : isTyping ? 'typing…'
                   : isServerOnline ? 'Online' : 'Offline'}
              </div>
            </div>
            <button
                className="sidebar-icon-btn chat-settings-btn"
                type="button"
                aria-label="Open chat settings"
                onClick={() => {
                    setSidebarView('chatSettings');
                    setChatScreen('chatSettings');
                }}
            >
                <Icon.Settings />
            </button>
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
                <span className="empty-title">A little space to connect.</span>
                <span className="empty-subtitle">Say hello or share what’s on your mind. Create an avatar in settings to unlock portraits.</span>
                <div className="starter-prompts" aria-label="Conversation starters">
                  {['Hey, how are you?', 'Tell me something fun', 'What can you do?'].map(prompt => (
                    <button
                      className="starter-prompt"
                      key={prompt}
                      type="button"
                      onClick={() => {
                        setMessage(prompt);
                        inputRef.current?.focus();
                      }}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="date-pill" style={{display: messages.length ? 'block' : 'none'}}>
              Today
            </div>

            {messages.map((msg, i) => {
              const isUser = msg.role === 'user';
              const hasImage = msg.image || msg.gif;
              // show gap between consecutive same-sender msgs
              const prevSame = i > 0 && messages[i-1].role === msg.role;
              return (
                <React.Fragment key={i}>
                  {prevSame && <div className="msg-gap" />}
                  <div className={`msg-row ${isUser ? 'user' : 'ai'} ${hasImage ? 'image-msg' : ''}`}>
                    <div className="msg-bubble">
                      {msg.text && <span className="msg-text">{msg.text}</span>}
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
                <div style={{display:'flex',alignItems:'center',gap:12}}>
                  <div style={{position:'relative',width:40,height:40}}>
                    <CircularProgress
                      variant="determinate"
                      value={genProgress}
                      size={40}
                      style={{color:'var(--accent)'}}
                    />
                    <div style={{
                      position:'absolute',
                      top:0,left:0,right:0,bottom:0,
                      display:'flex',alignItems:'center',justifyContent:'center',
                      fontSize:12,fontWeight:600,color:'var(--text-primary)'
                    }}>
                      {genProgress}%
                    </div>
                  </div>
                  <span>Generating image…</span>
                </div>
              </div>
            )}

            {/* GIF generation indicator */}
            {isGenGif && (
              <div className="gen-bubble">
                <div style={{display:'flex',alignItems:'center',gap:12}}>
                  <div style={{position:'relative',width:40,height:40}}>
                    <CircularProgress
                      variant="determinate"
                      value={genProgress}
                      size={40}
                      style={{color:'var(--accent)'}}
                    />
                    <div style={{
                      position:'absolute',
                      top:0,left:0,right:0,bottom:0,
                      display:'flex',alignItems:'center',justifyContent:'center',
                      fontSize:12,fontWeight:600,color:'var(--text-primary)'
                    }}>
                      {genProgress}%
                    </div>
                  </div>
                  <span>Generating GIF…</span>
                </div>
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

        </section>
  );
}
