import React, { useState, useEffect, useRef } from 'react';
import { getCellarName, saveCellarName, exportCellarData, importCellarData } from '../db';

export default function Settings({ onReset }) {
  const [cellarTitle, setCellarTitle] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [savedKey, setSavedKey] = useState(false);
  const [savedTitle, setSavedTitle] = useState(false);
  const [importError, setImportError] = useState('');
  const [importSuccess, setImportSuccess] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    setCellarTitle(getCellarName());
    setApiKey(localStorage.getItem('gemini_api_key') || '');
  }, []);

  const handleSaveKey = (e) => {
    e.preventDefault();
    localStorage.setItem('gemini_api_key', apiKey.trim());
    setSavedKey(true);
    setTimeout(() => setSavedKey(false), 2000);
  };

  const handleSaveTitle = (e) => {
    e.preventDefault();
    saveCellarName(cellarTitle);
    setSavedTitle(true);
    setTimeout(() => setSavedTitle(false), 2000);
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        setImportError('');
        const content = event.target.result;
        importCellarData(content);
        setImportSuccess(true);
        setTimeout(() => {
          window.location.reload(); // Reload to refresh all tabs with imported data
        }, 1500);
      } catch (err) {
        setImportError(err.message || 'Failed to parse JSON file.');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="screen-content">
      <div style={{ marginBottom: '24px', textAlign: 'left' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700 }}>Settings</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Configure API keys, backup cellar, and customize name</p>
      </div>

      {/* Cellar Customization */}
      <div className="settings-group">
        <label className="settings-label" htmlFor="cellar-title-input">Cellar Title</label>
        <form onSubmit={handleSaveTitle} style={{ display: 'flex', gap: '10px' }}>
          <input
            id="cellar-title-input"
            className="settings-input"
            style={{ marginBottom: 0 }}
            type="text"
            value={cellarTitle}
            onChange={(e) => setCellarTitle(e.target.value)}
          />
          <button type="submit" className="btn-save">
            Update
          </button>
        </form>
        {savedTitle && (
          <div style={{ color: '#4caf50', fontSize: '0.85rem', marginTop: '6px', textAlign: 'left' }}>
            ✓ Cellar title updated!
          </div>
        )}
      </div>

      {/* Gemini Settings */}
      <div className="settings-group" style={{ marginTop: '24px' }}>
        <label className="settings-label" htmlFor="gemini-key-input">Gemini API Key</label>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '10px', lineHeight: '1.4' }}>
          Required for label camera scanning and AI Sommelier Chat. Stored locally in your browser.
        </p>
        <form onSubmit={handleSaveKey}>
          <input
            id="gemini-key-input"
            className="settings-input"
            type="password"
            placeholder="AIzaSy..."
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button type="submit" className="btn-save">
              Save Key
            </button>
            <a 
              href="https://aistudio.google.com/" 
              target="_blank" 
              rel="noopener noreferrer" 
              style={{ color: 'var(--accent-gold)', fontSize: '0.85rem', textDecoration: 'none' }}
            >
              Get Free API Key ↗
            </a>
          </div>
        </form>
        {savedKey && (
          <div style={{ color: '#4caf50', fontSize: '0.85rem', marginTop: '8px', textAlign: 'left' }}>
            ✓ API Key saved successfully!
          </div>
        )}
      </div>

      {/* Backup & Import Group */}
      <div className="settings-group" style={{ marginTop: '32px', paddingTop: '20px', borderTop: '1px solid var(--panel-border)' }}>
        <label className="settings-label">Backup & Portability</label>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '16px', lineHeight: '1.4' }}>
          Since your data is stored in this browser, use backups to export your cellar or sync it to another device.
        </p>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <button 
            onClick={exportCellarData} 
            className="btn-save"
            style={{ background: 'var(--accent-primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
          >
            📥 Export JSON
          </button>
          
          <button 
            onClick={handleImportClick} 
            className="btn-save"
            style={{ background: 'transparent', border: '1px solid var(--panel-border)', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
          >
            📤 Import JSON
          </button>
        </div>

        <input 
          type="file" 
          accept=".json" 
          ref={fileInputRef} 
          style={{ display: 'none' }}
          onChange={handleFileImport}
        />

        {importSuccess && (
          <div style={{ color: '#4caf50', fontSize: '0.85rem', marginTop: '12px', textAlign: 'left' }}>
            ✓ Backup imported successfully! Reloading cellar...
          </div>
        )}

        {importError && (
          <div style={{ color: '#ff6b6b', fontSize: '0.85rem', marginTop: '12px', textAlign: 'left' }}>
            ⚠ {importError}
          </div>
        )}
      </div>

      <button 
        className="btn-signout" 
        onClick={onReset}
        style={{ marginTop: '40px' }}
      >
        Lock Cellar Gates (Reset Welcome Screen)
      </button>
    </div>
  );
}
