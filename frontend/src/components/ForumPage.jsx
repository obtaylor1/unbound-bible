import { useState, useEffect, useCallback } from 'react'
import './ForumPage.css'

const FORUM_BASE = '/api/forum'
const CATEGORIES = ['All', 'Historical Context', 'Geography', 'Translation', 'Archaeology', 'Theology']

const MOCK_POSTS = [
  {
    id: 'mock-1',
    title: '[Historical Context] Historical Context of the Book of Daniel',
    content: "I've been studying the historical context of Daniel and its prophecies. What are your thoughts on the dating controversy? The traditional view places it in the 6th century BC, but some scholars argue for a 2nd century BC composition. How does this affect our interpretation of the prophetic elements?",
    author: { username: 'Dr. Sarah Johnson', full_name: 'Dr. Sarah Johnson' },
    created_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    likes: 12, comments_count: 8, isMock: true
  },
  {
    id: 'mock-2',
    title: '[Geography] Geographic Accuracy in Luke\'s Gospel',
    content: "Luke demonstrates remarkable geographic accuracy in his Gospel and Acts. Has anyone compiled a comprehensive list of the locations mentioned and their archaeological verification? This could be valuable for apologetics and historical study.",
    author: { username: 'Prof. Michael Chen', full_name: 'Prof. Michael Chen' },
    created_at: new Date(Date.now() - 5 * 3600000).toISOString(),
    likes: 18, comments_count: 15, isMock: true
  },
  {
    id: 'mock-3',
    title: '[Translation] Translation Challenges in Isaiah 7:14',
    content: "The Hebrew word 'almah' in Isaiah 7:14 has been a subject of much debate. How should we approach this translation challenge, and what are the implications for different interpretations? Looking for scholarly perspectives on the Hebrew linguistic evidence.",
    author: { username: 'Rabbi David Goldstein', full_name: 'Rabbi David Goldstein' },
    created_at: new Date(Date.now() - 24 * 3600000).toISOString(),
    likes: 25, comments_count: 22, isMock: true
  },
  {
    id: 'mock-4',
    title: '[Archaeology] Archaeological Evidence for Solomon\'s Temple',
    content: "What archaeological evidence do we have for the First Temple period? I'm particularly interested in recent discoveries that might shed light on the scale and architecture of Solomon's Temple as described in 1 Kings and 2 Chronicles.",
    author: { username: 'Dr. Elizabeth Carter', full_name: 'Dr. Elizabeth Carter' },
    created_at: new Date(Date.now() - 48 * 3600000).toISOString(),
    likes: 20, comments_count: 12, isMock: true
  }
]

function parseCategory(title) {
  const match = title.match(/^\[([^\]]+)\]\s*/)
  if (match) {
    return { category: match[1], cleanTitle: title.slice(match[0].length) }
  }
  return { category: 'General', cleanTitle: title }
}

function timeAgo(dateStr) {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = Math.floor((now - then) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)} days ago`
  return new Date(dateStr).toLocaleDateString()
}

function getInitials(name) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

function AuthModal({ mode, onClose, onSuccess }) {
  const [formMode, setFormMode] = useState(mode)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (formMode === 'register') {
        const res = await fetch(`${FORUM_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, username, full_name: fullName, password })
        })
        const data = await res.json()
        if (!res.ok) {
          const msg = data.detail
          if (Array.isArray(msg)) setError(msg.map(e => e.msg).join('. '))
          else setError(msg || 'Registration failed')
          return
        }
        setFormMode('login')
        setError('')
        setPassword('')
      } else {
        const res = await fetch(`${FORUM_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        })
        const data = await res.json()
        if (!res.ok) {
          setError(data.detail || 'Login failed')
          return
        }
        localStorage.setItem('forum_token', data.access_token)
        const meRes = await fetch(`${FORUM_BASE}/auth/me`, {
          headers: { 'Authorization': `Bearer ${data.access_token}` }
        })
        const me = await meRes.json()
        onSuccess(me, data.access_token)
      }
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        <div className="auth-tabs">
          <button className={formMode === 'login' ? 'active' : ''} onClick={() => { setFormMode('login'); setError('') }}>Sign In</button>
          <button className={formMode === 'register' ? 'active' : ''} onClick={() => { setFormMode('register'); setError('') }}>Join</button>
        </div>
        <h2>{formMode === 'login' ? 'Welcome back, Scholar' : 'Join the Conversation'}</h2>
        <form onSubmit={handleSubmit}>
          {formMode === 'register' && (
            <>
              <input type="text" placeholder="Full Name" value={fullName} onChange={e => setFullName(e.target.value)} required />
              <input type="text" placeholder="Username (letters, numbers, _ -)" value={username} onChange={e => setUsername(e.target.value)} required />
            </>
          )}
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
          <input type="password" placeholder={formMode === 'register' ? 'Password (12+ chars, A-Z, 0-9, symbol)' : 'Password'} value={password} onChange={e => setPassword(e.target.value)} required />
          {error && <div className="auth-error">{error}</div>}
          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Please wait…' : formMode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
        {formMode === 'login' && (
          <p className="auth-switch">New here? <button onClick={() => { setFormMode('register'); setError('') }}>Create an account</button></p>
        )}
        {formMode === 'register' && (
          <p className="auth-switch">Already a member? <button onClick={() => { setFormMode('login'); setError('') }}>Sign in</button></p>
        )}
      </div>
    </div>
  )
}

function CommentsPanel({ post, token, currentUser, onClose }) {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [commentText, setCommentText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (post.isMock) { setLoading(false); return }
    fetch(`${FORUM_BASE}/posts/${post.id}/comments`)
      .then(r => r.json())
      .then(data => { setComments(Array.isArray(data) ? data : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [post])

  const submitComment = async (e) => {
    e.preventDefault()
    if (!commentText.trim() || !token) return
    setSubmitting(true)
    setError('')
    try {
      const res = await fetch(`${FORUM_BASE}/posts/${post.id}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ content: commentText.trim() })
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Failed to post comment'); return }
      setComments(prev => [...prev, data])
      setCommentText('')
    } catch { setError('Network error') }
    finally { setSubmitting(false) }
  }

  const { cleanTitle } = parseCategory(post.title)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="comments-modal" onClick={e => e.stopPropagation()}>
        <div className="comments-header">
          <h2>{cleanTitle}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="original-post-content">
          <div className="post-author-row">
            <span className="author-avatar">{getInitials(post.author?.full_name || post.author?.username || '?')}</span>
            <span className="author-name">{post.author?.full_name || post.author?.username}</span>
            <span className="post-time">{timeAgo(post.created_at)}</span>
          </div>
          <p>{post.content}</p>
        </div>
        <div className="comments-list">
          <h3>Discussion {comments.length > 0 ? `(${comments.length})` : ''}</h3>
          {loading && <div className="comments-loading">Loading comments…</div>}
          {post.isMock && !loading && (
            <div className="mock-notice">Sign in to see and post real comments on community discussions.</div>
          )}
          {comments.map(c => (
            <div key={c.id} className="comment-item">
              <div className="comment-author-row">
                <span className="author-avatar small">{getInitials(c.author?.full_name || c.author?.username || '?')}</span>
                <span className="author-name">{c.author?.full_name || c.author?.username}</span>
                <span className="post-time">{timeAgo(c.created_at)}</span>
              </div>
              <p className="comment-text">{c.content}</p>
            </div>
          ))}
          {!loading && comments.length === 0 && !post.isMock && (
            <p className="no-comments">Be the first to comment on this discussion.</p>
          )}
        </div>
        {currentUser && !post.isMock ? (
          <form className="comment-form" onSubmit={submitComment}>
            <textarea
              placeholder="Share your scholarly perspective…"
              value={commentText}
              onChange={e => setCommentText(e.target.value)}
              rows={3}
              maxLength={2000}
            />
            {error && <div className="auth-error">{error}</div>}
            <button type="submit" disabled={submitting || !commentText.trim()}>
              {submitting ? 'Posting…' : 'Post Comment'}
            </button>
          </form>
        ) : !currentUser ? (
          <div className="sign-in-prompt">Sign in to join this discussion.</div>
        ) : null}
      </div>
    </div>
  )
}

function NewPostModal({ token, onClose, onSuccess }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('Historical Context')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const cats = CATEGORIES.filter(c => c !== 'All')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim() || !content.trim()) return
    setSubmitting(true)
    setError('')
    const fullTitle = `[${category}] ${title.trim()}`
    try {
      const res = await fetch(`${FORUM_BASE}/posts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ title: fullTitle, content: content.trim() })
      })
      const data = await res.json()
      if (!res.ok) {
        const msg = data.detail
        if (Array.isArray(msg)) setError(msg.map(e => e.msg).join('. '))
        else setError(msg || 'Failed to create post')
        return
      }
      onSuccess(data)
    } catch { setError('Network error') }
    finally { setSubmitting(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="new-post-modal" onClick={e => e.stopPropagation()}>
        <div className="comments-header">
          <h2>Start a New Discussion</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label>Category</label>
            <select value={category} onChange={e => setCategory(e.target.value)}>
              {cats.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label>Title</label>
            <input type="text" placeholder="Discussion title…" value={title} onChange={e => setTitle(e.target.value)} required maxLength={180} />
          </div>
          <div className="form-field">
            <label>Content</label>
            <textarea
              placeholder="Share your thoughts, questions, or research…"
              value={content}
              onChange={e => setContent(e.target.value)}
              rows={6}
              required
              maxLength={10000}
            />
          </div>
          {error && <div className="auth-error">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="auth-submit" disabled={submitting || !title.trim() || !content.trim()}>
              {submitting ? 'Publishing…' : 'Publish Discussion'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ForumPage() {
  const [activeCategory, setActiveCategory] = useState('All')
  const [searchTerm, setSearchTerm] = useState('')
  const [posts, setPosts] = useState(MOCK_POSTS)
  const [loadingPosts, setLoadingPosts] = useState(true)
  const [currentUser, setCurrentUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('forum_token') || '')
  const [showAuth, setShowAuth] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [showNewPost, setShowNewPost] = useState(false)
  const [selectedPost, setSelectedPost] = useState(null)
  const [likedPosts, setLikedPosts] = useState(new Set())

  const fetchPosts = useCallback(async () => {
    try {
      const res = await fetch(`${FORUM_BASE}/posts`)
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          setPosts([...data, ...MOCK_POSTS])
        }
      }
    } catch {}
    finally { setLoadingPosts(false) }
  }, [])

  const fetchMe = useCallback(async (tok) => {
    if (!tok) return
    try {
      const res = await fetch(`${FORUM_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${tok}` }
      })
      if (res.ok) {
        const me = await res.json()
        setCurrentUser(me)
      } else {
        localStorage.removeItem('forum_token')
        setToken('')
      }
    } catch {}
  }, [])

  useEffect(() => {
    fetchPosts()
    if (token) fetchMe(token)
  }, [fetchPosts, fetchMe, token])

  const handleAuthSuccess = (user, tok) => {
    setCurrentUser(user)
    setToken(tok)
    localStorage.setItem('forum_token', tok)
    setShowAuth(false)
  }

  const handleLogout = () => {
    localStorage.removeItem('forum_token')
    setToken('')
    setCurrentUser(null)
  }

  const handleNewPost = (post) => {
    setPosts(prev => [post, ...prev])
    setShowNewPost(false)
  }

  const handleLike = (postId) => {
    setLikedPosts(prev => {
      const next = new Set(prev)
      if (next.has(postId)) next.delete(postId)
      else next.add(postId)
      return next
    })
    setPosts(prev => prev.map(p =>
      p.id === postId ? { ...p, likes: (p.likes || 0) + (likedPosts.has(postId) ? -1 : 1) } : p
    ))
  }

  const filteredPosts = posts.filter(post => {
    const { category, cleanTitle } = parseCategory(post.title)
    const matchesCategory = activeCategory === 'All' || category === activeCategory
    const matchesSearch = !searchTerm ||
      cleanTitle.toLowerCase().includes(searchTerm.toLowerCase()) ||
      post.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (post.author?.username || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (post.author?.full_name || '').toLowerCase().includes(searchTerm.toLowerCase())
    return matchesCategory && matchesSearch
  })

  return (
    <div className="forum-page">
      <div className="forum-header">
        <div className="forum-header-content">
          <h1 className="forum-title">Community Forum</h1>
          <p className="forum-subtitle">
            Engage with fellow scholars, theologians, and students in thoughtful discussions about biblical studies, historical context, and textual analysis.
          </p>
        </div>
        <div className="forum-user-area">
          {currentUser ? (
            <div className="user-info">
              <span className="user-avatar">{getInitials(currentUser.full_name || currentUser.username)}</span>
              <span className="user-name">{currentUser.username}</span>
              <button className="logout-btn" onClick={handleLogout}>Sign Out</button>
            </div>
          ) : (
            <div className="auth-buttons">
              <button className="sign-in-btn" onClick={() => { setAuthMode('login'); setShowAuth(true) }}>Sign In</button>
              <button className="join-btn" onClick={() => { setAuthMode('register'); setShowAuth(true) }}>Join</button>
            </div>
          )}
        </div>
      </div>

      <div className="forum-controls">
        <div className="category-tabs">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              className={`category-tab ${activeCategory === cat ? 'active' : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className="forum-actions">
          <div className="search-container">
            <input
              type="text"
              placeholder="Search discussions…"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
            <span className="search-icon">🔍</span>
          </div>
          <button
            className="new-discussion-btn"
            onClick={() => currentUser ? setShowNewPost(true) : (setAuthMode('login'), setShowAuth(true))}
          >
            <span className="plus-icon">+</span>
            New Discussion
          </button>
        </div>
      </div>

      {loadingPosts && (
        <div className="forum-loading">Loading discussions…</div>
      )}

      <div className="forum-posts">
        {filteredPosts.map(post => {
          const { category, cleanTitle } = parseCategory(post.title)
          const authorName = post.author?.full_name || post.author?.username || 'Scholar'
          const liked = likedPosts.has(post.id)
          return (
            <div key={post.id} className={`forum-post ${post.isMock ? 'mock-post' : 'real-post'}`}>
              <div className="post-content">
                <div className="post-header">
                  <h3 className="post-title" onClick={() => setSelectedPost(post)}>{cleanTitle}</h3>
                  <div className="post-category-tag" data-category={category}>{category}</div>
                </div>
                <div className="post-author-info">
                  <span className="author-initials">{getInitials(authorName)}</span>
                  <span className="author-name">{authorName}</span>
                  <span className="post-time">{timeAgo(post.created_at)}</span>
                  {post.isMock && <span className="featured-badge">Featured</span>}
                </div>
                <p className="post-description">{post.content.length > 220 ? post.content.slice(0, 220) + '…' : post.content}</p>
                <button className="read-more-btn" onClick={() => setSelectedPost(post)}>Read & discuss →</button>
              </div>
              <div className="post-stats">
                <button
                  className={`post-stat like-btn ${liked ? 'liked' : ''}`}
                  onClick={() => handleLike(post.id)}
                  title={liked ? 'Unlike' : 'Like'}
                >
                  <span className="stat-icon">👍</span>
                  <span className="stat-count">{(post.likes || 0) + (liked && !post.isMock ? 0 : 0)}</span>
                </button>
                <button className="post-stat comment-stat-btn" onClick={() => setSelectedPost(post)}>
                  <span className="stat-icon">💬</span>
                  <span className="stat-count">{post.comments_count || post.comments || 0}</span>
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {filteredPosts.length === 0 && !loadingPosts && (
        <div className="no-results">
          <p>No discussions found matching your criteria.</p>
          {currentUser && <button className="new-discussion-btn" onClick={() => setShowNewPost(true)}>Start a new discussion</button>}
        </div>
      )}

      {showAuth && (
        <AuthModal mode={authMode} onClose={() => setShowAuth(false)} onSuccess={handleAuthSuccess} />
      )}
      {showNewPost && (
        <NewPostModal token={token} onClose={() => setShowNewPost(false)} onSuccess={handleNewPost} />
      )}
      {selectedPost && (
        <CommentsPanel post={selectedPost} token={token} currentUser={currentUser} onClose={() => setSelectedPost(null)} />
      )}
    </div>
  )
}

export default ForumPage
