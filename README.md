# 🍇 JR Wine Inventory

A premium, modern, multi-user digital wine cellar, catalog, and AI-powered sommelier assistant. Designed for circles of friends who want to share, track, and explore wines together, this platform provides a consumer-friendly, jargon-free gateway to wine education and cellar management.

---

## 🍇 App Overview & Value Proposition

**JR Wine Cellar** is a private, lightweight, and highly interactive wine inventory platform built to remove the intimidation factor from wine collection. Instead of using snobby, academic wine descriptions, the app uses everyday language to help users learn about what is in their glass. 

### Why JR Wine Cellar?
- **Zero Snobbery:** Educational profiles focus on tactile descriptors, home-cooked food pairings, and fun historical takeaways.
- **Instant Digitalization:** Vision-based label scanning means you can digitize your collection in seconds.
- **Social & Isolated:** Access your private collection under a unified sheet database via secure personal entry keys.
- **Tailored Sommelier:** A conversational assistant that knows exactly what you have in stock and how you rated past bottles.

---

## 📱 Key Features & User Guide

The application is structured into four functional tab ecosystems to streamline the intake, tracking, consumption, and discussion of your wine collection:

```
┌────────────────────────────────────────────────────────┐
│                    JR Wine Cellar                      │
├──────────────┬──────────────┬──────────────┬───────────┤
│ Log a Bottle │ Active Cellar│ Cellar Hist. │ Cellar Chat│
└──────────────┴──────────────┴──────────────┴───────────┘
```

### 1. ➕ Log a Bottle
* **Camera Scanner (Single & Bulk):** Upload one or more label images. Scenario A (exactly one image) parses the label via Gemini Vision and immediately auto-populates the input form. Scenario B (multiple images) processes them sequentially and lists them in a review queue for one-click bulk confirmation.
* **Smart Appending Prompt:** The Gemini vision extractor automatically identifies special designations (e.g. Reserve, Cuvée, Single Vineyard) and appends them in parentheses next to the varietal (e.g. *Zinfandel (Eight Spur)*).
* **Dual Action Intake:**
  - **📦 Storing it in my cellar:** Adds the bottle to active stock or increments the quantity count if it already exists.
  - **🍷 Drinking it right now!:** Bypasses active inventory checking, requests an immediate rating, and appends it directly to your cellar history with status `"Drank"`.

### 2. 🍷 Active Cellar
* **Metric Cards:** Displays current stats for total active bottles and unique grape varieties in stock.
* **Space-Saving Quantity Tracker:** Grouped by unique wine profile characteristics, preventing duplicate rows for identical bottles.
* **Interactive Post-Drink Intercept:** Clicking **"🍷 Bottle Finished"** opens an inline rating selector: *"We hope you enjoyed it! How would you rate this specific bottle before we update your inventory? [Loved | Liked | Disliked | None]"*. Decrements the quantity by 1, or shifts the status to `"Drank"` if it was the last bottle in stock.
* **📋 Share Details:** Generate a beautifully formatted plain-text sharing card containing origin details, tasting notes, and pairings to text to a friend, copied directly via Streamlit's native copy-to-clipboard code widget.

### 3. 📜 Cellar History
* **Sorting:** Consumed bottles sorted with the most recently drunk entries displayed at the top.
* **"⭐ My Favorites" Toggle:** Instantly filters history to display only bottles marked as **"Loved"** or **"Liked"** to serve as a smart grocery shopping list for future repurchases.
* **Restoration Checkbox:** Check the restore box next to any entry to instantly return a consumed bottle back to active stock with its rating reset to `"None"`.

### 4. 💬 Cellar Chat
* **Personalized Context Sommelier:** An interactive chatbot powered by Gemini (operating at temperature `0.3`). The prompt dynamically injects your current stock list and your rated taste history.
* **Context Fallback Priority System:**
  1. *Primary:* Suggests matching bottles currently available to pull from your **Active Cellar**.
  2. *Secondary:* Recommends styles, regions, and grape varieties that mirror bottles you marked as `"Loved"` or `"Liked"` in your history.
  3. *Fallback:* If your cellar is empty or lacks matching styles, provides conversational retail purchase suggestions you should buy at the store, clearly noting that it is a retail match.

---

## 🛠️ Technical Architecture & Stack

```
               [ User Device ] 
                      │  (Camera Images / Text Query)
                      ▼
            [ Streamlit Frontend ] <───> [ In-Memory Cache (Pandas) ]
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
     [ Gemini API ]      [ Google Sheets DB ]
 (Vision / Chat Model)      (gspread CRUD)
```

- **Frontend/UI:** Built with Python-native **Streamlit Cloud** styled using custom CSS overrides. Customizations include glassmorphic card elements, custom Outfit typography, and glowing borders.
- **AI Core Engine:** Employs the official **Google GenAI SDK** targeting custom-configured environment models. Uses a zero-temperature config for label parsing (deterministic output) and `temperature=0.3` for cellar chat conversations.
- **In-Memory Performance Layer:**
  - **Image Compression:** Employs PIL auto-orientation (EXIF Transpose), scale downsampling (1024px maximum bounds), and 80% quality JPEG conversion. This reduces massive iPhone raw camera photos down to lightweight ~200KB payloads to maintain speed over mobile data networks.
  - **Database Caching:** Caches the entire spreadsheet array inside `st.session_state["full_wine_df"]`. Live API calls via `sheet.get_all_values()` only trigger on initial login or when `refresh_needed` is flagged `True`.
- **Database Architecture:** Uses a **Google Sheets API** back-end managed with the `gspread` library. Employs Pandas vector logic to match rows, updating sheets using single-range coordinate calls (`sheet.update("F2:G2", ...)`) to eliminate sluggish cell loops. Multi-user isolation is enforced dynamically by partitioning reads/writes based on unique `user_code` fields.

---

## 🔑 Getting Started & Configuration

### 📊 Database Schema Layout
Your Google Sheet must contain two worksheets: `Sheet1` (Wine data) and `Authorized_Users` (Access codes).

#### Sheet1 (Wine Ledger) Columns:
`["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"]`

#### Authorized_Users Columns:
`["access_code", "name"]`

---

### 🚀 Local Deployment Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Streamlit Secrets:**
   Create a `.streamlit/secrets.toml` file in your root folder:
   ```toml
   [auth]
   gemini_api_key = "AIzaSyYourGeminiAPIKeyHere"
   target_model = "gemini-flash-latest"

   [allowed_users]
   usercode1234 = "Friend Name"
   usercode5678 = "Second Friend"

   [gcp_service_account]
   type = "service_account"
   project_id = "your-gcp-project-id"
   private_key_id = "your-key-id"
   private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7...\n-----END PRIVATE KEY-----\n"
   client_email = "service-account@your-gcp-project.iam.gserviceaccount.com"
   client_id = "12345678901234567890"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/service-account..."
   universe_domain = "googleapis.com"
   ```

3. **Run Application:**
   ```bash
   streamlit run app.py
   ```
