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

  // Determine wine category/type based on varietal or name keywords
  const getWineType = (varietal = '', name = '') => {
    const v = varietal.toLowerCase();
    const n = name.toLowerCase();

    if (
      v.includes('cabernet') || v.includes('pinot noir') || v.includes('merlot') || 
      v.includes('syrah') || v.includes('shiraz') || v.includes('zinfandel') || 
      v.includes('red') || v.includes('tempranillo') || v.includes('malbec') || 
      v.includes('bordeaux') || v.includes('blend') || v.includes('chianti') ||
      n.includes('cab') || n.includes('pinot noir') || n.includes('merlot') || 
      n.includes('red')
    ) {
      return { class: 'type-red', icon: '🍷' };
    }

    if (v.includes('rose') || v.includes('rosé') || n.includes('rose') || n.includes('rosé')) {
      return { class: 'type-rose', icon: '🍷' };
    }

    if (
      v.includes('champagne') || v.includes('prosecco') || v.includes('cava') || 
      v.includes('sparkling') || v.includes('brut') ||
      n.includes('champagne') || n.includes('prosecco') || n.includes('sparkling')
    ) {
      return { class: 'type-sparkling', icon: '🍾' };
    }

    if (
      v.includes('chardonnay') || v.includes('sauvignon') || v.includes('pinot grigio') || 
      v.includes('pinot gris') || v.includes('riesling') || v.includes('white') || 
      v.includes('moscato') ||
      n.includes('chardonnay') || n.includes('sauvignon') || n.includes('white')
    ) {
      return { class: 'type-white', icon: '🥂' };
    }

    return { class: 'type-default', icon: '🍷' };
  };

  const wineType = getWineType(wine.varietal, wine.name);

  const addedDate = wine.addedAt 
    ? new Date(wine.addedAt.toDate ? wine.addedAt.toDate() : wine.addedAt).toLocaleDateString() 
    : 'Recently';

  return (
    <div 
      className={`wine-card-perspective ${isFlipped ? 'flipped' : ''}`}
      onClick={handleCardClick}
    >
      <div className="wine-card-inner">
        {/* FRONT: Clean typography label, color-coded border */}
        <div className={`wine-card-front ${wineType.class}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', width: '100%' }}>
            <span className="wine-type-silhouette">{wineType.icon}</span>
            {wine.year && wine.year !== 'N/A' && (
              <span className="wine-year-badge">{wine.year}</span>
            )}
          </div>

          <div className="wine-label-details">
            <h4 className="wine-label-name">{wine.name}</h4>
            <p className="wine-label-varietal">{wine.varietal || 'Unknown Blend'}</p>
          </div>
        </div>

        {/* BACK: Detailed view + Snapped photo thumbnail + Pop Button */}
        <div className="wine-card-back">
          <div className="wine-back-upper">
            {wine.photoUrl ? (
              <img 
                src={wine.photoUrl} 
                alt="Label preview" 
                className="wine-back-thumbnail" 
                loading="lazy"
              />
            ) : (
              <div className="wine-back-thumbnail" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem' }}>
                🍇
              </div>
            )}

            <div className="wine-back-details">
              <div className="wine-detail-name">{wine.name}</div>
              
              <div className="wine-detail-label">Grape / Blend</div>
              <div className="wine-detail-value">{wine.varietal || 'N/A'}</div>

              <div className="wine-detail-label">Vintage</div>
              <div className="wine-detail-value">{wine.year || 'N/A'}</div>
              
              <div className="wine-detail-label">Added</div>
              <div className="wine-detail-value" style={{ fontSize: '0.75rem' }}>{addedDate}</div>
            </div>
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
