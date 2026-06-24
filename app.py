import streamlit as st
import pandas as pd
import datetime
from google import genai
from google.genai import types
from PIL import Image
import io
import json
import gspread
from google.oauth2.service_account import Credentials

# Set page configuration first
st.set_page_config(
    page_title="JR Wine Inventory",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Google Sheets Setup ---
@st.cache_resource
def get_gspread_client():
    # Convert secrets AttrDict to standard dict before passing to credentials parser
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
    elif "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
    else:
        raise Exception("GCP service account credentials not found in st.secrets.")
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_wine_worksheets():
    client = get_gspread_client()
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1OXY3blai3bGKOTytbBtV6ScLoTaKq-241dl2ee-BG5I/edit"
    spreadsheet = client.open_by_url(spreadsheet_url)
    
    # .sheet1 always grabs the very first tab safely
    wine_sheet = spreadsheet.sheet1 
    user_sheet = spreadsheet.worksheet("Authorized_Users")
    return wine_sheet, user_sheet

def init_sheet_if_empty(sheet):
    try:
        values = sheet.get_all_values()
        if not values:
            headers = ["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"]
            sheet.append_row(headers)
    except Exception as e:
        st.error(f"Error checking or initializing sheet: {e}")

def read_all_wines(sheet) -> pd.DataFrame:
    try:
        # Check if full_wine_df is in session state and we don't need refresh
        if "full_wine_df" in st.session_state and not st.session_state.get("refresh_needed", False):
            df = st.session_state["full_wine_df"]
        else:
            records = sheet.get_all_records()
            if not records:
                df = pd.DataFrame(columns=["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"])
            else:
                df = pd.DataFrame(records)
            
            # Ensure all columns exist
            expected_cols = ["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
                    
            # Normalize data types
            df["user_code"] = df["user_code"].fillna("").astype(str)
            df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
            df["vintage"] = pd.to_numeric(df["vintage"], errors="coerce").astype("Int64")
            df["winery"] = df["winery"].fillna("").astype(str)
            df["varietal"] = df["varietal"].fillna("").astype(str)
            df["status"] = df["status"].fillna("Active").astype(str)
            df["rating"] = df["rating"].fillna("None").astype(str)
            df["wine_101"] = df["wine_101"].fillna("").astype(str)
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
            
            st.session_state["full_wine_df"] = df
            st.session_state["refresh_needed"] = False
            
        # Filter by logged-in user code
        user_code = st.session_state.get("user_code")
        if user_code:
            filtered_df = df[df["user_code"] == str(user_code)].copy()
        else:
            filtered_df = df.iloc[0:0].copy()
            
        return filtered_df
    except Exception as e:
        # Fallback to init if sheet has issues
        init_sheet_if_empty(sheet)
        return pd.DataFrame(columns=["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"])

def add_wine(sheet, user_code: str, winery: str, varietal: str, vintage, wine_101: str, quantity: int = 1) -> bool:
    try:
        values = sheet.get_all_values()
        if not values:
            return False
            
        headers = values[0]
        rows = values[1:]
        max_len = len(headers)
        padded_rows = [r + [""] * (max_len - len(r)) if len(r) < max_len else r[:max_len] for r in rows]
        df_all = pd.DataFrame(padded_rows, columns=headers)
        
        def parse_vintage(v):
            if v is None:
                return None
            v_str = str(v).strip()
            if v_str == "" or v_str.lower() in ["none", "nan", "null", "<na>"]:
                return None
            try:
                return int(float(v_str))
            except ValueError:
                return None

        # Convert vintages in df to integers for clean comparison
        df_all["parsed_vintage"] = df_all["vintage"].apply(parse_vintage)
        target_vintage = parse_vintage(vintage)
        
        match = df_all[
            (df_all["user_code"] == str(user_code)) &
            (df_all["status"] == "Active") &
            (df_all["winery"].str.strip().str.lower() == winery.strip().lower()) &
            (df_all["varietal"].str.strip().str.lower() == varietal.strip().lower()) &
            (df_all["parsed_vintage"] == target_vintage)
        ]
        
        if not match.empty:
            # Match found, increment quantity
            row_num = match.index[0] + 2
            matched_row = values[row_num - 1]
            current_qty = 1
            if len(matched_row) > 8:
                try:
                    current_qty = int(float(str(matched_row[8]).strip()))
                except ValueError:
                    current_qty = 1
            new_qty = current_qty + quantity
            sheet.update_cell(row_num, 9, new_qty)
            st.session_state["refresh_needed"] = True
            return True
        else:
            # No match found, generate new ID and append row
            df_filtered = read_all_wines(sheet)
            new_id = 1 if df_filtered.empty else int(df_filtered["id"].max()) + 1
            vintage_val = "" if (vintage is None or pd.isna(vintage)) else int(vintage)
            row = [user_code, new_id, winery, varietal, vintage_val, "Active", "None", wine_101, quantity]
            sheet.append_row(row)
            st.session_state["refresh_needed"] = True
            return True
    except Exception as e:
        st.error(f"Failed to save bottle to Google Sheets: {e}")
        return False

def update_wine_status(sheet, user_code: str, wine_id: int, status: str) -> bool:
    try:
        values = sheet.get_all_values()
        if not values:
            return False
            
        headers = values[0]
        rows = values[1:]
        max_len = len(headers)
        padded_rows = [r + [""] * (max_len - len(r)) if len(r) < max_len else r[:max_len] for r in rows]
        df_all = pd.DataFrame(padded_rows, columns=headers)
        
        df_all["id"] = pd.to_numeric(df_all["id"], errors="coerce")
        match = df_all[(df_all["user_code"] == str(user_code)) & (df_all["id"] == int(wine_id))]
        
        if match.empty:
            st.error(f"Bottle ID {wine_id} not found in sheet for user {user_code}.")
            return False
            
        row_num = match.index[0] + 2
        sheet.update_cell(row_num, 6, status)  # Column 6 is 'status'
        st.session_state["refresh_needed"] = True
        return True
    except Exception as e:
        st.error(f"Failed to update status in Google Sheets: {e}")
        return False

def update_wine_rating(sheet, user_code: str, wine_id: int, rating: str) -> bool:
    try:
        values = sheet.get_all_values()
        if not values:
            return False
            
        headers = values[0]
        rows = values[1:]
        max_len = len(headers)
        padded_rows = [r + [""] * (max_len - len(r)) if len(r) < max_len else r[:max_len] for r in rows]
        df_all = pd.DataFrame(padded_rows, columns=headers)
        
        df_all["id"] = pd.to_numeric(df_all["id"], errors="coerce")
        match = df_all[(df_all["user_code"] == str(user_code)) & (df_all["id"] == int(wine_id))]
        
        if match.empty:
            st.error(f"Bottle ID {wine_id} not found in sheet for user {user_code}.")
            return False
            
        row_num = match.index[0] + 2
        sheet.update_cell(row_num, 7, rating)  # Column 7 is 'rating'
        st.session_state["refresh_needed"] = True
        return True
    except Exception as e:
        st.error(f"Failed to update rating in Google Sheets: {e}")
        return False

def mark_bottle_as_drank(sheet, user_code: str, wine_id: int, rating: str) -> bool:
    try:
        values = sheet.get_all_values()
        if not values:
            return False
            
        headers = values[0]
        rows = values[1:]
        max_len = len(headers)
        padded_rows = [r + [""] * (max_len - len(r)) if len(r) < max_len else r[:max_len] for r in rows]
        df_all = pd.DataFrame(padded_rows, columns=headers)
        
        df_all["id"] = pd.to_numeric(df_all["id"], errors="coerce")
        match = df_all[(df_all["user_code"] == str(user_code)) & (df_all["id"] == int(wine_id))]
        
        if match.empty:
            st.error(f"Bottle ID {wine_id} not found in sheet for user {user_code}.")
            return False
            
        row_num = match.index[0] + 2
        matched_row = values[row_num - 1]
        
        current_qty = 1
        if len(matched_row) > 8:
            try:
                current_qty = int(float(str(matched_row[8]).strip()))
            except ValueError:
                current_qty = 1
        
        if current_qty > 1:
            new_qty = current_qty - 1
            sheet.update_cell(row_num, 9, new_qty)  # Column 9 is quantity
        else:
            sheet.update(f"F{row_num}:G{row_num}", [["Drank", rating]])  # F and G are status and rating
            
        st.session_state["refresh_needed"] = True
        return True
    except Exception as e:
        st.error(f"Failed to mark bottle as drank: {e}")
        return Falselse


# --- Styling & CSS ---
def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
            
            /* Global Font Settings */
            html, body, [class*="css"], .stApp {
                font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
                background-color: #0F0C0F;
            }
            
            /* Glassmorphic Cards for Wine List / Detail Panel */
            .wine-card {
                background: rgba(27, 23, 28, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 16px;
                margin-top: 12px;
                margin-bottom: 8px;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                backdrop-filter: blur(10px);
            }
            .wine-card:hover {
                border-color: rgba(122, 28, 60, 0.4);
                background: rgba(35, 29, 36, 0.8);
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            }
            
            /* Typography */
            .wine-title {
                font-size: 1.15rem;
                font-weight: 600;
                color: #F2EDF2;
            }
            .wine-subtitle {
                font-size: 0.95rem;
                color: #B4A9B5;
                margin-top: 2px;
            }
            .wine-meta {
                font-size: 0.9rem;
                color: #C5A059;
                font-weight: 500;
            }
            
            /* Form Custom Styling */
            .stForm {
                background: rgba(27, 23, 28, 0.4) !important;
                border: 1px solid rgba(255, 255, 255, 0.05) !important;
                border-radius: 14px !important;
                padding: 24px !important;
                box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2);
            }
            
            /* Input borders and focus state */
            input, select, textarea {
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                background-color: rgba(255, 255, 255, 0.03) !important;
                color: #F2EDF2 !important;
            }
            
            /* Premium Button Styling */
            .stButton>button {
                border-radius: 8px !important;
                border: 1px solid rgba(197, 160, 89, 0.3) !important;
                background-color: rgba(122, 28, 60, 0.25) !important;
                color: #F2EDF2 !important;
                font-weight: 500 !important;
                transition: all 0.25s ease !important;
                width: 100%;
                padding: 8px 16px !important;
            }
            .stButton>button:hover {
                background-color: #7A1C3C !important;
                border-color: #C5A059 !important;
                color: white !important;
                box-shadow: 0 4px 12px rgba(122, 28, 60, 0.3);
            }
            
            /* Secondary Button Styling for Restore */
            .restore-btn button {
                background-color: rgba(255, 255, 255, 0.05) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
            }
            .restore-btn button:hover {
                background-color: rgba(255, 255, 255, 0.15) !important;
                border-color: rgba(255, 255, 255, 0.3) !important;
                color: white !important;
            }
            
            /* Hide Streamlit components */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

def get_rating_badge_html(rating):
    colors = {
        "Loved": "background-color: rgba(212, 175, 55, 0.15); color: #D4AF37; border: 1px solid rgba(212, 175, 55, 0.3);",
        "Liked": "background-color: rgba(78, 190, 146, 0.15); color: #4EBE92; border: 1px solid rgba(78, 190, 146, 0.3);",
        "Disliked": "background-color: rgba(255, 102, 106, 0.15); color: #FF666A; border: 1px solid rgba(255, 102, 106, 0.3);",
        "None": "background-color: rgba(255, 255, 255, 0.05); color: #B4A9B5; border: 1px solid rgba(255, 255, 255, 0.08);"
    }
    style = colors.get(rating, colors["None"])
    return f'<span style="padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; {style}">{rating}</span>'

def extract_101_field(text: str, field_name: str) -> str:
    import re
    # Match both "**FieldName:** value" and "**FieldName** value"
    pattern = rf"\*\*{field_name}:?\*\*\s*(.*?)(?=\s*\*\*|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "N/A"

# Apply the theme styling
inject_custom_css()

# Helper function to generate Wine 101 description using Gemini
def generate_wine_101(winery: str, varietal: str, vintage) -> str:
    try:
        api_key = st.secrets["auth"]["gemini_api_key"]
    except KeyError:
        api_key = None
        
    if not api_key:
        return "Summary loading... refresh or edit rating to retry."
    
    try:
        model_env = st.secrets["auth"].get("target_model", "gemini-flash-latest")
        client = genai.Client(api_key=api_key)
        vintage_str = "current release" if (vintage is None or pd.isna(vintage)) else str(int(vintage))
        
        prompt = f"""Provide a clean, professional, and simple wine 101 overview for a {vintage_str} {winery} {varietal}. Keep it simple, plain English only, and strictly adhere to these guidelines:

1. Vocabulary Constraints:
- Absolutely FORBID the use of these academic wine words: "structured", "tannic", "acidic", "minerality", "terroir", or "finish".
- For texture/mouthfeel, explain it in everyday tactile terms. E.g., instead of "structured finish", say "leaves a bold, rich, slightly mouth-drying feel that lingers pleasantly".
- For Tasting Notes, strictly use edible/familiar items that an everyday person eats or smells. FORBID non-edible terms like "cedar", "tobacco", "forest floor", "graphite", or "Mediterranean herbs". Instead, use accessible markers like "subtle vanilla/oak", "baking spices", "dried rosemary", "ripe cherries", or "dark chocolate".
- For Serving, forbid vague statements like "serve chilled" or "serve below room temperature". Instead, require specific, practical time-tricks (e.g. "Pop it in the fridge for 15–20 minutes before pouring to take the warm edge off" or "Serve ice-cold straight from the fridge").

2. Layout Guidelines:
Your response must strictly follow this exact 6-part layout using bold inline labels (no emojis in the labels, no large headers):

**Overview:** [One clean, conversational sentence describing the body and taste vibe, without using banned words]
**Origin:** [Region, Country]
**Tasting Notes:** [3 or 4 familiar flavors separated by vertical pipes, e.g. 🍒 Dark Cherries | 🍓 Ripe Strawberries | 🪵 A hint of vanilla/oak]
**Pairings:** [One easy home-cooked option and one casual takeout or snack option]
**Serving & Timeline:** [Practical temperature time-trick + clear advice on when to drink it]
**Fun Fact:** [One punchy, interesting takeaway about the winery, region, or grape history]

Ensure the output strictly returns clean markdown text using the bold labels as shown above to fit inside our detail panel container."""
        
        response = client.models.generate_content(
            model=model_env,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return "Summary loading... refresh or edit rating to retry."


# --- Gatekeeper Login Wall ---
if "user_code" not in st.session_state:
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    c_left, c_mid, c_right = st.columns([1, 2, 1])
    with c_mid:
        st.markdown("<h3 style='text-align: center; color: #B4A9B5;'>🍷 Cellar Entry</h3>", unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            access_code_input = st.text_input("Enter your Cellar Access Code", type="password")
            login_submitted = st.form_submit_button("🔑 Unlock Cellar")
            
            if login_submitted:
                if not access_code_input.strip():
                    st.error("Please enter an access code.")
                else:
                    with st.spinner("Verifying authorization..."):
                        try:
                            # Query Authorized_Users worksheet
                            _, auth_sheet = get_wine_worksheets()
                            users_records = auth_sheet.get_all_records()
                            
                            # Find matching code
                            match = None
                            for r in users_records:
                                code = str(r.get("access_code", "")).strip()
                                name = str(r.get("name", "")).strip()
                                if code == access_code_input.strip():
                                    match = (code, name)
                                    break
                            
                            if match:
                                st.session_state["user_code"] = match[0]
                                st.session_state["user_name"] = match[1]
                                st.toast(f"Welcome back, {match[1]}! 🍾")
                                st.rerun()
                            else:
                                st.error("Access code not recognized. Check with Jason!")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
        st.stop()


# --- Main Application Code (Authenticated) ---
# Connect to Google Sheets
try:
    sheet, _ = get_wine_worksheets()
    init_sheet_if_empty(sheet)
except Exception as conn_err:
    st.error(f"Could not connect to Google Sheets: {conn_err}")
    st.stop()

# Handle toast message queue across reruns
if "toast_message" in st.session_state:
    msg, icon = st.session_state.pop("toast_message")
    st.toast(msg, icon=icon)

# Initialize session state variables for prefilling wine label scans
if "prefill_winery" not in st.session_state:
    st.session_state["prefill_winery"] = ""
if "prefill_varietal" not in st.session_state:
    st.session_state["prefill_varietal"] = ""
if "prefill_vintage" not in st.session_state:
    st.session_state["prefill_vintage"] = None
if "last_scanned_file" not in st.session_state:
    st.session_state["last_scanned_file"] = None
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# Smart loading with Session State cache to prevent laggy search inputs
if "df" not in st.session_state or st.session_state.get("refresh_needed", False):
    with st.spinner("Fetching stock from Google Sheets..."):
        st.session_state["df"] = read_all_wines(sheet)
        st.session_state["refresh_needed"] = False

df = st.session_state["df"]

# Header layout with welcoming banner & Sign Out button
col_title, col_user = st.columns([2, 1])
with col_title:
    st.markdown("<h2 style='margin: 0; padding: 0;'>🍇 JR Wine Cellar</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #B4A9B5; margin: 4px 0 0 0;'>👋 Welcome, {st.session_state['user_name']}!</p>", unsafe_allow_html=True)
with col_user:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True) # spacing
    if st.button("🚪 Sign Out", key="sign_out_btn"):
        st.session_state.clear()
        st.rerun()

# Check the logged-in user's active bottle DataFrame count before rendering the tabs
active_wines = df[df["status"] == "Active"].copy()
if "cellar_tabs" not in st.session_state:
    if len(active_wines) == 0:
        st.session_state["cellar_tabs"] = "➕ Log a Bottle"
    else:
        st.session_state["cellar_tabs"] = "🍷 Active Cellar"

# Create tabs for inventory navigation
tab_add, tab_active, tab_history = st.tabs(["➕ Log a Bottle", "🍷 Active Cellar", "📜 Cellar History"], key="cellar_tabs")

# Tab 1: Log a Bottle (Add Bottle Form & Gemini Scanner)
with tab_add:
    st.subheader("Log a New Bottle")
    with st.expander("➕ Log a New Bottle", expanded=True):
        # Create two columns for Scanner UI and Manual Entry Form
        col_scan, col_form = st.columns([1, 1])
        
        with col_scan:
            st.markdown("### 📷 Scan a Bottle Label")
            uploaded_files = st.file_uploader(
                "Upload photo(s) of the wine label to scan",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key=f"wine_label_uploader_{st.session_state['uploader_key']}"
            )
            
            # Reset scanned file tracking if cleared
            if not uploaded_files:
                if st.session_state.get("last_scanned_file") is not None:
                    st.session_state["last_scanned_file"] = None
                if "bulk_scan_cache" in st.session_state:
                    st.session_state["bulk_scan_cache"] = {}
                    
            # Gemini processing block
            if uploaded_files:
                # Initialize bulk_scan_cache if not present
                if "bulk_scan_cache" not in st.session_state:
                    st.session_state["bulk_scan_cache"] = {}
                
                # Filter out files no longer uploaded
                current_filenames = [f.name for f in uploaded_files]
                for k in list(st.session_state["bulk_scan_cache"].keys()):
                    if k not in current_filenames:
                        st.session_state["bulk_scan_cache"].pop(k)
                
                # Scan any file that isn't cached yet
                total_files = len(uploaded_files)
                for idx, f in enumerate(uploaded_files):
                    if f.name not in st.session_state["bulk_scan_cache"]:
                        status_placeholder = st.empty()
                        status_placeholder.info(f"Processing label {idx + 1} of {total_files}: {f.name}...")
                        try:
                            with st.spinner(f"Analyzing {f.name} with Gemini..."):
                                f.seek(0)
                                image_data = f.read()
                                image = Image.open(io.BytesIO(image_data))
                                
                                # Auto-orient
                                try:
                                    from PIL import ImageOps
                                    image = ImageOps.exif_transpose(image)
                                except Exception:
                                    pass
                                
                                # Check if image needs resizing
                                max_dimension = 1024
                                width, height = image.size
                                if width > max_dimension or height > max_dimension:
                                    if width > height:
                                        new_width = max_dimension
                                        new_height = int(height * (max_dimension / width))
                                    else:
                                        new_height = max_dimension
                                        new_width = int(width * (max_dimension / height))
                                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                
                                # Compress
                                if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                                    image = image.convert("RGB")
                                elif image.mode != "RGB":
                                    image = image.convert("RGB")
                                    
                                compressed_io = io.BytesIO()
                                image.save(compressed_io, format="JPEG", quality=80)
                                compressed_io.seek(0)
                                compressed_image = Image.open(compressed_io)
                                
                                # Call Gemini
                                api_key = st.secrets["auth"].get("gemini_api_key")
                                if not api_key:
                                    st.error("Gemini API Key is missing in st.secrets.")
                                    break
                                    
                                client = genai.Client(api_key=api_key)
                                model_env = st.secrets["auth"].get("target_model", "gemini-flash-latest")
                                
                                prompt = (
                                    "You are a precise data extraction tool. Analyze this wine bottle label image.\n"
                                    "Strictly extract the following three fields and return them as a clean JSON object:\n"
                                    "1. 'winery': The exact producer or vineyard name. If unclear, use the most prominent brand text.\n"
                                    "2. 'varietal': The grape variety or blend (e.g., Cabernet Sauvignon, Red Blend). If not explicitly stated, infer it based on the region or style visible.\n"
                                    "3. 'vintage': The 4-digit production year. Look closely at the neck, front, and bottom labels. If absolutely no year is visible, return null.\n\n"
                                    "Rules:\n"
                                    "- Do not include any conversational text or markdown code blocks outside of the raw JSON.\n"
                                    "- If a field cannot be found, use null instead of guessing."
                                )
                                
                                response = client.models.generate_content(
                                    model=model_env,
                                    contents=[compressed_image, prompt],
                                    config=types.GenerateContentConfig(
                                        response_mime_type="application/json",
                                        temperature=0.0
                                    )
                                )
                                
                                # Parse JSON response
                                cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
                                result = json.loads(cleaned_text)
                                
                                # Validate/convert vintage
                                vintage_val = result.get("vintage")
                                if vintage_val is not None:
                                    try:
                                        vintage_val = int(vintage_val)
                                        if vintage_val < 1800 or vintage_val > 2100:
                                            vintage_val = None
                                    except Exception:
                                        vintage_val = None
                                        
                                st.session_state["bulk_scan_cache"][f.name] = {
                                    "winery": result.get("winery", ""),
                                    "varietal": result.get("varietal", ""),
                                    "vintage": vintage_val
                                }
                        except Exception as ex:
                            st.error(f"Error scanning {f.name}: {ex}")
                            st.session_state["bulk_scan_cache"][f.name] = {
                                "winery": "Error scanning",
                                "varietal": "Error scanning",
                                "vintage": None
                            }
                        finally:
                            status_placeholder.empty()
                
                # Single or Multiple file UI handling
                if len(uploaded_files) == 1:
                    # Single file uploaded: Auto-prefill (original behavior)
                    single_file = uploaded_files[0]
                    res = st.session_state["bulk_scan_cache"].get(single_file.name)
                    if res and st.session_state.get("last_scanned_file") != single_file.name:
                        st.session_state["prefill_winery"] = res["winery"]
                        st.session_state["prefill_varietal"] = res["varietal"]
                        st.session_state["prefill_vintage"] = res["vintage"]
                        st.session_state["last_scanned_file"] = single_file.name
                        st.toast("Label scanned and form auto-filled!")
                        st.rerun()
                        
                    # Show preview
                    st.image(single_file, caption="Uploaded Label Preview", use_column_width=True)
                else:
                    # Multiple files uploaded: Bulk scan UI
                    st.markdown("### 📋 Bulk Scan Review")
                    
                    display_list = []
                    for f in uploaded_files:
                        res = st.session_state["bulk_scan_cache"].get(f.name, {})
                        display_list.append({
                            "File Name": f.name,
                            "Winery": res.get("winery", ""),
                            "Varietal": res.get("varietal", ""),
                            "Vintage": res.get("vintage", None)
                        })
                    
                    review_df = pd.DataFrame(display_list)
                    st.dataframe(review_df, use_container_width=True, hide_index=True)
                    
                    with st.expander("🖼️ View Uploaded Previews", expanded=False):
                        for f in uploaded_files:
                            try:
                                f.seek(0)
                                st.image(f, caption=f.name, use_column_width=True)
                            except:
                                pass
                                
                    if st.button("✨ Confirm & Add All to Cellar", key="bulk_confirm_btn"):
                        success_count = 0
                        with st.spinner("Saving batch to Cellar..."):
                            for row_data in display_list:
                                winery_val = row_data["Winery"]
                                varietal_val = row_data["Varietal"]
                                vintage_val = row_data["Vintage"]
                                
                                if winery_val == "Error scanning" or not winery_val.strip():
                                    continue
                                    
                                # Generate Wine 101 for each
                                wine_101_val = generate_wine_101(winery_val.strip(), varietal_val.strip(), vintage_val)
                                if add_wine(sheet, st.session_state["user_code"], winery_val.strip(), varietal_val.strip(), vintage_val, wine_101_val, 1):
                                    success_count += 1
                                    
                        if success_count > 0:
                            st.session_state["refresh_needed"] = True
                            st.session_state["bulk_scan_cache"] = {}
                            st.session_state["uploader_key"] += 1
                            st.session_state["toast_message"] = (f"🍾 {success_count} bottle(s) saved to cellar!", "✅")
                            st.rerun()
                        else:
                            st.error("No bottles could be saved. Check the scanned details.")
 
        with col_form:
            st.markdown("### ✍️ Add Details")
            with st.form("add_wine_form", clear_on_submit=True):
                winery = st.text_input(
                    "🍇 Winery / Producer", 
                    value=st.session_state.get("prefill_winery", ""), 
                    placeholder="e.g. Caymus Vineyards"
                )
                varietal = st.text_input(
                    "🍷 Varietal / Blend", 
                    value=st.session_state.get("prefill_varietal", ""), 
                    placeholder="e.g. Cabernet Sauvignon"
                )
                
                prefill_vintage_val = st.session_state.get("prefill_vintage", None)
                if prefill_vintage_val is not None:
                    try:
                        prefill_vintage_val = int(prefill_vintage_val)
                        if prefill_vintage_val < 1800 or prefill_vintage_val > 2100:
                            prefill_vintage_val = None
                    except Exception:
                        prefill_vintage_val = None
                    
                vintage = st.number_input(
                    "📅 Vintage Year", 
                    min_value=1800, 
                    max_value=2100, 
                    value=prefill_vintage_val, 
                    step=1
                )
                
                quantity = st.number_input(
                    "🔢 Quantity to Add",
                    min_value=1,
                    value=1,
                    step=1
                )
                
                submitted = st.form_submit_button("✨ Add Bottle to Cellar")
                
                if submitted:
                    if not winery.strip() or not varietal.strip():
                        st.error("Please provide both Winery and Varietal names.")
                    else:
                        # Call Gemini to generate educational 101 background one-time
                        with st.spinner("Generating Wine 101 profile with Gemini..."):
                            wine_101 = generate_wine_101(winery.strip(), varietal.strip(), vintage)
                        
                        with st.spinner("Saving bottle(s) to Cellar..."):
                            success = add_wine(sheet, st.session_state["user_code"], winery.strip(), varietal.strip(), vintage, wine_101, quantity)
                        
                        if success:
                            st.session_state["refresh_needed"] = True
                            # Clear session state pre-fills & reset uploader key
                            st.session_state["prefill_winery"] = ""
                            st.session_state["prefill_varietal"] = ""
                            st.session_state["prefill_vintage"] = None
                            st.session_state["last_scanned_file"] = None
                            st.session_state["uploader_key"] += 1
                            st.session_state["toast_message"] = (f"🍾 {quantity} bottle(s) saved to cellar!", "✅")
                            st.rerun()

# Tab 2: Active Cellar (Interactive Data Editor)
with tab_active:
    st.subheader("Active Cellar Stock")
    
    # Filter active wines
    active_wines = df[df["status"] == "Active"].copy()
    
    if active_wines.empty:
        st.markdown(f"""
            <div class="wine-card" style="border-left: 4px solid #C5A059; padding: 24px; margin-top: 15px;">
                <h4 style="color: #C5A059; margin-top: 0;">👋 Welcome to your new digital cellar, {st.session_state['user_name']}!</h4>
                <p style="color: #F2EDF2; font-size: 1rem; line-height: 1.6; margin-bottom: 0;">
                    Your inventory is currently empty. Let's get your first bottle logged! <br><br>
                    Swipe over to the <b>'Log a Bottle'</b> tab to mass-upload labels from your camera roll or add a bottle manually.
                </p>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Dashboard Metrics
        total_active = len(active_wines)
        unique_varietals = active_wines[active_wines["varietal"].str.strip() != ""]["varietal"].str.strip().str.title().nunique()
        
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Total Active Bottles", total_active)
        m_col2.metric("Unique Varietals", unique_varietals)
        
        # We need the columns: ["winery", "varietal", "vintage", "rating", "id", "status", "wine_101", "user_code", "quantity"]
        cols_to_display = ["winery", "varietal", "vintage", "rating", "id", "status", "wine_101", "user_code", "quantity"]
        display_df = active_wines[[c for c in cols_to_display if c in active_wines.columns]]
        
        # Native selection enabled using st.dataframe for Option A
        event = st.dataframe(
            display_df,
            column_config={
                "winery": st.column_config.Column("Winery"),
                "varietal": st.column_config.Column("Varietal"),
                "vintage": st.column_config.Column("Vintage"),
                "rating": st.column_config.Column("Rating"),
                "id": None,          # Hide ID column
                "status": None,      # Hide status column
                "wine_101": None,    # Hide wine_101 column
                "user_code": None,   # Hide user_code column
                "quantity": None     # Hide quantity column
            },
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            key="active_cellar_df"
        )
        
        # Render premium "Wine Detail Panel" layout if a row is selected
        selected_row = None
        selected_rows = event.selection.rows
        if selected_rows:
            selected_idx = selected_rows[0]
            if 0 <= selected_idx < len(display_df):
                selected_row = display_df.iloc[selected_idx]
                
        if selected_row is not None:
            st.markdown("### 🍷 Wine Detail Panel")
            wine_101_text = selected_row["wine_101"]
            vintage_str = "N/A" if (pd.isna(selected_row["vintage"]) or not selected_row["vintage"]) else str(int(selected_row["vintage"]))
            
            # Format markdown bold and newlines to HTML for proper rendering inside the glassmorphic card
            import re
            if wine_101_text and wine_101_text.strip():
                formatted_101 = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', wine_101_text)
                formatted_101 = formatted_101.replace("\n", "<br>")
            else:
                formatted_101 = "No Wine 101 educational profile saved for this bottle."
            
            # Display details card with quantity
            st.markdown(f"""
                <div class="wine-card" style="border-left: 4px solid #C5A059; margin-top: 10px;">
                    <h4 style="margin: 0 0 8px 0; color: #C5A059;">{selected_row['winery']} - {selected_row['varietal']} ({vintage_str}) <span style="float: right; font-size: 0.9rem; color: #B4A9B5; font-weight: normal;">Quantity: {selected_row['quantity']}</span></h4>
                    <div style="font-size: 0.95rem; color: #F2EDF2; line-height: 1.6;">
                        {formatted_101}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Share Wine Details Button and Block
            share_key = f"show_share_{selected_row['id']}"
            
            sc_1, sc_2 = st.columns([1, 1])
            with sc_1:
                if st.button("📋 Share Wine Details", key=f"share_btn_{selected_row['id']}"):
                    st.session_state[share_key] = True
                    st.toast("Share text prepared! Click copy in the box below.", icon="📋")
            
            if st.session_state.get(share_key, False):
                origin_text = extract_101_field(wine_101_text, "Origin")
                tasting_text = extract_101_field(wine_101_text, "Tasting Notes")
                pairings_text = extract_101_field(wine_101_text, "Pairings")
                
                share_text = f"🍷 Just enjoying this from my cellar!\n{selected_row['winery']} - {selected_row['varietal']} ({vintage_str})\nOrigin: {origin_text}\nWhat it tastes like: {tasting_text}\nBest paired with: {pairings_text}"
                st.code(share_text, language="text")
                
            # Remove rating selectbox from details panel. Show "🍷 Bottle Finished" button.
            confirm_key = f"confirm_drank_{selected_row['id']}"
            
            if not st.session_state.get(confirm_key, False):
                if st.button("🍷 Bottle Finished", key=f"drank_btn_{selected_row['id']}"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            
            # Post-drink rating confirmation intercept
            if st.session_state.get(confirm_key, False):
                st.markdown("""
                    <div style='margin-top: 15px; padding: 16px; background: rgba(122, 28, 60, 0.1); border: 1px solid rgba(122, 28, 60, 0.3); border-radius: 10px;'>
                        <h5 style='margin: 0 0 10px 0; color: #F2EDF2;'>🍇 Rate before moving to history</h5>
                    </div>
                """, unsafe_allow_html=True)
                
                rating_options = ["Loved", "Liked", "Disliked", "None"]
                # Default rating can be the bottle's current rating if valid, otherwise "None"
                current_rating = selected_row["rating"]
                default_idx = rating_options.index(current_rating) if current_rating in rating_options else rating_options.index("None")
                
                final_rating = st.radio(
                    "How was this bottle?",
                    options=rating_options,
                    index=default_idx,
                    key=f"final_rating_{selected_row['id']}",
                    horizontal=True
                )
                
                c_conf1, c_conf2 = st.columns(2)
                with c_conf1:
                    if st.button("👍 Confirm & Save to History", key=f"conf_drink_btn_{selected_row['id']}"):
                        bottle_id = int(selected_row["id"])
                        bottle_name = f"{selected_row['winery']} - {selected_row['varietal']} ({vintage_str})"
                        qty_before = int(selected_row["quantity"])
                        with st.spinner("Updating cellar..."):
                            if mark_bottle_as_drank(sheet, st.session_state["user_code"], bottle_id, final_rating):
                                st.session_state.pop(confirm_key, None)
                                st.session_state["refresh_needed"] = True
                                if qty_before > 1:
                                    toast_msg = f"🍷 Decremented quantity for {bottle_name}."
                                else:
                                    toast_msg = f"🍷 Marked {bottle_name} as Drank. Cheers!"
                                st.session_state["toast_message"] = (toast_msg, "✅")
                                st.rerun()
                with c_conf2:
                    if st.button("❌ Cancel", key=f"cancel_drink_btn_{selected_row['id']}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

# Tab 3: Cellar History (Interactive Data Editor for Restoring)
with tab_history:
    st.subheader("Cellar History")
    
    # Filter drank wines
    drank_wines = df[df["status"] == "Drank"].copy()
    
    if drank_wines.empty:
        st.info("No wine history yet. Keep drinking!")
    else:
        # Filter selection radio above the data grid
        history_filter = st.radio("Filter History:", ["All Consumed", "⭐ My Favorites"], horizontal=True, key="history_filter_radio")
        
        # Sort drank wines so the most recently consumed bottles appear at the top (by id descending)
        drank_wines = drank_wines.sort_values(by="id", ascending=False)
        
        if history_filter == "⭐ My Favorites":
            drank_wines = drank_wines[drank_wines["rating"].isin(["Loved", "Liked"])].copy()
            
        if drank_wines.empty:
            st.info("No favorite wines recorded in history yet.")
        else:
            # 1. Data Preparation: Add temporary boolean column "Restore to Cellar" set to False
            drank_wines["Restore to Cellar"] = False
            
            # We need the columns: ["Restore to Cellar", "winery", "varietal", "vintage", "rating", "id", "status", "wine_101", "user_code", "quantity"]
            cols_to_display = ["Restore to Cellar", "winery", "varietal", "vintage", "rating", "id", "status", "wine_101", "user_code", "quantity"]
            display_df = drank_wines[[c for c in cols_to_display if c in drank_wines.columns]]
            
            # 2. Interactive Table: Render data using st.data_editor
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "Restore to Cellar": st.column_config.CheckboxColumn(
                        "Restore?",
                        help="Check this box to restore this bottle back to the Active Cellar",
                        default=False,
                        disabled=False
                    ),
                    "winery": st.column_config.Column(
                        "Winery",
                        disabled=True
                    ),
                    "varietal": st.column_config.Column(
                        "Varietal",
                        disabled=True
                    ),
                    "vintage": st.column_config.Column(
                        "Vintage",
                        disabled=True
                    ),
                    "rating": st.column_config.Column(
                        "Rating",
                        disabled=True
                    ),
                    "id": None,          # Hide ID column
                    "status": None,      # Hide status column
                    "wine_101": None,    # Hide wine_101 column
                    "user_code": None,   # Hide user_code column
                    "quantity": None     # Hide quantity column
                },
                hide_index=True,
                use_container_width=True,
                key="graveyard_editor"
            )
            
            # 3. Restore Logic: Check if any row has 'Restore to Cellar' set to True
            restore_mask = edited_df["Restore to Cellar"] == True
            if restore_mask.any():
                # Get the first checked row
                row = edited_df[restore_mask].iloc[0]
                bottle_id = int(row["id"])
                vintage_str = "N/A" if pd.isna(row["vintage"]) else str(row["vintage"])
                bottle_name = f"{row['winery']} - {row['varietal']} ({vintage_str})"
                
                with st.spinner("Restoring to Active Cellar..."):
                    success_status = update_wine_status(sheet, st.session_state["user_code"], bottle_id, "Active")
                    success_rating = update_wine_rating(sheet, st.session_state["user_code"], bottle_id, "None")
                    
                    if success_status and success_rating:
                        st.session_state["refresh_needed"] = True
                        st.session_state["toast_message"] = (f"🔄 Restored {bottle_name} to Active Cellar.", "🍷")
                        st.rerun()
