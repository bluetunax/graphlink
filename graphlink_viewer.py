# graphlink_viewer.py (Final, Complete, and Optimized Version)
# This is the complete, feature-rich application with a 60 FPS limit for performance.
# - Middle Mouse Scroll: Zoom in and out
# - Middle Mouse Click + Drag: Pan the view
# - R Key: Reset the view
# - Search bar with auto-complete
# - Color picker for selected nodes
# - Copy buttons for name and URL

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
INFO_PANEL_HEIGHT = 160
GRAPH_AREA_HEIGHT = SCREEN_HEIGHT - INFO_PANEL_HEIGHT
BG_COLOR, INFO_PANEL_COLOR = (20, 30, 40), (40, 50, 60)
TEXT_COLOR, URL_COLOR = (230, 230, 230), (100, 180, 255)
NODE_RADIUS, SOURCE_NODE_RADIUS = 10, 15
NODE_COLOR, SOURCE_COLOR, TARGET_COLOR = (0, 150, 255), (0, 255, 150), (255, 150, 0)
SELECTED_COLOR, HIGHLIGHT_COLOR = (255, 255, 0), (255, 255, 255)
EDGE_COLOR, EDGE_WIDTH = (70, 90, 110), 2
NODE_LABEL_COLOR = (200, 200, 200)
BUTTON_WIDTH, BUTTON_HEIGHT = 90, 35
BUTTON_COLOR, BUTTON_HOVER_COLOR = (80, 100, 120), (110, 130, 150)
BUTTON_TEXT_COLOR = (255, 255, 255)
SEARCH_BAR_RECT = pygame.Rect(SCREEN_WIDTH - 420, GRAPH_AREA_HEIGHT + 20, 400, 40)
SEARCH_ACTIVE_COLOR = (200, 200, 200)
SEARCH_INACTIVE_COLOR = (100, 100, 100)
COLOR_PALETTE = [
    (255, 80, 80), (80, 255, 150), (80, 150, 255),
    (255, 150, 80), (200, 100, 255), NODE_COLOR
]

# --- Pygame Node Class ---
class PygameNode:
    def __init__(self, data, pos):
        self.id = data['id']; self.label = data['label']; self.url = data['url']; self.type = data['type']
        self.world_x, self.world_y = int(pos[0]), int(pos[1])
        if self.type == 'source': self.base_color, self.radius = SOURCE_COLOR, SOURCE_NODE_RADIUS
        elif self.type == 'target': self.base_color, self.radius = TARGET_COLOR, NODE_RADIUS
        else: self.base_color, self.radius = NODE_COLOR, NODE_RADIUS
        self.color = self.base_color
        self.screen_pos = (0, 0)
        self.screen_radius = 0
        self.screen_rect = pygame.Rect(0, 0, 0, 0)

    def update_screen_transform(self, camera_offset, zoom):
        self.screen_pos = (int(self.world_x * zoom + camera_offset.x), int(self.world_y * zoom + camera_offset.y))
        self.screen_radius = max(2, int(self.radius * zoom))
        self.screen_rect = pygame.Rect(self.screen_pos[0] - self.screen_radius, self.screen_pos[1] - self.screen_radius, self.screen_radius * 2, self.screen_radius * 2)

# --- Main Pygame Function ---
def run_visualization(json_filepath):
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"GraphLinkViewer - {os.path.basename(json_filepath)}")
    fonts = {
        'large': pygame.font.Font(None, 40), 'medium': pygame.font.Font(None, 30),
        'small': pygame.font.Font(None, 18), 'button': pygame.font.Font(None, 24),
        'search': pygame.font.Font(None, 32)
    }

    # Create a clock object to manage the frame rate
    clock = pygame.time.Clock()

    # State variables
    camera_offset = pygame.Vector2(SCREEN_WIDTH / 2, GRAPH_AREA_HEIGHT / 2)
    zoom = 1.0
    panning = False
    pan_start_pos = (0, 0)
    copy_feedback_text, copy_feedback_timer = "", 0
    search_active = False
    search_text = ""
    search_suggestions = []

    # Data Loading
    try:
        with open(json_filepath, 'r') as f: data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Cannot find file '{json_filepath}'")
        return

    G = nx.Graph()
    node_list = []
    for node_data in data['nodes']:
        G.add_node(node_data['id'])
        node_list.append(node_data)
    for edge in data['edges']: G.add_edge(edge['source'], edge['target'])
    
    print("Calculating layout...")
    layout_pos = nx.spring_layout(G, scale=min(SCREEN_WIDTH/2, GRAPH_AREA_HEIGHT/2), center=(0, 0), iterations=150, seed=42)
    nodes = {node_data['id']: PygameNode(node_data, layout_pos[node_data['id']]) for node_data in data['nodes']}
    edges = data['edges']
    selected_node = None
    running = True

    while running:
        for node in nodes.values():
            node.update_screen_transform(camera_offset, zoom)

        mouse_pos = pygame.mouse.get_pos()
        if copy_feedback_timer > 0:
            copy_feedback_timer -= 1
            if copy_feedback_timer == 0:
                copy_feedback_text = ""

        # Event Loop
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if search_active:
                    if event.key == pygame.K_BACKSPACE:
                        search_text = search_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        if search_suggestions:
                            node_id_to_jump = search_suggestions[0][1]
                            selected_node = nodes[node_id_to_jump]
                            zoom = 1.5
                            target_x = selected_node.world_x * zoom
                            target_y = selected_node.world_y * zoom
                            camera_offset.x = SCREEN_WIDTH / 2 - target_x
                            camera_offset.y = GRAPH_AREA_HEIGHT / 2 - target_y
                            search_active, search_text, search_suggestions = False, "", []
                    else:
                        search_text += event.unicode
                    
                    if search_text:
                        search_suggestions = [(n['label'], n['id']) for n in node_list if search_text.lower() in n['label'].lower()][:5]
                    else:
                        search_suggestions = []
                elif event.key == pygame.K_r:
                    zoom = 1.0
                    camera_offset.xy = SCREEN_WIDTH / 2, GRAPH_AREA_HEIGHT / 2

            if event.type == pygame.MOUSEWHEEL:
                zoom_amount = 1.1 if event.y > 0 else 1 / 1.1
                zoom = max(0.1, min(zoom * zoom_amount, 5.0))

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2:
                    panning = True
                    pan_start_pos = event.pos
                if event.button == 1:
                    clicked_on_ui = False
                    if SEARCH_BAR_RECT.collidepoint(event.pos):
                        search_active = True
                        clicked_on_ui = True
                    else:
                        search_active = False

                    for i, (label, node_id) in enumerate(search_suggestions):
                        suggestion_rect = pygame.Rect(SEARCH_BAR_RECT.x, SEARCH_BAR_RECT.y - 30 * (i + 1), SEARCH_BAR_RECT.width, 30)
                        if suggestion_rect.collidepoint(event.pos):
                            selected_node = nodes[node_id]
                            zoom = 1.5
                            target_x = selected_node.world_x * zoom
                            target_y = selected_node.world_y * zoom
                            camera_offset.x = SCREEN_WIDTH / 2 - target_x
                            camera_offset.y = GRAPH_AREA_HEIGHT / 2 - target_y
                            search_active, search_text, search_suggestions = False, "", []
                            clicked_on_ui = True
                            break
                    
                    if selected_node and not clicked_on_ui:
                        name_text_rect = fonts['large'].render(selected_node.label, True, TEXT_COLOR).get_rect(topleft=(20, GRAPH_AREA_HEIGHT + 20))
                        url_text_rect = fonts['medium'].render(selected_node.url, True, URL_COLOR).get_rect(topleft=(20, GRAPH_AREA_HEIGHT + 65))
                        name_copy_rect = pygame.Rect(name_text_rect.right + 10, name_text_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
                        url_copy_rect = pygame.Rect(url_text_rect.right + 10, url_text_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
                        
                        if name_copy_rect.collidepoint(event.pos):
                            pyperclip.copy(selected_node.label); copy_feedback_text = "Name Copied!"; copy_feedback_timer = 120
                            clicked_on_ui = True
                        elif url_copy_rect.collidepoint(event.pos):
                            pyperclip.copy(selected_node.url); copy_feedback_text = "URL Copied!"; copy_feedback_timer = 120
                            clicked_on_ui = True

                        for i, color in enumerate(COLOR_PALETTE):
                            color_rect = pygame.Rect(20 + i * 40, GRAPH_AREA_HEIGHT + 110, 30, 30)
                            if color_rect.collidepoint(event.pos):
                                selected_node.base_color = color
                                clicked_on_ui = True
                                break
                    
                    if not clicked_on_ui:
                        if selected_node:
                            selected_node.color = selected_node.base_color
                        selected_node = None
                        for node in reversed(list(nodes.values())):
                            if node.screen_rect.collidepoint(event.pos):
                                selected_node = node
                                selected_node.color = SELECTED_COLOR
                                break

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2:
                    panning = False
            if event.type == pygame.MOUSEMOTION:
                if panning:
                    camera_offset += event.rel

        # Drawing Logic
        screen.fill(BG_COLOR)

        for edge in edges:
            pygame.draw.line(screen, EDGE_COLOR, nodes[edge['source']].screen_pos, nodes[edge['target']].screen_pos, EDGE_WIDTH)

        for node in nodes.values():
            if node.type == 'source':
                pygame.draw.circle(screen, HIGHLIGHT_COLOR, node.screen_pos, node.screen_radius, 3)
            pygame.draw.circle(screen, node.color, node.screen_pos, node.screen_radius)
            if node.screen_radius > 5:
                label_surf = fonts['small'].render(node.label, True, NODE_LABEL_COLOR)
                screen.blit(label_surf, label_surf.get_rect(center=(node.screen_pos[0], node.screen_pos[1] + node.screen_radius + 10)))
        
        pygame.draw.rect(screen, INFO_PANEL_COLOR, (0, GRAPH_AREA_HEIGHT, SCREEN_WIDTH, INFO_PANEL_HEIGHT))
        if selected_node:
            name_surf = fonts['large'].render(selected_node.label, True, TEXT_COLOR); name_rect = screen.blit(name_surf, (20, GRAPH_AREA_HEIGHT + 20))
            url_surf = fonts['medium'].render(selected_node.url, True, URL_COLOR); url_rect = screen.blit(url_surf, (20, GRAPH_AREA_HEIGHT + 65))
            name_copy_rect = pygame.Rect(name_rect.right + 10, name_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
            url_copy_rect = pygame.Rect(url_rect.right + 10, url_rect.centery - BUTTON_HEIGHT//2, BUTTON_WIDTH, BUTTON_HEIGHT)
            
            pygame.draw.rect(screen, BUTTON_HOVER_COLOR if name_copy_rect.collidepoint(mouse_pos) else BUTTON_COLOR, name_copy_rect, border_radius=5)
            screen.blit(fonts['button'].render("Copy", True, BUTTON_TEXT_COLOR), fonts['button'].render("Copy", True, BUTTON_TEXT_COLOR).get_rect(center=name_copy_rect.center))
            pygame.draw.rect(screen, BUTTON_HOVER_COLOR if url_copy_rect.collidepoint(mouse_pos) else BUTTON_COLOR, url_copy_rect, border_radius=5)
            screen.blit(fonts['button'].render("Copy", True, BUTTON_TEXT_COLOR), fonts['button'].render("Copy", True, BUTTON_TEXT_COLOR).get_rect(center=url_copy_rect.center))

            for i, color in enumerate(COLOR_PALETTE):
                color_rect = pygame.Rect(20 + i * 40, GRAPH_AREA_HEIGHT + 110, 30, 30)
                pygame.draw.rect(screen, color, color_rect, border_radius=5)
            
            if copy_feedback_timer > 0:
                feedback_surf = fonts['medium'].render(copy_feedback_text, True, SOURCE_COLOR)
                screen.blit(feedback_surf, (url_copy_rect.right + 20, url_copy_rect.centery - feedback_surf.get_height()//2))
        else:
            help_surf = fonts['large'].render("Click a node | Middle-Click to Pan | Scroll to Zoom | 'R' to Reset", True, TEXT_COLOR)
            screen.blit(help_surf, (20, GRAPH_AREA_HEIGHT + 40))
        
        search_border_color = SEARCH_ACTIVE_COLOR if search_active else SEARCH_INACTIVE_COLOR
        pygame.draw.rect(screen, search_border_color, SEARCH_BAR_RECT, 2, border_radius=5)
        search_surf = fonts['search'].render(search_text, True, TEXT_COLOR)
        screen.blit(search_surf, (SEARCH_BAR_RECT.x + 10, SEARCH_BAR_RECT.y + 5))
        
        for i, (label, node_id) in enumerate(search_suggestions):
            suggestion_rect = pygame.Rect(SEARCH_BAR_RECT.x, SEARCH_BAR_RECT.y - 30 * (i + 1), SEARCH_BAR_RECT.width, 30)
            suggestion_color = BUTTON_HOVER_COLOR if suggestion_rect.collidepoint(mouse_pos) else BUTTON_COLOR
            pygame.draw.rect(screen, suggestion_color, suggestion_rect, border_radius=5)
            suggestion_surf = fonts['button'].render(label, True, TEXT_COLOR)
            screen.blit(suggestion_surf, (suggestion_rect.x + 10, suggestion_rect.y + 5))
        
        pygame.display.flip()
        
        # Tell the clock to wait to maintain 60 FPS
        clock.tick(60)
    
    pygame.quit()

# --- Interactive File Selection Logic ---
if __name__ == '__main__':
    if not os.path.isdir(OUTPUT_DIR_NAME):
        print(f"Error: Output directory '{OUTPUT_DIR_NAME}' not found.")
        sys.exit()
    try:
        json_files = [f for f in os.listdir(OUTPUT_DIR_NAME) if f.lower().endswith('.json')]
    except FileNotFoundError:
        json_files = []
    if not json_files:
        print(f"No export files (.json) found in the '{OUTPUT_DIR_NAME}' directory.")
        sys.exit()
    
    print("\n--- Select a GraphLink Export to View ---")
    for i, filename in enumerate(json_files, 1):
        print(f"  {i}: {filename}")
    
    selected_file = None
    while True:
        try:
            choice_str = input(f"\nEnter the number of the file to load (1-{len(json_files)}): ")
            if 1 <= int(choice_str) <= len(json_files):
                selected_file = json_files[int(choice_str) - 1]
                break
            else:
                print("Invalid number.")
        except (ValueError, IndexError):
            print("Invalid input.")
        except (KeyboardInterrupt):
            print("\nExiting.")
            sys.exit()
            
    full_path = os.path.join(OUTPUT_DIR_NAME, selected_file)
    print(f"Loading '{full_path}'...")
    run_visualization(full_path)
