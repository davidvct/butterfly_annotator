import sys
import os
import glob
import importlib.util
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                               QSlider, QSpinBox, QComboBox, QColorDialog, 
                               QScrollArea, QMessageBox, QGroupBox, QListWidget,
                               QMenuBar, QMenu)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QPaintEvent, QMouseEvent, QShortcut, QKeySequence, QAction
import numpy as np
from PIL import Image


class PaintWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None
        self.mask = None
        self.mask_overlay = None
        self.mask_dirty = True
        self.mask_visible = True
        self.drawing = False
        self.brush_size = 10
        self.current_class = 1
        self.class_colors = {
            0: QColor(0, 0, 0, 0),  # Background (transparent)
            1: QColor(255, 0, 0, 128),    # Class 1 (red)
            2: QColor(0, 255, 0, 128),    # Class 2 (green)
            3: QColor(0, 0, 255, 128),    # Class 3 (blue)
            4: QColor(255, 255, 0, 128),  # Class 4 (yellow)
            5: QColor(255, 0, 255, 128),  # Class 5 (magenta)
        }
        self.mask_opacity = 128
        self.last_point = QPoint()
        self.update_regions = []
        self.eraser_mode = False
        self.cursor_pos = QPoint()
        self.show_cursor = False
        self.setMouseTracking(True)  # Enable mouse tracking for cursor
        
        # Undo system
        self.mask_history = []
        self.max_history = 50  # Limit history to prevent memory issues
        
        # Zoom system
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.original_size = None
        
        # Double-click detection for flood fill
        self.double_click_enabled = True
        
    def load_image(self, image_path):
        try:
            # Try loading with PIL first for better format support
            pil_image = Image.open(image_path)
            # Convert to RGB if necessary
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Convert PIL image to QPixmap
            width, height = pil_image.size
            rgb_data = pil_image.tobytes("raw", "RGB")
            qimage = QImage(rgb_data, width, height, QImage.Format_RGB888)
            self.image = QPixmap.fromImage(qimage)
            
            if self.image.isNull():
                return False, "Failed to convert image to QPixmap"
            
            # Initialize mask with same dimensions as image
            self.mask = np.zeros((self.image.height(), self.image.width()), dtype=np.uint8)
            self.mask_overlay = None
            self.mask_dirty = True
            # Clear history when loading new image
            self.mask_history = []
            self.original_size = self.image.size()
            self.update_widget_size()
            self.update()
            return True, "Success"
            
        except Exception as e:
            return False, f"Error loading image: {str(e)}"
    
    def set_brush_size(self, size):
        self.brush_size = size
    
    def set_current_class(self, class_id):
        self.current_class = class_id
    
    def set_eraser_mode(self, enabled):
        self.eraser_mode = enabled
    
    def save_mask_state(self):
        """Save current mask state to history for undo functionality"""
        if self.mask is not None:
            # Add current mask to history
            self.mask_history.append(self.mask.copy())
            # Limit history size
            if len(self.mask_history) > self.max_history:
                self.mask_history.pop(0)
    
    def undo(self):
        """Undo last operation by restoring previous mask state"""
        if len(self.mask_history) > 0 and self.mask is not None:
            # Restore previous mask state
            self.mask = self.mask_history.pop()
            self.mask_dirty = True
            self.update()
            
            # Signal that mask has been modified
            parent = self.parent()
            while parent and not hasattr(parent, 'mask_modified'):
                parent = parent.parent()
            if parent:
                parent.mask_modified = True
            return True
        return False
    
    def can_undo(self):
        """Check if undo is available"""
        return len(self.mask_history) > 0
    
    def set_zoom(self, zoom_factor):
        """Set zoom factor and update widget size"""
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, zoom_factor))
        self.update_widget_size()
        self.update()
    
    def update_widget_size(self):
        """Update widget size based on zoom factor"""
        if self.original_size is not None:
            new_size = self.original_size * self.zoom_factor
            self.setFixedSize(new_size)
    
    def get_zoom_factor(self):
        """Get current zoom factor"""
        return self.zoom_factor
    
    def screen_to_image_coords(self, screen_point):
        """Convert screen coordinates to image coordinates accounting for zoom"""
        if self.zoom_factor == 0:
            return screen_point
        return QPoint(int(screen_point.x() / self.zoom_factor), int(screen_point.y() / self.zoom_factor))
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if self.image is not None:
            # Zoom with Ctrl+wheel
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                zoom_in = delta > 0
                zoom_step = 0.1
                
                if zoom_in:
                    new_zoom = self.zoom_factor + zoom_step
                else:
                    new_zoom = self.zoom_factor - zoom_step
                
                self.set_zoom(new_zoom)
                
                # Update parent zoom controls
                parent = self.parent()
                while parent and not hasattr(parent, 'update_zoom_display'):
                    parent = parent.parent()
                if parent and hasattr(parent, 'update_zoom_display'):
                    parent.update_zoom_display()
                
                event.accept()
            else:
                super().wheelEvent(event)
        else:
            super().wheelEvent(event)
    
    def enterEvent(self, event):
        self.show_cursor = True
        self.update()
    
    def leaveEvent(self, event):
        self.show_cursor = False
        self.update()
    
    def set_mask_opacity(self, opacity):
        self.mask_opacity = opacity
        # Update class colors with new opacity
        for class_id in self.class_colors:
            if class_id != 0:  # Don't change background
                color = self.class_colors[class_id]
                self.class_colors[class_id] = QColor(color.red(), color.green(), color.blue(), opacity)
        self.mask_dirty = True
        self.update()
    
    def add_class_color(self, class_id, color):
        self.class_colors[class_id] = QColor(color.red(), color.green(), color.blue(), self.mask_opacity)
        self.mask_dirty = True
    
    def update_mask_overlay(self):
        if self.mask is None:
            return
            
        # Create mask overlay using numpy for better performance
        height, width = self.mask.shape
        rgba_array = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Apply colors for each class efficiently
        for class_id, color in self.class_colors.items():
            if class_id != 0:  # Skip background
                mask_indices = self.mask == class_id
                if np.any(mask_indices):
                    rgba_array[mask_indices] = [color.red(), color.green(), color.blue(), color.alpha()]
        
        # Convert to QImage
        qimage = QImage(rgba_array.data, width, height, QImage.Format_RGBA8888)
        self.mask_overlay = QPixmap.fromImage(qimage)
        self.mask_dirty = False
    
    def paintEvent(self, event):
        if self.image is None:
            return
            
        painter = QPainter(self)
        
        # Draw the original image scaled
        if self.zoom_factor != 1.0 and self.original_size is not None:
            scaled_size = self.original_size * self.zoom_factor
            scaled_image = self.image.scaled(scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled_image)
        else:
            painter.drawPixmap(0, 0, self.image)
        
        # Draw the mask overlay (use cached version if available)
        if self.mask is not None and self.mask_visible:
            if self.mask_dirty or self.mask_overlay is None:
                self.update_mask_overlay()
            
            if self.mask_overlay is not None:
                if self.zoom_factor != 1.0 and self.original_size is not None:
                    scaled_size = self.original_size * self.zoom_factor
                    scaled_overlay = self.mask_overlay.scaled(scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    painter.drawPixmap(0, 0, scaled_overlay)
                else:
                    painter.drawPixmap(0, 0, self.mask_overlay)
        
        # Draw brush cursor (scaled with zoom)
        if self.show_cursor and self.image is not None:
            scaled_brush_size = int(self.brush_size * self.zoom_factor)
            radius = scaled_brush_size // 2
            # Set pen for hollow circle
            if self.eraser_mode:
                # Red circle for eraser mode
                pen = QPen(QColor(255, 0, 0), 2)
            else:
                # White circle with black outline for paint mode
                pen = QPen(QColor(255, 255, 255), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)  # Hollow circle
            painter.drawEllipse(self.cursor_pos.x() - radius, self.cursor_pos.y() - radius, 
                              scaled_brush_size, scaled_brush_size)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image is not None:
            # Save current mask state for undo before starting to draw
            self.save_mask_state()
            self.drawing = True
            self.last_point = self.screen_to_image_coords(event.position().toPoint())
            self.draw_on_mask(self.last_point)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click for flood fill"""
        if event.button() == Qt.LeftButton and self.image is not None and not self.eraser_mode:
            current_pos = self.screen_to_image_coords(event.position().toPoint())
            print(f"Double-click detected at {current_pos.x()}, {current_pos.y()}")
            
            # Perform flood fill
            if self.flood_fill(current_pos, self.current_class):
                print("Flood fill successful")
                # Update undo button availability in parent
                parent = self.parent()
                while parent and not hasattr(parent, 'undo_btn'):
                    parent = parent.parent()
                if parent and hasattr(parent, 'undo_btn'):
                    parent.undo_btn.setEnabled(self.can_undo())
            else:
                print("Flood fill failed or no area to fill")
    
    def mouseMoveEvent(self, event):
        # Update cursor position for brush preview (screen coordinates)
        self.cursor_pos = event.position().toPoint()
        if self.show_cursor:
            self.update()
        
        if event.buttons() & Qt.LeftButton and self.drawing and self.image is not None:
            current_point = self.screen_to_image_coords(event.position().toPoint())
            self.draw_line(self.last_point, current_point)
            self.last_point = current_point
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            # Update undo button availability in parent
            parent = self.parent()
            while parent and not hasattr(parent, 'undo_btn'):
                parent = parent.parent()
            if parent and hasattr(parent, 'undo_btn'):
                parent.undo_btn.setEnabled(self.can_undo())
    
    def draw_on_mask(self, point):
        if self.mask is None:
            return
            
        x, y = point.x(), point.y()
        radius = self.brush_size // 2
        
        # Track the region that needs updating
        min_x, max_x = max(0, x - radius), min(self.mask.shape[1], x + radius + 1)
        min_y, max_y = max(0, y - radius), min(self.mask.shape[0], y + radius + 1)
        
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx*dx + dy*dy <= radius*radius:
                    mask_x, mask_y = x + dx, y + dy
                    if 0 <= mask_x < self.mask.shape[1] and 0 <= mask_y < self.mask.shape[0]:
                        if self.eraser_mode:
                            self.mask[mask_y, mask_x] = 0  # Set to background
                        else:
                            self.mask[mask_y, mask_x] = self.current_class
        
        self.mask_dirty = True
        # Only update the affected region for better performance
        self.update(min_x, min_y, max_x - min_x, max_y - min_y)
        
        # Signal that mask has been modified
        parent = self.parent()
        while parent and not hasattr(parent, 'mask_modified'):
            parent = parent.parent()
        if parent:
            parent.mask_modified = True
    
    def draw_line(self, start_point, end_point):
        # Draw a line by interpolating points between start and end
        steps = max(abs(end_point.x() - start_point.x()), abs(end_point.y() - start_point.y()))
        if steps == 0:
            return
            
        for i in range(steps + 1):
            t = i / steps if steps > 0 else 0
            x = int(start_point.x() + t * (end_point.x() - start_point.x()))
            y = int(start_point.y() + t * (end_point.y() - start_point.y()))
            self.draw_on_mask(QPoint(x, y))
    
    def get_mask(self):
        return self.mask.copy() if self.mask is not None else None
    
    def flood_fill(self, start_point, fill_class):
        """Fill an enclosed region using flood fill algorithm"""
        if self.mask is None:
            print("Flood fill failed: no mask")
            return False
            
        x, y = start_point.x(), start_point.y()
        print(f"Flood fill starting at ({x}, {y}), mask shape: {self.mask.shape}")
        
        if not (0 <= x < self.mask.shape[1] and 0 <= y < self.mask.shape[0]):
            print(f"Flood fill failed: coordinates out of bounds")
            return False
        
        # Save state for undo
        self.save_mask_state()
        
        # Get the original value at the starting point
        original_value = self.mask[y, x]
        print(f"Original value at ({x}, {y}): {original_value}, target class: {fill_class}")
        
        # If already the target class, find nearby background area to fill
        if original_value == fill_class:
            print(f"Clicked on existing class {fill_class}, searching for nearby background area...")
            
            # Search in expanding circles for a background (class 0) pixel
            max_search_radius = min(50, min(self.mask.shape) // 10)  # Limit search radius
            found_bg = False
            
            for radius in range(1, max_search_radius + 1):
                for angle in range(0, 360, 15):  # Check every 15 degrees
                    search_x = x + int(radius * np.cos(np.radians(angle)))
                    search_y = y + int(radius * np.sin(np.radians(angle)))
                    
                    if (0 <= search_x < self.mask.shape[1] and 
                        0 <= search_y < self.mask.shape[0] and
                        self.mask[search_y, search_x] == 0):  # Found background
                        
                        print(f"Found background area at ({search_x}, {search_y}), radius {radius}")
                        x, y = search_x, search_y
                        original_value = 0
                        found_bg = True
                        break
                
                if found_bg:
                    break
            
            if not found_bg:
                print("No nearby background area found to fill")
                return False
        
        # Use a stack-based flood fill to avoid recursion depth issues
        stack = [(x, y)]
        filled_pixels = 0
        max_fill_pixels = 100000  # Prevent filling extremely large areas
        
        while stack and filled_pixels < max_fill_pixels:
            cx, cy = stack.pop()
            
            # Skip if out of bounds or already processed
            if not (0 <= cx < self.mask.shape[1] and 0 <= cy < self.mask.shape[0]):
                continue
            if self.mask[cy, cx] != original_value:
                continue
            
            # Fill this pixel
            self.mask[cy, cx] = fill_class
            filled_pixels += 1
            
            # Add adjacent pixels to stack
            stack.append((cx + 1, cy))
            stack.append((cx - 1, cy))
            stack.append((cx, cy + 1))
            stack.append((cx, cy - 1))
        
        print(f"Flood fill completed: {filled_pixels} pixels filled")
        
        if filled_pixels > 0:
            self.mask_dirty = True
            self.update()
            
            # Signal that mask has been modified
            parent = self.parent()
            while parent and not hasattr(parent, 'mask_modified'):
                parent = parent.parent()
            if parent:
                parent.mask_modified = True
            
            return True
        return False
    
    def clear_mask(self):
        if self.mask is not None:
            self.mask.fill(0)
            self.mask_dirty = True
            self.update()
            
            # Signal that mask has been modified
            while parent and not hasattr(parent, 'mask_modified'):
                parent = parent.parent()
            if parent:
                parent.mask_modified = True

    def toggle_mask_visibility(self):
        self.mask_visible = not self.mask_visible
        self.update()


class SegmentationAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_session_file = None
        self.update_window_title()
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_session_file = None
        self.current_image_path = None
        self.mask_save_folder = None
        self.image_folder = None
        self.image_list = []
        self.current_image_index = 0
        self.mask_modified = False
        self.class_definitions = None
        self.class_names = {}
        self.default_class_colors = {
            0: QColor(0, 0, 0, 0),  # Background (transparent)
            1: QColor(255, 0, 0, 128),    # Class 1 (red)
            2: QColor(0, 255, 0, 128),    # Class 2 (green)
            3: QColor(0, 0, 255, 128),    # Class 3 (blue)
            4: QColor(255, 255, 0, 128),  # Class 4 (yellow)
            5: QColor(255, 0, 255, 128),  # Class 5 (magenta)
        }
        
        self.init_ui()
        self.setup_menu()
        
        # Load session if available
        self.load_session()
        self.update_window_title()

    def update_window_title(self):
        base_title = "Butterfly"
        if hasattr(self, 'current_session_file') and self.current_session_file:
            self.setWindowTitle(f"{base_title} - {self.current_session_file}")
        else:
            self.setWindowTitle(base_title)
        
    def setup_menu(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")

        open_session_action = QAction("Open Session", self)
        open_session_action.setShortcut("Ctrl+O")
        open_session_action.triggered.connect(self.open_session_dialog)
        file_menu.addAction(open_session_action)

        save_session_action = QAction("Save Session", self)
        save_session_action.triggered.connect(self.save_session_dialog)
        file_menu.addAction(save_session_action)

        save_session_as_action = QAction("Save As Session...", self)
        save_session_as_action.setShortcut("Ctrl+Shift+S")
        save_session_as_action.triggered.connect(self.save_session_as_dialog)
        file_menu.addAction(save_session_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        
        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.undo_last_action)
        edit_menu.addAction(undo_action)
        
        edit_menu.addSeparator()
        
        clear_mask_action = QAction("Clear Mask", self)
        clear_mask_action.triggered.connect(self.clear_mask)
        edit_menu.addAction(clear_mask_action)
        
        # Setting Menu
        setting_menu = menubar.addMenu("&Setting")
        
        load_class_action = QAction("Load Class Definition", self)
        load_class_action.triggered.connect(self.load_class_definitions)
        setting_menu.addAction(load_class_action)
        
        set_image_path_action = QAction("Set Image Path", self)
        set_image_path_action.triggered.connect(self.load_image_folder)
        setting_menu.addAction(set_image_path_action)
        
        set_mask_path_action = QAction("Set Mask Path", self)
        set_mask_path_action.triggered.connect(self.set_mask_folder)
        setting_menu.addAction(set_mask_path_action)
        
        # View Menu
        view_menu = menubar.addMenu("&View")
        
        self.toggle_mask_action = QAction("Hide/Unhide Mask", self)
        self.toggle_mask_action.setShortcut("I")
        self.toggle_mask_action.triggered.connect(self.toggle_mask_visibility)
        view_menu.addAction(self.toggle_mask_action)
        
        view_menu.addSeparator()
        
        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut("W")
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.zoom_in_action.setEnabled(False)
        view_menu.addAction(self.zoom_in_action)
        
        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut("S")
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.zoom_out_action.setEnabled(False)
        view_menu.addAction(self.zoom_out_action)
        
        self.zoom_reset_action = QAction("Reset Zoom (1:1)", self)
        self.zoom_reset_action.setShortcut("Ctrl+0")
        self.zoom_reset_action.triggered.connect(self.zoom_reset)
        self.zoom_reset_action.setEnabled(False)
        view_menu.addAction(self.zoom_reset_action)
        
        # About Menu
        about_menu = menubar.addMenu("&About")
        
        about_action = QAction("About Butterfly", self)
        about_action.triggered.connect(self.show_about_dialog)
        about_menu.addAction(about_action)
        
    def show_about_dialog(self):
        QMessageBox.about(self, "About Butterfly",
                          "<b>Butterfly</b><br>"
                          "Segmentation Annotation App<br>"
                          "Version: 1.0.0<br>"
                          "Released on: 2026-Feb-24")
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Top info panel
        self.paths_label = QLabel("<b>Image Path:</b> Not Set <br> <b>Mask Path:</b> Not Set")
        self.paths_label.setStyleSheet("padding: 7px; background-color: #f0f0f0; border-bottom: 1px solid #ccc; font-size: 10pt;")
        main_layout.addWidget(self.paths_label)
        
        # Content layout
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        
        # Left panel for controls
        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        left_layout = QVBoxLayout(left_panel)
        
        # File operations group
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout(file_group)
        
        # Navigation controls
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous (Left)")
        self.prev_btn.clicked.connect(self.previous_image)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next ▶ (Right)")
        self.next_btn.clicked.connect(self.next_image)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)
        
        file_layout.addLayout(nav_layout)
        
        # Mask suffix option
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("Mask Suffix:"))
        self.mask_suffix_combo = QComboBox()
        self.mask_suffix_combo.addItems(["None (same name)", "_tagged", "_mask"])
        self.mask_suffix_combo.setCurrentIndex(2) # Default to '_mask'
        self.mask_suffix_combo.currentIndexChanged.connect(self.on_mask_suffix_changed)
        suffix_layout.addWidget(self.mask_suffix_combo)
        file_layout.addLayout(suffix_layout)
        
        # Image info
        self.image_info_label = QLabel("No images loaded")
        self.image_info_label.setWordWrap(True)
        file_layout.addWidget(self.image_info_label)
        
        self.save_mask_btn = QPushButton("Save Mask (Ctrl+S)")
        self.save_mask_btn.clicked.connect(self.save_mask)
        self.save_mask_btn.setEnabled(False)
        file_layout.addWidget(self.save_mask_btn)
        
        left_layout.addWidget(file_group)
        
        # Brush controls group
        brush_group = QGroupBox("Brush Controls")
        brush_layout = QVBoxLayout(brush_group)
        
        # Brush size
        brush_layout.addWidget(QLabel("Brush Size (A/D):"))
        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setRange(1, 50)
        self.brush_size_slider.setValue(10)
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)
        brush_layout.addWidget(self.brush_size_slider)
        
        self.brush_size_label = QLabel("10")
        brush_layout.addWidget(self.brush_size_label)
        
        # Eraser toggle
        self.eraser_btn = QPushButton("Eraser Mode (M)")
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.setChecked(False)
        self.eraser_btn.clicked.connect(self.toggle_eraser_mode)
        brush_layout.addWidget(self.eraser_btn)
        
        # Flood fill instructions
        flood_fill_label = QLabel("💡 Flood Fill: Double-click inside a closed region to fill it instantly")
        flood_fill_label.setWordWrap(True)
        flood_fill_label.setStyleSheet("QLabel { color: #666; font-size: 9pt; padding: 5px; background-color: #f0f0f0; border-radius: 3px; }")
        brush_layout.addWidget(flood_fill_label)
        
        left_layout.addWidget(brush_group)
        
        # Class selection group
        class_group = QGroupBox("Class Selection")
        class_layout = QVBoxLayout(class_group)
        
        # Create label with fixed spacing
        class_label = QLabel("Select Class:")
        class_label.setContentsMargins(0, 0, 0, 0)
        class_layout.addWidget(class_label)
        
        # Create list widget that can expand
        self.class_list = QListWidget()
        self.class_list.setMinimumHeight(400)  # Set minimum height to display more items
        self.setup_default_classes()
        self.class_list.currentRowChanged.connect(self.update_current_class)
        class_layout.addWidget(self.class_list, 2)  # stretch factor 2 for expansion
        
        self.add_class_btn = QPushButton("Add New Class")
        self.add_class_btn.clicked.connect(self.add_new_class)
        class_layout.addWidget(self.add_class_btn)
        
        self.change_color_btn = QPushButton("Change Class Color")
        self.change_color_btn.clicked.connect(self.change_class_color)
        class_layout.addWidget(self.change_color_btn)
        
        left_layout.addWidget(class_group)
        
        # Mask controls group
        mask_group = QGroupBox("Mask Controls")
        mask_layout = QVBoxLayout(mask_group)
        
        # Mask opacity
        mask_layout.addWidget(QLabel("Mask Transparency:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 255)
        self.opacity_slider.setValue(128)
        self.opacity_slider.valueChanged.connect(self.update_mask_opacity)
        mask_layout.addWidget(self.opacity_slider)
        
        self.opacity_label = QLabel("50%")
        mask_layout.addWidget(self.opacity_label)
        
        self.clear_mask_btn = QPushButton("Clear Mask")
        self.clear_mask_btn.clicked.connect(self.clear_mask)
        self.clear_mask_btn.setEnabled(False)
        mask_layout.addWidget(self.clear_mask_btn)
        
        self.undo_btn = QPushButton("Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo_last_action)
        self.undo_btn.setEnabled(False)
        mask_layout.addWidget(self.undo_btn)
        
        left_layout.addWidget(mask_group)
        
        # Zoom info group
        zoom_group = QGroupBox("View Info")
        zoom_layout = QVBoxLayout(zoom_group)
        
        # Zoom level display
        self.zoom_label = QLabel("Zoom: 100%")
        zoom_layout.addWidget(self.zoom_label)
        
        left_layout.addWidget(zoom_group)
        
        # Add stretch at bottom to push everything up and maintain fixed spacing
        left_layout.addStretch()
        
        # Right panel for image display
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Scroll area for image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        self.paint_widget = PaintWidget()
        self.scroll_area.setWidget(self.paint_widget)
        
        right_layout.addWidget(self.scroll_area)
        
        # Add panels to content layout
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Undo shortcut (Ctrl+Z)
        self.undo_shortcut = QShortcut(QKeySequence.Undo, self)
        self.undo_shortcut.activated.connect(self.undo_last_action)
        
        # Zoom shortcuts (Ctrl++ and Ctrl+- keep working as fallbacks)
        self.zoom_in_shortcut = QShortcut(QKeySequence.ZoomIn, self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        
        self.zoom_out_shortcut = QShortcut(QKeySequence.ZoomOut, self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)
        
        # Additional zoom shortcuts with + and - keys
        self.zoom_in_plus = QShortcut(QKeySequence("+"), self)
        self.zoom_in_plus.activated.connect(self.zoom_in)
        
        self.zoom_out_minus = QShortcut(QKeySequence("-"), self)
        self.zoom_out_minus.activated.connect(self.zoom_out)
        
        # Brush shortcuts
        self.brush_inc = QShortcut(QKeySequence("D"), self)
        self.brush_inc.activated.connect(lambda: self.brush_size_slider.setValue(self.brush_size_slider.value() + 1))
        
        self.brush_dec = QShortcut(QKeySequence("A"), self)
        self.brush_dec.activated.connect(lambda: self.brush_size_slider.setValue(self.brush_size_slider.value() - 1))
        
        # Eraser shortcut
        self.eraser_shortcut = QShortcut(QKeySequence("M"), self)
        self.eraser_shortcut.activated.connect(self.eraser_btn.click)
        
        # Opacity shortcuts
        self.opacity_inc = QShortcut(QKeySequence("E"), self)
        self.opacity_inc.activated.connect(lambda: self.opacity_slider.setValue(min(255, self.opacity_slider.value() + 25)))
        
        self.opacity_dec = QShortcut(QKeySequence("Q"), self)
        self.opacity_dec.activated.connect(lambda: self.opacity_slider.setValue(max(0, self.opacity_slider.value() - 25)))
        
        # Navigation shortcuts
        self.prev_shortcut = QShortcut(QKeySequence("Left"), self)
        self.prev_shortcut.activated.connect(self.previous_image)
        
        self.next_shortcut = QShortcut(QKeySequence("Right"), self)
        self.next_shortcut.activated.connect(self.next_image)
        
        # Save Mask shortcut
        self.save_mask_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_mask_shortcut.activated.connect(self.save_mask)
        
        # Class selection shortcuts 1-9
        for i in range(1, 10):
            shortcut = QShortcut(QKeySequence(str(i)), self)
            shortcut.activated.connect(lambda idx=i: self.select_class_by_shortcut(idx))

    def select_class_by_shortcut(self, key_num):
        row = key_num - 1
        if 0 <= row < self.class_list.count():
            self.class_list.setCurrentRow(row)
    
    def setup_default_classes(self):
        """Setup default classes when no class file is loaded"""
        self.class_list.clear()
        for i in range(1, 6):
            self.class_list.addItem(f"Class {i} ({i})")
        self.class_names = {i: f"Class {i}" for i in range(1, 6)}
        # Set first item as selected
        if self.class_list.count() > 0:
            self.class_list.setCurrentRow(0)
        # Reset paint widget to use default colors
        if hasattr(self, 'paint_widget'):
            self.paint_widget.class_colors = self.default_class_colors.copy()
    
    def load_class_definitions(self):
        """Load class definitions from a Python file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Class Definitions", "", "Python Files (*.py)"
        )
        
        if not file_path:
            return
            
        try:
            # First, try to fix the indentation issue by reading and parsing the file manually
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if the file has indentation issues and try to fix them
            lines = content.split('\n')
            fixed_lines = []
            in_function = False
            
            for line in lines:
                if line.strip().startswith('def feature_type():'):
                    in_function = True
                    fixed_lines.append(line)
                elif in_function and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                    # This line should be indented but isn't
                    fixed_lines.append('    ' + line)
                else:
                    fixed_lines.append(line)
            
            fixed_content = '\n'.join(fixed_lines)
            
            # Try to execute the fixed content
            try:
                namespace = {}
                exec(fixed_content, namespace)
                
                if 'feature_type' in namespace:
                    class_definitions = namespace['feature_type']()
                    self.load_classes_from_definitions(class_definitions)
                else:
                    QMessageBox.warning(self, "Error", "No 'feature_type' function found in the file")
            except Exception as exec_error:
                # If fixing indentation didn't work, try the original approach
                try:
                    spec = importlib.util.spec_from_file_location("class_definitions", file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, 'feature_type'):
                        class_definitions = module.feature_type()
                        self.load_classes_from_definitions(class_definitions)
                    else:
                        QMessageBox.warning(self, "Error", "No 'feature_type' function found in the file")
                except Exception as module_error:
                    raise exec_error  # Use the exec error as it's more informative
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load class definitions:\n{str(e)}")
    
    def load_classes_from_definitions(self, class_definitions):
        """Load classes from the parsed definitions"""
        self.class_definitions = class_definitions
        self.class_names = {}
        
        # Clear existing list
        self.class_list.clear()
        
        # Process each class definition (skip background at index 0)
        new_class_colors = {0: QColor(0, 0, 0, 0)}  # Keep transparent background
        
        row_idx = 1
        for i, class_def in enumerate(class_definitions):
            if i == 0:  # Skip background
                continue
                
            class_name = class_def[0]
            color_rgb = class_def[1]  # Use display color (index 1)
            
            # Store class name
            self.class_names[i] = class_name
            
            # Add to list widget
            shortcut_txt = f" ({row_idx})" if row_idx <= 9 else ""
            self.class_list.addItem(f"{class_name}{shortcut_txt}")
            
            # Set color with current opacity
            color = QColor(color_rgb[0], color_rgb[1], color_rgb[2], self.paint_widget.mask_opacity)
            new_class_colors[i] = color
            
            row_idx += 1
        
        # Set first item as selected
        if self.class_list.count() > 0:
            self.class_list.setCurrentRow(0)
        
        # Update paint widget colors
        self.paint_widget.class_colors = new_class_colors
        self.paint_widget.mask_dirty = True
        self.paint_widget.update()
    
    def load_image_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.image_folder = folder
            # Find all image files in the folder
            image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff', '*.gif', '*.webp']
            self.image_list = []
            
            for ext in image_extensions:
                self.image_list.extend(glob.glob(os.path.join(folder, ext)))
                self.image_list.extend(glob.glob(os.path.join(folder, ext.upper())))
            
            # Remove duplicates and sort
            self.image_list = sorted(list(set(self.image_list)))
            
            if self.image_list:
                self.current_image_index = 0
                self.load_current_image()
                self.update_navigation_buttons()
                self.update_image_info()
                self.update_paths_display()
            else:
                QMessageBox.warning(self, "Error", "No image files found in the selected folder!")
                self.update_paths_display()
    
    def load_current_image(self):
        if not self.image_list or self.current_image_index >= len(self.image_list):
            return
            
        file_path = self.image_list[self.current_image_index]
        success, message = self.paint_widget.load_image(file_path)
        if success:
            self.current_image_path = file_path
            self.save_mask_btn.setEnabled(True)
            self.clear_mask_btn.setEnabled(True)
            self.undo_btn.setEnabled(False)  # No history when loading new image
            self.zoom_in_action.setEnabled(True)
            self.zoom_out_action.setEnabled(True)
            self.zoom_reset_action.setEnabled(True)
            self.update_zoom_display()
            
            # Try to load existing mask if it exists
            self.load_existing_mask()
            # Reset modification flag for new image
            self.mask_modified = False
        else:
            QMessageBox.warning(self, "Error", f"Failed to load image!\n{message}")
    
    def get_current_mask_suffix(self):
        suffix_idx = self.mask_suffix_combo.currentIndex()
        if suffix_idx == 0:
            return ""
        elif suffix_idx == 1:
            return "_tagged"
        else:
            return "_mask"

    def on_mask_suffix_changed(self):
        if hasattr(self, 'current_image_path') and self.current_image_path and getattr(self, 'mask_save_folder', None):
            if not getattr(self, 'mask_modified', False) or self.check_save_before_leave():
                self.paint_widget.clear_mask()
                self.load_existing_mask()
                self.mask_modified = False # Prevent popup if already handled

    def load_existing_mask(self):
        if not self.current_image_path or not getattr(self, 'mask_save_folder', None):
            return
            
        image_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        suffix = self.get_current_mask_suffix()
        mask_path = os.path.join(self.mask_save_folder, f"{image_name}{suffix}.png")
        
        if os.path.exists(mask_path):
            try:
                # Load existing mask
                mask_image = Image.open(mask_path)
                if mask_image.mode == 'RGB':
                    # Convert RGB mask back to class indices
                    mask_array = np.array(mask_image)
                    class_mask = np.zeros((mask_array.shape[0], mask_array.shape[1]), dtype=np.uint8)
                    
                    # Map RGB colors back to class IDs
                    color_to_class = {(0, 0, 0): 0}  # Background
                    
                    if self.class_definitions:
                        # Use colors from loaded class definitions
                        for i, class_def in enumerate(self.class_definitions):
                            if i == 0:  # Background
                                continue
                            color_rgb = class_def[1]  # Use display color
                            color_to_class[tuple(color_rgb)] = i
                    else:
                        # Use default color mapping
                        default_color_mapping = {
                            (255, 0, 0): 1,     # Class 1 (red)
                            (0, 255, 0): 2,     # Class 2 (green)
                            (0, 0, 255): 3,     # Class 3 (blue)
                            (255, 255, 0): 4,   # Class 4 (yellow)
                            (255, 0, 255): 5,   # Class 5 (magenta)
                        }
                        color_to_class.update(default_color_mapping)
                    
                    for (r, g, b), class_id in color_to_class.items():
                        mask_indices = np.all(mask_array == [r, g, b], axis=2)
                        class_mask[mask_indices] = class_id
                    
                    self.paint_widget.mask = class_mask
                    self.paint_widget.mask_dirty = True
                    self.paint_widget.update()
                    
            except Exception as e:
                print(f"Could not load existing mask: {e}")
    
    def previous_image(self):
        if self.image_list and self.current_image_index > 0:
            if self.check_save_before_leave():
                self.current_image_index -= 1
                self.load_current_image()
                self.update_navigation_buttons()
                self.update_image_info()
    
    def next_image(self):
        if self.image_list and self.current_image_index < len(self.image_list) - 1:
            if self.check_save_before_leave():
                self.current_image_index += 1
                self.load_current_image()
                self.update_navigation_buttons()
                self.update_image_info()
    
    def update_navigation_buttons(self):
        if not self.image_list:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return
            
        self.prev_btn.setEnabled(self.current_image_index > 0)
        self.next_btn.setEnabled(self.current_image_index < len(self.image_list) - 1)
    
    def update_image_info(self):
        if not self.image_list:
            self.image_info_label.setText("No images loaded")
            return
            
        current_file = os.path.basename(self.image_list[self.current_image_index])
        info_text = f"Image {self.current_image_index + 1} of {len(self.image_list)}\n{current_file}"
        self.image_info_label.setText(info_text)

    def update_paths_display(self):
        img_path = self.image_folder if self.image_folder else "Not Set"
        mask_path = self.mask_save_folder if self.mask_save_folder else "Not Set"
        self.paths_label.setText(f"<b>Image Path:</b> {img_path} <br> <b>Mask Path:</b> {mask_path}")
    
    def check_save_before_leave(self):
        if self.mask_modified and self.mask_save_folder:
            reply = QMessageBox.question(
                self, "Unsaved Changes", 
                "You have unsaved changes to the mask. Do you want to save before leaving this image?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.save_mask()
                return True
            elif reply == QMessageBox.No:
                return True
            else:  # Cancel
                return False
        return True
    
    def closeEvent(self, event):
        if self.check_save_before_leave():
            self.save_session()
            event.accept()
        else:
            event.ignore()
    def open_session_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Session", "", "JSON Files (*.json)"
        )
        if file_path:
            self.load_session(file_path)

    def save_session_dialog(self):
        if self.current_session_file:
            self.save_session(self.current_session_file)
            self.statusBar().showMessage("Session saved successfully.", 3000)
        else:
            self.save_session_as_dialog()

    def save_session_as_dialog(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Session As", "", "JSON Files (*.json)"
        )
        if file_path:
            self.save_session(file_path)
            self.statusBar().showMessage("Session saved successfully.", 3000)

    def save_session(self, file_path=None):
        if file_path is None:
            if self.current_session_file:
                file_path = self.current_session_file
            else:
                session_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(session_dir, 'session.json')
                
        self.current_session_file = file_path
        self.update_window_title()
        
        session_data = {
            'image_folder': self.image_folder,
            'mask_save_folder': self.mask_save_folder,
            'mask_suffix_index': self.mask_suffix_combo.currentIndex(),
            'current_image_index': self.current_image_index,
            'brush_size': self.brush_size_slider.value(),
            'transparency': self.opacity_slider.value(),
            'class_names': self.class_names,
            'class_definitions': self.class_definitions
        }
        
        if hasattr(self, 'paint_widget'):
            session_data['class_colors'] = {k: [v.red(), v.green(), v.blue(), v.alpha()] for k, v in self.paint_widget.class_colors.items()}
            
        try:
            with open(file_path, 'w') as f:
                json.dump(session_data, f, indent=4)
        except Exception as e:
            print(f"Failed to save session: {e}")

    def load_session(self, file_path=None):
        if file_path is None:
            session_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(session_dir, 'session.json')
            
        if not os.path.exists(file_path):
            return
            
        self.current_session_file = file_path
        self.update_window_title()
            
        try:
            with open(file_path, 'r') as f:
                session_data = json.load(f)
                
            if 'mask_suffix_index' in session_data:
                self.mask_suffix_combo.blockSignals(True)
                self.mask_suffix_combo.setCurrentIndex(session_data['mask_suffix_index'])
                self.mask_suffix_combo.blockSignals(False)

            if 'class_definitions' in session_data:
                self.class_definitions = session_data['class_definitions']
                
            if 'brush_size' in session_data:
                self.brush_size_slider.setValue(session_data['brush_size'])
                
            if 'transparency' in session_data:
                self.opacity_slider.setValue(session_data['transparency'])
                
            if 'class_names' in session_data and 'class_colors' in session_data:
                class_names = {int(k): v for k, v in session_data['class_names'].items()}
                class_colors = {int(k): v for k, v in session_data['class_colors'].items()}
                
                self.class_names = class_names
                self.class_list.clear()
                
                self.paint_widget.update()
                    
            if 'mask_save_folder' in session_data and session_data['mask_save_folder']:
                self.mask_save_folder = session_data['mask_save_folder']
                
            if 'image_folder' in session_data and session_data['image_folder']:
                folder = session_data['image_folder']
                if os.path.exists(folder):
                    self.image_folder = folder
                    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff', '*.gif', '*.webp']
                    self.image_list = []
                    for ext in image_extensions:
                        self.image_list.extend(glob.glob(os.path.join(folder, ext)))
                        self.image_list.extend(glob.glob(os.path.join(folder, ext.upper())))
                    self.image_list = sorted(list(set(self.image_list)))
                    
                    if self.image_list:
                        if 'current_image_index' in session_data:
                            self.current_image_index = min(session_data['current_image_index'], len(self.image_list) - 1)
                        else:
                            self.current_image_index = 0
                            
                        self.load_current_image()
                        self.update_navigation_buttons()
                        self.update_image_info()
                        
            self.update_paths_display()
                        
        except Exception as e:
            print(f"Failed to load session: {e}")
    
    def set_mask_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Mask Save Folder")
        if folder:
            self.mask_save_folder = folder
            self.update_paths_display()
    
    def save_mask(self):
        if not self.current_image_path:
            QMessageBox.warning(self, "Error", "No image loaded!")
            return
        
        if not self.mask_save_folder:
            QMessageBox.warning(self, "Error", "Please set a mask save folder first!")
            return
        
        mask = self.paint_widget.get_mask()
        if mask is None:
            QMessageBox.warning(self, "Error", "No mask to save!")
            return
        
        # Create mask filename based on image filename
        image_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        suffix = self.get_current_mask_suffix()
        mask_path = os.path.join(self.mask_save_folder, f"{image_name}{suffix}.png")
        
        # Convert mask to RGB for visualization
        height, width = mask.shape
        rgb_mask = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Map each class to its RGB color
        class_color_mapping = {0: (0, 0, 0)}  # Background (black)
        
        if self.class_definitions:
            # Use colors from loaded class definitions
            for i, class_def in enumerate(self.class_definitions):
                if i == 0:  # Background
                    continue
                color_rgb = class_def[1]  # Use display color
                class_color_mapping[i] = tuple(color_rgb)
        else:
            # Use default colors
            default_colors = {
                1: (255, 0, 0),     # Class 1 (red)
                2: (0, 255, 0),     # Class 2 (green)
                3: (0, 0, 255),     # Class 3 (blue)
                4: (255, 255, 0),   # Class 4 (yellow)
                5: (255, 0, 255),   # Class 5 (magenta)
            }
            class_color_mapping.update(default_colors)
        
        # Add any additional classes that were dynamically added
        for class_id in range(6, self.class_list.count() + 1):
            if class_id in self.paint_widget.class_colors:
                color = self.paint_widget.class_colors[class_id]
                class_color_mapping[class_id] = (color.red(), color.green(), color.blue())
        
        # Apply colors to mask
        for class_id, (r, g, b) in class_color_mapping.items():
            mask_indices = mask == class_id
            rgb_mask[mask_indices] = [r, g, b]
        
        # Save mask as RGB PIL Image
        mask_image = Image.fromarray(rgb_mask, mode='RGB')
        mask_image.save(mask_path)
        
        # Mark mask as saved
        self.mask_modified = False
    
    def update_brush_size(self, value):
        self.paint_widget.set_brush_size(value)
        self.brush_size_label.setText(str(value))
    
    def toggle_eraser_mode(self):
        is_eraser = self.eraser_btn.isChecked()
        self.paint_widget.set_eraser_mode(is_eraser)
        
        # Update button text and appearance
        if is_eraser:
            self.eraser_btn.setText("🗲 Eraser Mode")
            self.eraser_btn.setStyleSheet("QPushButton { background-color: #ffcccc; }")
        else:
            self.eraser_btn.setText("Eraser Mode")
            self.eraser_btn.setStyleSheet("")
    
    def update_current_class(self, row):
        # If we have class definitions, map the list row to the actual class ID
        if self.class_definitions:
            # Find the class ID for this list row (skip background at index 0)
            class_ids = [i for i in range(1, len(self.class_definitions)) if i in self.class_names]
            if row >= 0 and row < len(class_ids):
                self.paint_widget.set_current_class(class_ids[row])
        else:
            if row >= 0:
                self.paint_widget.set_current_class(row + 1)  # Classes start from 1
    
    def update_mask_opacity(self, value):
        self.paint_widget.set_mask_opacity(value)
        percentage = int((value / 255.0) * 100)
        self.opacity_label.setText(f"{percentage}%")
    
    def add_new_class(self):
        # Only allow adding new classes if no class definitions are loaded
        if self.class_definitions:
            QMessageBox.information(
                self, "Info", 
                "Cannot add new classes when class definitions are loaded from file.\n"
                "To add classes, modify the class definition file and reload it."
            )
            return
            
        current_classes = self.class_list.count()
        new_class_id = current_classes + 1
        
        # Choose color for new class
        color = QColorDialog.getColor(Qt.red, self, f"Choose color for Class {new_class_id}")
        if color.isValid():
            self.paint_widget.add_class_color(new_class_id, color)
            shortcut_txt = f" ({new_class_id})" if new_class_id <= 9 else ""
            self.class_list.addItem(f"Class {new_class_id}{shortcut_txt}")
            self.class_names[new_class_id] = f"Class {new_class_id}"
    
    def change_class_color(self):
        current_row = self.class_list.currentRow()
        
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select a class first")
            return
        
        if self.class_definitions:
            # Find the actual class ID for this list row
            class_ids = [i for i in range(1, len(self.class_definitions)) if i in self.class_names]
            if current_row < len(class_ids):
                current_class = class_ids[current_row]
                class_name = self.class_names[current_class]
            else:
                return
        else:
            current_class = current_row + 1
            class_name = f"Class {current_class}"
        
        color = QColorDialog.getColor(Qt.red, self, f"Choose color for {class_name}")
        if color.isValid():
            self.paint_widget.add_class_color(current_class, color)
    
    def undo_last_action(self):
        """Undo the last paint/erase action"""
        if self.paint_widget.undo():
            # Update undo button state
            self.undo_btn.setEnabled(self.paint_widget.can_undo())
    
    def zoom_in(self):
        """Zoom in the image"""
        current_zoom = self.paint_widget.get_zoom_factor()
        new_zoom = current_zoom + 0.2
        self.paint_widget.set_zoom(new_zoom)
        self.update_zoom_display()
    
    def zoom_out(self):
        """Zoom out the image"""
        current_zoom = self.paint_widget.get_zoom_factor()
        new_zoom = current_zoom - 0.2
        self.paint_widget.set_zoom(new_zoom)
        self.update_zoom_display()
    
    def zoom_reset(self):
        """Reset zoom to 100%"""
        self.paint_widget.set_zoom(1.0)
        self.update_zoom_display()
    
    def update_zoom_display(self):
        """Update zoom level display"""
        zoom_percent = int(self.paint_widget.get_zoom_factor() * 100)
        self.zoom_label.setText(f"Zoom: {zoom_percent}%")
        
        # Update action states
        current_zoom = self.paint_widget.get_zoom_factor()
        self.zoom_in_action.setEnabled(current_zoom < self.paint_widget.max_zoom)
        self.zoom_out_action.setEnabled(current_zoom > self.paint_widget.min_zoom)
    
    def clear_mask(self):
        reply = QMessageBox.question(
            self, "Clear Mask", "Are you sure you want to clear the entire mask?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Save state before clearing for undo
            self.paint_widget.save_mask_state()
            self.paint_widget.clear_mask()
            # Update undo button state
            self.undo_btn.setEnabled(self.paint_widget.can_undo())

    def toggle_mask_visibility(self):
        self.paint_widget.toggle_mask_visibility()


def main():
    app = QApplication(sys.argv)
    window = SegmentationAnnotator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()