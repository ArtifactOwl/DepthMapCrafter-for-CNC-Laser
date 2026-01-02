"""
DepthMapCrafter

A visual tool for converting color images to grayscale depth/height maps,
designed for laser engraving, CNC routing, and 3D texturing workflows.

Features:
- Eyedropper color sampling from source image
- Eyedropper height sampling from depth map preview
- Single-color rules (color range → single height)
- Gradient rules (color range → height gradient for smooth transitions)
- Lasso selection with auto color range detection and flood fill
- Channel locking for flexible color matching
- Synchronized zoom and pan between views
- Live preview with histograms
- Live eyedropper preview panel
- Progress indicator for long operations
- Load existing depth maps for continued editing
- Initialize depth from brightness or uniform value
- Save/load rules to JSON for reuse across similar images
- Full resolution output

Repository: https://github.com/YOUR_USERNAME/DepthMapCrafter
License: MIT
"""

from PIL import Image, ImageTk, ImageDraw
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from datetime import datetime


class HeightmapCreator:
    """
    Main application class for the DepthMapCrafter.
    """
    
    def __init__(self):
        """Initialize the application window and all UI components."""
        self.root = tk.Tk()
        self.root.title("DepthMapCrafter")
        
        # Core data attributes
        self.original = None
        self.display_img = None
        self.display_array = None
        self.display_scale = 1.0
        self.current_heightmap = None
        self.rules = []
        
        # Base heightmap
        self.base_heightmap = None
        self.base_type = "none"
        self.base_uniform_value = 128
        
        # Eyedropper state
        self.sampled_rgb = None
        self.sampled_rgb_low = None
        self.sampled_rgb_high = None
        
        # Photo references
        self.orig_photo = None
        self.height_photo = None
        
        # Zoom and pan state
        self.zoom_level = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.views_locked = True
        
        # Lasso state
        self.lasso_points = []
        self.is_drawing_lasso = False
        self.lasso_line_ids = []
        
        # Processing state
        self.is_processing = False
        self.processing_cancel = False
        
        # Current file paths
        self.current_image_path = None
        self.current_rules_path = None
        
        # Build the user interface
        self.setup_ui()
        
    def setup_ui(self):
        """Construct all UI elements."""
        
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # ============================================================
        # PROGRESS BAR
        # ============================================================
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill='x', pady=(0, 5))
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.working_label = ttk.Label(self.progress_frame, text="", foreground='blue', font=('TkDefaultFont', 9, 'bold'))
        
        # ============================================================
        # TOP CONTROL BAR
        # ============================================================
        controls = ttk.Frame(main_frame)
        controls.pack(fill='x', pady=(0, 10))
        
        # File menu button
        file_menu_btn = ttk.Menubutton(controls, text="File ▼")
        file_menu_btn.pack(side='left', padx=5)
        
        file_menu = tk.Menu(file_menu_btn, tearoff=0)
        file_menu_btn['menu'] = file_menu
        
        # Load submenu
        load_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Load Color Image", menu=load_menu)
        load_menu.add_command(label="With Uniform Default Height...", command=self.load_image_uniform)
        load_menu.add_command(label="Using Brightness as Initial Depth...", command=self.load_image_brightness)
        
        file_menu.add_command(label="Load Existing Depth Map...", command=self.load_depth_map)
        file_menu.add_separator()
        file_menu.add_command(label="Save Heightmap...", command=self.save_heightmap)
        file_menu.add_separator()
        
        # Rules submenu
        rules_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Rules", menu=rules_menu)
        rules_menu.add_command(label="Save Rules to JSON...", command=self.save_rules_to_json)
        rules_menu.add_command(label="Load Rules from JSON...", command=self.load_rules_from_json)
        rules_menu.add_command(label="Append Rules from JSON...", command=self.append_rules_from_json)
        
        ttk.Button(controls, text="Clear Rules", command=self.clear_rules).pack(side='left', padx=5)
        
        ttk.Separator(controls, orient='vertical').pack(side='left', fill='y', padx=10)
        
        # Zoom controls
        ttk.Label(controls, text="Zoom:").pack(side='left', padx=(0, 5))
        ttk.Button(controls, text="-", width=3, command=self.zoom_out).pack(side='left')
        self.zoom_label = ttk.Label(controls, text="100%", width=6)
        self.zoom_label.pack(side='left', padx=2)
        ttk.Button(controls, text="+", width=3, command=self.zoom_in).pack(side='left')
        ttk.Button(controls, text="Fit", command=self.zoom_fit).pack(side='left', padx=5)
        
        self.lock_views_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Lock Views", variable=self.lock_views_var,
                        command=self.on_lock_views_change).pack(side='left', padx=10)
        
        ttk.Separator(controls, orient='vertical').pack(side='left', fill='y', padx=10)
        
        # Tolerance slider
        ttk.Label(controls, text="Tolerance:").pack(side='left', padx=(0, 5))
        self.tolerance_var = tk.IntVar(value=30)
        ttk.Scale(
            controls, from_=0, to=100, variable=self.tolerance_var,
            orient='horizontal', length=100, command=self.on_tolerance_change
        ).pack(side='left')
        self.tolerance_label = ttk.Label(controls, text="30")
        self.tolerance_label.pack(side='left', padx=5)
        
        # ============================================================
        # BASE HEIGHTMAP INFO
        # ============================================================
        base_frame = ttk.LabelFrame(main_frame, text="Base Heightmap", padding=5)
        base_frame.pack(fill='x', pady=(0, 10))
        
        self.base_info_label = ttk.Label(base_frame, text="No image loaded", foreground='gray')
        self.base_info_label.pack(side='left', padx=5)
        
        ttk.Button(base_frame, text="Reset to Uniform", command=self.reset_base_uniform).pack(side='right', padx=5)
        ttk.Button(base_frame, text="Reset to Brightness", command=self.reset_base_brightness).pack(side='right', padx=5)
        
        # ============================================================
        # MODE SELECTION
        # ============================================================
        mode_frame = ttk.LabelFrame(main_frame, text="Mapping Mode", padding=5)
        mode_frame.pack(fill='x', pady=(0, 10))
        
        self.mode_var = tk.StringVar(value='single')
        
        ttk.Radiobutton(
            mode_frame, text="Single Height",
            variable=self.mode_var, value='single', command=self.on_mode_change
        ).pack(side='left', padx=10)
        
        ttk.Radiobutton(
            mode_frame, text="Gradient",
            variable=self.mode_var, value='gradient', command=self.on_mode_change
        ).pack(side='left', padx=10)
        
        ttk.Radiobutton(
            mode_frame, text="Lasso Select",
            variable=self.mode_var, value='lasso', command=self.on_mode_change
        ).pack(side='left', padx=10)
        
        # ============================================================
        # CHANNEL LOCKS
        # ============================================================
        lock_frame = ttk.LabelFrame(main_frame, text="Lock Channels (ignore when matching)", padding=5)
        lock_frame.pack(fill='x', pady=(0, 10))
        
        self.lock_r_var = tk.BooleanVar()
        self.lock_g_var = tk.BooleanVar()
        self.lock_b_var = tk.BooleanVar()
        
        ttk.Checkbutton(lock_frame, text="Lock R", variable=self.lock_r_var).pack(side='left', padx=10)
        ttk.Checkbutton(lock_frame, text="Lock G", variable=self.lock_g_var).pack(side='left', padx=10)
        ttk.Checkbutton(lock_frame, text="Lock B", variable=self.lock_b_var).pack(side='left', padx=10)
        
        # ============================================================
        # SETTINGS CONTAINER
        # ============================================================
        self.settings_container = ttk.Frame(main_frame)
        self.settings_container.pack(fill='x', pady=(0, 10))
        
        # Single-height settings
        self.single_frame = ttk.LabelFrame(self.settings_container, text="Single Height Settings", padding=5)
        
        ttk.Label(self.single_frame, text="Sampled Color:").pack(side='left')
        self.color_preview = tk.Canvas(self.single_frame, width=40, height=25, bg='gray')
        self.color_preview.pack(side='left', padx=5)
        self.color_label = ttk.Label(self.single_frame, text="Click image to sample")
        self.color_label.pack(side='left', padx=5)
        
        ttk.Label(self.single_frame, text="→ Height:").pack(side='left', padx=(20, 5))
        self.gray_var = tk.IntVar(value=128)
        ttk.Scale(self.single_frame, from_=0, to=255, variable=self.gray_var,
                  orient='horizontal', length=100).pack(side='left')
        self.gray_label = ttk.Label(self.single_frame, text="128")
        self.gray_var.trace_add('write', self.on_gray_change)
        self.gray_label.pack(side='left', padx=5)
        
        self.height_preview = tk.Canvas(self.single_frame, width=40, height=25, bg='gray')
        self.height_preview.pack(side='left', padx=5)
        
        ttk.Button(self.single_frame, text="Add Rule", command=self.add_single_rule).pack(side='left', padx=20)
        
        # Gradient settings
        self.gradient_frame = ttk.LabelFrame(self.settings_container, text="Gradient Settings", padding=5)
        
        sample_target_frame = ttk.Frame(self.gradient_frame)
        sample_target_frame.pack(fill='x', pady=(0, 5))
        
        self.sample_target_var = tk.StringVar(value='low')
        ttk.Label(sample_target_frame, text="Sampling for:").pack(side='left')
        ttk.Radiobutton(sample_target_frame, text="Low Color", variable=self.sample_target_var, value='low').pack(side='left', padx=10)
        ttk.Radiobutton(sample_target_frame, text="High Color", variable=self.sample_target_var, value='high').pack(side='left', padx=10)
        
        low_frame = ttk.Frame(self.gradient_frame)
        low_frame.pack(fill='x', pady=2)
        
        ttk.Label(low_frame, text="Low Color:").pack(side='left')
        self.low_color_preview = tk.Canvas(low_frame, width=40, height=25, bg='gray')
        self.low_color_preview.pack(side='left', padx=5)
        self.low_color_label = ttk.Label(low_frame, text="Not sampled")
        self.low_color_label.pack(side='left', padx=5)
        
        ttk.Label(low_frame, text="→ Height:").pack(side='left', padx=(20, 5))
        self.low_height_var = tk.IntVar(value=50)
        ttk.Scale(low_frame, from_=0, to=255, variable=self.low_height_var, orient='horizontal', length=80).pack(side='left')
        self.low_height_label = ttk.Label(low_frame, text="50")
        self.low_height_var.trace_add('write', self.on_low_height_change)
        self.low_height_label.pack(side='left', padx=5)
        self.low_height_preview = tk.Canvas(low_frame, width=30, height=20, bg='#323232')
        self.low_height_preview.pack(side='left', padx=5)
        ttk.Button(low_frame, text="Clear", command=self.clear_low_color).pack(side='left', padx=5)
        
        high_frame = ttk.Frame(self.gradient_frame)
        high_frame.pack(fill='x', pady=2)
        
        ttk.Label(high_frame, text="High Color:").pack(side='left')
        self.high_color_preview = tk.Canvas(high_frame, width=40, height=25, bg='gray')
        self.high_color_preview.pack(side='left', padx=5)
        self.high_color_label = ttk.Label(high_frame, text="Not sampled")
        self.high_color_label.pack(side='left', padx=5)
        
        ttk.Label(high_frame, text="→ Height:").pack(side='left', padx=(20, 5))
        self.high_height_var = tk.IntVar(value=200)
        ttk.Scale(high_frame, from_=0, to=255, variable=self.high_height_var, orient='horizontal', length=80).pack(side='left')
        self.high_height_label = ttk.Label(high_frame, text="200")
        self.high_height_var.trace_add('write', self.on_high_height_change)
        self.high_height_label.pack(side='left', padx=5)
        self.high_height_preview = tk.Canvas(high_frame, width=30, height=20, bg='#c8c8c8')
        self.high_height_preview.pack(side='left', padx=5)
        ttk.Button(high_frame, text="Clear", command=self.clear_high_color).pack(side='left', padx=5)
        
        gradient_button_frame = ttk.Frame(self.gradient_frame)
        gradient_button_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(gradient_button_frame, text="Add Gradient Rule", command=self.add_gradient_rule).pack(side='left', padx=5)
        self.gradient_info_label = ttk.Label(gradient_button_frame, text="Sample both colors, then add rule", foreground='gray')
        self.gradient_info_label.pack(side='left', padx=10)
        
        # Lasso settings
        self.lasso_frame = ttk.LabelFrame(self.settings_container, text="Lasso Selection Settings", padding=5)
        
        lasso_info_frame = ttk.Frame(self.lasso_frame)
        lasso_info_frame.pack(fill='x', pady=2)
        
        ttk.Label(lasso_info_frame, text="Draw a lasso on the original image. Colors inside will be auto-detected.").pack(side='left')
        
        # Lasso height sampling target
        lasso_sample_frame = ttk.Frame(self.lasso_frame)
        lasso_sample_frame.pack(fill='x', pady=(5, 2))
        
        self.lasso_sample_target_var = tk.StringVar(value='low')
        ttk.Label(lasso_sample_frame, text="Height sampling for:").pack(side='left')
        ttk.Radiobutton(lasso_sample_frame, text="Low Height", variable=self.lasso_sample_target_var, value='low').pack(side='left', padx=10)
        ttk.Radiobutton(lasso_sample_frame, text="High Height", variable=self.lasso_sample_target_var, value='high').pack(side='left', padx=10)
        
        # Lasso low height row
        lasso_low_frame = ttk.Frame(self.lasso_frame)
        lasso_low_frame.pack(fill='x', pady=2)
        
        ttk.Label(lasso_low_frame, text="Low Height:").pack(side='left')
        self.lasso_low_height_var = tk.IntVar(value=50)
        ttk.Scale(lasso_low_frame, from_=0, to=255, variable=self.lasso_low_height_var,
                  orient='horizontal', length=80).pack(side='left', padx=5)
        self.lasso_low_label = ttk.Label(lasso_low_frame, text="50")
        self.lasso_low_height_var.trace_add('write', self.on_lasso_low_change)
        self.lasso_low_label.pack(side='left', padx=5)
        self.lasso_low_preview = tk.Canvas(lasso_low_frame, width=30, height=20, bg='#323232')
        self.lasso_low_preview.pack(side='left', padx=5)
        
        # Lasso high height row
        lasso_high_frame = ttk.Frame(self.lasso_frame)
        lasso_high_frame.pack(fill='x', pady=2)
        
        ttk.Label(lasso_high_frame, text="High Height:").pack(side='left')
        self.lasso_high_height_var = tk.IntVar(value=200)
        ttk.Scale(lasso_high_frame, from_=0, to=255, variable=self.lasso_high_height_var,
                  orient='horizontal', length=80).pack(side='left', padx=5)
        self.lasso_high_label = ttk.Label(lasso_high_frame, text="200")
        self.lasso_high_height_var.trace_add('write', self.on_lasso_high_change)
        self.lasso_high_label.pack(side='left', padx=5)
        self.lasso_high_preview = tk.Canvas(lasso_high_frame, width=30, height=20, bg='#c8c8c8')
        self.lasso_high_preview.pack(side='left', padx=5)
        
        lasso_options_frame = ttk.Frame(self.lasso_frame)
        lasso_options_frame.pack(fill='x', pady=5)
        
        self.lasso_flood_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lasso_options_frame, text="Flood fill neighbors with matching colors",
                        variable=self.lasso_flood_var).pack(side='left')
        
        lasso_button_frame = ttk.Frame(self.lasso_frame)
        lasso_button_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(lasso_button_frame, text="Clear Lasso", command=self.clear_lasso).pack(side='left', padx=5)
        self.lasso_status_label = ttk.Label(lasso_button_frame, text="Draw on original image to select region", foreground='gray')
        self.lasso_status_label.pack(side='left', padx=10)
        
        # Show single frame by default
        self.single_frame.pack(fill='x')
        
        # ============================================================
        # IMAGE DISPLAY AREA
        # ============================================================
        image_frame = ttk.Frame(main_frame)
        image_frame.pack(fill='both', expand=True)
        
        # Original image canvas
        orig_container = ttk.LabelFrame(image_frame, text="Original (click/drag to sample, scroll to zoom)")
        orig_container.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        self.orig_canvas = tk.Canvas(orig_container, bg='#333', width=400, height=300)
        self.orig_canvas.pack(fill='both', expand=True)
        
        self.orig_canvas.bind('<Button-1>', self.on_original_click)
        self.orig_canvas.bind('<B1-Motion>', self.on_original_drag)
        self.orig_canvas.bind('<ButtonRelease-1>', self.on_original_release)
        self.orig_canvas.bind('<Button-2>', self.on_pan_start)
        self.orig_canvas.bind('<B2-Motion>', self.on_pan_drag)
        self.orig_canvas.bind('<Button-3>', self.on_pan_start)
        self.orig_canvas.bind('<B3-Motion>', self.on_pan_drag)
        self.orig_canvas.bind('<MouseWheel>', self.on_mouse_wheel)
        self.orig_canvas.bind('<Button-4>', self.on_mouse_wheel)
        self.orig_canvas.bind('<Button-5>', self.on_mouse_wheel)
        self.orig_canvas.bind('<Motion>', self.on_original_mouse_move)
        self.orig_canvas.bind('<Leave>', self.on_canvas_leave)
        
        # Heightmap preview canvas
        height_container = ttk.LabelFrame(image_frame, text="Heightmap (click to sample height, scroll to zoom)")
        height_container.pack(side='left', fill='both', expand=True, padx=(5, 0))
        
        self.height_canvas = tk.Canvas(height_container, bg='#333', width=400, height=300)
        self.height_canvas.pack(fill='both', expand=True)
        
        self.height_canvas.bind('<Button-1>', self.on_heightmap_click)
        self.height_canvas.bind('<Button-2>', self.on_pan_start_height)
        self.height_canvas.bind('<B2-Motion>', self.on_pan_drag_height)
        self.height_canvas.bind('<Button-3>', self.on_pan_start_height)
        self.height_canvas.bind('<B3-Motion>', self.on_pan_drag_height)
        self.height_canvas.bind('<MouseWheel>', self.on_mouse_wheel_height)
        self.height_canvas.bind('<Button-4>', self.on_mouse_wheel_height)
        self.height_canvas.bind('<Button-5>', self.on_mouse_wheel_height)
        self.height_canvas.bind('<Motion>', self.on_heightmap_mouse_move)
        self.height_canvas.bind('<Leave>', self.on_canvas_leave)
        
        # ============================================================
        # BOTTOM SECTION
        # ============================================================
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill='x', pady=(10, 0))
        
        # Rules list
        rules_frame = ttk.LabelFrame(bottom_frame, text="Active Rules", padding=5)
        rules_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        self.rules_listbox = tk.Listbox(rules_frame, height=5)
        self.rules_listbox.pack(fill='both', side='left', expand=True)
        
        rules_scroll = ttk.Scrollbar(rules_frame, orient='vertical', command=self.rules_listbox.yview)
        rules_scroll.pack(side='left', fill='y')
        self.rules_listbox.config(yscrollcommand=rules_scroll.set)
        
        rule_buttons = ttk.Frame(rules_frame)
        rule_buttons.pack(side='right', fill='y', padx=(5, 0))
        ttk.Button(rule_buttons, text="Delete", command=self.delete_rule).pack(pady=2)
        ttk.Button(rule_buttons, text="Move Up", command=self.move_rule_up).pack(pady=2)
        ttk.Button(rule_buttons, text="Move Down", command=self.move_rule_down).pack(pady=2)
        
        # Live preview panel
        live_frame = ttk.LabelFrame(bottom_frame, text="Live Preview", padding=5)
        live_frame.pack(side='left', fill='both', padx=(0, 10))
        
        # Color preview (original image)
        color_live_frame = ttk.Frame(live_frame)
        color_live_frame.pack(fill='x', pady=2)
        
        ttk.Label(color_live_frame, text="Color:").pack(side='left')
        self.live_color_swatch = tk.Canvas(color_live_frame, width=40, height=25, bg='#333')
        self.live_color_swatch.pack(side='left', padx=5)
        self.live_color_label = ttk.Label(color_live_frame, text="---", width=18)
        self.live_color_label.pack(side='left')
        
        # Height preview (heightmap)
        height_live_frame = ttk.Frame(live_frame)
        height_live_frame.pack(fill='x', pady=2)
        
        ttk.Label(height_live_frame, text="Height:").pack(side='left')
        self.live_height_swatch = tk.Canvas(height_live_frame, width=40, height=25, bg='#333')
        self.live_height_swatch.pack(side='left', padx=5)
        self.live_height_label = ttk.Label(height_live_frame, text="---", width=18)
        self.live_height_label.pack(side='left')
        
        # Coordinates
        coord_frame = ttk.Frame(live_frame)
        coord_frame.pack(fill='x', pady=2)
        
        ttk.Label(coord_frame, text="Position:").pack(side='left')
        self.live_coord_label = ttk.Label(coord_frame, text="---", width=18)
        self.live_coord_label.pack(side='left', padx=5)
        
        # Histograms
        hist_frame = ttk.LabelFrame(bottom_frame, text="Histograms", padding=5)
        hist_frame.pack(side='left', fill='both', expand=True)
        
        ttk.Label(hist_frame, text="Original:").pack(anchor='w')
        self.orig_hist_canvas = tk.Canvas(hist_frame, width=256, height=50, bg='#222')
        self.orig_hist_canvas.pack(pady=(0, 5))
        
        ttk.Label(hist_frame, text="Heightmap:").pack(anchor='w')
        self.height_hist_canvas = tk.Canvas(hist_frame, width=256, height=50, bg='#222')
        self.height_hist_canvas.pack()
        
        # Status bar
        self.status_var = tk.StringVar(value="Load an image to begin (File menu)")
        ttk.Label(main_frame, textvariable=self.status_var, relief='sunken', padding=(5, 2)).pack(fill='x', pady=(10, 0))

    # ================================================================
    # PROGRESS INDICATOR
    # ================================================================
    
    def show_progress(self, message="Processing...", determinate=True):
        self.is_processing = True
        self.processing_cancel = False
        
        self.progress_label.config(text=message)
        self.progress_label.pack(side='left', padx=(0, 10))
        
        if determinate:
            self.progress_bar.config(mode='determinate')
            self.progress_var.set(0)
        else:
            self.progress_bar.config(mode='indeterminate')
            self.progress_bar.start(10)
            
        self.progress_bar.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.working_label.config(text="⚙ Working")
        self.working_label.pack(side='left')
        
        self.animate_working()
        self.root.update_idletasks()
        
    def update_progress(self, value, message=None):
        self.progress_var.set(value)
        if message:
            self.progress_label.config(text=message)
        self.root.update_idletasks()
        
    def hide_progress(self):
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        self.working_label.pack_forget()
        self.root.update_idletasks()
        
    def animate_working(self):
        if not self.is_processing:
            return
        current = self.working_label.cget('text')
        dots = current.count('.')
        dots = (dots % 3) + 1
        self.working_label.config(text="⚙ Working" + "." * dots)
        self.root.after(300, self.animate_working)

    # ================================================================
    # LIVE PREVIEW
    # ================================================================
    
    def update_live_preview(self, x, y, source='original'):
        """Update the live preview panel with color/height at given coordinates."""
        if self.original is None:
            return
            
        # Validate coordinates
        if x < 0 or y < 0 or x >= self.original.shape[1] or y >= self.original.shape[0]:
            return
            
        # Update coordinates
        self.live_coord_label.config(text=f"({x}, {y})")
        
        # Get color from original
        r, g, b = self.original[y, x]
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        self.live_color_swatch.config(bg=hex_color)
        self.live_color_label.config(text=f"RGB({r}, {g}, {b})")
        
        # Get height from heightmap
        if self.current_heightmap is not None and y < self.current_heightmap.shape[0] and x < self.current_heightmap.shape[1]:
            height = int(self.current_heightmap[y, x])
            hex_height = f'#{height:02x}{height:02x}{height:02x}'
            self.live_height_swatch.config(bg=hex_height)
            self.live_height_label.config(text=f"Gray({height})")
        else:
            self.live_height_swatch.config(bg='#333')
            self.live_height_label.config(text="---")
            
    def clear_live_preview(self):
        """Clear the live preview panel."""
        self.live_color_swatch.config(bg='#333')
        self.live_color_label.config(text="---")
        self.live_height_swatch.config(bg='#333')
        self.live_height_label.config(text="---")
        self.live_coord_label.config(text="---")
        
    def on_canvas_leave(self, event):
        """Handle mouse leaving canvas."""
        self.clear_live_preview()

    # ================================================================
    # RULES SAVE/LOAD
    # ================================================================
    
    def rule_to_dict(self, rule):
        """Convert a rule to a JSON-serializable dictionary."""
        rule_dict = {
            'type': rule['type'],
            'min_rgb': list(rule['min_rgb']),
            'max_rgb': list(rule['max_rgb']),
            'locks': list(rule['locks']) if 'locks' in rule else [False, False, False]
        }
        
        if rule['type'] == 'single':
            rule_dict['gray'] = rule['gray']
            rule_dict['sampled'] = list(rule['sampled']) if rule.get('sampled') else None
            rule_dict['tolerance'] = rule.get('tolerance', 30)
            
        elif rule['type'] == 'gradient':
            rule_dict['low_rgb'] = list(rule['low_rgb'])
            rule_dict['high_rgb'] = list(rule['high_rgb'])
            rule_dict['low_height'] = rule['low_height']
            rule_dict['high_height'] = rule['high_height']
            rule_dict['tolerance'] = rule.get('tolerance', 30)
            
        elif rule['type'] == 'lasso':
            rule_dict['low_rgb'] = list(rule['low_rgb'])
            rule_dict['high_rgb'] = list(rule['high_rgb'])
            rule_dict['low_height'] = rule['low_height']
            rule_dict['high_height'] = rule['high_height']
            rule_dict['pixel_count'] = rule.get('pixel_count', 0)
            if 'lasso_points' in rule:
                rule_dict['lasso_points'] = rule['lasso_points']
                
        return rule_dict
    
    def dict_to_rule(self, rule_dict, recreate_mask=True):
        """Convert a dictionary back to a rule."""
        rule = {
            'type': rule_dict['type'],
            'min_rgb': tuple(rule_dict['min_rgb']),
            'max_rgb': tuple(rule_dict['max_rgb']),
            'locks': tuple(rule_dict.get('locks', [False, False, False]))
        }
        
        if rule_dict['type'] == 'single':
            rule['gray'] = rule_dict['gray']
            rule['sampled'] = tuple(rule_dict['sampled']) if rule_dict.get('sampled') else None
            rule['tolerance'] = rule_dict.get('tolerance', 30)
            
        elif rule_dict['type'] == 'gradient':
            rule['low_rgb'] = tuple(rule_dict['low_rgb'])
            rule['high_rgb'] = tuple(rule_dict['high_rgb'])
            rule['low_height'] = rule_dict['low_height']
            rule['high_height'] = rule_dict['high_height']
            rule['tolerance'] = rule_dict.get('tolerance', 30)
            
        elif rule_dict['type'] == 'lasso':
            rule['low_rgb'] = tuple(rule_dict['low_rgb'])
            rule['high_rgb'] = tuple(rule_dict['high_rgb'])
            rule['low_height'] = rule_dict['low_height']
            rule['high_height'] = rule_dict['high_height']
            rule['pixel_count'] = rule_dict.get('pixel_count', 0)
            
            if 'lasso_points' in rule_dict:
                rule['lasso_points'] = rule_dict['lasso_points']
            
            if recreate_mask and self.original is not None:
                rule['mask'] = self.recreate_lasso_mask(rule_dict)
            else:
                rule['mask'] = None
                rule['needs_mask_recreation'] = True
                
        return rule
    
    def recreate_lasso_mask(self, rule_dict):
        """Recreate a lasso mask from stored data."""
        if self.original is None:
            return None
            
        height, width = self.original.shape[:2]
        
        if 'lasso_points' in rule_dict and rule_dict['lasso_points']:
            mask_img = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(mask_img)
            points = [tuple(p) for p in rule_dict['lasso_points']]
            draw.polygon(points, fill=255)
            mask = np.array(mask_img)
            
            min_rgb = tuple(rule_dict['min_rgb'])
            max_rgb = tuple(rule_dict['max_rgb'])
            
            try:
                from scipy import ndimage
                struct = ndimage.generate_binary_structure(2, 1)
                
                for _ in range(100):
                    dilated = ndimage.binary_dilation(mask > 0, structure=struct)
                    new_pixels = dilated & (mask == 0)
                    
                    if not np.any(new_pixels):
                        break
                        
                    matching = (
                        (self.original[:,:,0] >= min_rgb[0]) & (self.original[:,:,0] <= max_rgb[0]) &
                        (self.original[:,:,1] >= min_rgb[1]) & (self.original[:,:,1] <= max_rgb[1]) &
                        (self.original[:,:,2] >= min_rgb[2]) & (self.original[:,:,2] <= max_rgb[2])
                    )
                    
                    pixels_to_add = new_pixels & matching
                    if not np.any(pixels_to_add):
                        break
                        
                    mask[pixels_to_add] = 255
            except ImportError:
                pass
                
            return mask
        else:
            min_rgb = tuple(rule_dict['min_rgb'])
            max_rgb = tuple(rule_dict['max_rgb'])
            
            mask = (
                (self.original[:,:,0] >= min_rgb[0]) & (self.original[:,:,0] <= max_rgb[0]) &
                (self.original[:,:,1] >= min_rgb[1]) & (self.original[:,:,1] <= max_rgb[1]) &
                (self.original[:,:,2] >= min_rgb[2]) & (self.original[:,:,2] <= max_rgb[2])
            ).astype(np.uint8) * 255
            
            return mask
    
    def save_rules_to_json(self):
        """Save current rules to a JSON file."""
        if not self.rules:
            messagebox.showinfo("No Rules", "There are no rules to save.")
            return
            
        initial_name = "rules"
        if self.current_image_path:
            base = os.path.splitext(os.path.basename(self.current_image_path))[0]
            initial_name = f"{base}_rules"
            
        path = filedialog.asksaveasfilename(
            title="Save Rules to JSON",
            defaultextension=".json",
            initialfile=initial_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not path:
            return
            
        self.show_progress("Saving rules...", determinate=False)
        
        try:
            rules_data = {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'source_image': os.path.basename(self.current_image_path) if self.current_image_path else None,
                'image_dimensions': [self.original.shape[1], self.original.shape[0]] if self.original is not None else None,
                'base_type': self.base_type,
                'base_uniform_value': self.base_uniform_value if self.base_type == 'uniform' else None,
                'rule_count': len(self.rules),
                'rules': [self.rule_to_dict(rule) for rule in self.rules]
            }
            
            rules_data['_description'] = {
                'version': 'File format version',
                'base_type': 'How the base heightmap was initialized: uniform, brightness, or loaded',
                'rules': 'List of mapping rules applied in order (later rules override earlier)',
                'rule_types': {
                    'single': 'Maps a color range to a single height value',
                    'gradient': 'Maps a color range to a gradient between two height values',
                    'lasso': 'Maps a drawn region to a height gradient based on color'
                }
            }
            
            with open(path, 'w') as f:
                json.dump(rules_data, f, indent=2)
                
            self.current_rules_path = path
            self.status_var.set(f"Saved {len(self.rules)} rules to {os.path.basename(path)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save rules:\n{str(e)}")
            
        finally:
            self.hide_progress()
    
    def load_rules_from_json(self):
        """Load rules from a JSON file, replacing current rules."""
        if self.rules:
            if not messagebox.askyesno("Replace Rules", 
                "This will replace all current rules.\nContinue?"):
                return
                
        self._load_rules_json(append=False)
    
    def append_rules_from_json(self):
        """Load rules from a JSON file, appending to current rules."""
        self._load_rules_json(append=True)
    
    def _load_rules_json(self, append=False):
        """Internal method to load rules from JSON."""
        path = filedialog.askopenfilename(
            title="Load Rules from JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not path:
            return
            
        self.show_progress("Loading rules...", determinate=True)
        
        try:
            with open(path, 'r') as f:
                rules_data = json.load(f)
                
            if 'rules' not in rules_data:
                raise ValueError("Invalid rules file: missing 'rules' key")
                
            if self.original is not None and rules_data.get('image_dimensions'):
                saved_dims = rules_data['image_dimensions']
                current_dims = [self.original.shape[1], self.original.shape[0]]
                if saved_dims != current_dims:
                    result = messagebox.askyesno(
                        "Dimension Mismatch",
                        f"Rules were created for image size {saved_dims[0]}x{saved_dims[1]}\n"
                        f"but current image is {current_dims[0]}x{current_dims[1]}.\n\n"
                        "Lasso regions may not align correctly.\n"
                        "Continue anyway?"
                    )
                    if not result:
                        return
            
            if not append:
                self.rules = []
                self.rules_listbox.delete(0, 'end')
            
            loaded_rules = rules_data['rules']
            total = len(loaded_rules)
            
            for i, rule_dict in enumerate(loaded_rules):
                self.update_progress((i + 1) / total * 100, f"Loading rule {i + 1}/{total}...")
                
                rule = self.dict_to_rule(rule_dict)
                self.rules.append(rule)
                
                self.rules_listbox.insert('end', self.get_rule_display_text(rule))
            
            self.current_rules_path = path
            self.update_preview()
            
            action = "Appended" if append else "Loaded"
            self.status_var.set(f"{action} {len(loaded_rules)} rules from {os.path.basename(path)}")
            
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON file:\n{str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load rules:\n{str(e)}")
            
        finally:
            self.hide_progress()
    
    def get_rule_display_text(self, rule):
        """Get display text for a rule in the listbox."""
        if rule['type'] == 'single':
            r, g, b = rule.get('sampled', rule['min_rgb'])
            tol = rule.get('tolerance', '?')
            lock_str = ""
            if any(rule.get('locks', [])):
                lock_str = " [" + "".join(c for c, l in zip("RGB", rule['locks']) if l) + "]"
            return f"[S] RGB({r},{g},{b}) ±{tol}{lock_str} → {rule['gray']}"
            
        elif rule['type'] == 'gradient':
            low = rule['low_rgb']
            high = rule['high_rgb']
            return f"[G] {low}→{high} → {rule['low_height']}-{rule['high_height']}"
            
        elif rule['type'] == 'lasso':
            min_rgb = rule['min_rgb']
            max_rgb = rule['max_rgb']
            px = rule.get('pixel_count', '?')
            return f"[L] {px}px RGB({min_rgb[0]}-{max_rgb[0]},{min_rgb[1]}-{max_rgb[1]},{min_rgb[2]}-{max_rgb[2]}) → {rule['low_height']}-{rule['high_height']}"
            
        return "[?] Unknown rule type"

    # ================================================================
    # FILE OPERATIONS - LOADING
    # ================================================================
    
    def load_image_uniform(self):
        self._load_color_image(use_brightness=False)
        
    def load_image_brightness(self):
        self._load_color_image(use_brightness=True)
        
    def _load_color_image(self, use_brightness=False):
        path = filedialog.askopenfilename(
            title="Load Color Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif")]
        )
        if not path:
            return
            
        self.show_progress("Loading image...", determinate=False)
        
        try:
            img = Image.open(path).convert('RGB')
            
            max_size = 500
            if img.width > max_size or img.height > max_size:
                ratio = min(max_size / img.width, max_size / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                self.display_img = img.resize(new_size, Image.LANCZOS)
            else:
                self.display_img = img.copy()
            
            self.original = np.array(img)
            self.display_array = np.array(self.display_img)
            self.display_scale = self.display_img.width / img.width
            self.current_image_path = path
            
            if use_brightness:
                self.base_heightmap = (
                    0.299 * self.original[:,:,0] +
                    0.587 * self.original[:,:,1] +
                    0.114 * self.original[:,:,2]
                ).astype(np.uint8)
                self.base_type = "brightness"
                self.base_info_label.config(text=f"Base: Brightness-derived | {img.width}x{img.height}", foreground='blue')
            else:
                self.base_heightmap = np.full(self.original.shape[:2], 128, dtype=np.uint8)
                self.base_type = "uniform"
                self.base_uniform_value = 128
                self.base_info_label.config(text=f"Base: Uniform (128) | {img.width}x{img.height}", foreground='green')
            
            self.zoom_level = 1.0
            self.pan_offset_x = 0
            self.pan_offset_y = 0
            self.update_zoom_label()
            
            self.clear_rules()
            
            self.refresh_display()
            self.update_histograms()
            
            mode_str = "brightness" if use_brightness else "uniform"
            self.status_var.set(f"Loaded: {img.width}x{img.height} with {mode_str} base heightmap")
            
        finally:
            self.hide_progress()
            
    def load_depth_map(self):
        if self.original is None:
            messagebox.showwarning(
                "No Color Image", 
                "Please load a color image first.\n\n"
                "The depth map must match the color image dimensions."
            )
            return
            
        path = filedialog.askopenfilename(
            title="Load Existing Depth Map",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif")]
        )
        if not path:
            return
            
        self.show_progress("Loading depth map...", determinate=False)
        
        try:
            depth_img = Image.open(path)
            
            if depth_img.mode != 'L':
                depth_img = depth_img.convert('L')
                
            depth_array = np.array(depth_img)
            
            expected_shape = self.original.shape[:2]
            if depth_array.shape != expected_shape:
                messagebox.showerror(
                    "Size Mismatch",
                    f"Depth map dimensions ({depth_array.shape[1]}x{depth_array.shape[0]}) "
                    f"don't match color image ({expected_shape[1]}x{expected_shape[0]}).\n\n"
                    "The depth map must be the same size as the color image."
                )
                return
                
            self.base_heightmap = depth_array.copy()
            self.base_type = "loaded"
            
            self.clear_rules()
            
            self.base_info_label.config(
                text=f"Base: Loaded from file | {depth_array.shape[1]}x{depth_array.shape[0]}", 
                foreground='purple'
            )
            
            self.refresh_display()
            self.update_histograms()
            
            self.status_var.set(f"Loaded depth map: {depth_array.shape[1]}x{depth_array.shape[0]}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load depth map:\n{str(e)}")
            
        finally:
            self.hide_progress()
            
    def reset_base_uniform(self):
        if self.original is None:
            return
            
        dialog = UniformValueDialog(self.root)
        if dialog.result is not None:
            self.base_heightmap = np.full(self.original.shape[:2], dialog.result, dtype=np.uint8)
            self.base_type = "uniform"
            self.base_uniform_value = dialog.result
            self.base_info_label.config(text=f"Base: Uniform ({dialog.result})", foreground='green')
            self.update_preview()
            self.status_var.set(f"Reset base to uniform height {dialog.result}")
            
    def reset_base_brightness(self):
        if self.original is None:
            return
            
        self.base_heightmap = (
            0.299 * self.original[:,:,0] +
            0.587 * self.original[:,:,1] +
            0.114 * self.original[:,:,2]
        ).astype(np.uint8)
        self.base_type = "brightness"
        self.base_info_label.config(text="Base: Brightness-derived", foreground='blue')
        self.update_preview()
        self.status_var.set("Reset base to brightness-derived heightmap")

    def save_heightmap(self):
        if self.original is None:
            return
            
        initial_name = "heightmap"
        if self.current_image_path:
            base = os.path.splitext(os.path.basename(self.current_image_path))[0]
            initial_name = f"{base}_depth"
            
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=initial_name,
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")]
        )
        if not path:
            return
            
        self.show_progress("Generating full-resolution heightmap...", determinate=True)
        
        try:
            self.update_progress(50, "Applying rules...")
            heightmap = self.generate_heightmap()
            
            self.update_progress(90, "Saving file...")
            heightmap.save(path)
            
            self.status_var.set(f"Saved: {path}")
            
        finally:
            self.hide_progress()

    # ================================================================
    # MODE SWITCHING
    # ================================================================
    
    def on_mode_change(self):
        mode = self.mode_var.get()
        
        self.single_frame.pack_forget()
        self.gradient_frame.pack_forget()
        self.lasso_frame.pack_forget()
        
        self.clear_lasso()
        
        if mode == 'single':
            self.single_frame.pack(fill='x')
            self.status_var.set("Single mode: Click image to sample color")
        elif mode == 'gradient':
            self.gradient_frame.pack(fill='x')
            self.status_var.set("Gradient mode: Select Low/High, then click image")
        else:
            self.lasso_frame.pack(fill='x')
            self.status_var.set("Lasso mode: Click and drag on original image to draw selection")

    # ================================================================
    # ZOOM AND PAN
    # ================================================================
    
    def on_lock_views_change(self):
        self.views_locked = self.lock_views_var.get()
        
    def zoom_in(self):
        self.zoom_level = min(10.0, self.zoom_level * 1.25)
        self.update_zoom_label()
        self.refresh_display()
        
    def zoom_out(self):
        self.zoom_level = max(0.1, self.zoom_level / 1.25)
        self.update_zoom_label()
        self.refresh_display()
        
    def zoom_fit(self):
        self.zoom_level = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.update_zoom_label()
        self.refresh_display()
        
    def update_zoom_label(self):
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
        
    def on_mouse_wheel(self, event):
        if self.original is None:
            return
            
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            factor = 1.1
        else:
            factor = 1 / 1.1
            
        old_zoom = self.zoom_level
        self.zoom_level = max(0.1, min(10.0, self.zoom_level * factor))
        
        if old_zoom != self.zoom_level:
            canvas_x = event.x
            canvas_y = event.y
            img_x = (canvas_x - self.pan_offset_x) / old_zoom
            img_y = (canvas_y - self.pan_offset_y) / old_zoom
            self.pan_offset_x = canvas_x - img_x * self.zoom_level
            self.pan_offset_y = canvas_y - img_y * self.zoom_level
            
            self.update_zoom_label()
            self.refresh_display()
            
    def on_mouse_wheel_height(self, event):
        if self.views_locked:
            self.on_mouse_wheel(event)
            
    def on_pan_start(self, event):
        self.is_panning = True
        self.pan_start_x = event.x - self.pan_offset_x
        self.pan_start_y = event.y - self.pan_offset_y
        
    def on_pan_drag(self, event):
        if self.is_panning:
            self.pan_offset_x = event.x - self.pan_start_x
            self.pan_offset_y = event.y - self.pan_start_y
            self.refresh_display()
            
    def on_pan_start_height(self, event):
        if self.views_locked:
            self.on_pan_start(event)
            
    def on_pan_drag_height(self, event):
        if self.views_locked:
            self.on_pan_drag(event)
            
    def screen_to_image(self, screen_x, screen_y):
        if self.original is None:
            return None, None
        img_x = (screen_x - self.pan_offset_x) / self.zoom_level / self.display_scale
        img_y = (screen_y - self.pan_offset_y) / self.zoom_level / self.display_scale
        img_x = int(max(0, min(self.original.shape[1] - 1, img_x)))
        img_y = int(max(0, min(self.original.shape[0] - 1, img_y)))
        return img_x, img_y
        
    def image_to_screen(self, img_x, img_y):
        screen_x = img_x * self.display_scale * self.zoom_level + self.pan_offset_x
        screen_y = img_y * self.display_scale * self.zoom_level + self.pan_offset_y
        return screen_x, screen_y

    # ================================================================
    # EVENT HANDLERS
    # ================================================================
    
    def on_tolerance_change(self, event=None):
        self.tolerance_label.config(text=str(self.tolerance_var.get()))
        
    def on_gray_change(self, *args):
        val = self.gray_var.get()
        self.gray_label.config(text=str(val))
        self.height_preview.config(bg=f'#{val:02x}{val:02x}{val:02x}')
        
    def on_low_height_change(self, *args):
        val = self.low_height_var.get()
        self.low_height_label.config(text=str(val))
        self.low_height_preview.config(bg=f'#{val:02x}{val:02x}{val:02x}')
        
    def on_high_height_change(self, *args):
        val = self.high_height_var.get()
        self.high_height_label.config(text=str(val))
        self.high_height_preview.config(bg=f'#{val:02x}{val:02x}{val:02x}')
        
    def on_lasso_low_change(self, *args):
        val = self.lasso_low_height_var.get()
        self.lasso_low_label.config(text=str(val))
        self.lasso_low_preview.config(bg=f'#{val:02x}{val:02x}{val:02x}')
        
    def on_lasso_high_change(self, *args):
        val = self.lasso_high_height_var.get()
        self.lasso_high_label.config(text=str(val))
        self.lasso_high_preview.config(bg=f'#{val:02x}{val:02x}{val:02x}')

    # ================================================================
    # ORIGINAL IMAGE EVENTS
    # ================================================================
    
    def on_original_mouse_move(self, event):
        if self.original is None:
            return
        x, y = self.screen_to_image(event.x, event.y)
        if x is not None and 0 <= x < self.original.shape[1] and 0 <= y < self.original.shape[0]:
            # Update live preview
            self.update_live_preview(x, y, source='original')
            
            r, g, b = self.original[y, x]
            mode = self.mode_var.get()
            if mode == 'single':
                self.status_var.set(f"RGB({r}, {g}, {b}) @ ({x},{y}) — Click to sample color")
            elif mode == 'gradient':
                target = self.sample_target_var.get().upper()
                self.status_var.set(f"RGB({r}, {g}, {b}) @ ({x},{y}) — Click to sample {target} color")
            else:
                if self.is_drawing_lasso:
                    self.status_var.set(f"Drawing lasso... ({len(self.lasso_points)} points)")
                else:
                    self.status_var.set(f"RGB({r}, {g}, {b}) @ ({x},{y}) — Click and drag to draw lasso")
            
    def on_original_click(self, event):
        if self.original is None:
            return
            
        mode = self.mode_var.get()
        
        if mode == 'lasso':
            self.is_drawing_lasso = True
            self.lasso_points = [(event.x, event.y)]
            self.clear_lasso_lines()
            return
            
        x, y = self.screen_to_image(event.x, event.y)
        if x is None:
            return
            
        if 0 <= x < self.original.shape[1] and 0 <= y < self.original.shape[0]:
            r, g, b = self.original[y, x]
            hex_color = f'#{r:02x}{g:02x}{b:02x}'
            
            if mode == 'single':
                self.sampled_rgb = (r, g, b)
                self.color_preview.config(bg=hex_color)
                self.color_label.config(text=f"RGB({r}, {g}, {b})")
                self.status_var.set(f"Sampled RGB({r}, {g}, {b})")
            else:  # gradient
                target = self.sample_target_var.get()
                if target == 'low':
                    self.sampled_rgb_low = (r, g, b)
                    self.low_color_preview.config(bg=hex_color)
                    self.low_color_label.config(text=f"RGB({r}, {g}, {b})")
                    self.status_var.set(f"LOW = RGB({r}, {g}, {b})")
                else:
                    self.sampled_rgb_high = (r, g, b)
                    self.high_color_preview.config(bg=hex_color)
                    self.high_color_label.config(text=f"RGB({r}, {g}, {b})")
                    self.status_var.set(f"HIGH = RGB({r}, {g}, {b})")
                self.update_gradient_info()
                
    def on_original_drag(self, event):
        if self.mode_var.get() == 'lasso' and self.is_drawing_lasso:
            self.lasso_points.append((event.x, event.y))
            if len(self.lasso_points) >= 2:
                x1, y1 = self.lasso_points[-2]
                x2, y2 = self.lasso_points[-1]
                line_id = self.orig_canvas.create_line(x1, y1, x2, y2, fill='yellow', width=2)
                self.lasso_line_ids.append(line_id)
                
    def on_original_release(self, event):
        if self.mode_var.get() == 'lasso' and self.is_drawing_lasso:
            self.is_drawing_lasso = False
            
            if len(self.lasso_points) >= 3:
                x1, y1 = self.lasso_points[-1]
                x2, y2 = self.lasso_points[0]
                line_id = self.orig_canvas.create_line(x1, y1, x2, y2, fill='yellow', width=2)
                self.lasso_line_ids.append(line_id)
                self.process_lasso_selection()
            else:
                self.clear_lasso()
                self.status_var.set("Lasso too small - draw a larger region")

    def clear_lasso(self):
        self.lasso_points = []
        self.is_drawing_lasso = False
        self.clear_lasso_lines()
        
    def clear_lasso_lines(self):
        for line_id in self.lasso_line_ids:
            self.orig_canvas.delete(line_id)
        self.lasso_line_ids = []
        
    def process_lasso_selection(self):
        if len(self.lasso_points) < 3 or self.original is None:
            return
            
        self.show_progress("Processing lasso selection...", determinate=True)
        
        try:
            self.update_progress(10, "Converting coordinates...")
            
            img_points = []
            for sx, sy in self.lasso_points:
                ix, iy = self.screen_to_image(sx, sy)
                if ix is not None:
                    img_points.append([ix, iy])
                    
            if len(img_points) < 3:
                self.status_var.set("Lasso region too small")
                return
                
            self.update_progress(20, "Creating mask...")
            
            height, width = self.original.shape[:2]
            mask_img = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(mask_img)
            draw.polygon([tuple(p) for p in img_points], fill=255)
            mask = np.array(mask_img)
            
            self.update_progress(30, "Analyzing colors...")
            
            inside_pixels = self.original[mask > 0]
            
            if len(inside_pixels) == 0:
                self.status_var.set("No pixels inside lasso")
                return
                
            min_rgb = inside_pixels.min(axis=0)
            max_rgb = inside_pixels.max(axis=0)
            
            self.update_progress(40, "Calculating color range...")
            
            tol = self.tolerance_var.get()
            
            if self.lock_r_var.get():
                final_min_r, final_max_r = 0, 255
            else:
                final_min_r = max(0, int(min_rgb[0]) - tol)
                final_max_r = min(255, int(max_rgb[0]) + tol)
                
            if self.lock_g_var.get():
                final_min_g, final_max_g = 0, 255
            else:
                final_min_g = max(0, int(min_rgb[1]) - tol)
                final_max_g = min(255, int(max_rgb[1]) + tol)
                
            if self.lock_b_var.get():
                final_min_b, final_max_b = 0, 255
            else:
                final_min_b = max(0, int(min_rgb[2]) - tol)
                final_max_b = min(255, int(max_rgb[2]) + tol)
                
            if self.lasso_flood_var.get():
                self.update_progress(50, "Flood filling neighbors...")
                mask = self.flood_fill_mask(
                    mask, 
                    (final_min_r, final_min_g, final_min_b),
                    (final_max_r, final_max_g, final_max_b),
                    progress_callback=lambda p: self.update_progress(50 + p * 0.4, f"Flood fill: {int(p*100)}%")
                )
                
            self.update_progress(90, "Creating rule...")
            
            low_height = self.lasso_low_height_var.get()
            high_height = self.lasso_high_height_var.get()
            
            rule = {
                'type': 'lasso',
                'mask': mask.copy(),
                'min_rgb': (final_min_r, final_min_g, final_min_b),
                'max_rgb': (final_max_r, final_max_g, final_max_b),
                'low_rgb': tuple(min_rgb.astype(int)),
                'high_rgb': tuple(max_rgb.astype(int)),
                'low_height': low_height,
                'high_height': high_height,
                'pixel_count': int(np.sum(mask > 0)),
                'locks': (self.lock_r_var.get(), self.lock_g_var.get(), self.lock_b_var.get()),
                'lasso_points': img_points
            }
            self.rules.append(rule)
            
            self.rules_listbox.insert('end', self.get_rule_display_text(rule))
            
            self.update_progress(95, "Updating preview...")
            self.update_preview()
            
            self.clear_lasso()
            self.status_var.set(f"Added lasso rule: {rule['pixel_count']} pixels, heights {low_height}-{high_height}")
            
        finally:
            self.hide_progress()
        
    def flood_fill_mask(self, initial_mask, min_rgb, max_rgb, progress_callback=None):
        try:
            from scipy import ndimage
        except ImportError:
            self.status_var.set("scipy not installed - flood fill disabled")
            return initial_mask
            
        result_mask = initial_mask.copy()
        struct = ndimage.generate_binary_structure(2, 1)
        
        iterations = 0
        max_iterations = 500
        
        while iterations < max_iterations:
            if progress_callback:
                progress_callback(iterations / max_iterations)
                
            dilated = ndimage.binary_dilation(result_mask > 0, structure=struct)
            new_pixels = dilated & (result_mask == 0)
            
            if not np.any(new_pixels):
                break
                
            matching = (
                (self.original[:,:,0] >= min_rgb[0]) & (self.original[:,:,0] <= max_rgb[0]) &
                (self.original[:,:,1] >= min_rgb[1]) & (self.original[:,:,1] <= max_rgb[1]) &
                (self.original[:,:,2] >= min_rgb[2]) & (self.original[:,:,2] <= max_rgb[2])
            )
            
            pixels_to_add = new_pixels & matching
            
            if not np.any(pixels_to_add):
                break
                
            result_mask[pixels_to_add] = 255
            iterations += 1
            
        if progress_callback:
            progress_callback(1.0)
            
        return result_mask

    def clear_low_color(self):
        self.sampled_rgb_low = None
        self.low_color_preview.config(bg='gray')
        self.low_color_label.config(text="Not sampled")
        self.update_gradient_info()
        
    def clear_high_color(self):
        self.sampled_rgb_high = None
        self.high_color_preview.config(bg='gray')
        self.high_color_label.config(text="Not sampled")
        self.update_gradient_info()
        
    def update_gradient_info(self):
        if self.sampled_rgb_low is None and self.sampled_rgb_high is None:
            self.gradient_info_label.config(text="Sample both colors, then add rule")
        elif self.sampled_rgb_low is None:
            self.gradient_info_label.config(text="Now sample LOW color")
        elif self.sampled_rgb_high is None:
            self.gradient_info_label.config(text="Now sample HIGH color")
        else:
            self.gradient_info_label.config(text="Ready! Click Add Gradient Rule")

    # ================================================================
    # HEIGHTMAP EVENTS
    # ================================================================
    
    def on_heightmap_mouse_move(self, event):
        if self.current_heightmap is None:
            return
        x, y = self.screen_to_image(event.x, event.y)
        if x is not None and 0 <= x < self.current_heightmap.shape[1] and 0 <= y < self.current_heightmap.shape[0]:
            # Update live preview
            self.update_live_preview(x, y, source='heightmap')
            
            height = self.current_heightmap[y, x]
            mode = self.mode_var.get()
            
            if mode == 'single':
                self.status_var.set(f"Height: {height} @ ({x},{y}) — Click to set target height")
            elif mode == 'gradient':
                target = self.sample_target_var.get().upper()
                self.status_var.set(f"Height: {height} @ ({x},{y}) — Click to set {target} height")
            else:  # lasso
                target = self.lasso_sample_target_var.get().upper()
                self.status_var.set(f"Height: {height} @ ({x},{y}) — Click to set {target} height")
            
    def on_heightmap_click(self, event):
        if self.current_heightmap is None:
            return
        x, y = self.screen_to_image(event.x, event.y)
        if x is not None and 0 <= x < self.current_heightmap.shape[1] and 0 <= y < self.current_heightmap.shape[0]:
            height = int(self.current_heightmap[y, x])
            
            mode = self.mode_var.get()
            if mode == 'single':
                self.gray_var.set(height)
                self.status_var.set(f"Height set to {height}")
            elif mode == 'gradient':
                target = self.sample_target_var.get()
                if target == 'low':
                    self.low_height_var.set(height)
                    self.status_var.set(f"LOW height set to {height}")
                else:
                    self.high_height_var.set(height)
                    self.status_var.set(f"HIGH height set to {height}")
            else:  # lasso
                target = self.lasso_sample_target_var.get()
                if target == 'low':
                    self.lasso_low_height_var.set(height)
                    self.status_var.set(f"Lasso LOW height set to {height}")
                else:
                    self.lasso_high_height_var.set(height)
                    self.status_var.set(f"Lasso HIGH height set to {height}")

    # ================================================================
    # DISPLAY FUNCTIONS
    # ================================================================
    
    def refresh_display(self):
        self.show_original()
        self.update_preview()
    
    def show_original(self):
        if self.display_img is None:
            return
            
        zoomed_width = int(self.display_img.width * self.zoom_level)
        zoomed_height = int(self.display_img.height * self.zoom_level)
        
        if self.zoom_level != 1.0:
            zoomed_img = self.display_img.resize((zoomed_width, zoomed_height), 
                                                  Image.NEAREST if self.zoom_level > 2 else Image.LANCZOS)
        else:
            zoomed_img = self.display_img
            
        self.orig_photo = ImageTk.PhotoImage(zoomed_img)
        
        self.orig_canvas.delete('all')
        self.orig_canvas.create_image(self.pan_offset_x, self.pan_offset_y, 
                                       anchor='nw', image=self.orig_photo)
        
    def update_preview(self):
        if self.original is None:
            return
            
        heightmap = self.generate_heightmap()
        if heightmap:
            self.current_heightmap = np.array(heightmap)
            
            display_height = heightmap.resize(self.display_img.size, Image.LANCZOS)
            
            zoomed_width = int(display_height.width * self.zoom_level)
            zoomed_height = int(display_height.height * self.zoom_level)
            
            if self.zoom_level != 1.0:
                zoomed_img = display_height.resize((zoomed_width, zoomed_height),
                                                    Image.NEAREST if self.zoom_level > 2 else Image.LANCZOS)
            else:
                zoomed_img = display_height
                
            self.height_photo = ImageTk.PhotoImage(zoomed_img)
            
            self.height_canvas.delete('all')
            self.height_canvas.create_image(self.pan_offset_x, self.pan_offset_y,
                                            anchor='nw', image=self.height_photo)
            
            self.update_height_histogram(heightmap)
            
    def update_histograms(self):
        if self.original is None:
            return
        luminosity = (
            0.299 * self.original[:,:,0] +
            0.587 * self.original[:,:,1] +
            0.114 * self.original[:,:,2]
        ).astype(np.uint8)
        self.draw_histogram(self.orig_hist_canvas, luminosity.flatten(), '#88ff88')
        
    def update_height_histogram(self, heightmap):
        height_array = np.array(heightmap)
        self.draw_histogram(self.height_hist_canvas, height_array.flatten(), '#8888ff')
        
    def draw_histogram(self, canvas, data, color):
        canvas.delete('all')
        hist, _ = np.histogram(data, bins=256, range=(0, 256))
        canvas_height = 50
        max_val = hist.max() if hist.max() > 0 else 1
        normalized = (hist / max_val) * canvas_height
        for i, h in enumerate(normalized):
            if h > 0:
                canvas.create_line(i, canvas_height, i, canvas_height - h, fill=color)
        canvas.create_line(0, canvas_height, 256, canvas_height, fill='#666')

    # ================================================================
    # RULE MANAGEMENT
    # ================================================================
    
    def add_single_rule(self):
        if self.sampled_rgb is None:
            self.status_var.set("No color sampled!")
            return
            
        r, g, b = self.sampled_rgb
        tol = self.tolerance_var.get()
        gray = self.gray_var.get()
        
        min_r = 0 if self.lock_r_var.get() else max(0, r - tol)
        max_r = 255 if self.lock_r_var.get() else min(255, r + tol)
        min_g = 0 if self.lock_g_var.get() else max(0, g - tol)
        max_g = 255 if self.lock_g_var.get() else min(255, g + tol)
        min_b = 0 if self.lock_b_var.get() else max(0, b - tol)
        max_b = 255 if self.lock_b_var.get() else min(255, b + tol)
        
        rule = {
            'type': 'single',
            'min_rgb': (min_r, min_g, min_b),
            'max_rgb': (max_r, max_g, max_b),
            'gray': gray,
            'sampled': self.sampled_rgb,
            'tolerance': tol,
            'locks': (self.lock_r_var.get(), self.lock_g_var.get(), self.lock_b_var.get())
        }
        self.rules.append(rule)
        
        self.rules_listbox.insert('end', self.get_rule_display_text(rule))
        
        self.update_preview()
        self.status_var.set(f"Added: RGB({r},{g},{b}) → {gray}")
        
    def add_gradient_rule(self):
        if self.sampled_rgb_low is None:
            self.status_var.set("No LOW color sampled!")
            return
        if self.sampled_rgb_high is None:
            self.status_var.set("No HIGH color sampled!")
            return
            
        low_rgb = self.sampled_rgb_low
        high_rgb = self.sampled_rgb_high
        low_height = self.low_height_var.get()
        high_height = self.high_height_var.get()
        tol = self.tolerance_var.get()
        
        min_r = 0 if self.lock_r_var.get() else max(0, min(low_rgb[0], high_rgb[0]) - tol)
        max_r = 255 if self.lock_r_var.get() else min(255, max(low_rgb[0], high_rgb[0]) + tol)
        min_g = 0 if self.lock_g_var.get() else max(0, min(low_rgb[1], high_rgb[1]) - tol)
        max_g = 255 if self.lock_g_var.get() else min(255, max(low_rgb[1], high_rgb[1]) + tol)
        min_b = 0 if self.lock_b_var.get() else max(0, min(low_rgb[2], high_rgb[2]) - tol)
        max_b = 255 if self.lock_b_var.get() else min(255, max(low_rgb[2], high_rgb[2]) + tol)
        
        rule = {
            'type': 'gradient',
            'min_rgb': (min_r, min_g, min_b),
            'max_rgb': (max_r, max_g, max_b),
            'low_rgb': low_rgb,
            'high_rgb': high_rgb,
            'low_height': low_height,
            'high_height': high_height,
            'tolerance': tol,
            'locks': (self.lock_r_var.get(), self.lock_g_var.get(), self.lock_b_var.get())
        }
        self.rules.append(rule)
        
        self.rules_listbox.insert('end', self.get_rule_display_text(rule))
        
        self.update_preview()
        self.status_var.set(f"Added gradient: {low_height} to {high_height}")
        
    def delete_rule(self):
        sel = self.rules_listbox.curselection()
        if sel:
            self.rules_listbox.delete(sel[0])
            del self.rules[sel[0]]
            self.update_preview()
            
    def move_rule_up(self):
        sel = self.rules_listbox.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            self.rules[idx], self.rules[idx-1] = self.rules[idx-1], self.rules[idx]
            text = self.rules_listbox.get(idx)
            self.rules_listbox.delete(idx)
            self.rules_listbox.insert(idx-1, text)
            self.rules_listbox.selection_set(idx-1)
            self.update_preview()
            
    def move_rule_down(self):
        sel = self.rules_listbox.curselection()
        if sel and sel[0] < len(self.rules) - 1:
            idx = sel[0]
            self.rules[idx], self.rules[idx+1] = self.rules[idx+1], self.rules[idx]
            text = self.rules_listbox.get(idx)
            self.rules_listbox.delete(idx)
            self.rules_listbox.insert(idx+1, text)
            self.rules_listbox.selection_set(idx+1)
            self.update_preview()
            
    def clear_rules(self):
        self.rules = []
        self.rules_listbox.delete(0, 'end')
        self.update_preview()

    # ================================================================
    # HEIGHTMAP GENERATION
    # ================================================================
    
    def generate_heightmap(self):
        if self.original is None:
            return None
            
        if self.base_heightmap is not None:
            result = self.base_heightmap.astype(np.float32).copy()
        else:
            result = np.full(self.original.shape[:2], 128, dtype=np.float32)
        
        for rule in self.rules:
            rule_type = rule['type']
            
            if rule_type == 'lasso':
                if rule.get('mask') is None or rule.get('needs_mask_recreation'):
                    rule['mask'] = self.recreate_lasso_mask(self.rule_to_dict(rule))
                    rule['needs_mask_recreation'] = False
                    
                if rule['mask'] is None:
                    continue
                    
                mask = rule['mask'] > 0
                low_height = rule['low_height']
                high_height = rule['high_height']
                low_rgb = np.array(rule['low_rgb'], dtype=np.float32)
                high_rgb = np.array(rule['high_rgb'], dtype=np.float32)
                locks = rule.get('locks', (False, False, False))
                
                matching_pixels = self.original[mask].astype(np.float32)
                
                if len(matching_pixels) == 0:
                    continue
                    
                direction = high_rgb - low_rgb
                if locks[0]: direction[0] = 0
                if locks[1]: direction[1] = 0
                if locks[2]: direction[2] = 0
                
                dir_length_sq = np.sum(direction ** 2)
                
                if dir_length_sq < 0.001:
                    result[mask] = (low_height + high_height) / 2
                else:
                    pixel_vectors = matching_pixels - low_rgb
                    if locks[0]: pixel_vectors[:, 0] = 0
                    if locks[1]: pixel_vectors[:, 1] = 0
                    if locks[2]: pixel_vectors[:, 2] = 0
                    
                    t = np.sum(pixel_vectors * direction, axis=1) / dir_length_sq
                    t = np.clip(t, 0, 1)
                    heights = low_height + t * (high_height - low_height)
                    result[mask] = heights
                    
            else:
                min_rgb = rule['min_rgb']
                max_rgb = rule['max_rgb']
                
                mask = (
                    (self.original[:,:,0] >= min_rgb[0]) & (self.original[:,:,0] <= max_rgb[0]) &
                    (self.original[:,:,1] >= min_rgb[1]) & (self.original[:,:,1] <= max_rgb[1]) &
                    (self.original[:,:,2] >= min_rgb[2]) & (self.original[:,:,2] <= max_rgb[2])
                )
                
                if rule_type == 'single':
                    result[mask] = rule['gray']
                else:
                    low_rgb = np.array(rule['low_rgb'], dtype=np.float32)
                    high_rgb = np.array(rule['high_rgb'], dtype=np.float32)
                    low_height = rule['low_height']
                    high_height = rule['high_height']
                    locks = rule.get('locks', (False, False, False))
                    
                    matching_pixels = self.original[mask].astype(np.float32)
                    if len(matching_pixels) == 0:
                        continue
                    
                    direction = high_rgb - low_rgb
                    if locks[0]: direction[0] = 0
                    if locks[1]: direction[1] = 0
                    if locks[2]: direction[2] = 0
                    
                    dir_length_sq = np.sum(direction ** 2)
                    
                    if dir_length_sq < 0.001:
                        result[mask] = (low_height + high_height) / 2
                    else:
                        pixel_vectors = matching_pixels - low_rgb
                        if locks[0]: pixel_vectors[:, 0] = 0
                        if locks[1]: pixel_vectors[:, 1] = 0
                        if locks[2]: pixel_vectors[:, 2] = 0
                        
                        t = np.sum(pixel_vectors * direction, axis=1) / dir_length_sq
                        t = np.clip(t, 0, 1)
                        heights = low_height + t * (high_height - low_height)
                        result[mask] = heights
        
        result = np.clip(result, 0, 255).astype(np.uint8)
        return Image.fromarray(result, mode='L')

    # ================================================================
    # RUN
    # ================================================================
    
    def run(self):
        self.root.mainloop()


class UniformValueDialog:
    """Simple dialog to get a uniform height value."""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Set Uniform Height")
        self.dialog.geometry("300x120")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.geometry(f"+{parent.winfo_x() + 100}+{parent.winfo_y() + 100}")
        
        ttk.Label(self.dialog, text="Enter uniform height value (0-255):").pack(pady=(15, 5))
        
        self.value_var = tk.IntVar(value=128)
        
        slider_frame = ttk.Frame(self.dialog)
        slider_frame.pack(fill='x', padx=20)
        
        self.slider = ttk.Scale(slider_frame, from_=0, to=255, variable=self.value_var,
                                orient='horizontal', command=self.on_slider_change)
        self.slider.pack(side='left', fill='x', expand=True)
        
        self.value_label = ttk.Label(slider_frame, text="128", width=4)
        self.value_label.pack(side='left', padx=(5, 0))
        
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=15)
        
        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side='left', padx=5)
        
        self.dialog.bind('<Return>', lambda e: self.on_ok())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())
        
        parent.wait_window(self.dialog)
        
    def on_slider_change(self, event=None):
        self.value_label.config(text=str(self.value_var.get()))
        
    def on_ok(self):
        self.result = self.value_var.get()
        self.dialog.destroy()

    def on_cancel(self):
        self.result = None
        self.dialog.destroy()

if __name__ == '__main__':
    try:
        from scipy import ndimage
        print("scipy found - flood fill enabled")
    except ImportError:
        print("Note: scipy not found. Lasso flood-fill will be disabled.")
        print("Install with: pip install scipy")
        
    app = HeightmapCreator()
    app.run()

"""## Changes Made:

### 1. Lasso Mode - Separate Low/High Height Sampling
- Added "Height sampling for:" radio buttons (Low Height / High Height) in lasso settings
- Clicking on heightmap now sets either low or high height based on selection
- Both values have their own swatches that update in real-time

### 2. Lasso Height Swatches
- Added `lasso_low_preview` and `lasso_high_preview` canvas swatches
- They update automatically when the slider values change
- Visual consistency with gradient mode's height previews

### 3. Live Preview Panel
- New "Live Preview" section in the bottom panel (between Rules and Histograms)
- Shows real-time data as you move the cursor over either canvas:
  - **Color swatch + RGB values** from the original image
  - **Height swatch + Gray value** from the heightmap
  - **Position coordinates** (x, y)
- Updates on mouse move over either canvas
- Clears when mouse leaves the canvas area

### 4. Improved Status Bar Messages
- More contextual hints based on mode:
  - Single: "Click to set target height"
  - Gradient: "Click to set LOW/HIGH height" (based on selection)
  - Lasso: "Click to set LOW/HIGH height" (based on selection)

### Interface Layout
The live preview panel provides a unified experience where:
- All sampling targets have corresponding swatches
- Real-time feedback shows exactly what you're pointing at
- Easy to compare colors/heights across the image before clicking to sample"""