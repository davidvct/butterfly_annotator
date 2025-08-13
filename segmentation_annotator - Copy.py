import sys
import os
import glob
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                               QSlider, QSpinBox, QComboBox, QColorDialog, 
                               QScrollArea, QMessageBox, QGroupBox)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QPaintEvent, QMouseEvent
import numpy as np
from PIL import Image


class PaintWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None
        self.mask = None
        self.mask_overlay = None
        self.mask_dirty = True
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
            self.setFixedSize(self.image.size())
            self.update()
            return True, "Success"
            
        except Exception as e:
            return False, f"Error loading image: {str(e)}"
    
    def set_brush_size(self, size):
        self.brush_size = size
    
    def set_current_class(self, class_id):
        self.current_class = class_id
    
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
        
        # Draw the original image
        painter.drawPixmap(0, 0, self.image)
        
        # Draw the mask overlay (use cached version if available)
        if self.mask is not None:
            if self.mask_dirty or self.mask_overlay is None:
                self.update_mask_overlay()
            
            if self.mask_overlay is not None:
                painter.drawPixmap(0, 0, self.mask_overlay)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image is not None:
            self.drawing = True
            self.last_point = event.position().toPoint()
            self.draw_on_mask(self.last_point)
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drawing and self.image is not None:
            current_point = event.position().toPoint()
            self.draw_line(self.last_point, current_point)
            self.last_point = current_point
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
    
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


class SegmentationAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Segmentation Annotator")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_image_path = None
        self.mask_save_folder = None
        self.image_folder = None
        self.image_list = []
        self.current_image_index = 0
        self.mask_modified = False
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for controls
        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        left_layout = QVBoxLayout(left_panel)
        
        # File operations group
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout(file_group)
        
        self.load_folder_btn = QPushButton("Select Image Folder")
        self.load_folder_btn.clicked.connect(self.load_image_folder)
        file_layout.addWidget(self.load_folder_btn)
        
        # Navigation controls
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.previous_image)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_image)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)
        
        file_layout.addLayout(nav_layout)
        
        # Image info
        self.image_info_label = QLabel("No images loaded")
        self.image_info_label.setWordWrap(True)
        file_layout.addWidget(self.image_info_label)
        
        self.set_mask_folder_btn = QPushButton("Set Mask Save Folder")
        self.set_mask_folder_btn.clicked.connect(self.set_mask_folder)
        file_layout.addWidget(self.set_mask_folder_btn)
        
        self.save_mask_btn = QPushButton("Save Mask")
        self.save_mask_btn.clicked.connect(self.save_mask)
        self.save_mask_btn.setEnabled(False)
        file_layout.addWidget(self.save_mask_btn)
        
        left_layout.addWidget(file_group)
        
        # Brush controls group
        brush_group = QGroupBox("Brush Controls")
        brush_layout = QVBoxLayout(brush_group)
        
        # Brush size
        brush_layout.addWidget(QLabel("Brush Size:"))
        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setRange(1, 50)
        self.brush_size_slider.setValue(10)
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)
        brush_layout.addWidget(self.brush_size_slider)
        
        self.brush_size_label = QLabel("10")
        brush_layout.addWidget(self.brush_size_label)
        
        left_layout.addWidget(brush_group)
        
        # Class selection group
        class_group = QGroupBox("Class Selection")
        class_layout = QVBoxLayout(class_group)
        
        class_layout.addWidget(QLabel("Current Class:"))
        self.class_combo = QComboBox()
        self.class_combo.addItems([f"Class {i}" for i in range(1, 6)])
        self.class_combo.currentIndexChanged.connect(self.update_current_class)
        class_layout.addWidget(self.class_combo)
        
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
        
        left_layout.addWidget(mask_group)
        
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
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
    
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
            else:
                QMessageBox.warning(self, "Error", "No image files found in the selected folder!")
    
    def load_current_image(self):
        if not self.image_list or self.current_image_index >= len(self.image_list):
            return
            
        file_path = self.image_list[self.current_image_index]
        success, message = self.paint_widget.load_image(file_path)
        if success:
            self.current_image_path = file_path
            self.save_mask_btn.setEnabled(True)
            self.clear_mask_btn.setEnabled(True)
            
            # Try to load existing mask if it exists
            self.load_existing_mask()
            # Reset modification flag for new image
            self.mask_modified = False
        else:
            QMessageBox.warning(self, "Error", f"Failed to load image!\n{message}")
    
    def load_existing_mask(self):
        if not self.current_image_path or not self.mask_save_folder:
            return
            
        image_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        mask_path = os.path.join(self.mask_save_folder, f"{image_name}_mask.png")
        
        if os.path.exists(mask_path):
            try:
                # Load existing mask
                mask_image = Image.open(mask_path)
                if mask_image.mode == 'RGB':
                    # Convert RGB mask back to class indices
                    mask_array = np.array(mask_image)
                    class_mask = np.zeros((mask_array.shape[0], mask_array.shape[1]), dtype=np.uint8)
                    
                    # Map RGB colors back to class IDs
                    color_to_class = {
                        (0, 0, 0): 0,       # Background
                        (255, 0, 0): 1,     # Class 1 (red)
                        (0, 255, 0): 2,     # Class 2 (green)
                        (0, 0, 255): 3,     # Class 3 (blue)
                        (255, 255, 0): 4,   # Class 4 (yellow)
                        (255, 0, 255): 5,   # Class 5 (magenta)
                    }
                    
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
            event.accept()
        else:
            event.ignore()
    
    def set_mask_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Mask Save Folder")
        if folder:
            self.mask_save_folder = folder
    
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
        mask_path = os.path.join(self.mask_save_folder, f"{image_name}_mask.png")
        
        # Convert mask to RGB for visualization
        height, width = mask.shape
        rgb_mask = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Map each class to its RGB color
        class_color_mapping = {
            0: (0, 0, 0),       # Background (black)
            1: (255, 0, 0),     # Class 1 (red)
            2: (0, 255, 0),     # Class 2 (green)
            3: (0, 0, 255),     # Class 3 (blue)
            4: (255, 255, 0),   # Class 4 (yellow)
            5: (255, 0, 255),   # Class 5 (magenta)
        }
        
        # Add any additional classes that were dynamically added
        for class_id in range(6, self.class_combo.count() + 1):
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
    
    def update_current_class(self, index):
        self.paint_widget.set_current_class(index + 1)  # Classes start from 1
    
    def update_mask_opacity(self, value):
        self.paint_widget.set_mask_opacity(value)
        percentage = int((value / 255.0) * 100)
        self.opacity_label.setText(f"{percentage}%")
    
    def add_new_class(self):
        current_classes = self.class_combo.count()
        new_class_id = current_classes + 1
        
        # Choose color for new class
        color = QColorDialog.getColor(Qt.red, self, f"Choose color for Class {new_class_id}")
        if color.isValid():
            self.paint_widget.add_class_color(new_class_id, color)
            self.class_combo.addItem(f"Class {new_class_id}")
    
    def change_class_color(self):
        current_class = self.class_combo.currentIndex() + 1
        color = QColorDialog.getColor(Qt.red, self, f"Choose color for Class {current_class}")
        if color.isValid():
            self.paint_widget.add_class_color(current_class, color)
    
    def clear_mask(self):
        reply = QMessageBox.question(
            self, "Clear Mask", "Are you sure you want to clear the entire mask?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.paint_widget.clear_mask()


def main():
    app = QApplication(sys.argv)
    window = SegmentationAnnotator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()