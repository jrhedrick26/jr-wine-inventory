import sqlite3
import pandas as pd
import os
import streamlit as st
import logging

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
        except Exception as e:
            logging.error(f"Error updating wine rating in SQLite: {e}", exc_info=True)
            st.error(f"Failed to update rating: {e}")
