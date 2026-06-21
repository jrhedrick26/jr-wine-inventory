import streamlit as st
import pandas as pd
import os

try:
    from streamlit_gsheets import GSheetsConnection
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

class WineDatabase:
    def __init__(self):
        self.use_gsheets = False
        self.conn = None
        self.csv_fallback = "wine_inventory.csv"
        
        # Check secrets configuration
        secrets = st.secrets
        
        # Trigger lazy loading of secrets to populate the internal secrets dictionary
        try:
            _ = secrets.keys()
        except Exception:
            pass
            
        # Programmatically clean the private_key inside Streamlit secrets to prevent PEM decoding errors
        try:
            if "_secrets" in dir(secrets) and isinstance(secrets._secrets, dict):
                connections = secrets._secrets.get("connections", {})
                if isinstance(connections, dict):
                    gsheets_secrets = connections.get("gsheets", {})
                    if isinstance(gsheets_secrets, dict) and "private_key" in gsheets_secrets:
                        pkey = gsheets_secrets["private_key"]
                        if isinstance(pkey, str):
                            print("--- WINE CELLAR DIAGNOSTICS ---")
                            print("DEBUG: raw private_key length:", len(pkey))
                            print("DEBUG: raw private_key start:", repr(pkey[:35]))
                            print("DEBUG: raw private_key end:", repr(pkey[-35:]))
                            
                            # Clean key using both double and single backslash replacements
                            cleaned_key = pkey.replace("\\\\n", "\n").replace("\\n", "\n")
                            cleaned_key = cleaned_key.replace("\r", "")
                            cleaned_key = cleaned_key.strip("'\" \n\t")
                            
                            print("DEBUG: cleaned private_key length:", len(cleaned_key))
                            # Extract base64 part
                            b64_data = cleaned_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").replace("\n", "").replace(" ", "").strip()
                            print("DEBUG: base64 payload length:", len(b64_data))
                            print("DEBUG: base64 payload multiple of 4?", len(b64_data) % 4 == 0)
                            print("--------------------------------")
                            
                            gsheets_secrets["private_key"] = cleaned_key
        except Exception as e:
            print("DEBUG: Error during credentials cleaning:", e)

        # Retrieve the configuration for checks
        gsheets_config = secrets.get("connections", {}).get("gsheets", {})

        # Determine connection type:
        # Use Google Sheets if the package is installed and 'spreadsheet' URL is defined
        if HAS_GSHEETS and "spreadsheet" in gsheets_config:
            try:
                # We call st.connection WITHOUT passing **kwargs, complying with GSheetsConnection._connect signature!
                self.conn = st.connection("gsheets", type=GSheetsConnection)
                # Test read to verify credentials are authenticated and valid
                self.conn.read(ttl=0)
                self.use_gsheets = True
            except Exception as e:
                st.warning(f"Could not connect to Google Sheets: {e}. Checking fallback SQL database.")
                self.use_gsheets = False
                self.conn = None

        if not self.use_gsheets:
            # Fallback to SQL connection (e.g. SQLite)
            # If the user has a custom database URL in secrets under connections.gsheets
            if "url" in gsheets_config:
                try:
                    self.conn = st.connection("gsheets", type="sql")
                    self._init_db()
                except Exception as e:
                    st.warning(f"Could not connect to SQL database connection: {e}. Falling back to CSV file.")
                    self.conn = None
            else:
                # No database URL is specified. Connect directly to local SQLite.
                # We use a custom name ("local_sqlite") to prevent Streamlit from reading
                # the "connections.gsheets" block which lacks standard SQL connection parameters.
                try:
                    self.conn = st.connection("local_sqlite", type="sql", url="sqlite:///wine_inventory.db")
                    self._init_db()
                except Exception as e:
                    st.warning(f"Could not connect to SQLite database: {e}. Falling back to CSV file.")
                    self.conn = None
                
        if self.conn is None and not self.use_gsheets:
            self._init_csv()

    def _init_db(self):
        """Initialize the SQLite/SQL database table if it doesn't exist."""
        from sqlalchemy import text
        try:
            with self.conn.session as session:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS wines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        winery TEXT,
                        varietal TEXT,
                        vintage INTEGER,
                        status TEXT,
                        rating TEXT
                    )
                """))
                session.commit()
        except Exception as e:
            st.error(f"Database initialization error: {e}")

    def _init_csv(self):
        """Initialize the local CSV file if it doesn't exist."""
        if not os.path.exists(self.csv_fallback):
            df = pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating"])
            df.to_csv(self.csv_fallback, index=False)

    def read_all(self) -> pd.DataFrame:
        """Reads all wines. Caching is disabled (ttl=0) to ensure real-time UI updates."""
        if self.use_gsheets:
            try:
                df = self.conn.read(ttl=0)
                expected_cols = ["id", "winery", "varietal", "vintage", "status", "rating"]
                if df is None or df.empty:
                    df = pd.DataFrame(columns=expected_cols)
                else:
                    df.columns = [c.strip() for c in df.columns]
                    for col in expected_cols:
                        if col not in df.columns:
                            df[col] = None
                
                # Normalize types
                df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
                df["vintage"] = pd.to_numeric(df["vintage"], errors="coerce").fillna(0).astype(int)
                df["winery"] = df["winery"].fillna("").astype(str)
                df["varietal"] = df["varietal"].fillna("").astype(str)
                df["status"] = df["status"].fillna("Active").astype(str)
                df["rating"] = df["rating"].fillna("None").astype(str)
                return df
            except Exception as e:
                st.error(f"Error reading Google Sheet: {e}")
                return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating"])
        
        elif self.conn is not None:
            # SQL connection
            from sqlalchemy import text
            try:
                df = self.conn.query("SELECT * FROM wines", ttl=0)
                if df is None or df.empty:
                    return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating"])
                
                # Normalize column names just in case
                df.columns = [c.strip().lower() for c in df.columns]
                # Ensure columns are typed correctly
                df["id"] = df["id"].astype(int)
                df["vintage"] = df["vintage"].astype(int)
                return df
            except Exception as e:
                st.error(f"Error reading from SQL Database: {e}")
                return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating"])
        
        else:
            # CSV fallback
            try:
                df = pd.read_csv(self.csv_fallback)
                df["id"] = df["id"].fillna(0).astype(int)
                df["vintage"] = df["vintage"].fillna(0).astype(int)
                return df
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
                return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating"])

    def add_wine(self, winery: str, varietal: str, vintage: int):
        """Adds a new wine to the cellar."""
        if self.use_gsheets:
            df = self.read_all()
            new_id = int(df["id"].max() + 1) if not df.empty and pd.notna(df["id"].max()) else 1
            new_row = pd.DataFrame([{
                "id": new_id,
                "winery": winery,
                "varietal": varietal,
                "vintage": int(vintage),
                "status": "Active",
                "rating": "None"
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            self.conn.update(data=df)
            
        elif self.conn is not None:
            from sqlalchemy import text
            try:
                with self.conn.session as session:
                    session.execute(
                        text("INSERT INTO wines (winery, varietal, vintage, status, rating) VALUES (:winery, :varietal, :vintage, :status, :rating)"),
                        {"winery": winery, "varietal": varietal, "vintage": int(vintage), "status": "Active", "rating": "None"}
                    )
                    session.commit()
            except Exception as e:
                st.error(f"SQL database write error: {e}")
                
        else:
            df = self.read_all()
            new_id = int(df["id"].max() + 1) if not df.empty and pd.notna(df["id"].max()) else 1
            new_row = pd.DataFrame([{
                "id": new_id,
                "winery": winery,
                "varietal": varietal,
                "vintage": int(vintage),
                "status": "Active",
                "rating": "None"
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(self.csv_fallback, index=False)

    def update_wine_status(self, wine_id: int, status: str):
        """Updates the status (Active or Drank) of a specific wine."""
        if self.use_gsheets:
            df = self.read_all()
            df.loc[df["id"] == wine_id, "status"] = status
            self.conn.update(data=df)
            
        elif self.conn is not None:
            from sqlalchemy import text
            try:
                with self.conn.session as session:
                    session.execute(
                        text("UPDATE wines SET status = :status WHERE id = :id"),
                        {"status": status, "id": int(wine_id)}
                    )
                    session.commit()
            except Exception as e:
                st.error(f"SQL database update error: {e}")
                
        else:
            df = self.read_all()
            df.loc[df["id"] == wine_id, "status"] = status
            df.to_csv(self.csv_fallback, index=False)

    def update_wine_rating(self, wine_id: int, rating: str):
        """Updates the rating (None, Disliked, Liked, Loved) of a specific wine."""
        if self.use_gsheets:
            df = self.read_all()
            df.loc[df["id"] == wine_id, "rating"] = rating
            self.conn.update(data=df)
            
        elif self.conn is not None:
            from sqlalchemy import text
            try:
                with self.conn.session as session:
                    session.execute(
                        text("UPDATE wines SET rating = :rating WHERE id = :id"),
                        {"rating": rating, "id": int(wine_id)}
                    )
                    session.commit()
            except Exception as e:
                st.error(f"SQL database update error: {e}")
                
        else:
            df = self.read_all()
            df.loc[df["id"] == wine_id, "rating"] = rating
            df.to_csv(self.csv_fallback, index=False)
