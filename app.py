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

def get_worksheet():
    client = get_gspread_client()
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1OXY3blai3bGKOTytbBtV6ScLoTaKq-241dl2ee-BG5I/edit"
    return client.open_by_url(spreadsheet_url).sheet1

def init_sheet_if_empty(sheet):
    try:
        values = sheet.get_all_values()
        if not values:
            headers = ["id", "winery", "varietal", "vintage", "status", "rating", "wine_101"]
            sheet.append_row(headers)
    except Exception as e:
        st.error(f"Error checking or initializing sheet: {e}")

def read_all_wines(sheet) -> pd.DataFrame:
    try:
        records = sheet.get_all_records()
        if not records:
            return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating", "wine_101"])
        
        df = pd.DataFrame(records)
        
        # Ensure all columns exist
        expected_cols = ["id", "winery", "varietal", "vintage", "status", "rating", "wine_101"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
                
        # Normalize data types
        df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
        df["vintage"] = pd.to_numeric(df["vintage"], errors="coerce").astype("Int64")
        df["winery"] = df["winery"].fillna("").astype(str)
        df["varietal"] = df["varietal"].fillna("").astype(str)
        df["status"] = df["status"].fillna("Active").astype(str)
        df["rating"] = df["rating"].fillna("None").astype(str)
        df["wine_101"] = df["wine_101"].fillna("").astype(str)
        return df
    except Exception as e:
        # Fallback to init if sheet has issues
        init_sheet_if_empty(sheet)
        return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating", "wine_101"])

def add_wine(sheet, winery: str, varietal: str, vintage, wine_101: str) -> bool:
    try:
        df = read_all_wines(sheet)
        new_id = 1 if df.empty else int(df["id"].max()) + 1
        vintage_val = "" if (vintage is None or pd.isna(vintage)) else int(vintage)
        row = [new_id, winery, varietal, vintage_val, "Active", "None", wine_101]
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Failed to save bottle to Google Sheets: {e}")
        return False

def update_wine_status(sheet, wine_id: int, status: str) -> bool:
    try:
        values = sheet.get_all_values()
        for idx, row in enumerate(values):
            if idx == 0:
                continue
            if len(row) > 0 and str(row[0]) == str(wine_id):
                row_num = idx + 1
                sheet.update_cell(row_num, 5, status)  # Column 5 is 'status'
                return True
        st.error(f"Bottle ID {wine_id} not found in sheet.")
        return False
    except Exception as e:
        st.error(f"Failed to update status in Google Sheets: {e}")
        return False

def update_wine_rating(sheet, wine_id: int, rating: str) -> bool:
    try:
        values = sheet.get_all_values()
        for idx, row in enumerate(values):
            if idx == 0:
                continue
            if len(row) > 0 and str(row[0]) == str(wine_id):
                row_num = idx + 1
                sheet.update_cell(row_num, 6, rating)  # Column 6 is 'rating'
                return True
        st.error(f"Bottle ID {wine_id} not found in sheet.")
        return False
    except Exception as e:
        st.error(f"Failed to update rating in Google Sheets: {e}")
        return False

def mark_bottle_as_drank(sheet, wine_id: int, rating: str) -> bool:
    try:
        values = sheet.get_all_values()
        for idx, row in enumerate(values):
            if idx == 0:
                continue
            if len(row) > 0 and str(row[0]) == str(wine_id):
                row_num = idx + 1
                sheet.update(f"E{row_num}:F{row_num}", [["Drank", rating]])
                return True
        st.error(f"Bottle ID {wine_id} not found in sheet.")
        return False
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

# Apply the theme styling
inject_custom_css()

# Header layout (Password wall removed completely)
st.markdown("<h2 style='margin: 0; padding: 0 0 10px 0;'>🍇 JR Wine Cellar</h2>", unsafe_allow_html=True)

# Helper function to generate Wine 101 description using Gemini
def generate_wine_101(winery: str, varietal: str, vintage) -> str:
    try:
        api_key = st.secrets["auth"]["gemini_api_key"]
    except KeyError:
        api_key = None
        
    if not api_key:
        return "Summary loading... refresh or edit rating to retry."
    
    try:
        client = genai.Client(api_key=api_key)
        vintage_str = "current release" if (vintage is None or pd.isna(vintage)) else str(int(vintage))
        
        prompt = (
            f"Provide a fun, beginner-friendly, and engaging 101 overview for a {vintage_str} {winery} {varietal}. "
            "Explain what flavors to expect, a cool fact about the region or grape style, and a great casual food pairing. "
            "Keep it light, witty, and educational."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return "Summary loading... refresh or edit rating to retry."


# --- Authenticated App Code ---
# Connect to Google Sheets
try:
    sheet = get_worksheet()
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

# Create tabs for inventory navigation
tab_add, tab_active, tab_graveyard = st.tabs(["➕ Log a Bottle", "🍷 Active Cellar", "📜 The Graveyard"])

# Tab 1: Log a Bottle (Add Bottle Form & Gemini Scanner)
with tab_add:
    st.subheader("Log a New Bottle")
    with st.expander("➕ Log a New Bottle", expanded=True):
        # Create two columns for Scanner UI and Manual Entry Form
        col_scan, col_form = st.columns([1, 1])
        
        with col_scan:
            st.markdown("### 📷 Scan a Bottle Label")
            uploaded_file = st.file_uploader(
                "Upload a photo of the wine label to auto-fill the form",
                type=["png", "jpg", "jpeg"],
                key=f"wine_label_uploader_{st.session_state['uploader_key']}"
            )
            
            # Reset scanned file tracking if cleared
            if uploaded_file is None:
                if st.session_state.get("last_scanned_file") is not None:
                    st.session_state["last_scanned_file"] = None
                    
            # Gemini processing block
            if uploaded_file is not None:
                if st.session_state.get("last_scanned_file") != uploaded_file.name:
                    with st.spinner("Analyzing wine label with Gemini..."):
                        try:
                            try:
                                api_key = st.secrets["auth"]["gemini_api_key"]
                            except KeyError:
                                api_key = None
                                
                            if not api_key:
                                st.error("Gemini API Key is missing in st.secrets.")
                            else:
                                client = genai.Client(api_key=api_key)
                                
                                # Load image
                                image_data = uploaded_file.read()
                                image = Image.open(io.BytesIO(image_data))
                                
                                # Request analysis
                                prompt = (
                                    "Analyze this wine bottle label image. "
                                    "Extract the Winery name, the Varietal/Blend (e.g., Cabernet Sauvignon, Chardonnay, Red Blend), "
                                    "and the Vintage Year. Return the data as a clean JSON object with the exact keys: "
                                    "'winery', 'varietal', 'vintage'. "
                                    "If you cannot find a vintage year on the label, return null for the 'vintage' key."
                                )
                                
                                response = client.models.generate_content(
                                    model='gemini-2.5-flash',
                                    contents=[image, prompt],
                                    config=types.GenerateContentConfig(
                                        response_mime_type="application/json"
                                    )
                                )
                                
                                # Parse JSON response
                                cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
                                result = json.loads(cleaned_text)
                                
                                st.session_state["prefill_winery"] = result.get("winery", "")
                                st.session_state["prefill_varietal"] = result.get("varietal", "")
                                
                                # Validate and convert vintage
                                try:
                                    vintage_val = result.get("vintage")
                                    if vintage_val is None:
                                        st.session_state["prefill_vintage"] = None
                                    else:
                                        vintage_val = int(vintage_val)
                                        if vintage_val < 1800 or vintage_val > 2100:
                                            st.session_state["prefill_vintage"] = None
                                        else:
                                            st.session_state["prefill_vintage"] = vintage_val
                                except Exception:
                                    st.session_state["prefill_vintage"] = None
                                    
                                st.session_state["last_scanned_file"] = uploaded_file.name
                                st.toast("Label scanned and form auto-filled!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error scanning label: {e}")
                            
                st.image(uploaded_file, caption="Uploaded Label Preview", width="stretch")
 
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
                
                submitted = st.form_submit_button("✨ Add Bottle to Cellar")
                
                if submitted:
                    if not winery.strip() or not varietal.strip():
                        st.error("Please provide both Winery and Varietal names.")
                    else:
                        # Call Gemini to generate educational 101 background one-time
                        with st.spinner("Generating Wine 101 profile with Gemini..."):
                            wine_101 = generate_wine_101(winery.strip(), varietal.strip(), vintage)
                        
                        if add_wine(sheet, winery.strip(), varietal.strip(), vintage, wine_101):
                            st.session_state["refresh_needed"] = True
                            # Clear session state pre-fills & reset uploader key
                            st.session_state["prefill_winery"] = ""
                            st.session_state["prefill_varietal"] = ""
                            st.session_state["prefill_vintage"] = None
                            st.session_state["last_scanned_file"] = None
                            st.session_state["uploader_key"] += 1
                            st.session_state["toast_message"] = ("🍾 Bottle saved to cellar with Wine 101 profile!", "✅")
                            st.rerun()

# Tab 2: Active Cellar (Interactive Data Editor)
with tab_active:
    st.subheader("Active Cellar Stock")
    
    # Filter active wines
    active_wines = df[df["status"] == "Active"].copy()
    
    # Dashboard Metrics
    total_active = len(active_wines)
    unique_varietals = active_wines[active_wines["varietal"].str.strip() != ""]["varietal"].str.strip().str.title().nunique()
    
    m_col1, m_col2 = st.columns(2)
    m_col1.metric("Total Active Bottles", total_active)
    m_col2.metric("Unique Varietals", unique_varietals)
    
    if active_wines.empty:
        st.info("No active wines in stock. Go to 'Log a Bottle' to add one!")
    else:
        # We need the columns: ["winery", "varietal", "vintage", "rating", "id", "status", "wine_101"]
        cols_to_display = ["winery", "varietal", "vintage", "rating", "id", "status", "wine_101"]
        display_df = active_wines[[c for c in cols_to_display if c in active_wines.columns]]
        
        # Native selection enabled using st.dataframe for Option A
        event = st.dataframe(
            display_df,
            column_config={
                "winery": st.column_config.Column("Winery"),
                "varietal": st.column_config.Column("Varietal"),
                "vintage": st.column_config.Column("Vintage"),
                "rating": st.column_config.Column("Rating"),
                "id": None,      # Hide ID column
                "status": None,  # Hide status column
                "wine_101": None # Hide wine_101 column
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
            
            # Display details card
            st.markdown(f"""
                <div class="wine-card" style="border-left: 4px solid #C5A059; margin-top: 10px;">
                    <h4 style="margin: 0 0 8px 0; color: #C5A059;">{selected_row['winery']} - {selected_row['varietal']} ({vintage_str})</h4>
                    <div style="font-size: 0.95rem; color: #F2EDF2; line-height: 1.6;">
                        {wine_101_text if (wine_101_text and wine_101_text.strip()) else "No Wine 101 educational profile saved for this bottle."}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Actions columns
            act_col1, act_col2 = st.columns([1, 1])
            with act_col1:
                rating_options = ["None", "Disliked", "Liked", "Loved"]
                current_rating = selected_row["rating"]
                if current_rating not in rating_options:
                    current_rating = "None"
                new_rating = st.selectbox(
                    "Update Rating",
                    options=rating_options,
                    index=rating_options.index(current_rating),
                    key=f"rating_select_{selected_row['id']}"
                )
                if new_rating != selected_row["rating"]:
                    with st.spinner("Updating rating..."):
                        if update_wine_rating(sheet, int(selected_row["id"]), new_rating):
                            st.session_state["refresh_needed"] = True
                            st.session_state["toast_message"] = (f"🍾 Rating for {selected_row['winery']} set to {new_rating}!", "✅")
                            st.rerun()
                            
            with act_col2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # spacing
                if st.button("🍷 Mark as Drank", key=f"drank_btn_{selected_row['id']}"):
                    bottle_id = int(selected_row["id"])
                    bottle_name = f"{selected_row['winery']} - {selected_row['varietal']} ({vintage_str})"
                    with st.spinner("Recording to Graveyard..."):
                        if mark_bottle_as_drank(sheet, bottle_id, new_rating):
                            st.session_state["refresh_needed"] = True
                            st.session_state["toast_message"] = (f"🍷 Marked {bottle_name} as Drank. Cheers!", "✅")
                            st.rerun()

# Tab 3: The Graveyard (Interactive Data Editor for Restoring)
with tab_graveyard:
    st.subheader("The Graveyard (Cellar History)")
    
    # Filter drank wines
    drank_wines = df[df["status"] == "Drank"].copy()
    
    if drank_wines.empty:
        st.info("No wine history yet. Keep drinking!")
    else:
        # 1. Data Preparation: Add temporary boolean column "Restore to Cellar" set to False
        drank_wines["Restore to Cellar"] = False
        
        # Sort drank wines so the most recently consumed bottles appear at the top (by id descending)
        drank_wines = drank_wines.sort_values(by="id", ascending=False)
        
        # We need the columns: ["Restore to Cellar", "winery", "varietal", "vintage", "rating", "id", "status", "wine_101"]
        # Rearrange to put "Restore to Cellar" first for a clean checkbox alignment
        cols_to_display = ["Restore to Cellar", "winery", "varietal", "vintage", "rating", "id", "status", "wine_101"]
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
                "id": None,      # Hide ID column
                "status": None,  # Hide status column
                "wine_101": None # Hide wine_101 column
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
                success_status = update_wine_status(sheet, bottle_id, "Active")
                success_rating = update_wine_rating(sheet, bottle_id, "None")
                
                if success_status and success_rating:
                    st.session_state["refresh_needed"] = True
                    st.session_state["toast_message"] = (f"🔄 Restored {bottle_name} to Active Cellar.", "🍷")
                    st.rerun()
