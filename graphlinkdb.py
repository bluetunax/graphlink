# graphlinkdb.py
# Part of the GraphLink Project
# This script scans for CSV friend lists and populates the graphlink.sqlite database.

import pandas as pd
import os
import time
import sqlite3
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
from urllib.parse import urlparse, urlunparse
from functools import partial  # <--- CHANGE #1: ADD THIS IMPORT

# --- Configuration ---
OUTPUT_DIR_NAME = "output_graphlink"
DB_FILENAME = "graphlink.sqlite"
INPUT_FOLDER = "./"

URL_COLUMN_INDEX = 0
NAME_COLUMN_INDEX = 2

def filename_to_owner_url(filename):
    base_name = os.path.splitext(filename)[0]
    return f"https://facebook.com/profile.php?id={base_name}"

MAX_WORKERS = os.cpu_count()

# --- Helper Function ---
def normalize_url(url):
    if not isinstance(url, str) or not url.startswith(('http', 'https:')): return None
    try:
        parsed = urlparse(url.lower())
        netloc = parsed.netloc.replace('www.', '')
        path = parsed.path.rstrip('/')
        if 'profile.php' in path and parsed.query:
            query_params = [q for q in parsed.query.split('&') if q.startswith('id=')]
            clean_query = '&'.join(query_params)
            return urlunparse(('https', netloc, path, '', clean_query, ''))
        else:
            return urlunparse(('https', netloc, path, '', '', ''))
    except (ValueError, TypeError): return None

# --- Database Functions ---

def initialize_database(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY,
            profile_url TEXT NOT NULL UNIQUE,
            name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            profile_id_1 INTEGER,
            profile_id_2 INTEGER,
            PRIMARY KEY (profile_id_1, profile_id_2),
            FOREIGN KEY (profile_id_1) REFERENCES profiles (id),
            FOREIGN KEY (profile_id_2) REFERENCES profiles (id)
        )
    ''')
    conn.commit()
    conn.close()

def process_csv_to_db(file_path, db_path): # Function signature is correct
    file_name = os.path.basename(file_path)
    owner_url = normalize_url(filename_to_owner_url(file_name))
    if not owner_url: return f"Skipped {file_name}: Invalid owner URL."

    try:
        df = pd.read_csv(file_path, usecols=[URL_COLUMN_INDEX, NAME_COLUMN_INDEX], header=0)
        df.columns = ['URL', 'Name']
        df.dropna(inplace=True)
        
        profiles_to_add = [(normalize_url(row['URL']), row['Name']) for _, row in df.iterrows() if normalize_url(row['URL'])]
        profiles_to_add.append((owner_url, os.path.splitext(file_name)[0]))
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executemany('INSERT INTO profiles (profile_url, name) VALUES (?, ?) ON CONFLICT(profile_url) DO UPDATE SET name = excluded.name', profiles_to_add)

        owner_id = cursor.execute('SELECT id FROM profiles WHERE profile_url = ?', (owner_url,)).fetchone()[0]
        friend_urls = tuple([p[0] for p in profiles_to_add if p[0] != owner_url])
        
        if not friend_urls:
            conn.close()
            return f"Processed {file_name}: No valid friends."

        placeholders = ', '.join('?' for _ in friend_urls)
        friend_ids = [row[0] for row in cursor.execute(f'SELECT id FROM profiles WHERE profile_url IN ({placeholders})', friend_urls).fetchall()]

        edges_to_add = [(min(owner_id, fid), max(owner_id, fid)) for fid in friend_ids if owner_id != fid]
        cursor.executemany('INSERT OR IGNORE INTO friendships (profile_id_1, profile_id_2) VALUES (?, ?)', edges_to_add)
        
        conn.commit()
        conn.close()
        return f"Successfully processed {file_name}."
    except Exception as e:
        return f"Failed to process {file_name}: {e}"

# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- GraphLinkDB Ingestion Tool ---")
    start_time = time.time()
    
    output_dir = os.path.join(os.path.abspath(INPUT_FOLDER), OUTPUT_DIR_NAME)
    db_path = os.path.join(output_dir, DB_FILENAME)

    initialize_database(db_path)
    print(f"Database located at: {db_path}")

    file_paths = [os.path.join(INPUT_FOLDER, f) for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.csv')]
    
    if file_paths:
        print(f"Found {len(file_paths)} CSV files to process.")
        
        # Create a partial function with the db_path argument already filled in
        process_func = partial(process_csv_to_db, db_path=db_path)

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Now we use .map() with our new single-argument function
            # <--- CHANGE #2: THIS WHOLE BLOCK IS REVISED
            results = list(tqdm(executor.map(process_func, file_paths), total=len(file_paths), desc="Ingesting CSVs"))
            
        print("Database ingestion complete.")
    else:
        print("No new CSV files found to ingest.")
        
    print(f"\nScript finished in {time.time() - start_time:.2f} seconds.")