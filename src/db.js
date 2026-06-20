/**
 * Local-First Database Manager for WineStock (using localStorage)
 */

// Helper to generate a unique random ID
function generateId() {
  return Math.random().toString(36).substring(2, 9);
}

// 1. Cellar Custom Name
export const getCellarName = () => {
  return localStorage.getItem('winestock_cellar_name') || "My Private Cellar";
};

export const saveCellarName = (name) => {
  localStorage.setItem('winestock_cellar_name', name.trim());
};

// 2. Active Inventory
export const getInventory = () => {
  const data = localStorage.getItem('winestock_inventory');
  return data ? JSON.parse(data) : [];
};

export const saveInventory = (inventory) => {
  localStorage.setItem('winestock_inventory', JSON.stringify(inventory));
};

export const addWineToInventory = (wineData) => {
  const inventory = getInventory();
  const newWine = {
    id: generateId(),
    name: wineData.name || 'Unknown Wine',
    year: wineData.year || 'N/A',
    varietal: wineData.varietal || 'N/A',
    photoUrl: wineData.photoUrl || '',
    addedAt: new Date().toISOString()
  };
  inventory.unshift(newWine); // Add to beginning
  saveInventory(inventory);
  return newWine;
};

// 3. Drinking History
export const getHistory = () => {
  const data = localStorage.getItem('winestock_history');
  return data ? JSON.parse(data) : [];
};

export const saveHistory = (history) => {
  localStorage.setItem('winestock_history', JSON.stringify(history));
};

export const popCork = (wineId, wineData) => {
  // 1. Add to history log
  const history = getHistory();
  const poppedWine = {
    id: generateId(),
    name: wineData.name || 'Unknown Wine',
    year: wineData.year || 'N/A',
    varietal: wineData.varietal || 'N/A',
    photoUrl: wineData.photoUrl || '',
    addedAt: wineData.addedAt || null,
    poppedAt: new Date().toISOString()
  };
  history.unshift(poppedWine);
  saveHistory(history);

  // 2. Remove from active stock
  const inventory = getInventory();
  const updatedInventory = inventory.filter(w => w.id !== wineId);
  saveInventory(updatedInventory);
};

// 4. Export / Import Backup Helpers
export const exportCellarData = () => {
  const data = {
    cellarName: getCellarName(),
    inventory: getInventory(),
    history: getHistory()
  };
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `winestock_backup_${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const importCellarData = (jsonData) => {
  try {
    const data = JSON.parse(jsonData);
    if (data.cellarName) saveCellarName(data.cellarName);
    if (Array.isArray(data.inventory)) saveInventory(data.inventory);
    if (Array.isArray(data.history)) saveHistory(data.history);
    return true;
  } catch (error) {
    console.error("Failed to import cellar backup:", error);
    throw new Error("Invalid backup file format.");
  }
};
