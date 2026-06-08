import React, { useState, useRef, useEffect } from 'react';
import './ChatInterface.css';

const SUGGESTED_QUESTIONS = [
  "What does Genesis 1:1 reveal about creation?",
  "Who were the Watchers in 1 Enoch?",
  "What is the Ethiopian Orthodox Bible?",
  "How was the biblical canon formed?",
  "Explain the Hebrew name of Jesus (Yeshua)",
  "What does 'almah' mean in Isaiah 7:14?",
  "Tell me about the Dead Sea Scrolls",
  "What is the Book of Jubilees?",
];

function formatAnswer(text) {
  if (!text) return null;
  // Split into paragraphs
  const paragraphs = text.split(/\n\n+/);
  return paragraphs.map((para, i) => {
    // Bold **text**
    const parts = para.split(/\*\*(.*?)\*\*/g);
    const formatted = parts.map((part, j) => j % 2 === 1 ? <strong key={j}>{part}</strong> : part);
    return <p key={i} className="answer-para">{formatted}</p>;
  });
}

function CitationCard({ source, index }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`citation-card ${expanded ? 'expanded' : ''}`} onClick={() => setExpanded(!expanded)}>
      <div className="citation-header">
        <span className="citation-number">[{index + 1}]</span>
        <span className="citation-text">{source}</span>
        <span className="citation-toggle">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="citation-detail">
          <p>Source reference from the Unbound Bible database: <em>{source}</em></p>
        </div>
      )}
    </div>
  );
}

const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const sendMessage = async (question) => {
    const q = question.trim();
    if (!q || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: q,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setShowSuggestions(false);
    setCurrentQuestion('');

    try {
      const response = await fetch('/api/v1/chat/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();

      const aiMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: data.answer,
        sources: data.context_used || [],
        timestamp: new Date(),
        followUps: generateFollowUps(q, data.answer)
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        type: 'error',
        content: 'I encountered an error. Please check your connection and try again.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const generateFollowUps = (question, answer) => {
    const q = question.toLowerCase();
    if (q.includes('enoch') || q.includes('watcher')) {
      return ['What is the Book of Jubilees?', 'How does 1 Enoch relate to the New Testament?', 'What are the Nephilim?'];
    }
    if (q.includes('canon') || q.includes('bible')) {
      return ['What books are in the Ethiopian Orthodox Bible?', 'Why were the Apocrypha removed?', 'What is the Septuagint?'];
    }
    if (q.includes('genesis') || q.includes('creation')) {
      return ['What does Elohim mean in Hebrew?', 'Who were Adam and Eve in the Cave of Treasures?', 'Tell me about the Fall narrative'];
    }
    if (q.includes('name') || q.includes('jesus') || q.includes('yeshua')) {
      return ['What does "Christ" mean in Hebrew?', 'What language did Jesus speak?', 'Who is Peter/Kepha?'];
    }
    return ['Tell me more about this topic', 'What does the Ethiopian tradition say?', 'What do the original languages reveal?'];
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(currentQuestion);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(currentQuestion);
    }
  };

  const formatTimestamp = (ts) =>
    new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <div className="chat-header-content">
          <div className="chat-header-icon">🔍</div>
          <div>
            <h1>AI Biblical Assistant</h1>
            <p className="chat-subtitle">Powered by Unbound Bible database · Multi-canonical · Decolonized scholarship</p>
          </div>
        </div>
        <div className="chat-disclaimer">
          <span className="disclaimer-icon">ℹ️</span>
          AI responses draw from this app's biblical database. Verify important claims with scholarly sources.
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-screen">
            <div className="welcome-icon">📖</div>
            <h3>Welcome to The Unbound Bible AI</h3>
            <p>Ask about biblical texts, historical context, original languages, canonical traditions, and the decolonization of scripture.</p>
            <div className="feature-pills">
              <span className="feature-pill">📚 46,000+ verses</span>
              <span className="feature-pill">🌍 Ethiopian Canon</span>
              <span className="feature-pill">🔤 Hebrew & Greek</span>
              <span className="feature-pill">⚠️ Bias Detection</span>
            </div>
          </div>
        )}

        {showSuggestions && messages.length === 0 && (
          <div className="suggestions-grid">
            <p className="suggestions-label">Try asking:</p>
            <div className="suggestions-list">
              {SUGGESTED_QUESTIONS.map((q, i) => (
                <button key={i} className="suggestion-chip" onClick={() => sendMessage(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`message-row ${message.type}-row`}>
            {message.type === 'ai' && (
              <div className="message-avatar ai-avatar">AI</div>
            )}
            {message.type === 'user' && (
              <div className="message-avatar user-avatar">You</div>
            )}

            <div className={`message-bubble ${message.type}-bubble`}>
              <div className="message-content-area">
                {message.type === 'ai' ? (
                  <div className="ai-response">
                    <div className="answer-body">{formatAnswer(message.content)}</div>

                    {message.sources && message.sources.length > 0 && (
                      <div className="sources-section">
                        <h4 className="sources-title">
                          <span>📚</span> Sources Consulted
                        </h4>
                        <div className="citations-list">
                          {message.sources.map((src, i) => (
                            <CitationCard key={i} source={src} index={i} />
                          ))}
                        </div>
                      </div>
                    )}

                    {message.followUps && (
                      <div className="follow-ups-section">
                        <p className="follow-ups-label">Continue exploring:</p>
                        <div className="follow-ups-list">
                          {message.followUps.map((q, i) => (
                            <button key={i} className="follow-up-chip" onClick={() => sendMessage(q)}>
                              {q} →
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : message.type === 'error' ? (
                  <p className="error-content">{message.content}</p>
                ) : (
                  <p className="user-content">{message.content}</p>
                )}
              </div>
              <span className="message-time">{formatTimestamp(message.timestamp)}</span>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message-row ai-row">
            <div className="message-avatar ai-avatar">AI</div>
            <div className="message-bubble ai-bubble loading-bubble">
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
              <p className="loading-label">Searching biblical texts and analyzing…</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            value={currentQuestion}
            onChange={(e) => setCurrentQuestion(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about scripture, history, original languages, or canonical traditions…"
            className="chat-input"
            rows="2"
            disabled={isLoading}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!currentQuestion.trim() || isLoading}
            title="Send message"
          >
            {isLoading ? <span className="loading-spinner">⏳</span> : <span className="send-icon">↑</span>}
          </button>
        </div>
        <div className="input-footer">
          <span className="input-hint">Enter to send · Shift+Enter for new line</span>
          <span className="powered-by">Powered by GPT-4 + Unbound Bible DB</span>
        </div>
      </form>
    </div>
  );
};

export default ChatInterface;
