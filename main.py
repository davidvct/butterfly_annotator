import sys
from PySide6.QtWidgets import QApplication
from segmentation_app.ui.main_window import SegmentationAnnotator

def main():
    app = QApplication(sys.argv)
    window = SegmentationAnnotator()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
