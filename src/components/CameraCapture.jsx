import React, { useState, useRef } from 'react';
import { addWineToInventory } from '../firebase';
import { scanWineLabel } from '../gemini';

export default function CameraCapture({ userId, onClose, onAddSuccess }) {
  const [step, setStep] = useState('upload'); // 'upload' | 'scanning' | 'verify'
  const [imagePreview, setImagePreview] = useState('');
  const [wineData, setWineData] = useState({ name: '', year: '', varietal: '' });
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  // Resize and compress image using HTML5 Canvas
  const compressImage = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = (event) => {
        const img = new Image();
        img.src = event.target.result;
        img.onload = () => {
          const canvas = document.createElement('canvas');
          const maxDim = 400; // Optimal size for label reading & database storage
          let width = img.width;
          let height = img.height;

          if (width > height) {
            if (width > maxDim) {
              height *= maxDim / width;
              width = maxDim;
            }
          } else {
            if (height > maxDim) {
              width *= maxDim / height;
              height = maxDim;
            }
          }

          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);

          // Compress to JPEG with 75% quality
          const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.75);
          resolve(compressedDataUrl);
        };
        img.onerror = () => reject(new Error("Could not load image"));
      };
      reader.onerror = () => reject(new Error("Could not read file"));
    });
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError('');
    setStep('scanning');

    try {
      const compressedBase64 = await compressImage(file);
      setImagePreview(compressedBase64);

      // Scan image using Gemini (no local API key parameter needed!)
      const parsedDetails = await scanWineLabel(compressedBase64, 'image/jpeg');
      
      setWineData({
        name: parsedDetails.name || '',
        year: parsedDetails.year || 'N/A',
        varietal: parsedDetails.varietal || ''
      });
      setStep('verify');
    } catch (err) {
      console.error(err);
      setError(err.message || 'Scanning failed. Try taking a clearer photo.');
      setStep('upload');
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!wineData.name.trim()) {
      setError('Wine name is required.');
      return;
    }

    try {
      setError('');
      const dataToSave = {
        name: wineData.name,
        year: wineData.year,
        varietal: wineData.varietal,
        photoUrl: imagePreview // Save compressed base64 string directly
      };
      
      await addWineToInventory(userId, dataToSave);
      if (onAddSuccess) onAddSuccess();
      onClose();
    } catch (err) {
      console.error(err);
      setError('Could not save to database.');
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 className="modal-header">
            {step === 'upload' && 'Add New Bottle'}
            {step === 'scanning' && 'AI Cellar Scan'}
            {step === 'verify' && 'Verify Details'}
          </h3>
          <button 
            className="btn-icon-only" 
            style={{ color: 'var(--text-muted)', fontSize: '1.25rem', padding: '0 0 10px 10px' }} 
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {error && (
          <div style={{ color: '#ff6b6b', fontSize: '0.85rem', marginBottom: '16px', lineHeight: '1.4', textAlign: 'left' }}>
            ⚠ {error}
          </div>
        )}

        {step === 'upload' && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '3rem', marginBottom: '20px' }}>📸</div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '24px', lineHeight: '1.4' }}>
              Snap a photo of the wine label or upload one from your photo library.
            </p>
            
            {/* REMOVED capture="environment" to allow both Camera Roll and Camera snap */}
            <input 
              type="file" 
              accept="image/*" 
              ref={fileInputRef} 
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            <button 
              className="btn-pop-cork" 
              style={{ background: 'var(--accent-gold)', color: 'var(--text-dark)' }}
              onClick={() => fileInputRef.current?.click()}
            >
              Choose Photo / Take Picture
            </button>
          </div>
        )}

        {step === 'scanning' && (
          <div className="loading-spinner-container">
            <div className="spinner"></div>
            <p style={{ fontSize: '0.95rem', fontWeight: 500, marginBottom: '6px' }}>Reading Label...</p>
            <p className="loading-message">Gemini is extracting vintage, blend, and producer details.</p>
          </div>
        )}

        {step === 'verify' && (
          <form onSubmit={handleSave} style={{ textAlign: 'left' }}>
            {imagePreview && (
              <div style={{ width: '100px', height: '130px', margin: '0 auto 16px auto', borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--panel-border)' }}>
                <img src={imagePreview} alt="Scanned Label" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            )}

            <div className="settings-group">
              <label className="settings-label" style={{ fontSize: '0.8rem' }} htmlFor="wine-name">Wine Name / Producer</label>
              <input 
                id="wine-name"
                className="settings-input" 
                style={{ padding: '8px 12px', fontSize: '0.9rem', marginBottom: '10px' }}
                type="text" 
                value={wineData.name} 
                onChange={(e) => setWineData({ ...wineData, name: e.target.value })}
                required
              />

              <label className="settings-label" style={{ fontSize: '0.8rem' }} htmlFor="wine-varietal">Varietal / Grape Blend</label>
              <input 
                id="wine-varietal"
                className="settings-input" 
                style={{ padding: '8px 12px', fontSize: '0.9rem', marginBottom: '10px' }}
                type="text" 
                value={wineData.varietal} 
                onChange={(e) => setWineData({ ...wineData, varietal: e.target.value })}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px' }}>
                <div>
                  <label className="settings-label" style={{ fontSize: '0.8rem' }} htmlFor="wine-year">Vintage (Year)</label>
                  <input 
                    id="wine-year"
                    className="settings-input" 
                    style={{ padding: '8px 12px', fontSize: '0.9rem' }}
                    type="text" 
                    value={wineData.year} 
                    onChange={(e) => setWineData({ ...wineData, year: e.target.value })}
                  />
                </div>
              </div>
            </div>

            <button type="submit" className="btn-pop-cork" style={{ marginTop: '8px' }}>
              Add to Cellar
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
