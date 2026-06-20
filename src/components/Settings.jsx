import React from 'react';
import { logoutUser } from '../firebase';

export default function Settings({ user }) {
  const handleSignOut = async () => {
    try {
      await logoutUser();
    } catch (error) {
      console.error("Error signing out:", error);
    }
  };

  return (
    <div className="screen-content">
      <div style={{ marginBottom: '24px', textAlign: 'left' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700 }}>Settings</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Configure account and cellar preferences</p>
      </div>

      {/* User Info Card */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        background: 'var(--panel-bg)',
        border: '1px solid var(--panel-border)',
        padding: '16px',
        borderRadius: '16px',
        marginBottom: '24px'
      }}>
        {user?.photoURL ? (
          <img 
            src={user.photoURL} 
            alt="Profile" 
            style={{ width: '48px', height: '48px', borderRadius: '50%', border: '1px solid var(--accent-gold)' }} 
          />
        ) : (
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'var(--accent-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.25rem'
          }}>🍷</div>
        )}
        <div style={{ textAlign: 'left' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{user?.displayName || 'Wine Enthusiast'}</h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{user?.email}</p>
        </div>
      </div>

      {/* API Configuration Card */}
      <div style={{
        background: 'var(--panel-bg)',
        border: '1px solid var(--panel-border)',
        padding: '16px',
        borderRadius: '16px',
        textAlign: 'left'
      }}>
        <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--accent-gold)', fontSize: '1rem', marginBottom: '8px' }}>
          System Configuration
        </h3>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.9rem', marginBottom: '6px' }}>
          <span>AI Sommelier Service:</span>
          <span style={{ color: '#4caf50', fontWeight: 600 }}>Active (Global Key)</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.9rem' }}>
          <span>Cellar Cloud Sync:</span>
          <span style={{ color: '#4caf50', fontWeight: 600 }}>Connected</span>
        </div>
      </div>

      <button className="btn-signout" onClick={handleSignOut} style={{ marginTop: '40px' }}>
        Sign Out from Cellar
      </button>
    </div>
  );
}
