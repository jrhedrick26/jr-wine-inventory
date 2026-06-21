import sqlite3
import pandas as pd
import os
import streamlit as st
import logging

def sync_db_from_supabase():
    """Checks if wine_inventory.db exists in Supabase bucket 'wine-data'.
    If it exists, downloads it to the local environment.
    If not, initializes a local DB and uploads it for the first time."""
    db_path = "wine_inventory.db"
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except KeyError:
        logging.warning("Supabase URL or Key missing in secrets. Skipping startup sync.")
        return
        
    try:
        from supabase import create_client
        supabase = create_client(url, key)
        
        # Ensure bucket exists
        try:
            supabase.storage.get_bucket("wine-data")
        except Exception:
            try:
                supabase.storage.create_bucket("wine-data", options={"public": False})
                logging.warning("Created Supabase storage bucket 'wine-data'")
            except Exception as bucket_err:
                logging.error(f"Could not create bucket 'wine-data': {bucket_err}")
                
        bucket = supabase.storage.from_("wine-data")
        
        file_exists = False
        try:
            file_exists = bucket.exists(db_path)
        except Exception:
            # Fallback listing
            try:
                files = bucket.list()
                file_exists = any(f.get("name") == db_path for f in files)
            except Exception:
                pass
                
        if file_exists:
            logging.warning("wine_inventory.db found in Supabase. Downloading...")
            res = bucket.download(db_path)
            with open(db_path, "wb") as f:
                f.write(res)
            logging.warning("Download complete!")
        else:
            logging.warning("wine_inventory.db not found in Supabase. Initializing locally and uploading...")
            # Initialize a fresh database locally
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    winery TEXT,
                    varietal TEXT,
                    vintage INTEGER,
                    status TEXT,
                    rating TEXT
                )
            """)
            conn.commit()
            conn.close()
            
            # Upload to Supabase
            with open(db_path, "rb") as f:
                bucket.upload(path=db_path, file=f, file_options={"upsert": "true"})
            logging.warning("Initial upload to Supabase complete!")
            
    except Exception as e:
        logging.error(f"Error during Supabase startup sync: {e}", exc_info=True)


class WineDatabase:
    def __init__(self):
        self.db_path = "wine_inventory.db"
        self._init_db()

    def _get_connection(self):
        # check_same_thread=False is safe for read/write SQLite in a simple Streamlit environment
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        """Initialize the SQLite database table if it doesn't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS wines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        winery TEXT,
                        varietal TEXT,
                        vintage INTEGER,
                        status TEXT,
                        rating TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logging.error(f"SQLite database initialization error: {e}", exc_info=True)
            st.error(f"Database initialization error: {e}")

    def _upload_to_supabase(self):
        """Uploads the local SQLite database file to Supabase in a background thread."""
        import threading
        
        def run():
            try:
                url = st.secrets["SUPABASE_URL"]
                key = st.secrets["SUPABASE_KEY"]
            except KeyError:
                logging.warning("Supabase URL or Key missing in secrets. Skipping background upload.")
                return
                
            try:
                from supabase import create_client
                supabase = create_client(url, key)
                
                # Ensure bucket exists
                try:
                    supabase.storage.get_bucket("wine-data")
                except Exception:
                    try:
                        supabase.storage.create_bucket("wine-data", options={"public": False})
                    except Exception as bucket_err:
                        logging.error(f"Could not create bucket 'wine-data' in background: {bucket_err}")
                
                with open(self.db_path, "rb") as f:
                    supabase.storage.from_("wine-data").upload(
                        path="wine_inventory.db",
                        file=f,
                        file_options={"upsert": "true"}
                    )
                logging.warning("Background upload of wine_inventory.db to Supabase succeeded!")
            except Exception as e:
                logging.error(f"Error uploading database to Supabase in background: {e}", exc_info=True)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def read_all(self) -> pd.DataFrame:
        """Reads all wines from the SQLite database."""
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query("SELECT * FROM wines", conn)
            
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
            logging.error(f"Error reading SQLite database: {e}", exc_info=True)
            return pd.DataFrame(columns=["id", "winery", "varietal", "vintage", "status", "rating"])

    def add_wine(self, winery: str, varietal: str, vintage: int):
        """Adds a new wine to the cellar."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO wines (winery, varietal, vintage, status, rating) VALUES (?, ?, ?, ?, ?)",
                    (winery, varietal, int(vintage), "Active", "None")
                )
                conn.commit()
            # Trigger background upload sync
            self._upload_to_supabase()
        except Exception as e:
            logging.error(f"Error inserting wine into SQLite: {e}", exc_info=True)
            st.error(f"Failed to add bottle: {e}")

    def update_wine_status(self, wine_id: int, status: str):
        """Updates the status (Active or Drank) of a specific wine."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE wines SET status = ? WHERE id = ?",
                    (status, int(wine_id))
                )
                conn.commit()
            # Trigger background upload sync
            self._upload_to_supabase()
        except Exception as e:
            logging.error(f"Error updating wine status in SQLite: {e}", exc_info=True)
            st.error(f"Failed to update status: {e}")

    def update_wine_rating(self, wine_id: int, rating: str):
        """Updates the rating (None, Disliked, Liked, Loved) of a specific wine."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE wines SET rating = ? WHERE id = ?",
                    (rating, int(wine_id))
                )
                conn.commit()
            # Trigger background upload sync
            self._upload_to_supabase()
        except Exception as e:
            logging.error(f"Error updating wine rating in SQLite: {e}", exc_info=True)
            st.error(f"Failed to update rating: {e}")
