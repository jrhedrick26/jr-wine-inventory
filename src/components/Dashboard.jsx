import React, { useState, useEffect } from 'react';
import { getInventory, getHistory } from '../db';
import Corkboard from './Corkboard';
import HistoryLog from './HistoryLog';
import ChatAssistant from './ChatAssistant';
import Settings from './Settings';
import CameraCapture from './CameraCapture';

export default function Dashboard({ cellarName, onReset }) {
  const [activeTab, setActiveTab] = useState('corkboard'); // 'corkboard' | 'history' | 'chat' | 'settings'
  const [wines, setWines] = useState([]);
  const [history, setHistory] = useState([]);
  const [loadingWines, setLoadingWines] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [showScanner, setShowScanner] = useState(false);

  // Load and refresh inventory from local storage
  const refreshData = () => {
    setWines(getInventory());
    setHistory(getHistory());
  };

  useEffect(() => {
    refreshData();
    setLoadingWines(false);
    setLoadingHistory(false);
  }, []);

  const handleAddSuccess = () => {
    refreshData();
    setActiveTab('corkboard');
  };

  const handlePopSuccess = () => {
    refreshData();
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <h1 className="app-title">{cellarName}</h1>
        <div style={{ fontSize: '0.85rem', color: 'var(--accent-gold)', fontWeight: 500 }}>
          {activeTab === 'corkboard' && 'Cellar'}
          {activeTab === 'history' && 'History'}
          {activeTab === 'chat' && 'AI Chat'}
          {activeTab === 'settings' && 'Settings'}
        </div>
      </header>

      {/* Main View Area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {activeTab === 'corkboard' && (
          <Corkboard 
            wines={wines} 
            loading={loadingWines} 
            onPopSuccess={handlePopSuccess}
          />
        )}
        {activeTab === 'history' && (
          <HistoryLog 
            history={history} 
            loading={loadingHistory} 
          />
        )}
        {activeTab === 'chat' && (
          <ChatAssistant 
            activeInventory={wines} 
            historyLog={history} 
          />
        )}
        {activeTab === 'settings' && (
          <Settings 
            onReset={onReset} 
          />
        )}
      </div>

      {/* Bottom Tab Bar Navigation */}
      <nav className="bottom-nav">
        <button 
          className={`nav-item ${activeTab === 'corkboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('corkboard')}
        >
          <span className="nav-icon">🍷</span>
          <span>Cellar</span>
        </button>

        <button 
          className={`nav-item ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <span className="nav-icon">📜</span>
          <span>History</span>
        </button>

        {/* Floating Center Capture Button */}
        <div className="nav-item add-btn-wrapper">
          <button 
            className="nav-add-btn"
            onClick={() => setShowScanner(true)}
            aria-label="Scan new bottle"
          >
            📸
          </button>
        </div>

        <button 
          className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <span className="nav-icon">💬</span>
          <span>AI Chat</span>
        </button>

        <button 
          className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <span className="nav-icon">⚙️</span>
          <span>Settings</span>
        </button>
      </nav>

      {/* Scanner Modal Overlay */}
      {showScanner && (
        <CameraCapture 
          onClose={() => setShowScanner(false)}
          onAddSuccess={handleAddSuccess}
        />
      )}
    </div>
  );
}
