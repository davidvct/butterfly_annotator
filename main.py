import sys
import os
import datetime
import ctypes
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap
from segmentation_app.ui.main_window import SegmentationAnnotator

APP_VERSION = "2.0.0"

def get_release_date():
    if getattr(sys, 'frozen', False):
        mtime = os.path.getmtime(sys.executable)
    else:
        mtime = os.path.getmtime(os.path.abspath(__file__))
    return datetime.datetime.fromtimestamp(mtime).strftime('%Y-%b-%d')

def main():
    # Set AppUserModelID so Windows taskbar shows our icon instead of Python's
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ButterflyAnnotator')

    app = QApplication(sys.argv)

    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        data_dir = sys._MEIPASS  # PyInstaller 6.x puts datas in _internal/
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = app_dir

    # Build icon from ico (best for Windows) with jpg fallback
    icon = QIcon()
    ico_path = os.path.join(data_dir, 'butterfly.ico')
    jpg_path = os.path.join(data_dir, 'butterfly.jpg')
    if os.path.exists(ico_path):
        icon = QIcon(ico_path)
    elif os.path.exists(jpg_path):
        icon = QIcon(QPixmap(jpg_path))
    app.setWindowIcon(icon)

    release_date = get_release_date()
    session_file = os.path.join(app_dir, 'session.json')

    window = SegmentationAnnotator(
        version=APP_VERSION,
        release_date=release_date,
        default_session_file=session_file
    )
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
