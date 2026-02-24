import sys
import os
import datetime
from PySide6.QtWidgets import QApplication
from segmentation_app.ui.main_window import SegmentationAnnotator

APP_VERSION = "1.0.1"

def get_release_date():
    if getattr(sys, 'frozen', False):
        mtime = os.path.getmtime(sys.executable)
    else:
        mtime = os.path.getmtime(os.path.abspath(__file__))
    return datetime.datetime.fromtimestamp(mtime).strftime('%Y-%b-%d')

def main():
    app = QApplication(sys.argv)
    
    release_date = get_release_date()
    
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        
    session_file = os.path.join(app_dir, 'session.json')
    
    window = SegmentationAnnotator(
        version=APP_VERSION, 
        release_date=release_date, 
        default_session_file=session_file
    )
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
