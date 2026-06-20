import React, { useState } from 'react';

export default function WineCard({ wine, onPop }) {
  const [isFlipped, setIsFlipped] = useState(false);

  const handleCardClick = () => {
    setIsFlipped(!isFlipped);
  };

  const handlePopClick = (e) => {
    e.stopPropagation(); // Prevent card from flipping back over
    if (onPop) {
      onPop(wine.id, wine);
    }
  };

  const addedDate = wine.addedAt 
    ? new Date(wine.addedAt).toLocaleDateString() 
    : 'Recently';

  return (
    <div 
      className={`wine-card-perspective ${isFlipped ? 'flipped' : ''}`}
      onClick={handleCardClick}
    >
      <div className="wine-card-inner">
        {/* FRONT: Cropped Image and Summary overlay */}
        <div className="wine-card-front">
          <div className="wine-image-container">
            {wine.photoUrl ? (
              <img 
                src={wine.photoUrl} 
                alt={wine.name} 
                className="wine-label-photo" 
                loading="lazy"
              />
            ) : (
              <div style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '3rem',
                background: 'linear-gradient(135deg, hsl(352, 60%, 15%) 0%, hsl(348, 15%, 8%) 100%)'
              }}>
                🍷
              </div>
            )}
            
            {wine.year && wine.year !== 'N/A' && (
              <span className="wine-year-badge">{wine.year}</span>
            )}

            <div className="wine-summary-area">
              <h4 className="wine-name-title">{wine.name}</h4>
              <p className="wine-varietal-sub">{wine.varietal || 'Unknown Varietal'}</p>
            </div>
          </div>
        </div>

        {/* BACK: Detailed view and Pop the Cork button */}
        <div className="wine-card-back">
          <div className="wine-back-details">
            <div className="wine-detail-label">Wine Name</div>
            <div className="wine-detail-name">{wine.name}</div>

            <div className="wine-detail-label">Varietal / Blend</div>
            <div className="wine-detail-value">{wine.varietal || 'N/A'}</div>

            <div className="wine-detail-label">Vintage Year</div>
            <div className="wine-detail-value">{wine.year || 'N/A'}</div>

            <div className="wine-detail-label">Added to Cellar</div>
            <div className="wine-detail-value">{addedDate}</div>
          </div>

          <button 
            className="btn-pop-cork"
            onClick={handlePopClick}
          >
            Pop the Cork 🍾
          </button>
        </div>
      </div>
    </div>
  );
}
