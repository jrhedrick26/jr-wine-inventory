import React, { useState, useEffect, useRef } from 'react';
import { getSommelierChatResponse } from '../gemini';

export default function ChatAssistant({ activeInventory, historyLog }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(true);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Check if API key is present
    const apiKey = localStorage.getItem('gemini_api_key');
    if (!apiKey) {
      setHasApiKey(false);
      return;
    }
    setHasApiKey(true);

    // Initialize with a welcome message if empty
    if (messages.length === 0) {
      const bottleCount = activeInventory.length;
      const initialText = bottleCount > 0
        ? `Welcome back to your cellar! I see you have ${bottleCount} ${bottleCount === 1 ? 'bottle' : 'bottles'} in stock. What shall we pair tonight, or would you like me to recommend a bottle to uncork?`
        : "Welcome to your digital cellar! It looks like your cellar is currently empty. Scan a wine label using the camera button below, and I'll help you pair it or recommend when to drink it!";
      
      setMessages([
        { id: 'init', role: 'assistant', text: initialText }
      ]);
    }
  }, [activeInventory.length]);

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || loading) return;

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      text: inputValue
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      const apiKey = localStorage.getItem('gemini_api_key');
      const chatHistoryForApi = [...messages, userMessage];

      const aiResponseText = await getSommelierChatResponse(
        apiKey,
        chatHistoryForApi,
        activeInventory,
        historyLog
      );

      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: aiResponseText
      }]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: "I apologies, but I had trouble accessing your cellar info. Please check your internet connection or verify your API key in Settings."
      }]);
    } finally {
      setLoading(false);
    }
  };

  if (!hasApiKey) {
    return (
      <div className="screen-content">
        <div style={{ marginBottom: '24px', textAlign: 'left' }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700 }}>AI Sommelier</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Personalized pairing & cellar recommendations</p>
        </div>

        <div className="empty-state">
          <div className="empty-state-icon">🤖</div>
          <h3>API Key Required</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '12px', marginBottom: '20px', lineHeight: '1.4' }}>
            To activate your personal AI Sommelier, please navigate to the **Settings** tab and enter a Gemini API Key.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="screen-content" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Title Header */}
      <div style={{ textAlign: 'left' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700 }}>AI Sommelier</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Ask for pairings, recommendations, or tasting notes</p>
      </div>

      <div className="chat-container">
        {/* Messages Frame */}
        <div className="chat-messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`chat-bubble ${msg.role}`}>
              {msg.text}
            </div>
          ))}
          {loading && (
            <div className="chat-bubble assistant" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div className="spinner" style={{ width: '12px', height: '12px', borderWidth: '2px', margin: 0 }}></div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Sommelier is thinking...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Form Input Frame */}
        <form onSubmit={handleSend} className="chat-input-area">
          <input
            className="chat-input"
            type="text"
            placeholder="Suggest a pairing for salmon..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={loading}
          />
          <button 
            type="submit" 
            className="chat-send-btn"
            disabled={loading || !inputValue.trim()}
          >
            ➔
          </button>
        </form>
      </div>
    </div>
  );
}
