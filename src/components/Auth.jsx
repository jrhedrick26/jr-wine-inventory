import React, { useState } from 'react';

export default function Auth({ onEnter }) {
  const [name, setName] = useState('My Private Cellar');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (onEnter) {
      onEnter(name.trim());
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-logo-area">
        <div className="auth-icon">🍷</div>
        <h1 className="auth-logo-text">WineStock</h1>
        <p className="auth-subtitle">Your private offline cellar and AI sommelier assistant</p>
      </div>

      <div className="auth-card">
        <form onSubmit={handleSubmit} style={{ textAlign: 'left' }}>
          <label 
            className="settings-label" 
            style={{ fontSize: '0.85rem', marginBottom: '8px', color: 'var(--text-muted)' }}
            htmlFor="cellar-name-input"
          >
            Cellar Name / Owner
          </label>
          <input
            id="cellar-name-input"
            className="settings-input"
            style={{ marginBottom: '20px' }}
            type="text"
            placeholder="e.g. Jason's Cellar"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          
          <button 
            type="submit"
            className="btn-google"
            style={{ background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-primary-light) 100%)', color: 'white', border: 'none', boxShadow: '0 4px 15px rgba(128, 28, 40, 0.4)' }}
          >
            Open My Cellar ➔
          </button>
        </form>
      </div>
    </div>
  );
}
