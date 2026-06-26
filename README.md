# 🍇 JR Wine Inventory - Developer Documentation

A high-performance, developer-focused, multi-user digital wine cellar, catalog, and AI sommelier platform. This project leverages **Streamlit** for the frontend UI, **Pandas** for high-speed in-memory state caching, **Google Sheets API (gspread)** for a lightweight relational backend database, and the **Google GenAI SDK** for vision-based label extraction and conversational AI.

---

## 🛠️ Architecture Overview

```
                 [ User Device / Browser ]
                            │  (Image Uploads / Chat Prompts)
                            ▼
              ┌───────────────────────────┐
              │    Streamlit Web App      │ <──> [ In-Memory Cache (Pandas) ]
              └───────────────────────────┘
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
         [ Gemini API ]         [ Google Sheets DB ]
      (Vision / Chat Model)       (gspread Client)
```

The application runs as a Python-native Streamlit dashboard. Performance bottlenecks associated with Google Sheets network latency are mitigated by caching all sheet data in-memory inside the Streamlit session state and executing batch writes.

### Core Stack
- **Web App**: [Streamlit](https://streamlit.io/)
- **Data Manipulation**: [Pandas](https://pandas.pydata.org/)
- **Database Backend**: [Google Sheets API via gspread](https://github.com/nolar/gspread)
- **AI/LLM Engine**: [Google GenAI SDK](https://github.com/google/generative-ai-python)
- **Image Operations**: [Pillow (PIL)](https://python-pillow.org/)

---

## 📊 Database Schema Layout

The database backend is modeled on a single Google Sheet containing two worksheets:

### 1. `Sheet1` (Wine Ledger)
Stores active, archived, and consumed (drank) wines for all users.
* **Schema**: `["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"]`
* **Column Types**:
  * `user_code`: `str` (partitioning key for user isolation)
  * `id`: `int` (incremental row identifier per user)
  * `winery`: `str` (winery/brand name)
  * `varietal`: `str` (grape type or blend)
  * `vintage`: `Int64` (nullable integer representing the harvest year)
  * `status`: `str` (`"Active"`, `"Drank"`, or `"Archived"`)
  * `rating`: `str` (`"Loved"`, `"Liked"`, `"Disliked"`, or `"None"`)
  * `wine_101`: `str` (JSON/Text block representing tasting profiles)
  * `quantity`: `int` (number of physical bottles available)

### 2. `Authorized_Users` (Access Control)
Validates credentials during login and maps codes to user profiles.
* **Schema**: `["access_code", "name"]`
* **Column Types**:
  * `access_code`: `str` (unique sign-in credential)
  * `name`: `str` (display name for greeting)

---

## ⚙️ Key Technical Features & Implementations

### 1. In-Memory Cache Sync & Race Condition Prevention
To prevent sluggish sheet queries on every page reload, the dataset is loaded once upon authentication and stored in `st.session_state["full_wine_df"]`. 
* **Write-Through Caching**: Any insert, delete, or update operation writes to the Google Sheet first and then immediately syncs the local `full_wine_df` DataFrame in-place using `.loc` index updates or `pd.concat` for inserts.
* **Refresh Flags**: Setting `st.session_state["refresh_needed"] = True` ensures the app pulls fresh sheet data if an out-of-sync state is detected.

### 2. Batch Network Operations
To prevent Google Sheets API rate-limiting and minimize network latency, cell updates are grouped:
* In `restore_wine`, the `status` and `rating` columns are written in a single execution using a range update `sheet.update("F2:G2", [["Active", "None"]])` rather than triggering individual cell updates.

### 3. Image Compression Pipeline
High-resolution camera uploads are downsampled before they are transmitted to the Gemini API to decrease latency and bandwidth consumption:
1. **EXIF Alignment**: Automatically rotates images to their correct orientation using PIL `ImageOps.exif_transpose`.
2. **Dimension Clamping**: Proportionally resizes any image exceeding `1024px` on its longest side.
3. **JPEG Compression**: Converts images to the JPEG format at `80%` quality, reducing typical files from `5MB+` down to under `200KB`.

### 4. AI structured Label Parsing & Guardrails
The label scanner uses `gemini-1.5-flash` with the following parameters:
* **Temperature**: Clamped to `0.0` for deterministic metadata extraction.
* **Instructions**: The prompt restricts hallucinated values, forcing the model to fallback to generic grape info if winery-specific details are missing.
* **Duplicate Aggregation**: Prior to processing, the upload list is aggregated to group identical labels, performing a single Gemini call and updating the final table's quantity field.

### 5. Conversational Sommelier Chat Architecture
The chatbot operates on a `0.3` temperature setting. It dynamically builds its context window with:
1. The user's active wine list.
2. The user's historical ratings (favorites are prioritized).
3. System instructions restricting recommendations to the user's cellar stock first, falling back to historical matches and retail suggestions.

### 6. Interactive UI & Theme Tokens
Built with custom CSS overrides (`inject_custom_css`) injecting:
* Glassmorphism layout styling (`backdrop-filter: blur(10px)`)
* Custom Outfit Typography imports
* Multi-column responsive layout structures (side-by-side forms on single files, full-width data tables during bulk imports).

---

## 🚀 Setup & Installation

### Prerequisites
- Python `3.9` or higher
- A Google Cloud Project with the Google Sheets and Google Drive APIs enabled
- A service account key in JSON format (GCP credentials)
- A Gemini API key

### 1. Local Deployment
Staging is managed locally using Streamlit's environment framework.

1. **Clone & Navigate**:
   ```bash
   git clone <repo-url>
   cd jr-wine-inventory
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Secrets**:
   Create a `.streamlit/secrets.toml` file:
   ```toml
   [auth]
   gemini_api_key = "AIzaSyYourGeminiAPIKeyHere"
   target_model = "gemini-1.5-flash"

   [allowed_users]
   usercode1234 = "Developer User"

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

4. **Launch Local Server**:
   ```bash
   streamlit run app.py
   ```
