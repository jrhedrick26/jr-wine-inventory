import React, { useState, useEffect } from 'react';
import { query, orderBy, onSnapshot } from 'firebase/firestore';
import { getInventoryRef, getHistoryRef, popCork } from '../firebase';
import Corkboard from './Corkboard';
import HistoryLog from './HistoryLog';
import ChatAssistant from './ChatAssistant';
import Settings from './Settings';
import CameraCapture from './CameraCapture';

export default function Dashboard({ user }) {
  const [activeTab, setActiveTab] = useState('corkboard'); // 'corkboard' | 'history' | 'chat' | 'settings'
  const [wines, setWines] = useState([]);
  const [history, setHistory] = useState([]);
  const [loadingWines, setLoadingWines] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [showScanner, setShowScanner] = useState(false);
  
  // Tasting Feedback Modal state
  const [poppingWine, setPoppingWine] = useState(null); // null | { id, data }
  const [poppingLoading, setPoppingLoading] = useState(false);

  // Set up real-time listeners for active inventory and history
  useEffect(() => {
    if (!user) return;

    setLoadingWines(true);
    setLoadingHistory(true);

    // 1. Listen to active inventory
    const activeQuery = query(getInventoryRef(user.uid), orderBy('addedAt', 'desc'));
    const unsubscribeActive = onSnapshot(activeQuery, (snapshot) => {
      const activeList = [];
      snapshot.forEach((doc) => {
        activeList.push({ id: doc.id, ...doc.data() });
      });
      setWines(activeList);
      setLoadingWines(false);
    }, (error) => {
      console.error("Active inventory subscription error:", error);
      setLoadingWines(false);
    });

    // 2. Listen to history log
    const historyQuery = query(getHistoryRef(user.uid), orderBy('poppedAt', 'desc'));
    const unsubscribeHistory = onSnapshot(historyQuery, (snapshot) => {
      const historyList = [];
      snapshot.forEach((doc) => {
        historyList.push({ id: doc.id, ...doc.data() });
      });
      setHistory(historyList);
      setLoadingHistory(false);
    }, (error) => {
      console.error("History subscription error:", error);
      setLoadingHistory(false);
    });

    // Clean up subscriptions
    return () => {
      unsubscribeActive();
      unsubscribeHistory();
    };
  }, [user]);

  // Handle popping a cork with tasting feedback
  const handlePopClick = (wineId, wineData) => {
    setPoppingWine({ id: wineId, data: wineData });
  };

  const handleConfirmPop = async (liked) => {
    if (!poppingWine) return;
    setPoppingLoading(true);
    try {
      await popCork(user.uid, poppingWine.id, poppingWine.data, liked);
      setPoppingWine(null);
    } catch (error) {
      alert("Failed to pop cork: " + error.message);
    } finally {
      setPoppingLoading(false);
    }
  };

  // Get first name for cellar title
  const getCellarTitle = () => {
    if (user?.displayName) {
      const firstName = user.displayName.split(' ')[0];
      return `${firstName}'s Cellar`;
    }
    return "My Cellar";
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <h1 className="app-title">{getCellarTitle()}</h1>
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
            onPop={handlePopClick}
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
            user={user} 
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
          userId={user.uid}
          onClose={() => setShowScanner(false)}
          onAddSuccess={() => setActiveTab('corkboard')}
        />
      )}

      {/* Popping Cork Feedback Modal */}
      {poppingWine && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ textAlign: 'center' }}>
            <h3 className="modal-header">Pop the Cork! 🍾</h3>
            
            {poppingLoading ? (
              <div className="loading-spinner-container">
                <div className="spinner"></div>
                <p className="loading-message">Logging consumption...</p>
              </div>
            ) : (
              <>
                <p style={{ fontSize: '0.95rem', marginBottom: '16px', lineHeight: '1.4' }}>
                  Did you enjoy drinking <strong>{poppingWine.data.name}</strong>?
                </p>
                
                <div className="rating-buttons-container">
                  <button 
                    onClick={() => handleConfirmPop(true)} 
                    className="btn-rating like"
                  >
                    <span className="btn-rating-icon">❤️</span>
                    <span>Loved it!</span>
                  </button>
                  
                  <button 
                    onClick={() => handleConfirmPop(false)} 
                    className="btn-rating dislike"
                  >
                    <span className="btn-rating-icon">👎</span>
                    <span>Not a fan</span>
                  </button>
                </div>
                
                <button 
                  onClick={() => setPoppingWine(null)} 
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    fontSize: '0.85rem',
                    marginTop: '24px',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
