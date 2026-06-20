import { initializeApp } from 'firebase/app';
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithRedirect, 
  signOut, 
  onAuthStateChanged 
} from 'firebase/auth';
import { 
  getFirestore, 
  collection, 
  doc, 
  addDoc, 
  deleteDoc, 
  query, 
  orderBy, 
  onSnapshot, 
  serverTimestamp 
} from 'firebase/firestore';

// Web App's Firebase configuration loaded from environment variables
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || ""
};

// Check if credentials exist (avoids crash if environment variables aren't set yet)
export const isFirebaseConfigured = !!firebaseConfig.apiKey;

let auth = null;
let db = null;
let googleProvider = null;

if (isFirebaseConfigured) {
  const app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  db = getFirestore(app);
  googleProvider = new GoogleAuthProvider();
}

// Google Sign-In helper (redirect-based for PWA WebView compatibility)
export const loginWithGoogle = async () => {
  if (!auth) throw new Error("Firebase is not configured.");
  try {
    await signInWithRedirect(auth, googleProvider);
  } catch (error) {
    console.error("Google Sign-In Redirect Error:", error);
    throw error;
  }
};

// Log out helper
export const logoutUser = () => {
  if (!auth) return Promise.resolve();
  return signOut(auth);
};

// Active Inventory collection: /users/{userId}/inventory
export const getInventoryRef = (userId) => {
  if (!db) return null;
  return collection(db, 'users', userId, 'inventory');
};

// History Log collection: /users/{userId}/history
export const getHistoryRef = (userId) => {
  if (!db) return null;
  return collection(db, 'users', userId, 'history');
};

// Add new wine bottle to active inventory
export const addWineToInventory = async (userId, wineData) => {
  if (!db) throw new Error("Database is not configured.");
  const ref = getInventoryRef(userId);
  return addDoc(ref, {
    ...wineData,
    addedAt: serverTimestamp()
  });
};

// Pop the cork: move a bottle from active inventory to history log, capturing user feedback
export const popCork = async (userId, wineId, wineData, liked) => {
  if (!db) throw new Error("Database is not configured.");
  try {
    // 1. Add to history
    const historyRef = getHistoryRef(userId);
    await addDoc(historyRef, {
      name: wineData.name || 'Unknown Wine',
      year: wineData.year || 'N/A',
      varietal: wineData.varietal || 'N/A',
      photoUrl: wineData.photoUrl || '',
      addedAt: wineData.addedAt || null,
      poppedAt: serverTimestamp(),
      liked: liked // boolean: true (loved it) / false (not a fan)
    });

    // 2. Remove from active inventory
    const docRef = doc(db, 'users', userId, 'inventory', wineId);
    await deleteDoc(docRef);
  } catch (error) {
    console.error("Error popping cork:", error);
    throw error;
  }
};

export { auth, db };
