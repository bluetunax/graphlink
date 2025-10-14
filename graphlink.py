# graphlink.py
# The main program for the GraphLink Project.
# This tool uses the graphlink.sqlite database to export data and find paths.

import pandas as pd
import os
import networkx as nx
import sqlite3
import json
from urllib.parse import urlparse, urlunparse

# --- Configuration ---
OUTPUT_DIR_NAME = "output_graphlink"
DB_FILENAME = "graphlink.sqlite"
BLACKLIST_FILENAME = "blacklist.json"
OUTPUT_EDGES_FILENAME = "gephi_edge_list.csv"
OUTPUT_NODES_FILENAME = "gephi_node_list.csv"

# --- Helper Function ---
def normalize_url(url):
    # This function is unchanged
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

# --- Blacklist Functions ---
def load_blacklist(path):
    # This function is unchanged
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_blacklist(path, blacklist_urls):
    # This function is unchanged
    with open(path, 'w') as f:
        json.dump(blacklist_urls, f, indent=4)
    print("Blacklist saved.")

def manage_blacklist(path):
    # This function is unchanged
    while True:
        blacklist = load_blacklist(path)
        print("\n--- Blacklist Manager ---")
        if not blacklist:
            print("Current blacklist is empty.")
        else:
            print("Currently blacklisted URLs:")
            for i, url in enumerate(blacklist):
                print(f"  {i+1}: {url}")
        print("\nOptions: 1: Add URL, 2: Remove URL, 3: Return to main menu")
        choice = input("Enter your choice: ")
        if choice == '1':
            url_to_add = normalize_url(input("Enter the full URL to add: "))
            if url_to_add and url_to_add not in blacklist:
                blacklist.append(url_to_add)
                save_blacklist(path, blacklist)
            else: print("Invalid or duplicate URL.")
        elif choice == '2':
            try:
                idx = int(input("Enter the number of the URL to remove: ")) - 1
                if 0 <= idx < len(blacklist):
                    blacklist.pop(idx)
                    save_blacklist(path, blacklist)
                else: print("Invalid number.")
            except ValueError: print("Please enter a valid number.")
        elif choice == '3': break
        else: print("Invalid choice.")

# --- Analysis Functions ---
def generate_gephi_files_from_db(db_path, output_dir):
    # This function is unchanged
    print("\nQuerying database to generate Gephi files...")
    conn = sqlite3.connect(db_path)
    nodes_df = pd.read_sql_query("SELECT profile_url AS Id, name AS Label FROM profiles", conn)
    edges_query = "SELECT p1.profile_url AS Source, p2.profile_url AS Target FROM friendships f JOIN profiles p1 ON f.profile_id_1 = p1.id JOIN profiles p2 ON f.profile_id_2 = p2.id"
    edges_df = pd.read_sql_query(edges_query, conn)
    conn.close()
    node_path = os.path.join(output_dir, OUTPUT_NODES_FILENAME)
    edge_path = os.path.join(output_dir, OUTPUT_EDGES_FILENAME)
    nodes_df.to_csv(node_path, index=False)
    edges_df.to_csv(edge_path, index=False)
    print(f"✅ Success! Generated 2 files in '{output_dir}'.")

def run_shortest_path_tool(db_path, blacklist_path):
    print("\n--- GraphLink: Shortest Path Finder ---")
    print("Loading graph from database...")
    conn = sqlite3.connect(db_path)
    edges_df = pd.read_sql_query("SELECT profile_id_1, profile_id_2 FROM friendships", conn)
    profiles_df = pd.read_sql_query("SELECT id, profile_url, name FROM profiles", conn)
    conn.close()
    
    G = nx.from_pandas_edgelist(edges_df, 'profile_id_1', 'profile_id_2')
    print(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    url_to_id = pd.Series(profiles_df.id.values, index=profiles_df.profile_url).to_dict()
    id_to_url = pd.Series(profiles_df.profile_url.values, index=profiles_df.id).to_dict()
    id_to_name = pd.Series(profiles_df.name.values, index=profiles_df.id).to_dict()
    
    while True:
        blacklist_urls = load_blacklist(blacklist_path)
        G_temp = G.copy()
        blacklisted_node_ids = [url_to_id.get(url) for url in blacklist_urls if url_to_id.get(url)]
        G_temp.remove_nodes_from(blacklisted_node_ids)
        
        start_url_input = input("Enter start URL (or 'exit'): ")
        if start_url_input.lower() == 'exit': break
        start_url = normalize_url(start_url_input)

        end_url_input = input("Enter target URL: ")
        end_url = normalize_url(end_url_input)

        if start_url not in url_to_id or end_url not in url_to_id:
            print("Start or Target URL not in database."); continue
        
        start_node_id, end_node_id = url_to_id[start_url], url_to_id[end_url]
        if start_node_id in blacklisted_node_ids or end_node_id in blacklisted_node_ids:
            print("Error: Start or Target URL is on the blacklist."); continue

        # --- MODIFICATION START ---
        show_top_3 = input("Show top 3 shortest paths? (y/n) [n]: ").lower()

        try:
            if show_top_3 == 'y':
                print("\nSearching for top 3 shortest paths...")
                # Use the generator for k-shortest paths
                paths_generator = nx.shortest_simple_paths(G_temp, source=start_node_id, target=end_node_id)
                found_paths_count = 0
                for i, path_ids in enumerate(paths_generator):
                    if i >= 3: # Stop after finding 3 paths
                        break
                    
                    print(f"\n--- Path #{i+1} (Length: {len(path_ids)-1} introductions) ---")
                    for node_id in path_ids:
                        name = id_to_name.get(node_id, "Unknown Name")
                        url = id_to_url.get(node_id, "Unknown URL")
                        print(f"  -> {name}  ({url})")
                    found_paths_count += 1
                
                if found_paths_count == 0:
                    # This case is technically handled by the exception, but good for clarity
                    print("❌ No paths found between these two people in the network.\n")
                else:
                    print(f"\nFound {found_paths_count} path(s).\n")

            else:
                # Original behavior for finding just the single fastest path
                path_ids = nx.shortest_path(G_temp, source=start_node_id, target=end_node_id)
                print("\n✅ Shortest path found:")
                for i, node_id in enumerate(path_ids):
                    name = id_to_name.get(node_id, "Unknown Name")
                    url = id_to_url.get(node_id, "Unknown URL")
                    print(f"{i}: {name}  ({url})")
                print(f"\nPath requires {len(path_ids)-1} introductions.\n")

        except nx.NetworkXNoPath:
            print("❌ No path found between these two people in the network.\n")
        # --- MODIFICATION END ---


# --- Main Execution Block ---
if __name__ == "__main__":
    output_dir = os.path.join(os.path.abspath('.'), OUTPUT_DIR_NAME)
    db_path = os.path.join(output_dir, DB_FILENAME)
    blacklist_path = os.path.join(output_dir, BLACKLIST_FILENAME)
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        print("Please run 'graphlinkdb.py' first to build the database.")
        exit()

    while True:
        print("\n--- GraphLink Main Menu ---")
        print("1: Export latest graph files for Gephi")
        print("2: Find shortest path between two people")
        print("3: Manage Blacklist")
        print("4: Exit")
        choice = input("Enter your choice (1/2/3/4): ")

        if choice == '1':
            generate_gephi_files_from_db(db_path, output_dir)
        elif choice == '2':
            run_shortest_path_tool(db_path, blacklist_path)
        elif choice == '3':
            manage_blacklist(blacklist_path)
        elif choice == '4':
            print("Exiting GraphLink.")
            break
        else:
            print("Invalid choice. Please try again.")
