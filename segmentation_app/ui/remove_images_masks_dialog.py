import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFileDialog, QLineEdit, QCheckBox,
                               QMessageBox)
from PySide6.QtCore import Qt

class RemoveImagesMasksDialog(QDialog):
    def __init__(self, img_path="", mask_path="", words="", case_sensitive=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Images/Masks")
        self.setMinimumWidth(500)
        self.default_img_path = img_path
        self.default_mask_path = mask_path
        self.default_words = words
        self.default_case_sensitive = case_sensitive
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Image Path
        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Image Path:"))
        self.img_path_input = QLineEdit(self.default_img_path)
        self.img_path_input.setPlaceholderText("Leave empty to ignore")
        img_layout.addWidget(self.img_path_input)
        img_btn = QPushButton("Browse")
        img_btn.clicked.connect(self.browse_image_path)
        img_layout.addWidget(img_btn)
        layout.addLayout(img_layout)

        # Mask Path
        mask_layout = QHBoxLayout()
        mask_layout.addWidget(QLabel("Mask Path:"))
        self.mask_path_input = QLineEdit(self.default_mask_path)
        self.mask_path_input.setPlaceholderText("Leave empty to ignore")
        mask_layout.addWidget(self.mask_path_input)
        mask_btn = QPushButton("Browse")
        mask_btn.clicked.connect(self.browse_mask_path)
        mask_layout.addWidget(mask_btn)
        layout.addLayout(mask_layout)

        # Words
        words_layout = QHBoxLayout()
        words_layout.addWidget(QLabel("Words in filename (comma-separated):"))
        self.words_input = QLineEdit(self.default_words)
        self.words_input.setPlaceholderText("e.g. vflip, R180")
        words_layout.addWidget(self.words_input)
        layout.addLayout(words_layout)

        # Options
        self.case_sensitive_cb = QCheckBox("Case sensitive")
        self.case_sensitive_cb.setChecked(self.default_case_sensitive)
        layout.addWidget(self.case_sensitive_cb)

        # Button
        self.delete_btn = QPushButton("Delete Images and Masks")
        self.delete_btn.setStyleSheet("QPushButton { background-color: #ffcccc; color: #cc0000; font-weight: bold; }")
        self.delete_btn.clicked.connect(self.delete_files)
        layout.addWidget(self.delete_btn)

    def browse_image_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Path")
        if folder:
            self.img_path_input.setText(folder)

    def browse_mask_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Mask Path")
        if folder:
            self.mask_path_input.setText(folder)

    def delete_files(self):
        img_folder = self.img_path_input.text().strip()
        mask_folder = self.mask_path_input.text().strip()
        words_str = self.words_input.text().strip()
        case_sensitive = self.case_sensitive_cb.isChecked()

        if not img_folder and not mask_folder:
            QMessageBox.warning(self, "Error", "Please specify at least one path (Image or Mask).")
            return

        if not words_str:
            QMessageBox.warning(self, "Error", "Please specify words to match in filenames.")
            return

        words = [w.strip() for w in words_str.split(',') if w.strip()]
        if not words:
            QMessageBox.warning(self, "Error", "Please specify valid words.")
            return

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete files containing these words: {', '.join(words)}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        deleted_imgs = 0
        deleted_masks = 0

        if img_folder and os.path.isdir(img_folder):
            deleted_imgs = self._remove_files_in_folder(img_folder, words, case_sensitive)
        
        if mask_folder and os.path.isdir(mask_folder):
            deleted_masks = self._remove_files_in_folder(mask_folder, words, case_sensitive)

        if deleted_imgs == 0 and deleted_masks == 0:
            QMessageBox.information(self, "Result", "No files found matching the criteria.")
        else:
            QMessageBox.information(self, "Deletion Complete",
                                    f"Deleted {deleted_imgs} image files.\nDeleted {deleted_masks} mask files.")
            self.accept()

    def _remove_files_in_folder(self, folder, words, case_sensitive):
        deleted_count = 0
        try:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if not os.path.isfile(file_path):
                    continue
                
                name_to_check = filename if case_sensitive else filename.lower()
                words_to_check = words if case_sensitive else [w.lower() for w in words]

                for word in words_to_check:
                    if word in name_to_check:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting file {file_path}: {e}")
                        break
        except Exception as e:
            print(f"Error accessing folder {folder}: {e}")
        
        return deleted_count
