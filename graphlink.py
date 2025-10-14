# graphlink.py
# The main program for the GraphLink Project.
# This tool uses the graphlink.sqlite database to export data and find paths.

import pandas as pd
import os
import networkx as nx
import sqlite3
from urllib.parse import urlparse, urlunparse

# --- Configuration ---
OUTPUT_DIR_NAME = "output_graphlink"
DB_FILENAME = "graphlink.sqlite"
OUTPUT_EDGES_FILENAME = "gephi_edge_list.csv"
OUTPUT_NODES_FILENAME = "gephi_node_list.csv"

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

# --- Analysis Functions ---

def generate_gephi_files_from_db(db_path, output_dir):
    print("\nQuerying database to generate Gephi files...")
    conn = sqlite3.connect(db_path)
    nodes_df = pd.read_sql_query("SELECT profile_url AS Id, name AS Label FROM profiles", conn)
    edges_query = """
        SELECT p1.profile_url AS Source, p2.profile_url AS Target
        FROM friendships f JOIN profiles p1 ON f.profile_id_1 = p1.id JOIN profiles p2 ON f.profile_id_2 = p2.id
    """
    edges_df = pd.read_sql_query(edges_query, conn)
    conn.close()
    
    node_path = os.path.join(output_dir, OUTPUT_NODES_FILENAME)
    edge_path = os.path.join(output_dir, OUTPUT_EDGES_FILENAME)
    
    nodes_df.to_csv(node_path, index=False)
    edges_df.to_csv(edge_path, index=False)
    
    print(f"✅ Success! Generated 2 files in '{output_dir}':")
    print(f"  - Edges: {OUTPUT_EDGES_FILENAME} ({len(edges_df)} friendships)")
    print(f"  - Nodes: {OUTPUT_NODES_FILENAME} ({len(nodes_df)} unique people)")

def run_shortest_path_tool(db_path):
    print("\n--- GraphLink: Shortest Path Finder ---")
    print("Loading graph from database...")
    conn = sqlite3.connect(db_path)
    edges_df = pd.read_sql_query("SELECT profile_id_1, profile_id_2 FROM friendships", conn)
    
    G = nx.from_pandas_edgelist(edges_df, 'profile_id_1', 'profile_id_2')
    print(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    url_to_id = pd.read_sql_query("SELECT profile_url, id FROM profiles", conn, index_col='profile_url').to_dict()['id']
    id_to_url = {v: k for k, v in url_to_id.items()}
    conn.close()

    while True:
        start_url_input = input("Enter start URL (or 'exit'): ")
        if start_url_input.lower() == 'exit': break
        start_url = normalize_url(start_url_input)

        end_url_input = input("Enter target URL: ")
        end_url = normalize_url(end_url_input)

        if start_url not in url_to_id: print("Start URL not in database."); continue
        if end_url not in url_to_id: print("Target URL not in database."); continue

        start_node_id, end_node_id = url_to_id[start_url], url_to_id[end_url]

        try:
            path_ids = nx.shortest_path(G, source=start_node_id, target=end_node_id)
            path_urls = [id_to_url[id] for id in path_ids]
            print("\n✅ Shortest path found:")
            for i, url in enumerate(path_urls): print(f"{i}: {url}")
            print(f"Path requires {len(path_urls)-1} introductions.\n")
        except nx.NetworkXNoPath:
            print("❌ No path found between these two people in the network.\n")

# --- Main Execution Block ---
if __name__ == "__main__":
    output_dir = os.path.join(os.path.abspath('.'), OUTPUT_DIR_NAME)
    db_path = os.path.join(output_dir, DB_FILENAME)
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        print("Please run 'graphlinkdb.py' first to build the database.")
        exit()

    while True:
        print("\n--- GraphLink Main Menu ---")
        print("1: Export latest graph files for Gephi")
        print("2: Find shortest path between two people")
        print("3: Exit")
        choice = input("Enter your choice (1/2/3): ")

        if choice == '1':
            generate_gephi_files_from_db(db_path, output_dir)
        elif choice == '2':
            run_shortest_path_tool(db_path)
        elif choice == '3':
            print("Exiting GraphLink.")
            break
        else:
            print("Invalid choice. Please try again.")