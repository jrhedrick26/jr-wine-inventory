import React from 'react';

export default function HistoryLog({ history, loading }) {
  
  const formatDate = (timestamp) => {
    if (!timestamp) return 'Unknown Date';
    // Firestore Timestamp conversion
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    return date.toLocaleDateString(undefined, { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  };

  return (
    <div className="screen-content">
      <div style={{ marginBottom: '24px', textAlign: 'left' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700 }}>
          History Log
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Chronological record of popped bottles
        </p>
      </div>

      {loading ? (
        <div className="loading-spinner-container" style={{ marginTop: '40px' }}>
          <div className="spinner"></div>
          <p style={{ color: 'var(--text-muted)' }}>Loading history...</p>
        </div>
      ) : history.length > 0 ? (
        <div>
          {history.map((wine) => (
            <div key={wine.id} className="history-item">
              {wine.photoUrl ? (
                <img 
                  src={wine.photoUrl} 
                  alt={wine.name} 
                  className="history-img" 
                  loading="lazy"
                />
              ) : (
                <div style={{
                  width: '50px',
                  height: '65px',
                  borderRadius: '8px',
                  background: 'var(--panel-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1.5rem'
                }}>
                  🍾
                </div>
              )}
              
              <div className="history-info">
                <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>{wine.name}</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {wine.varietal} {wine.year && wine.year !== 'N/A' ? `(${wine.year})` : ''}
                </p>
                <div className="history-date">
                  Drank on {formatDate(wine.poppedAt)}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-state-icon">🍾</div>
          <h3>No bottles popped yet</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px', lineHeight: '1.4' }}>
            Go to your Active Cellar, tap a card, and hit "Pop the Cork" to start log history!
          </p>
        </div>
      )}
    </div>
  );
}
