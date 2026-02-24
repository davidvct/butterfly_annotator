import os
import glob
import numpy as np
from PIL import Image

class DataManager:
    @staticmethod
    def get_image_list(folder):
        """Get list of images from a folder."""
        if not os.path.exists(folder):
            return []
            
        image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff', '*.gif', '*.webp']
        image_list = []
        for ext in image_extensions:
            image_list.extend(glob.glob(os.path.join(folder, ext)))
            image_list.extend(glob.glob(os.path.join(folder, ext.upper())))
            
        return sorted(list(set(image_list)))
        
    @staticmethod
    def save_rgb_mask(mask, mask_path, class_color_mapping):
        """Save a class ID mask as an RGB image using the provided mapping."""
        try:
            height, width = mask.shape
            rgb_mask = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Apply colors to mask
            for class_id, (r, g, b) in class_color_mapping.items():
                mask_indices = mask == class_id
                rgb_mask[mask_indices] = [r, g, b]
            
            # Save mask as RGB PIL Image
            mask_image = Image.fromarray(rgb_mask, mode='RGB')
            mask_image.save(mask_path)
            return True, "Mask saved successfully"
        except Exception as e:
            return False, f"Failed to save mask: {e}"
