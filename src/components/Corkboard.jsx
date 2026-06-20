import React, { useState } from 'react';
import WineCard from './WineCard';
import { popCork } from '../db';

export default function Corkboard({ wines, loading, onPopSuccess }) {
  const [searchTerm, setSearchTerm] = useState('');

  const handlePop = async (wineId, wineData) => {
    try {
      await popCork(wineId, wineData);
      if (onPopSuccess) onPopSuccess();
    } catch (error) {
      alert("Error popping cork: " + error.message);
    }
  };

  const filteredWines = wines.filter(wine => {
    const term = searchTerm.toLowerCase();
    return (
      wine.name?.toLowerCase().includes(term) ||
      wine.varietal?.toLowerCase().includes(term) ||
      wine.year?.toLowerCase().includes(term)
    );
  });

  return (
    <div className="screen-content corkboard-bg" style={{ minHeight: '100%' }}>
      {/* Header and Search */}
      <div style={{ marginBottom: '16px', textAlign: 'left' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Active Cellar
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '16px' }}>
          {wines.length} {wines.length === 1 ? 'bottle' : 'bottles'} in stock. Tap a bottle to flip.
        </p>
        
        {wines.length > 0 && (
          <div className="search-container">
            <input 
              type="text" 
              placeholder="Search by name or grape..." 
              className="search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        )}
      </div>

      {loading ? (
        <div className="loading-spinner-container" style={{ marginTop: '40px' }}>
          <div className="spinner"></div>
          <p style={{ color: 'var(--text-muted)' }}>Inventory loading...</p>
        </div>
      ) : filteredWines.length > 0 ? (
        <div className="cork-grid-container">
          {filteredWines.map((wine) => (
            <WineCard 
              key={wine.id} 
              wine={wine} 
              onPop={handlePop}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-state-icon">🍷</div>
          <h3>
            {searchTerm ? "No matches found" : "Your cellar is empty"}
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px', lineHeight: '1.4' }}>
            {searchTerm 
              ? "Try adjusting your search terms." 
              : "Scan your first bottle using the camera button below to get started!"
            }
          </p>
        </div>
      )}
    </div>
  );
}
