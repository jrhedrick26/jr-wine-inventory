import React, { useState, useEffect } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth, isFirebaseConfigured } from './firebase';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';

export default function App() {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(isFirebaseConfigured);

  useEffect(() => {
    if (!isFirebaseConfigured) return;

    // Listen for authentication state changes
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setInitializing(false);
    });

    // Cleanup subscription
    return () => unsubscribe();
  }, []);

  if (!isFirebaseConfigured) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100dvh',
        backgroundColor: 'var(--bg-color)',
        color: 'var(--text-primary)',
        padding: '24px',
        textAlign: 'center'
      }}>
        <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🍷</div>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700, marginBottom: '12px' }}>
          Welcome to WineStock
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '20px', maxWidth: '320px', lineHeight: '1.5' }}>
          Connect the app to your database by adding these Environment Variables in your Vercel Project Settings:
        </p>
        <div style={{
          background: 'var(--panel-bg)',
          border: '1px solid var(--panel-border)',
          borderRadius: '16px',
          padding: '16px',
          textAlign: 'left',
          width: '100%',
          maxWidth: '340px',
          fontSize: '0.8rem',
          fontFamily: 'monospace',
          color: 'var(--accent-gold)',
          marginBottom: '24px',
          lineHeight: '1.8'
        }}>
          VITE_FIREBASE_API_KEY<br/>
          VITE_FIREBASE_AUTH_DOMAIN<br/>
          VITE_FIREBASE_PROJECT_ID<br/>
          VITE_FIREBASE_STORAGE_BUCKET<br/>
          VITE_FIREBASE_MESSAGING_SENDER_ID<br/>
          VITE_FIREBASE_APP_ID
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', lineHeight: '1.4' }}>
          Once configured, Vercel will build and reload this page to connect to your cellar and activate Google Login!
        </p>
      </div>
    );
  }

  if (initializing) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100dvh',
        backgroundColor: 'var(--bg-color)',
        color: 'var(--text-primary)'
      }}>
        <div className="spinner"></div>
        <p style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', color: 'var(--text-muted)' }}>
          Opening Cellar Gates...
        </p>
      </div>
    );
  }

  // If user is authenticated, show Dashboard. Otherwise, show Auth page (Google Sign-In).
  return (
    <>
      {user ? (
        <Dashboard user={user} />
      ) : (
        <Auth onAuthSuccess={(u) => setUser(u)} />
      )}
    </>
  );
}
