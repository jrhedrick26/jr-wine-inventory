import React, { useState } from 'react';
import { loginWithGoogle } from '../firebase';

export default function Auth({ onAuthSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      await loginWithGoogle();
      // loginWithGoogle uses signInWithRedirect, which will reload the page on success,
      // triggering the onAuthStateChanged listener in App.jsx.
    } catch (err) {
      console.error(err);
      setError('Could not complete Google Sign-In. Make sure Google Auth is enabled in the Firebase Console.');
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-logo-area">
        <div className="auth-icon">🍷</div>
        <h1 className="auth-logo-text">WineStock</h1>
        <p className="auth-subtitle">Your private digital cellar and sommelier assistant</p>
      </div>

      <div className="auth-card">
        {error && (
          <div style={{ color: '#ff6b6b', fontSize: '0.85rem', marginBottom: '16px', lineHeight: '1.4', textAlign: 'left' }}>
            {error}
          </div>
        )}
        
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '20px', lineHeight: '1.5' }}>
          Access your cellar securely from your phone or desktop.
        </p>

        <button 
          className="btn-google" 
          onClick={handleLogin}
          disabled={loading}
        >
          <img 
            src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
            alt="Google Logo" 
          />
          {loading ? 'Entering Cellar...' : 'Sign In with Google'}
        </button>
      </div>
    </div>
  );
}
