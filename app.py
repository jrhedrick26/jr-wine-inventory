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

# --- Robust State Initialization (Fixes the StreamlitAPIException) ---
if "manual_winery" not in st.session_state:
    st.session_state["manual_winery"] = ""
if "manual_varietal" not in st.session_state:
    st.session_state["manual_varietal"] = ""
if "manual_vintage" not in st.session_state:
    st.session_state["manual_vintage"] = ""
if "refresh_needed" not in st.session_state:
    st.session_state["refresh_needed"] = False
if "full_wine_df" not in st.session_state:
    st.session_state["full_wine_df"] = None
if "last_scanned_file" not in st.session_state:
    st.session_state["last_scanned_file"] = None
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
if "bulk_scan_cache" not in st.session_state:
    st.session_state["bulk_scan_cache"] = {}

# --- Google Sheets Setup ---
@st.cache_resource
def get_gspread_client():
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
    
    wine_sheet = spreadsheet.sheet1 
    user_sheet = spreadsheet.worksheet("Authorized_Users")
    return wine_sheet, user_sheet

# --- Google Sheets Schema & Column Mappings ---
SCHEMA = ["user_code", "id", "winery", "varietal", "vintage", "status", "rating", "wine_101", "quantity"]

def col_idx(col_name: str) -> int:
    return SCHEMA.index(col_name) + 1

def col_letter(col_name: str) -> str:
    import string
    idx = SCHEMA.index(col_name)
    return string.ascii_uppercase[idx]

def init_sheet_if_empty(sheet):
    try:
        values = sheet.get_all_values()
        if not values:
            headers = SCHEMA
            sheet.append_row(headers)
        else:
            current_headers = values[0]
            if len(current_headers) < len(SCHEMA) or current_headers[:len(SCHEMA)] != SCHEMA:
                sheet.update("A1:I1", [SCHEMA])
    except Exception as e:
        st.error(f"Error checking or initializing sheet: {e}")

def read_all_wines(sheet) -> pd.DataFrame:
    try:
        if "full_wine_df" in st.session_state and st.session_state["full_wine_df"] is not None and not st.session_state.get("refresh_needed", False):
            df = st.session_state["full_wine_df"]
        else:
            values = sheet.get_all_values()
            if not values or len(values) <= 1:
                df = pd.DataFrame(columns=SCHEMA)
            else:
                headers = values[0]
                rows = values[1:]
                max_len = len(headers)
                padded_rows = [r + [""] * (max_len - len(r)) if len(r) < max_len else r[:max_len] for r in rows]
                df = pd.DataFrame(padded_rows, columns=headers)
            
            for col in SCHEMA:
                if col not in df.columns:
                    df[col] = None
                    
            df["user_code"] = df["user_code"].fillna("").astype(str).str.strip()
            df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
            df["vintage"] = pd.to_numeric(df["vintage"], errors="coerce").astype("Int64")
            df["winery"] = df["winery"].fillna("").astype(str).str.strip()
            df["varietal"] = df["varietal"].fillna("").astype(str).str.strip()
            df["status"] = df["status"].fillna("Active").astype(str).str.strip().replace("", "Active")
            df["rating"] = df["rating"].fillna("None").astype(str).str.strip().replace("", "None")
            df["wine_101"] = df["wine_101"].fillna("").astype(str).str.strip()
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
            
            st.session_state["full_wine_df"] = df
            st.session_state["refresh_needed"] = False
            
        user_code = st.session_state.get("user_code")
        if user_code:
            filtered_df = df[df["user_code"] == str(user_code)].copy()
        else:
            filtered_df = df.iloc[0:0].copy()
            
        return filtered_df
    except Exception as e:
        init_sheet_if_empty(sheet)
        return pd.DataFrame(columns=SCHEMA)

def add_wine(sheet, user_code: str, winery: str, varietal: str, vintage, wine_101: str, quantity: int = 1) -> bool:
    try:
        if "full_wine_df" not in st.session_state or st.session_state["full_wine_df"] is None:
            read_all_wines(sheet)
        df_all = st.session_state["full_wine_df"]
        
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

        df_all_vintages = df_all["vintage"].apply(parse_vintage)
        target_vintage = parse_vintage(vintage)

        # Fix the Pandas NaN matching trap
        if target_vintage is None:
            vintage_mask = df_all_vintages.isna()
        else:
            vintage_mask = (df_all_vintages == target_vintage)

        match = df_all[
            (df_all["user_code"] == str(user_code)) &
            (df_all["status"] == "Active") &
            (df_all["winery"].str.strip().str.lower() == winery.strip().lower()) &
            (df_all["varietal"].str.strip().str.lower() == varietal.strip().lower()) &
            vintage_mask
        ]
        
        if not match.empty:
            row_idx_val = match.index[0]
            current_qty = int(match.iloc[0]["quantity"])
            new_qty = current_qty + quantity
            
            row_num = row_idx_val + 2
            col_let = col_letter("quantity")
            sheet.update(f"{col_let}{row_num}", [[new_qty]])
            
            # Update cache inline
            df_all.loc[row_idx_val, "quantity"] = new_qty
            st.session_state["full_wine_df"] = df_all
            st.session_state["refresh_needed"] = True
            st.session_state["write_action_performed"] = True
            return True
        else:
            user_wines = df_all[df_all["user_code"] == str(user_code)]
            new_id = 1 if user_wines.empty else int(user_wines["id"].max()) + 1
            try:
                vintage_val = "" if (vintage is None or pd.isna(vintage) or str(vintage).strip() == "") else int(float(str(vintage).strip()))
            except Exception:
                vintage_val = ""
            
            row = [None] * len(SCHEMA)
            row[SCHEMA.index("user_code")] = user_code
            row[SCHEMA.index("id")] = new_id
            row[SCHEMA.index("winery")] = winery
            row[SCHEMA.index("varietal")] = varietal
            row[SCHEMA.index("vintage")] = vintage_val
            row[SCHEMA.index("status")] = "Active"
            row[SCHEMA.index("rating")] = "None"
            row[SCHEMA.index("wine_101")] = wine_101
            row[SCHEMA.index("quantity")] = quantity
            
            sheet.append_row(row)
            
            # Update cache inline
            new_row_dict = {
                "user_code": str(user_code),
                "id": int(new_id),
                "winery": str(winery),
                "varietal": str(varietal),
                "vintage": vintage_val if vintage_val != "" else None,
                "status": "Active",
                "rating": "None",
                "wine_101": str(wine_101),
                "quantity": int(quantity)
            }
            new_row_df = pd.DataFrame([new_row_dict])
            new_row_df["vintage"] = pd.to_numeric(new_row_df["vintage"], errors="coerce").astype("Int64")
            new_row_df["id"] = new_row_df["id"].astype(int)
            new_row_df["quantity"] = new_row_df["quantity"].astype(int)
            st.session_state["full_wine_df"] = pd.concat([df_all, new_row_df], ignore_index=True)
            st.session_state["refresh_needed"] = True
            st.session_state["write_action_performed"] = True
            return True
    except Exception as e:
        st.error(f"Failed to save bottle to Google Sheets: {e}")
        return False

def restore_wine(sheet, user_code: str, wine_id: int) -> bool:
    try:
        if "full_wine_df" not in st.session_state or st.session_state["full_wine_df"] is None:
            read_all_wines(sheet)
        df_all = st.session_state["full_wine_df"]
        
        match = df_all[(df_all["user_code"] == str(user_code)) & (df_all["id"] == int(wine_id))]
        
        if match.empty:
            st.error(f"Bottle ID {wine_id} not found in sheet for user {user_code}.")
            return False
            
        row_idx = match.index[0]
        row_num = row_idx + 2
        
        # Batch update status to "Active" and rating to "None" in a single range call
        range_name = f"{col_letter('status')}{row_num}:{col_letter('rating')}{row_num}"
        sheet.update(range_name, [["Active", "None"]])
        
        # Update cache inline
        df_all.loc[row_idx, "status"] = "Active"
        df_all.loc[row_idx, "rating"] = "None"
        st.session_state["full_wine_df"] = df_all
        st.session_state["refresh_needed"] = True
        st.session_state["write_action_performed"] = True
        st.session_state["write_action_performed_hist"] = True
        return True
    except Exception as e:
        st.error(f"Failed to restore wine in Google Sheets: {e}")
        return False

def mark_bottle_as_drank(sheet, user_code: str, wine_id: int, rating: str) -> bool:
    try:
        if "full_wine_df" not in st.session_state or st.session_state["full_wine_df"] is None:
            read_all_wines(sheet)
        df_all = st.session_state["full_wine_df"]
        
        match = df_all[(df_all["user_code"] == str(user_code)) & (df_all["id"] == int(wine_id))]
        
        if match.empty:
            st.error(f"Bottle ID {wine_id} not found in sheet for user {user_code}.")
            return False
            
        row_idx_val = match.index[0]
        row_num = row_idx_val + 2
        current_qty = int(match.iloc[0]["quantity"])
        winery_val = match.iloc[0]["winery"]
        varietal_val = match.iloc[0]["varietal"]
        vintage_val = match.iloc[0]["vintage"]
        wine_101_val = match.iloc[0]["wine_101"]

        # Check if this exact bottle with this exact rating already exists in History
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

        df_all_vintages = df_all["vintage"].apply(parse_vintage)
        target_vintage = parse_vintage(vintage_val)

        if target_vintage is None:
            v_hist_mask = df_all_vintages.isna()
        else:
            v_hist_mask = (df_all_vintages == target_vintage)

        history_match = df_all[
            (df_all["user_code"] == str(user_code)) &
            (df_all["status"] == "Drank") &
            (df_all["rating"] == rating) &
            (df_all["winery"].str.strip().str.lower() == winery_val.strip().lower()) &
            (df_all["varietal"].str.strip().str.lower() == varietal_val.strip().lower()) &
            v_hist_mask
        ]

        if current_qty > 1:
            # Decrement active stock by 1
            sheet.update(f"{col_letter('quantity')}{row_num}", [[current_qty - 1]])
            df_all.loc[row_idx_val, "quantity"] = current_qty - 1
            
            # Update or append history
            if not history_match.empty:
                hist_row_idx = history_match.index[0]
                hist_row_num = hist_row_idx + 2
                hist_qty = int(history_match.iloc[0]["quantity"])
                sheet.update(f"{col_letter('quantity')}{hist_row_num}", [[hist_qty + 1]])
                df_all.loc[hist_row_idx, "quantity"] = hist_qty + 1
            else:
                new_id = 1 if df_all.empty else int(df_all["id"].max()) + 1
                row = [user_code, new_id, winery_val, varietal_val, "" if pd.isna(vintage_val) else vintage_val, "Drank", rating, wine_101_val, 1]
                sheet.append_row(row)
                
                # Append to cache
                new_row_dict = {
                    "user_code": str(user_code),
                    "id": int(new_id),
                    "winery": winery_val,
                    "varietal": varietal_val,
                    "vintage": vintage_val if (vintage_val != "" and not pd.isna(vintage_val)) else None,
                    "status": "Drank",
                    "rating": rating,
                    "wine_101": wine_101_val,
                    "quantity": int(1)
                }
                new_row_df = pd.DataFrame([new_row_dict])
                new_row_df["vintage"] = pd.to_numeric(new_row_df["vintage"], errors="coerce").astype("Int64")
                new_row_df["id"] = new_row_df["id"].astype(int)
                new_row_df["quantity"] = new_row_df["quantity"].astype(int)
                df_all = pd.concat([df_all, new_row_df], ignore_index=True)
        else:
            # Last bottle remaining: If an existing history entry matches, increment it and delete/archive this one. 
            # Otherwise, simply flip this row's status to Drank inline.
            if not history_match.empty:
                hist_row_idx = history_match.index[0]
                hist_row_num = hist_row_idx + 2
                hist_qty = int(history_match.iloc[0]["quantity"])
                sheet.update(f"{col_letter('quantity')}{hist_row_num}", [[hist_qty + 1]])
                sheet.update(f"{col_letter('status')}{row_num}", [["Archived"]]) # Mark old active row out of scope safely
                
                df_all.loc[hist_row_idx, "quantity"] = hist_qty + 1
                df_all.loc[row_idx_val, "status"] = "Archived"
            else:
                range_name = f"{col_letter('status')}{row_num}:{col_letter('rating')}{row_num}"
                sheet.update(range_name, [["Drank", rating]])
                
                df_all.loc[row_idx_val, "status"] = "Drank"
                df_all.loc[row_idx_val, "rating"] = rating
            
        st.session_state["full_wine_df"] = df_all
        st.session_state["refresh_needed"] = True
        st.session_state["write_action_performed"] = True
        return True
    except Exception as e:
        st.error(f"Failed to mark bottle as drank: {e}")
        return False

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
        try:
            vintage_str = "current release" if (vintage is None or pd.isna(vintage)) else str(int(float(str(vintage))))
        except Exception:
            vintage_str = "current release"
        
        prompt = f"""Provide a clean, professional, and simple wine 101 overview for a {vintage_str} {winery} {varietal}. Keep it simple, plain English only, and strictly adhere to these guidelines:

CRITICAL ACCURACY RULE: Do not guess or hallucinate. If you do not have factual, verifiable data for this specific producer and vintage, you must provide the standard profile for the grape varietal from its most common region. If doing so, begin your Overview with: 'General Varietal Profile:'

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
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0
            )
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

# Fetch stock
df = read_all_wines(sheet)

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

# Set default tab focus based on active inventory count on first load
active_wines_count = 0
if "user_code" in st.session_state:
    active_wines = df[df["status"] == "Active"]
    active_wines_count = len(active_wines)

if "cellar_tabs" not in st.session_state:
    if active_wines_count == 0:
        st.session_state["cellar_tabs"] = "➕ Log a Bottle"
    else:
        st.session_state["cellar_tabs"] = "🍷 Active Cellar"

# Create tabs for inventory navigation
tab_add, tab_active, tab_history, tab_chat = st.tabs(["➕ Log a Bottle", "🍷 Active Cellar", "📜 Cellar History", "💬 Cellar Chat"], key="cellar_tabs")

# Tab 1: Log a Bottle (Add Bottle Form & Gemini Scanner)
with tab_add:
    st.subheader("Log a New Bottle")
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    
    # 1. File Uploader rendered full width at the top
    uploaded_files = st.file_uploader(
        "Upload photo(s) of the wine label to scan (supports drag & drop / mobile camera roll)",
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
        if len(uploaded_files) == 1:
            # SCENARIO A: Exactly 1 Image Uploaded
            active_file = uploaded_files[0]
            
            if "bulk_scan_cache" not in st.session_state:
                st.session_state["bulk_scan_cache"] = {}
                
            if active_file.name not in st.session_state["bulk_scan_cache"]:
                status_placeholder = st.empty()
                status_placeholder.info(f"Processing label: {active_file.name}...")
                try:
                    with st.spinner("Analyzing label with Gemini..."):
                        active_file.seek(0)
                        image_data = active_file.read()
                        image = Image.open(io.BytesIO(image_data))
                        
                        # Auto-orient
                        try:
                            from PIL import ImageOps
                            image = ImageOps.exif_transpose(image)
                        except Exception:
                            pass
                        
                        # Resize
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
                        else:
                            client = genai.Client(api_key=api_key)
                            model_env = st.secrets["auth"].get("target_model", "gemini-flash-latest")
                            
                            prompt = (
                                "You are a precise data extraction tool. Analyze this wine bottle label image.\n"
                                "Strictly extract the following three fields and return them as a clean JSON object:\n"
                                "1. 'winery': The exact producer or vineyard name.\n"
                                "2. 'varietal': The grape variety or blend (e.g., Cabernet Sauvignon, Zinfandel).\n"
                                "   CRITICAL RULE FOR MULTIPLE BOTTLINGS: Look closely for any specific vineyard designations, cuvée names, barrel selections, or 'Reserve' status text on the label. "
                                "If any specific designation is present, append it cleanly in parentheses right next to the grape variety. "
                                "For example: 'Zinfandel (Old Vines)', 'Zinfandel (Juvenile Vineyard)', or 'Cabernet Sauvignon (Special Selection)'. "
                                "If no special designation is found, just return the standard grape name.\n"
                                "3. 'vintage': The 4-digit production year. If absolutely no year is visible, return null.\n\n"
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
                            
                            # Parse JSON
                            cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
                            result = json.loads(cleaned_text)
                            
                            vintage_val = result.get("vintage")
                            if vintage_val is not None:
                                try:
                                    vintage_val = int(vintage_val)
                                    if vintage_val < 1800 or vintage_val > 2100:
                                        vintage_val = ""
                                except Exception:
                                    vintage_val = ""
                            else:
                                vintage_val = ""
                                    
                            st.session_state["bulk_scan_cache"][active_file.name] = {
                                "winery": result.get("winery", ""),
                                "varietal": result.get("varietal", ""),
                                "vintage": vintage_val
                            }
                            
                            # Immediately assign values directly to backend session states:
                            st.session_state["manual_winery"] = result.get("winery", "")
                            st.session_state["manual_varietal"] = result.get("varietal", "")
                            st.session_state["manual_vintage"] = vintage_val
                            st.session_state["last_scanned_file"] = active_file.name
                            st.toast("Label scanned and form auto-filled!")
                            st.rerun()
                            
                except Exception as ex:
                    st.error("Could not process image file. Please try taking another photo or entering details manually.")
                    st.session_state["bulk_scan_cache"][active_file.name] = {
                        "winery": "Error scanning",
                        "varietal": "Error scanning",
                        "vintage": ""
                    }
                finally:
                    status_placeholder.empty()
                    
            else:
                # Auto-prefill widgets from cache if not already populated from this file
                if st.session_state.get("last_scanned_file") != active_file.name:
                    res = st.session_state["bulk_scan_cache"].get(active_file.name)
                    if res and res.get("winery") != "Error scanning":
                        st.session_state["manual_winery"] = res.get("winery", "")
                        st.session_state["manual_varietal"] = res.get("varietal", "")
                        st.session_state["manual_vintage"] = res.get("vintage", "")
                        st.session_state["last_scanned_file"] = active_file.name
                        st.toast("Label scanned and form auto-filled!")
                        st.rerun()
                        
        else:
            # SCENARIO B: Multiple Images Uploaded (Bulk behavior)
            # While bulk mode is active, clear or ignore the single-form session state keys
            st.session_state["manual_winery"] = ""
            st.session_state["manual_varietal"] = ""
            st.session_state["manual_vintage"] = ""
            st.session_state["last_scanned_file"] = None
            
            if "bulk_scan_cache" not in st.session_state:
                st.session_state["bulk_scan_cache"] = {}
            
            # Filter out cache elements no longer in uploaded_files
            current_filenames = [f.name for f in uploaded_files]
            for k in list(st.session_state["bulk_scan_cache"].keys()):
                if k not in current_filenames:
                    st.session_state["bulk_scan_cache"].pop(k)
                    
            # Loop sequentially
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
                            
                            # Resize
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
                                "1. 'winery': The exact producer or vineyard name.\n"
                                "2. 'varietal': The grape variety or blend (e.g., Cabernet Sauvignon, Zinfandel).\n"
                                "   CRITICAL RULE FOR MULTIPLE BOTTLINGS: Look closely for any specific vineyard designations, cuvée names, barrel selections, or 'Reserve' status text on the label. "
                                "If any specific designation is present, append it cleanly in parentheses right next to the grape variety. "
                                "For example: 'Zinfandel (Old Vines)', 'Zinfandel (Juvenile Vineyard)', or 'Cabernet Sauvignon (Special Selection)'. "
                                "If no special designation is found, just return the standard grape name.\n"
                                "3. 'vintage': The 4-digit production year. If absolutely no year is visible, return null.\n\n"
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
                            
                            vintage_val = result.get("vintage")
                            if vintage_val is not None:
                                try:
                                    vintage_val = int(vintage_val)
                                    if vintage_val < 1800 or vintage_val > 2100:
                                        vintage_val = ""
                                except Exception:
                                    vintage_val = ""
                            else:
                                vintage_val = ""
                                    
                            st.session_state["bulk_scan_cache"][f.name] = {
                                "winery": result.get("winery", ""),
                                "varietal": result.get("varietal", ""),
                                "vintage": vintage_val
                            }
                    except Exception as ex:
                        st.error("Could not process image file. Please try taking another photo or entering details manually.")
                        st.session_state["bulk_scan_cache"][f.name] = {
                            "winery": "Error scanning",
                            "varietal": "Error scanning",
                            "vintage": ""
                        }
                    finally:
                        status_placeholder.empty()

    # 2. Dynamic Layout Rendering
    if len(uploaded_files) <= 1:
        # Single scan or manual intake layout: 2 equal-width columns
        col_scan, col_form = st.columns([1, 1])
        
        with col_scan:
            st.markdown("### 📷 Label Scanner")
            if uploaded_files:
                # Preview single uploaded file
                active_file = uploaded_files[0]
                try:
                    st.image(active_file, caption=f"Uploaded: {active_file.name}", use_column_width=True)
                except Exception:
                    st.error("Could not render image preview. The file might be corrupt.")
            else:
                st.markdown("""
                <div class="wine-card" style="border-left: 4px solid #C5A059; padding: 20px;">
                    <p style="color: #F2EDF2; font-size: 1rem; font-weight: 500; margin-top: 0; margin-bottom: 8px;">💡 AI Label Scanning:</p>
                    <p style="color: #B4A9B5; font-size: 0.9rem; line-height: 1.5; margin-bottom: 0;">
                        Upload a front label photo. Gemini will automatically extract the winery name, varietal, and vintage to auto-fill the form on the right.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
        with col_form:
            st.markdown("### ✍️ Add Details")
            winery = st.text_input(
                "🍇 Winery / Producer", 
                value=st.session_state["manual_winery"], 
                placeholder="e.g. Caymus Vineyards"
            )
            varietal = st.text_input(
                "🍷 Varietal / Blend", 
                value=st.session_state["manual_varietal"], 
                placeholder="e.g. Cabernet Sauvignon"
            )
            
            prefill_vintage_val = st.session_state.get("manual_vintage", "")
            if prefill_vintage_val == "":
                prefill_vintage_val = None
            else:
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
            
            # Action Toggle
            bottle_action = st.radio(
                "✨ What are you doing with this bottle?",
                ["📦 Storing it in my cellar", "🍷 Drinking it right now!"],
                horizontal=True,
                key="manual_action"
            )
            
            # Inline Rating (only shown if Drinking right now)
            inline_rating = "None"
            if bottle_action == "🍷 Drinking it right now!":
                inline_rating = st.radio(
                    "⭐ Rate this bottle:",
                    ["Loved", "Liked", "Disliked", "None"],
                    horizontal=True,
                    index=3,
                    key="manual_rating"
                )
                quantity = 1
            else:
                quantity = st.number_input(
                    "🔢 Quantity to Add",
                    min_value=1,
                    value=1,
                    step=1,
                    key="manual_qty"
                )
                
            submitted = st.button("✨ Add Bottle to Cellar", key="manual_submit_btn")
            
            if submitted:
                if not winery.strip() or not varietal.strip():
                    st.error("Please provide both Winery and Varietal names.")
                else:
                    # Call Gemini to generate educational 101 background one-time
                    with st.spinner("Generating Wine 101 profile with Gemini..."):
                        # Check if we already have a Wine 101 profile cached in our database
                        existing_101 = None
                        if "full_wine_df" in st.session_state and st.session_state["full_wine_df"] is not None:
                            df_all = st.session_state["full_wine_df"]
                            
                            # Safe vintage parsing for matching
                            def quick_parse(v):
                                try: return int(float(str(v).strip())) if (v and str(v).strip().lower() not in ["none","nan","<na>"]) else None
                                except: return None
                                
                            df_vints = df_all["vintage"].apply(quick_parse)
                            tgt_vint = quick_parse(vintage)
                            v_mask = df_vints.isna() if tgt_vint is None else (df_vints == tgt_vint)
                            
                            profile_match = df_all[
                                (df_all["winery"].str.strip().str.lower() == winery.strip().lower()) &
                                (df_all["varietal"].str.strip().str.lower() == varietal.strip().lower()) &
                                v_mask &
                                (df_all["wine_101"].str.strip() != "")
                            ]
                            if not profile_match.empty:
                                existing_101 = profile_match.iloc[0]["wine_101"]

                        # Use existing text or generate a fresh one if missing
                        wine_101 = existing_101 if existing_101 else generate_wine_101(winery.strip(), varietal.strip(), vintage)
                    
                    if bottle_action == "🍷 Drinking it right now!":
                        with st.spinner("Saving consumed bottle to Cellar History..."):
                            try:
                                df_all = read_all_wines(sheet)
                                
                                # Parse inputs to match history database
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

                                df_all_vintages = df_all["vintage"].apply(parse_vintage)
                                target_vintage = parse_vintage(vintage)
                                
                                if target_vintage is None:
                                    v_hist_mask = df_all_vintages.isna()
                                else:
                                    v_hist_mask = (df_all_vintages == target_vintage)
                                    
                                history_match = df_all[
                                    (df_all["user_code"] == str(st.session_state["user_code"])) &
                                    (df_all["status"] == "Drank") &
                                    (df_all["rating"] == inline_rating) &
                                    (df_all["winery"].str.strip().str.lower() == winery.strip().lower()) &
                                    (df_all["varietal"].str.strip().str.lower() == varietal.strip().lower()) &
                                    v_hist_mask
                                ]
                                
                                if not history_match.empty:
                                    hist_row_idx = history_match.index[0]
                                    hist_row_num = hist_row_idx + 2
                                    hist_qty = int(history_match.iloc[0]["quantity"])
                                    sheet.update(f"{col_letter('quantity')}{hist_row_num}", [[hist_qty + 1]])
                                    
                                    # Update cache inline
                                    df_all.loc[hist_row_idx, "quantity"] = hist_qty + 1
                                else:
                                    new_id = 1 if df_all.empty else int(df_all["id"].max()) + 1
                                    try:
                                        vintage_val = "" if (vintage is None or pd.isna(vintage) or str(vintage).strip() == "") else int(float(str(vintage).strip()))
                                    except Exception:
                                        vintage_val = ""
                                        
                                    row = [None] * len(SCHEMA)
                                    row[SCHEMA.index("user_code")] = st.session_state["user_code"]
                                    row[SCHEMA.index("id")] = new_id
                                    row[SCHEMA.index("winery")] = winery.strip()
                                    row[SCHEMA.index("varietal")] = varietal.strip()
                                    row[SCHEMA.index("vintage")] = vintage_val
                                    row[SCHEMA.index("status")] = "Drank"
                                    row[SCHEMA.index("rating")] = inline_rating
                                    row[SCHEMA.index("wine_101")] = wine_101
                                    row[SCHEMA.index("quantity")] = int(1)
                                    
                                    sheet.append_row(row)
                                    
                                    # Append to cache
                                    new_row_dict = {
                                        "user_code": str(st.session_state["user_code"]),
                                        "id": int(new_id),
                                        "winery": winery.strip(),
                                        "varietal": varietal.strip(),
                                        "vintage": vintage_val if vintage_val != "" else None,
                                        "status": "Drank",
                                        "rating": inline_rating,
                                        "wine_101": wine_101,
                                        "quantity": int(1)
                                    }
                                    new_row_df = pd.DataFrame([new_row_dict])
                                    new_row_df["vintage"] = pd.to_numeric(new_row_df["vintage"], errors="coerce").astype("Int64")
                                    new_row_df["id"] = new_row_df["id"].astype(int)
                                    new_row_df["quantity"] = new_row_df["quantity"].astype(int)
                                    df_all = pd.concat([df_all, new_row_df], ignore_index=True)
                                
                                st.session_state["full_wine_df"] = df_all
                                success = True
                            except Exception as e:
                                st.error(f"Failed to save consumed bottle to Google Sheets: {e}")
                                success = False
                    else:
                        with st.spinner("Saving bottle(s) to Cellar..."):
                            success = add_wine(sheet, st.session_state["user_code"], winery.strip(), varietal.strip(), vintage, wine_101, quantity)
                    
                    if success:
                        st.session_state["refresh_needed"] = True
                        # Clear session state pre-fills & reset uploader key
                        st.session_state["manual_winery"] = ""
                        st.session_state["manual_varietal"] = ""
                        st.session_state["manual_vintage"] = ""
                        st.session_state["last_scanned_file"] = None
                        st.session_state["uploader_key"] += 1
                        if bottle_action == "🍷 Drinking it right now!":
                            toast_msg = f"🍷 Logged {winery.strip()} to Cellar History. Cheers!"
                        else:
                            toast_msg = f"🍾 {quantity} bottle(s) saved to cellar!"
                        st.session_state["toast_message"] = (toast_msg, "✅")
                        st.session_state["refresh_needed"] = True
                        st.rerun()
                        
    else:
        # SCENARIO B: Multiple Images Uploaded (Bulk scan layout: Full page width)
        st.markdown("### 📋 Bulk Scan Review")
        st.info("Review the scanned details below. You can double-click the **Quantity (Qty)** column to adjust the bottle count for any photo before confirming!")

        display_list = []
        for f in uploaded_files:
            res = st.session_state["bulk_scan_cache"].get(f.name, {})
            display_list.append({
                "File Name": f.name,
                "Winery": res.get("winery", ""),
                "Varietal": res.get("varietal", ""),
                "Vintage": res.get("vintage", ""),
                "Quantity": 1  # Default starting value
            })

        review_df = pd.DataFrame(display_list)

        # Turn the dataframe into an interactive editor (Expanded full width)
        edited_review_df = st.data_editor(
            review_df,
            column_config={
                "File Name": st.column_config.Column("Photo File", disabled=True, width="medium"),
                "Winery": st.column_config.Column("Winery / Producer", disabled=True, width="large"),
                "Varietal": st.column_config.Column("Varietal / Blend", disabled=True, width="large"),
                "Vintage": st.column_config.Column("Vintage", disabled=True, width="small"),
                "Quantity": st.column_config.NumberColumn("Quantity (Qty)", min_value=1, step=1, format="%d", width="small")
            },
            hide_index=True,
            use_container_width=True,
            key="bulk_scan_editor"
        )

        # Grid view of uploaded preview files below editor
        with st.expander("🖼️ View Uploaded Previews", expanded=False):
            img_cols = st.columns(4)
            for idx, f in enumerate(uploaded_files):
                with img_cols[idx % 4]:
                    try:
                        f.seek(0)
                        st.image(f, caption=f.name, use_column_width=True)
                    except:
                        pass
                        
        if st.button("✨ Confirm & Add All to Cellar", key="bulk_confirm_btn"):
            success_count = 0
            with st.spinner("Saving batch to Cellar..."):
                # Consolidate batch using the user's edited quantities
                consolidated_batch = {}
                for _, row_data in edited_review_df.iterrows():
                    w_val = str(row_data["Winery"]).strip()
                    var_val = str(row_data["Varietal"]).strip()
                    raw_vint = row_data["Vintage"]
                    user_qty = int(row_data["Quantity"])
                    
                    if w_val == "Error scanning" or not w_val:
                        continue
                        
                    final_vint = int(raw_vint) if (raw_vint and str(raw_vint).strip().isdigit()) else None
                    wine_key = (w_val.lower(), var_val.lower(), final_vint)
                    
                    if wine_key in consolidated_batch:
                        consolidated_batch[wine_key]["quantity"] += user_qty
                    else:
                        consolidated_batch[wine_key] = {
                            "winery": w_val,
                            "varietal": var_val,
                            "vintage": final_vint,
                            "quantity": user_qty
                        }

                # Push consolidated totals to Google Sheets
                for data in consolidated_batch.values():
                    # Check if we already have a Wine 101 profile cached in our database
                    existing_101 = None
                    if "full_wine_df" in st.session_state and st.session_state["full_wine_df"] is not None:
                        df_all = st.session_state["full_wine_df"]
                        
                        # Safe vintage parsing for matching
                        def quick_parse(v):
                            try: return int(float(str(v).strip())) if (v and str(v).strip().lower() not in ["none","nan","<na>"]) else None
                            except: return None
                            
                        df_vints = df_all["vintage"].apply(quick_parse)
                        tgt_vint = quick_parse(data["vintage"])
                        v_mask = df_vints.isna() if tgt_vint is None else (df_vints == tgt_vint)
                        
                        profile_match = df_all[
                            (df_all["winery"].str.strip().str.lower() == data["winery"].strip().lower()) &
                            (df_all["varietal"].str.strip().str.lower() == data["varietal"].strip().lower()) &
                            v_mask &
                            (df_all["wine_101"].str.strip() != "")
                        ]
                        if not profile_match.empty:
                            existing_101 = profile_match.iloc[0]["wine_101"]

                    # Use existing text or generate a fresh one if missing
                    wine_101_val = existing_101 if existing_101 else generate_wine_101(data["winery"], data["varietal"], data["vintage"])
                    
                    if add_wine(sheet, st.session_state["user_code"], data["winery"], data["varietal"], data["vintage"], wine_101_val, data["quantity"]):
                        success_count += data["quantity"]
                        
            if success_count > 0:
                st.session_state["refresh_needed"] = True
                st.session_state["bulk_scan_cache"] = {}
                st.session_state["uploader_key"] += 1
                st.session_state["toast_message"] = (f"🍾 {success_count} bottle(s) saved to cellar!", "✅")
                st.rerun()
            else:
                st.error("No bottles could be saved. Check the scanned details.")

# Tab 2: Active Cellar (Interactive Data Editor)
with tab_active:
    st.subheader("Active Cellar Stock")
    
    # Filter active wines
    active_wines = df[df["status"] == "Active"].copy()
    
    if active_wines.empty:
        st.markdown(f"""
            <div class="wine-card" style="border-left: 4px solid #C5A059; padding: 24px; margin-top: 15px;">
                <p style="color: #F2EDF2; font-size: 1rem; line-height: 1.6; margin: 0;">
                    👋 Welcome to your new digital cellar, {st.session_state['user_name']}! Your inventory is currently empty. Let's get your first bottle logged! Swipe over to the 'Log a Bottle' tab to mass-upload labels from your camera roll or add a bottle manually.
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
        
        # Display selected columns
        cols_to_display = ["winery", "varietal", "vintage", "rating", "id", "status", "wine_101", "user_code", "quantity"]
        display_df = active_wines[[c for c in cols_to_display if c in active_wines.columns]]
        
        # Native selection enabled using st.dataframe
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
                "quantity": st.column_config.NumberColumn("Qty", help="Number of bottles in stock", format="%d")
            },
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            key="active_cellar_df"
        )
        
        # Render premium "Wine Detail Panel" layout if a row is selected
        # Track selected row via persistent ID
        selected_row = None
        widget_rows = event.selection.rows
        
        # Track widget selection changes to handle user clicking different rows
        prev_selection = st.session_state.get("prev_active_cellar_selection", [])
        write_performed = st.session_state.pop("write_action_performed", False)
        
        if widget_rows != prev_selection:
            st.session_state["prev_active_cellar_selection"] = widget_rows
            if widget_rows:
                selected_idx = widget_rows[0]
                if 0 <= selected_idx < len(display_df):
                    st.session_state["selected_active_wine_id"] = int(display_df.iloc[selected_idx]["id"])
            else:
                if not write_performed:
                    st.session_state["selected_active_wine_id"] = None
        else:
            if not widget_rows and not write_performed:
                st.session_state["selected_active_wine_id"] = None
                
        # Resolve selected_row by looking up the selected_active_wine_id in display_df
        current_selected_id = st.session_state.get("selected_active_wine_id")
        if current_selected_id is not None:
            matched_rows = display_df[display_df["id"] == current_selected_id]
            if not matched_rows.empty:
                selected_row = matched_rows.iloc[0]
            else:
                st.session_state["selected_active_wine_id"] = None
                
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
                    origin_text = extract_101_field(wine_101_text, "Origin")
                    tasting_text = extract_101_field(wine_101_text, "Tasting Notes")
                    pairings_text = extract_101_field(wine_101_text, "Pairings")
                    
                    share_text = f"🍷 Just enjoying this from my cellar!\n{selected_row['winery']} - {selected_row['varietal']} ({vintage_str})\nOrigin: {origin_text}\nWhat it tastes like: {tasting_text}\nBest paired with: {pairings_text}"
                    st.session_state[share_key] = share_text
                    st.toast("Copied to clipboard! Text it to a friend.", icon="📋")
            
            if st.session_state.get(share_key, None):
                st.code(st.session_state[share_key], language="text")
                
            # Bottle Finished Rating confirmation intercept
            confirm_key = f"confirm_drank_{selected_row['id']}"
            
            if not st.session_state.get(confirm_key, False):
                if st.button("🍷 Bottle Finished", key=f"drank_btn_{selected_row['id']}"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            
            # Post-drink rating confirmation intercept
            if st.session_state.get(confirm_key, False):
                st.markdown("""
                    <div style='margin-top: 15px; padding: 16px; background: rgba(122, 28, 60, 0.15); border: 1px solid rgba(122, 28, 60, 0.3); border-radius: 10px;'>
                        <p style='margin: 0; color: #F2EDF2; font-size: 1rem;'>We hope you enjoyed it! How would you rate this specific bottle before we update your inventory?</p>
                    </div>
                """, unsafe_allow_html=True)
                
                rating_options = ["Loved", "Liked", "Disliked", "None"]
                current_rating = selected_row["rating"]
                default_idx = rating_options.index(current_rating) if current_rating in rating_options else rating_options.index("None")
                
                final_rating = st.radio(
                    "Rating:",
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
            cols_to_display = ["winery", "varietal", "vintage", "rating", "id", "status", "wine_101", "user_code", "quantity"]
            display_df = drank_wines[[c for c in cols_to_display if c in drank_wines.columns]]
            
            # Interactive Table: Render data using st.dataframe with selection enabled
            event_history = st.dataframe(
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
                    "quantity": st.column_config.NumberColumn("Qty Consumed", format="%d")
                },
                hide_index=True,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                key="history_cellar_df"
            )
            
            # Selection & Detail Panel Logic
            selected_row_hist = None
            widget_rows_hist = event_history.selection.rows
            
            prev_selection_hist = st.session_state.get("prev_history_cellar_selection", [])
            write_performed_hist = st.session_state.pop("write_action_performed_hist", False)
            
            if widget_rows_hist != prev_selection_hist:
                st.session_state["prev_history_cellar_selection"] = widget_rows_hist
                if widget_rows_hist:
                    selected_idx_hist = widget_rows_hist[0]
                    if 0 <= selected_idx_hist < len(display_df):
                        st.session_state["selected_history_wine_id"] = int(display_df.iloc[selected_idx_hist]["id"])
                else:
                    if not write_performed_hist:
                        st.session_state["selected_history_wine_id"] = None
            else:
                if not widget_rows_hist and not write_performed_hist:
                    st.session_state["selected_history_wine_id"] = None
                    
            current_selected_hist_id = st.session_state.get("selected_history_wine_id")
            if current_selected_hist_id is not None:
                matched_rows_hist = display_df[display_df["id"] == current_selected_hist_id]
                if not matched_rows_hist.empty:
                    selected_row_hist = matched_rows_hist.iloc[0]
                else:
                    st.session_state["selected_history_wine_id"] = None
                    
            if selected_row_hist is not None:
                st.markdown("### 🍷 Wine Detail Panel")
                wine_101_text = selected_row_hist["wine_101"]
                vintage_str = "N/A" if (pd.isna(selected_row_hist["vintage"]) or not selected_row_hist["vintage"]) else str(int(selected_row_hist["vintage"]))
                
                import re
                if wine_101_text and wine_101_text.strip():
                    formatted_101 = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', wine_101_text)
                    formatted_101 = formatted_101.replace("\n", "<br>")
                else:
                    formatted_101 = "No Wine 101 educational profile saved for this bottle."
                
                st.markdown(f"""
                    <div class="wine-card" style="border-left: 4px solid #C5A059; margin-top: 10px;">
                        <h4 style="margin: 0 0 8px 0; color: #C5A059;">{selected_row_hist['winery']} - {selected_row_hist['varietal']} ({vintage_str}) <span style="float: right; font-size: 0.9rem; color: #B4A9B5; font-weight: normal;">Qty Consumed: {selected_row_hist['quantity']}</span></h4>
                        <div style="font-size: 0.95rem; color: #F2EDF2; line-height: 1.6;">
                            {formatted_101}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                rating_badge = get_rating_badge_html(selected_row_hist["rating"])
                st.markdown(f"<div style='margin-bottom: 15px;'><b>My Rating:</b> {rating_badge}</div>", unsafe_allow_html=True)
                
                if st.button("🔄 Restore Bottle to Active Cellar", key=f"restore_btn_{selected_row_hist['id']}"):
                    bottle_id = int(selected_row_hist["id"])
                    bottle_name = f"{selected_row_hist['winery']} - {selected_row_hist['varietal']} ({vintage_str})"
                    with st.spinner("Restoring to Active Cellar..."):
                        if restore_wine(sheet, st.session_state["user_code"], bottle_id):
                            st.session_state["selected_history_wine_id"] = None
                            st.session_state["write_action_performed_hist"] = True
                            st.session_state["toast_message"] = (f"🔄 Restored {bottle_name} to Active Cellar.", "🍷")
                            st.rerun()

# Tab 4: Cellar Chat (Sommelier Assistant)
with tab_chat:
    st.subheader("💬 Cellar Chat")
    
    # Initialize chat history with an assistant welcome message
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {
                "role": "assistant", 
                "content": f"Hello {st.session_state.get('user_name', 'friend')}! I am your personal cellar sommelier. Ask me anything about your current inventory, food pairings, or for tailored recommendations!"
            }
        ]
        
    # Render chat messages
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Capture user input
    user_input = st.chat_input("Ask your sommelier about your cellar...")
    
    if user_input:
        # Display user message immediately in chat container
        with st.chat_message("user"):
            st.write(user_input)
            
        # Append user message to history
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        
        # Prepare dynamic context from user's current stock & history
        # 1. Active Stock
        active_df = df[df["status"] == "Active"]
        active_list = []
        for _, r in active_df.iterrows():
            active_list.append({
                "winery": r.get("winery", ""),
                "varietal": r.get("varietal", ""),
                "vintage": "N/A" if pd.isna(r.get("vintage")) else int(r.get("vintage")),
                "quantity": int(r.get("quantity", 1))
            })
            
        # 2. History
        history_df = df[df["status"] == "Drank"]
        history_list = []
        for _, r in history_df.iterrows():
            history_list.append({
                "winery": r.get("winery", ""),
                "varietal": r.get("varietal", ""),
                "vintage": "N/A" if pd.isna(r.get("vintage")) else int(r.get("vintage")),
                "rating": r.get("rating", "None")
            })
            
        context_payload = {
            "active_cellar_inventory": active_list,
            "consumption_history_and_ratings": history_list
        }
        
        # System instructions
        system_instruction = (
            "You are a friendly, down-to-earth personal wine sommelier assisting the user with their personal cellar collection. "
            "Your tone is conversational, helpful, and down-to-earth (avoid academic snobbery).\n\n"
            "Here is the user's current cellar data:\n"
            f"{json.dumps(context_payload, indent=2)}\n\n"
            "Strictly follow these rules when responding:\n"
            "Rule 1 (The Anchor): You must prioritize suggesting bottles that are currently available in the user's Active Cellar inventory data so they can physically go pull and drink them.\n"
            "Rule 2 (The Taste Profile): Look at their Cellar History. If they have bottles marked 'Loved' or 'Liked', favor styles, regions, or varietals that mirror those positive historical inputs. If they have bottles marked 'Disliked', actively avoid recommending similar profiles.\n"
            "Rule 3 (The Cold-Start Fallback): If the user's active inventory or history is empty, or contains no realistic matches for their request (e.g., they ask for a hot weather BBQ white but only have heavy winter reds in stock), do not break or hallucinate. Recommend a classic, casual retail style that perfectly matches their food/vibe query (e.g., 'You don't have any chilling whites in stock right now, but for a hot backyard BBQ, I highly recommend running out to grab a crisp, cold Sauvignon Blanc or a light Spanish Rosé!'). Ensure you clearly inform the user that this is a retail suggestion since they don't have a matching bottle in their current cellar inventory.\n"
            "Cold-Start Note: If both the active cellar inventory and history lists are empty, welcome them warmly to their digital cellar, acknowledge that their cellar is ready to be stocked, and provide a friendly, natural language conversational suggestion for a classic wine style (e.g. a specific classic style) they could buy at the store to start their collection or pair with their query."
        )
        
        # Generate response using Gemini
        api_key = st.secrets["auth"].get("gemini_api_key")
        if not api_key:
            st.error("Gemini API Key is missing in st.secrets.")
        else:
            with st.spinner("Sommelier is thinking..."):
                try:
                    client = genai.Client(api_key=api_key)
                    model_env = st.secrets["auth"].get("target_model", "gemini-flash-latest")
                    
                    contents = []
                    # Add previous conversation history
                    for msg in st.session_state["chat_history"]:
                        role = "user" if msg["role"] == "user" else "model"
                        contents.append({
                            "role": role,
                            "parts": [{"text": msg["content"]}]
                        })
                    
                    response = client.models.generate_content(
                        model=model_env,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.3
                        )
                    )
                    
                    response_text = response.text.strip()
                    
                    # Append assistant message to history
                    st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
                    st.rerun()
                    
                except Exception as ex:
                    st.error(f"Error communicating with Gemini: {ex}")
