from PySide6.QtGui import QColor

DEFAULT_CLASS_COLORS = {
    0: QColor(0, 0, 0, 0),  # Background (transparent)
    1: QColor(255, 0, 0, 128),    # Class 1 (red)
    2: QColor(0, 255, 0, 128),    # Class 2 (green)
    3: QColor(0, 0, 255, 128),    # Class 3 (blue)
    4: QColor(255, 255, 0, 128),  # Class 4 (yellow)
    5: QColor(255, 0, 255, 128),  # Class 5 (magenta)
}
