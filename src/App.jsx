import React, { useState, useEffect } from 'react';
import { getCellarName } from './db';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';

export default function App() {
  const [cellarName, setCellarName] = useState('');
  const [hasEntered, setHasEntered] = useState(false);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    // Check if the user has initialized their cellar name
    const storedName = localStorage.getItem('winestock_cellar_name');
    if (storedName) {
      setCellarName(storedName);
      setHasEntered(true);
    }
    setInitializing(false);
  }, []);

  const handleEnterCellar = (name) => {
    localStorage.setItem('winestock_cellar_name', name);
    setCellarName(name);
    setHasEntered(true);
  };

  const handleResetCellar = () => {
    // Log out equivalent: reset flags (keep database but prompt welcome setup again)
    setHasEntered(false);
  };

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

  return (
    <>
      {hasEntered ? (
        <Dashboard cellarName={cellarName} onReset={handleResetCellar} />
      ) : (
        <Auth onEnter={handleEnterCellar} />
      )}
    </>
  );
}
