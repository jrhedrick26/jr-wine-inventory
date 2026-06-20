import React, { useState, useEffect } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth, isFirebaseConfigured } from './firebase';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';

export default function App() {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(isFirebaseConfigured);
  const [tookTooLong, setTookTooLong] = useState(false);

  useEffect(() => {
    if (!isFirebaseConfigured) return;

    console.log("Firebase is configured. Initializing auth state listener...");

    // Set a timer to show diagnostics if auth takes too long to respond
    const timer = setTimeout(() => {
      setTookTooLong(true);
      console.warn("Firebase auth listener is taking longer than 5 seconds to respond. This might indicate a network or firewall block.");
    }, 5000);

    // Listen for authentication state changes
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      console.log("Firebase auth state changed. User:", firebaseUser ? firebaseUser.uid : "None");
      setUser(firebaseUser);
      setInitializing(false);
      clearTimeout(timer);
    }, (error) => {
      console.error("Firebase Auth State Changed Error:", error);
      clearTimeout(timer);
    });

    // Cleanup subscription and timer
    return () => {
      unsubscribe();
      clearTimeout(timer);
    };
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
        color: 'var(--text-primary)',
        padding: '24px',
        textAlign: 'center'
      }}>
        <div className="spinner" style={{ marginBottom: '20px' }}></div>
        <p style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
          Opening Cellar Gates...
        </p>
        
        {tookTooLong && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.2)',
            borderRadius: '12px',
            padding: '16px',
            maxWidth: '340px',
            fontSize: '0.85rem',
            lineHeight: '1.5',
            color: 'var(--text-secondary)',
            textAlign: 'left',
            animation: 'fadeIn 0.3s ease-out'
          }}>
            <p style={{ fontWeight: 600, color: '#ef4444', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              ⚠️ Connection taking longer than usual
            </p>
            <p style={{ marginBottom: '8px' }}>
              Firebase Auth is having trouble responding. This is common if:
            </p>
            <ul style={{ margin: '0 0 12px 16px', padding: 0 }}>
              <li>You are on a corporate network/VPN with a firewall blocking Google API domains.</li>
              <li>An ad-blocker or privacy extension is blocking the Firebase connection.</li>
            </ul>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Open your browser's Developer Console (Right-Click -> Inspect -> Console) to check for red network error logs.
            </p>
          </div>
        )}
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
