import React from 'react';
import { CircularProgress } from '@mui/material';
import { Icon } from './Icons';

export default function PrimaryScreen(props) {
  const { activeTab,
  chatScreen,
  setChatScreen,
  setCollectionRefreshNonce,
  chats,
  activeChatId,
  handleSelectChat,
  API_BASE,
  loadingCollection,
  collection,
  setLightbox,
  sidebarView,
  activeChat,
  handleRenameChat,
  avatarPrompt,
  setAvatarPrompt,
  fileInputRef,
  handleUploadAvatar,
  uploadingAvatar,
  loadingAvatar,
  handleSetAvatar,
  personality,
  setPersonality,
  handleChangePersonality,
  loadingPersonality,
  isServerOnline,
  voices,
  currentVoice,
  setCurrentVoice,
  ttsEnabled,
  setTtsEnabled,
  speakText,
  loadingReset,
  handleReset,
  handleNewChat,
  setActiveTab,
  setSidebarView,
  onLogout } = props;

  return (
        <main className={`app-primary ${activeTab === 'chats' && chatScreen === 'conversation' ? 'is-hidden' : ''}`}>
          <header className="app-primary-header">
            {(activeTab === 'chats' && chatScreen === 'chatSettings') && (
              <button className="chat-back-btn" type="button" aria-label="Back to chat" onClick={() => setChatScreen('conversation')}>
                <Icon.Back />
              </button>
            )}
            <div className="app-primary-heading">
              <span className="app-primary-eyebrow"><span className="eyebrow-spark" /> AI FRIEND <span className="eyebrow-divider">/</span> YOUR COMPANION SPACE</span>
              <h1 className="app-primary-title">
                {activeTab === 'chats'
                  ? chatScreen === 'chatSettings' ? 'Chat settings' : 'Chats'
                  : activeTab === 'collection' ? 'Collection' : 'Settings'}
              </h1>
            </div>
            {activeTab === 'collection' && (
              <button className="collection-refresh" type="button" aria-label="Refresh collection" onClick={() => setCollectionRefreshNonce(value => value + 1)}>↻</button>
            )}
          </header>

          <div className="app-primary-body">
            {activeTab === 'chats' && chatScreen === 'list' ? (
              <>
                <section className="chat-home-hero" aria-label="Your companion space">
                  <div className="hero-orbit hero-orbit-one" aria-hidden="true" />
                  <div className="hero-orbit hero-orbit-two" aria-hidden="true" />
                  <div className="hero-kicker"><span className="hero-live-dot" /> YOUR COMPANION SPACE</div>
                  <h2>Every chat starts a story.</h2>
                  <p>Pick a companion and pick up right where you left off.</p>
                  <div className="hero-footer">
                    <span className="hero-persona-count"><strong>{String(chats.length).padStart(2, '0')}</strong> {chats.length === 1 ? 'PERSONA' : 'PERSONAS'}</span>
                    <span className="hero-footer-divider" />
                    <span className="hero-footer-note">READY WHEN YOU ARE</span>
                  </div>
                </section>
                <div className="chat-list-heading">
                  <span>Your conversations</span>
                  <span className="chat-list-count">{chats.length}</span>
                </div>
                <div className="chat-list" aria-label="Your chats">
                  {chats.map(chat => (
                    <button
                      className={`chat-list-item ${chat.id === activeChatId ? 'active' : ''}`}
                      type="button"
                      key={chat.id}
                      aria-current={chat.id === activeChatId ? 'page' : undefined}
                      onClick={() => handleSelectChat(chat)}
                    >
                      <span className="chat-list-avatar" aria-hidden="true">
                        {(chat.name || 'Chat').trim().slice(0, 1).toUpperCase()}
                        <img
                          src={`${API_BASE}/media/avatars/${chat.sessionId}.png`}
                          alt=""
                          onError={event => { event.currentTarget.style.display = 'none'; }}
                        />
                      </span>
                      <span className="chat-list-item-copy">
                        <span className="chat-list-item-name">{chat.name || 'Untitled chat'}</span>
                        <span className="chat-list-item-caption">Your companion is ready</span>
                      </span>
                      <span className="chat-list-arrow" aria-hidden="true">↗</span>
                    </button>
                  ))}
                </div>
              </>
            ) : activeTab === 'collection' ? (
              loadingCollection ? (
                <div className="collection-empty"><CircularProgress size={28} /></div>
              ) : collection.length ? (
                <div className="collection-grid" aria-label="All generated images">
                  {collection.map((item, index) => (
                    <button className="collection-item" key={`${item.url}-${index}`} type="button" onClick={() => setLightbox(item.url)}>
                      <img src={item.url} alt={`${item.kind} from ${new Date(item.created_at).toLocaleDateString()}`} loading="lazy" />
                      <span className="collection-badge">{item.kind}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="collection-empty">No images yet. Images and avatars you create will appear here.</div>
              )
            ) : (
              <>
                {sidebarView === 'chatSettings' && (
                  <>
                    <div className="panel-section">
                      <div className="panel-label">Chat name</div>
                      <input
                        id="chat-persona-name"
                        className="wa-input"
                        aria-label="Current chat name"
                        maxLength={40}
                        value={activeChat.name}
                        onChange={event => handleRenameChat(event.target.value)}
                      />
                    </div>

            {/* Avatar section */}
            <div className="panel-section">
              <div className="panel-label">
                <span style={{marginRight:6}}>👤</span> Avatar
              </div>
              <textarea
                className="wa-input"
                rows={2}
                placeholder="Describe your avatar…"
                value={avatarPrompt}
                onChange={e => setAvatarPrompt(e.target.value)}
              />
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleUploadAvatar}
                style={{display: 'none'}}
                aria-label="Choose an avatar picture"
              />
              <button
                className="wa-btn secondary"
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingAvatar || loadingAvatar}
              >
                {uploadingAvatar
                  ? <><CircularProgress size={14} color="inherit" /> Uploading…</>
                  : <><Icon.Image /> Upload a picture</>
                }
              </button>
              <div className="avatar-help">JPEG, PNG, or WebP · up to 10 MB. Your picture is the visual reference. Ask for outfits or scenes directly in chat; the optional description guides chat text only.</div>
              <button
                className="wa-btn"
                onClick={handleSetAvatar}
                disabled={loadingAvatar || uploadingAvatar}
              >
                {loadingAvatar
                  ? <><CircularProgress size={14} color="inherit" /> Creating…</>
                  : <><Icon.Camera /> Create Avatar</>
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
                placeholder="Describe a personality…"
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

                  </>
                )}

                {sidebarView === 'globalSettings' && (
                  <>
                    <div className="status-row">
                      <div className="status-dot" style={{background: isServerOnline ? 'var(--accent)' : '#666'}}/>
                      <span>{isServerOnline ? 'Server connected' : 'Server offline'}</span>
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

            {/* Reset section */}
            <div className="panel-section">
              <div className="panel-label">⚠️ Danger Zone</div>
              <button
                className="wa-btn"
                onClick={handleReset}
                disabled={loadingReset}
                style={{background:'#c0392b'}}
              >
                {loadingReset
                  ? <><CircularProgress size={14} color="inherit" /> Clearing…</>
                  : <>🗑️ Delete All Data</>
                }
              </button>
              <div style={{fontSize:11, color:'var(--text-secondary)', marginTop:6, lineHeight:1.5}}>
                Deletes all chats, settings, avatars, and generated media from the server and this browser.
              </div>
              <button className="wa-btn secondary" type="button" onClick={onLogout} style={{marginTop:12}}>
                Sign out
              </button>
            </div>

                  </>
                )}
              </>
            )}
          </div>
          {!(activeTab === 'chats' && chatScreen !== 'list') && (
            <nav className="bottom-tabs" aria-label="Main navigation">
              <button className={`bottom-tab ${activeTab === 'chats' ? 'active' : ''}`} type="button" onClick={() => { setActiveTab('chats'); setChatScreen('list'); }} aria-current={activeTab === 'chats' ? 'page' : undefined}>
                <Icon.Chats />Chats
              </button>
              <button className={`bottom-tab ${activeTab === 'collection' ? 'active' : ''}`} type="button" onClick={() => setActiveTab('collection')} aria-current={activeTab === 'collection' ? 'page' : undefined}>
                <Icon.Gallery />Collection
              </button>
              <button className={`bottom-tab ${activeTab === 'settings' ? 'active' : ''}`} type="button" onClick={() => { setSidebarView('globalSettings'); setActiveTab('settings'); }} aria-current={activeTab === 'settings' ? 'page' : undefined}>
                <Icon.Settings />Settings
              </button>
            </nav>
          )}
          {activeTab === 'chats' && chatScreen === 'list' && (
            <button className="new-chat-fab" type="button" onClick={handleNewChat} aria-label="New chat">＋</button>
          )}
        </main>
  );
}
