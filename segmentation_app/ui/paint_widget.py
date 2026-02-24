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
from segmentation_app.config import DEFAULT_CLASS_COLORS
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
        self.class_colors = {k: QColor(v) for k, v in DEFAULT_CLASS_COLORS.items()}
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
            parent = self.parent()
            while parent and not hasattr(parent, 'mask_modified'):
                parent = parent.parent()
            if parent:
                parent.mask_modified = True

    def toggle_mask_visibility(self):
        self.mask_visible = not self.mask_visible
        self.update()

