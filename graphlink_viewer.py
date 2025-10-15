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
import pyperclip

# --- Configuration & Constants ---
OUTPUT_DIR_NAME = "output_graphlink"
SCREEN_WIDTH, SCREEN_HEIGHT = 1600, 1000
INFO_PANEL_HEIGHT = 120
GRAPH_AREA_HEIGHT = SCREEN_HEIGHT - INFO_PANEL_HEIGHT
# ... (All other color and size constants are the same)
BG_COLOR, INFO_PANEL_COLOR = (20, 30, 40), (40, 50, 60)
TEXT_COLOR, URL_COLOR = (230, 230, 230), (100, 180, 255)
NODE_RADIUS, SOURCE_NODE_RADIUS = 10, 15
NODE_COLOR, SOURCE_COLOR, TARGET_COLOR = (0, 150, 255), (0, 255, 150), (255, 150, 0)
SELECTED_COLOR, HIGHLIGHT_COLOR = (255, 255, 0), (255, 255, 255)
EDGE_COLOR, EDGE_WIDTH = (70, 90, 110), 2
NODE_LABEL_COLOR = (200, 200, 200)

# --- NEW: Button Constants ---
BUTTON_WIDTH, BUTTON_HEIGHT = 90, 35
BUTTON_COLOR = (80, 100, 120)
BUTTON_HOVER_COLOR = (110, 130, 150)
BUTTON_TEXT_COLOR = (255, 255, 255)

# --- Pygame Node Class (Unchanged) ---
class PygameNode:
    # ... (This class is exactly the same as the previous version)
    def __init__(self, data, pos):
        self.id = data['id']; self.label = data['label']; self.url = data['url']; self.type = data['type']
        self.world_x, self.world_y = int(pos[0]), int(pos[1])
        if self.type == 'source': self.base_color, self.radius = SOURCE_COLOR, SOURCE_NODE_RADIUS
        elif self.type == 'target': self.base_color, self.radius = TARGET_COLOR, NODE_RADIUS
        else: self.base_color, self.radius = NODE_COLOR, NODE_RADIUS
        self.color = self.base_color; self.screen_pos = (0, 0); self.screen_radius = 0
        self.screen_rect = pygame.Rect(0, 0, 0, 0)

    def update_screen_transform(self, camera_offset, zoom):
        self.screen_pos = (int(self.world_x * zoom + camera_offset.x), int(self.world_y * zoom + camera_offset.y))
        self.screen_radius = max(2, int(self.radius * zoom))
        self.screen_rect = pygame.Rect(self.screen_pos[0] - self.screen_radius, self.screen_pos[1] - self.screen_radius, self.screen_radius * 2, self.screen_radius * 2)

# --- Main Pygame Function (MODIFIED) ---
def run_visualization(json_filepath):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"GraphLinkViewer - {os.path.basename(json_filepath)}")
    font_large = pygame.font.Font(None, 40); font_medium = pygame.font.Font(None, 30); font_small = pygame.font.Font(None, 18); font_button = pygame.font.Font(None, 24)

    # Camera and Pan state... (unchanged)
    camera_offset = pygame.Vector2(SCREEN_WIDTH / 2, GRAPH_AREA_HEIGHT / 2); zoom = 1.0
    panning = False; pan_start_pos = (0, 0)
    
    # NEW: State variables for copy button feedback
    copy_feedback_text = ""
    copy_feedback_timer = 0
    
    # Data Loading... (unchanged)
    try:
        with open(json_filepath, 'r') as f: data = json.load(f)
    except FileNotFoundError: print(f"Error: Cannot find the file '{json_filepath}'"); return
    G = nx.Graph()
    for node_data in data['nodes']: G.add_node(node_data['id'])
    for edge in data['edges']: G.add_edge(edge['source'], edge['target'])
    print("Calculating graph layout...")
    layout_pos = nx.spring_layout(G, scale=min(SCREEN_WIDTH/2, GRAPH_AREA_HEIGHT/2), center=(0, 0), iterations=150, seed=42)
    nodes = {node_data['id']: PygameNode(node_data, layout_pos[node_data['id']]) for node_data in data['nodes']}
    edges = data['edges']; selected_node = None; running = True
    
    while running:
        # Update node screen positions
        for node in nodes.values(): node.update_screen_transform(camera_offset, zoom)

        # Get mouse position once per frame for hover checks
        mouse_pos = pygame.mouse.get_pos()
        
        # Manage copy feedback timer
        if copy_feedback_timer > 0:
            copy_feedback_timer -= 1
            if copy_feedback_timer == 0: copy_feedback_text = ""
        
        # Event Loop
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.MOUSEWHEEL:
                zoom_amount = 1.1 if event.y > 0 else 1 / 1.1
                zoom = max(0.1, min(zoom * zoom_amount, 5.0))
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2: panning = True; pan_start_pos = event.pos
                if event.button == 1:
                    # --- NEW: Copy Button Click Logic ---
                    if selected_node:
                        # Define button rectangles here to use for click detection
                        name_text_rect = font_large.render(selected_node.label, True, TEXT_COLOR).get_rect(topleft=(20, GRAPH_AREA_HEIGHT + 20))
                        url_text_rect = font_medium.render(selected_node.url, True, URL_COLOR).get_rect(topleft=(20, GRAPH_AREA_HEIGHT + 65))
                        name_copy_rect = pygame.Rect(name_text_rect.right + 20, name_text_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
                        url_copy_rect = pygame.Rect(url_text_rect.right + 20, url_text_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)

                        if name_copy_rect.collidepoint(event.pos):
                            pyperclip.copy(selected_node.label)
                            copy_feedback_text = "Name Copied!"
                            copy_feedback_timer = 120 # 2 seconds at 60fps
                        elif url_copy_rect.collidepoint(event.pos):
                            pyperclip.copy(selected_node.url)
                            copy_feedback_text = "URL Copied!"
                            copy_feedback_timer = 120
                        else:
                            # If not clicking a button, do node selection
                            if selected_node: selected_node.color = selected_node.base_color
                            selected_node = None
                            for node in nodes.values():
                                if node.screen_rect.collidepoint(event.pos):
                                    selected_node = node; selected_node.color = SELECTED_COLOR; break
                    else:
                        # If no node is selected, just do node selection
                        for node in nodes.values():
                            if node.screen_rect.collidepoint(event.pos):
                                selected_node = node; selected_node.color = SELECTED_COLOR; break

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2: panning = False
            if event.type == pygame.MOUSEMOTION and panning:
                camera_offset += event.rel
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                zoom = 1.0; camera_offset.xy = SCREEN_WIDTH / 2, GRAPH_AREA_HEIGHT / 2

        # Drawing Logic
        screen.fill(BG_COLOR)
        # Draw edges and nodes... (unchanged)
        for edge in edges: pygame.draw.line(screen, EDGE_COLOR, nodes[edge['source']].screen_pos, nodes[edge['target']].screen_pos, EDGE_WIDTH)
        for node in nodes.values():
            if node.type == 'source': pygame.draw.circle(screen, HIGHLIGHT_COLOR, node.screen_pos, node.screen_radius, 3)
            pygame.draw.circle(screen, node.color, node.screen_pos, node.screen_radius)
            if node.screen_radius > 5:
                label_surf = font_small.render(node.label, True, NODE_LABEL_COLOR)
                screen.blit(label_surf, label_surf.get_rect(center=(node.screen_pos[0], node.screen_pos[1] + node.screen_radius + 10)))
        
        # --- MODIFIED: Draw Info Panel ---
        pygame.draw.rect(screen, INFO_PANEL_COLOR, (0, GRAPH_AREA_HEIGHT, SCREEN_WIDTH, INFO_PANEL_HEIGHT))
        if selected_node:
            # Draw Name and URL
            name_surf = font_large.render(selected_node.label, True, TEXT_COLOR)
            name_rect = screen.blit(name_surf, (20, GRAPH_AREA_HEIGHT + 20))
            url_surf = font_medium.render(selected_node.url, True, URL_COLOR)
            url_rect = screen.blit(url_surf, (20, GRAPH_AREA_HEIGHT + 65))
            
            # --- NEW: Define and Draw Buttons ---
            name_copy_rect = pygame.Rect(name_rect.right + 20, name_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
            url_copy_rect = pygame.Rect(url_rect.right + 20, url_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
            
            # Name button
            name_button_color = BUTTON_HOVER_COLOR if name_copy_rect.collidepoint(mouse_pos) else BUTTON_COLOR
            pygame.draw.rect(screen, name_button_color, name_copy_rect, border_radius=5)
            name_copy_surf = font_button.render("Copy", True, BUTTON_TEXT_COLOR)
            screen.blit(name_copy_surf, name_copy_surf.get_rect(center=name_copy_rect.center))

            # URL button
            url_button_color = BUTTON_HOVER_COLOR if url_copy_rect.collidepoint(mouse_pos) else BUTTON_COLOR
            pygame.draw.rect(screen, url_button_color, url_copy_rect, border_radius=5)
            url_copy_surf = font_button.render("Copy", True, BUTTON_TEXT_COLOR)
            screen.blit(url_copy_surf, url_copy_surf.get_rect(center=url_copy_rect.center))
            
            # Draw Copy Feedback
            if copy_feedback_timer > 0:
                feedback_surf = font_medium.render(copy_feedback_text, True, SOURCE_COLOR)
                screen.blit(feedback_surf, (url_copy_rect.right + 30, url_copy_rect.centery - feedback_surf.get_height()//2))

        else:
            help_surf = font_large.render("Click a node | Middle-Click to Pan | Scroll to Zoom | 'R' to Reset", True, TEXT_COLOR)
            screen.blit(help_surf, (20, GRAPH_AREA_HEIGHT + 40))
        
        pygame.display.flip()
    
    pygame.quit()

# --- Interactive File Selection Logic (Unchanged) ---
if __name__ == '__main__':
    # ... (This entire section is the same)
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
