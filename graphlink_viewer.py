# graphlink_viewer.py (Final Version with Pan, Zoom, Labels, and Highlighting)
# This application now includes full camera controls.
# - Middle Mouse Scroll: Zoom in and out
# - Middle Mouse Click + Drag: Pan the view
# - R Key: Reset the view

import pygame
import json
import networkx as nx
import sys
import webbrowser
import os

# --- Configuration ---
OUTPUT_DIR_NAME = "output_graphlink"

# --- Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1600, 1000
INFO_PANEL_HEIGHT = 120
GRAPH_AREA_HEIGHT = SCREEN_HEIGHT - INFO_PANEL_HEIGHT
BG_COLOR = (20, 30, 40)
INFO_PANEL_COLOR = (40, 50, 60)
TEXT_COLOR = (230, 230, 230)
URL_COLOR = (100, 180, 255)
NODE_RADIUS = 10
NODE_COLOR = (0, 150, 255)
SOURCE_COLOR = (0, 255, 150)
TARGET_COLOR = (255, 150, 0)
SELECTED_COLOR = (255, 255, 0)
EDGE_COLOR = (70, 90, 110)
EDGE_WIDTH = 2
SOURCE_NODE_RADIUS = 15
HIGHLIGHT_COLOR = (255, 255, 255)
NODE_LABEL_COLOR = (200, 200, 200)

# --- Pygame Node Class (MODIFIED) ---
class PygameNode:
    def __init__(self, data, pos):
        self.id = data['id']; self.label = data['label']; self.url = data['url']; self.type = data['type']
        # These are the node's original "world" coordinates from the layout
        self.world_x, self.world_y = int(pos[0]), int(pos[1])
        
        if self.type == 'source':
            self.base_color = SOURCE_COLOR; self.radius = SOURCE_NODE_RADIUS
        elif self.type == 'target':
            self.base_color = TARGET_COLOR; self.radius = NODE_RADIUS
        else:
            self.base_color = NODE_COLOR; self.radius = NODE_RADIUS
        self.color = self.base_color
        
        # These will be updated each frame based on the camera
        self.screen_pos = (0, 0)
        self.screen_radius = 0
        self.screen_rect = pygame.Rect(0, 0, 0, 0)

    def update_screen_transform(self, camera_offset, zoom):
        """Calculates the node's position and size on the screen based on the camera."""
        # Apply zoom and then offset to the world coordinates
        self.screen_pos = (
            int(self.world_x * zoom + camera_offset.x),
            int(self.world_y * zoom + camera_offset.y)
        )
        self.screen_radius = max(2, int(self.radius * zoom)) # Ensure node is always visible
        
        # Update the collision rectangle for mouse clicks
        self.screen_rect = pygame.Rect(
            self.screen_pos[0] - self.screen_radius,
            self.screen_pos[1] - self.screen_radius,
            self.screen_radius * 2,
            self.screen_radius * 2
        )

# --- Main Pygame Function (MODIFIED) ---
def run_visualization(json_filepath):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"GraphLinkViewer - {os.path.basename(json_filepath)}")
    font_large = pygame.font.Font(None, 40); font_medium = pygame.font.Font(None, 30); font_small = pygame.font.Font(None, 18)
    
    # --- NEW: Camera and Pan State Variables ---
    camera_offset = pygame.Vector2(0, 0)
    zoom = 1.0
    panning = False
    pan_start_pos = (0, 0)

    try:
        with open(json_filepath, 'r') as f: data = json.load(f)
    except FileNotFoundError: print(f"Error: Cannot find the file '{json_filepath}'"); return
    
    G = nx.Graph()
    for node_data in data['nodes']: G.add_node(node_data['id'])
    for edge in data['edges']: G.add_edge(edge['source'], edge['target'])
    
    print("Calculating graph layout...")
    # The layout is calculated once in "world space" centered around (0,0) for easier zooming
    layout_pos = nx.spring_layout(G, scale=min(SCREEN_WIDTH/2, GRAPH_AREA_HEIGHT/2), center=(0, 0), iterations=150, seed=42)
    nodes = {node_data['id']: PygameNode(node_data, layout_pos[node_data['id']]) for node_data in data['nodes']}
    edges = data['edges']; selected_node = None; running = True
    
    # Start the camera centered on the graph area
    camera_offset.x = SCREEN_WIDTH / 2
    camera_offset.y = GRAPH_AREA_HEIGHT / 2
    
    while running:
        # --- Update node screen positions based on camera before handling events ---
        for node in nodes.values():
            node.update_screen_transform(camera_offset, zoom)

        # --- Event Loop (MODIFIED) ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False

            # --- NEW: Zooming Logic ---
            if event.type == pygame.MOUSEWHEEL:
                zoom_amount = 1.1 if event.y > 0 else 1 / 1.1
                zoom *= zoom_amount
                # Clamp zoom level to prevent issues
                zoom = max(0.1, min(zoom, 5.0))

            # --- NEW: Panning Logic ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2: # Middle mouse button
                    panning = True
                    pan_start_pos = event.pos
                if event.button == 1: # Left click (for selection)
                    if selected_node: selected_node.color = selected_node.base_color
                    selected_node = None
                    # Use the updated screen_rect for collision detection
                    for node in nodes.values():
                        if node.screen_rect.collidepoint(event.pos):
                            selected_node = node; selected_node.color = SELECTED_COLOR; break

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2: # Middle mouse button
                    panning = False
                if event.button == 1 and selected_node: # Left click release (for URL)
                    url_rect = pygame.Rect(20, GRAPH_AREA_HEIGHT + 65, 800, 30)
                    if url_rect.collidepoint(event.pos) and selected_node.url: webbrowser.open(selected_node.url)
            
            if event.type == pygame.MOUSEMOTION:
                if panning:
                    camera_offset.x += event.rel[0]
                    camera_offset.y += event.rel[1]
            
            # --- NEW: Reset View Logic ---
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    zoom = 1.0
                    camera_offset.x = SCREEN_WIDTH / 2
                    camera_offset.y = GRAPH_AREA_HEIGHT / 2

        # --- Drawing Logic (MODIFIED) ---
        screen.fill(BG_COLOR)

        # 1. Draw edges using updated screen positions
        for edge in edges:
            start_pos = nodes[edge['source']].screen_pos
            end_pos = nodes[edge['target']].screen_pos
            pygame.draw.line(screen, EDGE_COLOR, start_pos, end_pos, int(EDGE_WIDTH))

        # 2. Draw nodes and labels using updated screen positions and radius
        for node in nodes.values():
            if node.type == 'source':
                pygame.draw.circle(screen, HIGHLIGHT_COLOR, node.screen_pos, node.screen_radius, 3)
            
            pygame.draw.circle(screen, node.color, node.screen_pos, node.screen_radius)
            
            # Only draw labels if they are large enough to be readable
            if node.screen_radius > 5:
                label_surf = font_small.render(node.label, True, NODE_LABEL_COLOR)
                label_rect = label_surf.get_rect(center=(node.screen_pos[0], node.screen_pos[1] + node.screen_radius + 10))
                screen.blit(label_surf, label_rect)

        # 3. Draw the static info panel on top
        pygame.draw.rect(screen, INFO_PANEL_COLOR, (0, GRAPH_AREA_HEIGHT, SCREEN_WIDTH, INFO_PANEL_HEIGHT))
        if selected_node:
            name_surf = font_large.render(selected_node.label, True, TEXT_COLOR)
            url_surf = font_medium.render(selected_node.url, True, URL_COLOR)
            screen.blit(name_surf, (20, GRAPH_AREA_HEIGHT + 20)); screen.blit(url_surf, (20, GRAPH_AREA_HEIGHT + 65))
        else:
            help_surf = font_large.render("Click a node | Middle-Click to Pan | Scroll to Zoom | 'R' to Reset", True, TEXT_COLOR)
            screen.blit(help_surf, (20, GRAPH_AREA_HEIGHT + 40))
        
        pygame.display.flip()
    
    pygame.quit()

# --- Interactive File Selection Logic (Unchanged) ---
if __name__ == '__main__':
    # ... (the logic to find and list .json files is the same)
    if not os.path.isdir(OUTPUT_DIR_NAME): print(f"Error: Output directory '{OUTPUT_DIR_NAME}' not found."); sys.exit()
    try: json_files = [f for f in os.listdir(OUTPUT_DIR_NAME) if f.lower().endswith('.json')]
    except FileNotFoundError: json_files = []
    if not json_files: print(f"No export files (.json) found in the '{OUTPUT_DIR_NAME}' directory."); sys.exit()
    print("\n--- Select a GraphLink Export to View ---")
    for i, filename in enumerate(json_files, 1): print(f"  {i}: {filename}")
    selected_file = None
    while True:
        try:
            choice_str = input(f"\nEnter the number of the file to load (1-{len(json_files)}): ")
            choice_index = int(choice_str)
            if 1 <= choice_index <= len(json_files): selected_file = json_files[choice_index - 1]; break
            else: print("Invalid number.")
        except (ValueError, IndexError): print("Invalid input.")
        except (KeyboardInterrupt): print("\nExiting."); sys.exit()
    full_path = os.path.join(OUTPUT_DIR_NAME, selected_file)
    print(f"Loading '{full_path}'...")
    run_visualization(full_path)