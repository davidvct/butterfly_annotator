import sys
import os
import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from segmentation_app.ui.main_window import SegmentationAnnotator

APP_VERSION = "2.0.0"

def get_release_date():
    if getattr(sys, 'frozen', False):
        mtime = os.path.getmtime(sys.executable)
    else:
        mtime = os.path.getmtime(os.path.abspath(__file__))
    return datetime.datetime.fromtimestamp(mtime).strftime('%Y-%b-%d')

def main():
    app = QApplication(sys.argv)

    icon_path = os.path.join(
        os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
        else os.path.dirname(os.path.abspath(__file__)),
        'butterfly.jpg'
    )
    app.setWindowIcon(QIcon(icon_path))

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
