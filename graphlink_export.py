# graphlink_export.py (Saves to the correct directory)

import pandas as pd
import os
import networkx as nx
import sqlite3
import json
import re
from itertools import combinations
from urllib.parse import urlparse, urlunparse

# --- Configuration ---
OUTPUT_DIR_NAME = "output_graphlink"
DB_FILENAME = "graphlink.sqlite"

# --- Helper Function ---
def normalize_url(url):
    # (This function is unchanged)
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

# --- Core Logic ---
def load_graph_data(db_path):
    # (This function is unchanged)
    print("Connecting to the database and loading graph data...")
    # ... (rest of the function is the same)
    with sqlite3.connect(db_path) as conn:
        edges_df = pd.read_sql_query("SELECT profile_id_1, profile_id_2 FROM friendships", conn)
        profiles_df = pd.read_sql_query("SELECT id, profile_url, name FROM profiles", conn)
    
    G = nx.from_pandas_edgelist(edges_df, 'profile_id_1', 'profile_id_2')
    
    url_to_id = pd.Series(profiles_df.id.values, index=profiles_df.profile_url).to_dict()
    id_to_info = profiles_df.set_index('id').to_dict('index')
    
    print(f"Graph loaded successfully: {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    return G, url_to_id, id_to_info

def main():
    # (The interactive prompts are unchanged)
    print("\n--- GraphLink Exporter for Viewer ---")
    db_path = os.path.join(OUTPUT_DIR_NAME, DB_FILENAME)
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'. Please run graphlinkdb.py first.")
        return

    G, url_to_id, id_to_info = load_graph_data(db_path)

    # --- 1. Get Source ---
    source_url, source_id = None, None
    while True:
        source_input = input("\nEnter the SOURCE profile URL: ")
        normalized = normalize_url(source_input)
        if normalized and normalized in url_to_id:
            source_url = normalized; source_id = url_to_id[source_url]
            print(f"  > Source Found: {id_to_info[source_id]['name']}")
            break
        else: print("  > ERROR: URL not found in the database. Please try again.")

    # --- 2. Get Targets ---
    target_urls, target_ids = [], []
    print("\nEnter one or more TARGET profile URLs.")
    while True:
        target_input = input(f"  Enter Target URL #{len(target_urls) + 1} (or press Enter to finish): ")
        if not target_input:
            if not target_urls: print("  > WARNING: No targets entered. Please add at least one."); continue
            break
        
        normalized = normalize_url(target_input)
        if normalized and normalized in url_to_id:
            if normalized in target_urls: print("  > INFO: You've already added that target.")
            else:
                target_id = url_to_id[normalized]; target_urls.append(normalized); target_ids.append(target_id)
                print(f"    > Target Added: {id_to_info[target_id]['name']}")
        else: print("    > ERROR: URL not found in the database. It will be skipped.")

    # --- 3. Get Output Filename and Construct Full Path ---
    source_name = re.sub(r'[^a-zA-Z0-9]', '', id_to_info[source_id]['name'].split()[0]).lower()
    default_filename = f"{source_name}_export.json"
    output_filename_input = input(f"\nEnter output filename [default: {default_filename}]: ")
    output_filename = output_filename_input or default_filename
    
    # --- FIX IS HERE ---
    # We now explicitly join the output directory with the chosen filename.
    final_output_path = os.path.join(OUTPUT_DIR_NAME, output_filename)
    
    print(f"\nProcessing... will save to '{final_output_path}'")
    
    # --- 4. Pathfinding (Unchanged) ---
    all_nodes_in_paths = set(); all_edges_in_paths = set()
    print("Calculating source-to-target paths...")
    # ... (rest of pathfinding logic is the same)
    for target_id in target_ids:
        try:
            path = nx.shortest_path(G, source=source_id, target=target_id)
            all_nodes_in_paths.update(path); all_edges_in_paths.update(zip(path[:-1], path[1:]))
        except nx.NetworkXNoPath: print(f"  - No path found from source to target ID {target_id}")

    if len(target_ids) > 1:
        print("Calculating target-to-target paths...")
        for t1, t2 in combinations(target_ids, 2):
            try:
                path = nx.shortest_path(G, source=t1, target=t2)
                all_nodes_in_paths.update(path); all_edges_in_paths.update(zip(path[:-1], path[1:]))
            except nx.NetworkXNoPath: print(f"  - No path found between target IDs {t1} and {t2}")

    # --- 5. Data Export (Saves to the correct path) ---
    nodes_for_json = []; edges_for_json = []
    # ... (logic to build nodes_for_json is the same)
    for node_id in all_nodes_in_paths:
        info = id_to_info.get(node_id, {}); node_type = "intermediate"
        if node_id == source_id: node_type = "source"
        elif node_id in target_ids: node_type = "target"
        nodes_for_json.append({"id": node_id, "label": info.get('name'), "url": info.get('profile_url'), "type": node_type})
    
    edges_for_json = [{"source": u, "target": v} for u, v in all_edges_in_paths]
    export_data = {"nodes": nodes_for_json, "edges": edges_for_json}

    with open(final_output_path, 'w') as f:
        json.dump(export_data, f, indent=4)
        
    print(f"\n✅ Success! Exported {len(nodes_for_json)} nodes and {len(edges_for_json)} edges to '{final_output_path}'.")
    print("You can now open this file with graphlink_viewer.py")

if __name__ == "__main__":
    main()