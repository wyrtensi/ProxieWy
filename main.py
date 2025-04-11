import sys
import os

# Ensure the src directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Add assets directory for easier path management
ASSETS_DIR = os.path.join(src_dir, 'assets')
IMAGES_DIR = os.path.join(ASSETS_DIR, 'images')
STYLES_DIR = os.path.join(ASSETS_DIR, 'styles') # Added styles dir path

from PySide6.QtWidgets import QApplication, QMessageBox # Added QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings, QFile, QTextStream # Added QFile, QTextStream

from src.gui.main_window import MainWindow

# --- Constants ---
APP_NAME = "ProxieWy"
APP_VERSION = "1.0.0"
DEVELOPER_NAME = "wyrtensi"
ORGANIZATION_NAME = "wyrtensi" # For QSettings
MAIN_ICON_PATH = os.path.join(IMAGES_DIR, "icon.png")
DARK_THEME_PATH = os.path.join(STYLES_DIR, "dark.qss")
LIGHT_THEME_PATH = os.path.join(STYLES_DIR, "light.qss")

def load_stylesheet(theme_name: str) -> str:
    """Loads the stylesheet content for the given theme."""
    default_theme = DARK_THEME_PATH
    path = DARK_THEME_PATH if theme_name == 'dark' else LIGHT_THEME_PATH

    if not os.path.exists(path):
        print(f"Warning: Stylesheet not found at {path}. Falling back.")
        if not os.path.exists(default_theme):
             print("Warning: Default dark stylesheet also not found.")
             return "" # No stylesheet found
        path = default_theme

    file = QFile(path)
    if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
        stream = QTextStream(file)
        stylesheet = stream.readAll()
        file.close()
        return stylesheet
    else:
        print(f"Warning: Could not open stylesheet file: {path}")
        return ""

def main():
    """Main function to initialize and run the application."""
    # Check if the main icon exists
    if not os.path.exists(MAIN_ICON_PATH):
        # Use QMessageBox for better user feedback
        app_check = QApplication.instance() # Get instance if exists
        if app_check is None:
            app_check = QApplication(sys.argv) # Or create one

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(f"Error: Main application icon not found at:\n{MAIN_ICON_PATH}\nPlease ensure 'icon.png' exists in the 'src/assets/images' folder.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        sys.exit(1) # Exit if icon is missing

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME) # Used by QSettings
    app.setQuitOnLastWindowClosed(False) # Keep running in tray

    # Load and set the main application icon
    app_icon = QIcon(MAIN_ICON_PATH)
    app.setWindowIcon(app_icon)

    # --- Load Initial Theme ---
    settings = QSettings()
    current_theme = settings.value("ui/theme", defaultValue='dark', type=str)
    initial_stylesheet = load_stylesheet(current_theme)
    if initial_stylesheet:
        app.setStyleSheet(initial_stylesheet)
    # ---

    main_window = MainWindow()
    # main_window.show() # Don't show initially, let tray handle it or show based on settings

    # Instead of main_window.show(), let's just ensure the tray icon is visible
    # The user can click the tray icon to show the window the first time.
    # Or, load a setting later to decide whether to show on startup.

    sys.exit(app.exec())

if __name__ == "__main__":
    main() 