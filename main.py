import sys
import os

# Ensure the src directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Check if running as a PyInstaller bundle early
IS_FROZEN = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def resource_path_main(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller.
        Specific version for main.py before full app setup.
    """
    if IS_FROZEN:
        # Running in bundle
        base_path = sys._MEIPASS
        return os.path.join(base_path, relative_path)
    else:
        # Running in normal Python environment
        # Assume relative_path is relative to the project root where main.py is
        # or relative to src if main.py moves? Let's assume it's in root.
        # If main.py is in root, path like "src/assets/..." is correct.
        # If main.py is elsewhere, this needs adjustment. Assuming root for now.
        return os.path.join(os.path.dirname(__file__), relative_path) # More robust for dev


# --- Constants ---
APP_NAME = "ProxieWy"
APP_VERSION = "1.1.0"
DEVELOPER_NAME = "wyrtensi"
ORGANIZATION_NAME = "wyrtensi" # For QSettings
# Use relative paths for constants
MAIN_ICON_PATH_REL = "src/assets/images/icon.png"
DARK_THEME_PATH_REL = "src/assets/styles/dark.qss"
LIGHT_THEME_PATH_REL = "src/assets/styles/light.qss"

# Import necessary Qt modules after path setup
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings, QFile, QTextStream

# Import MainWindow after path setup
from src.gui.main_window import MainWindow

def load_stylesheet_main(theme_name: str) -> str:
    """Loads the stylesheet content for the given theme. (main.py version)"""
    default_theme_path = resource_path_main(DARK_THEME_PATH_REL)
    theme_file_path = resource_path_main(DARK_THEME_PATH_REL if theme_name == 'dark' else LIGHT_THEME_PATH_REL)

    path_to_use = theme_file_path
    if not QFile.exists(theme_file_path):
        print(f"Warning: Stylesheet not found at {theme_file_path}. Falling back.")
        if not QFile.exists(default_theme_path):
             print("Warning: Default dark stylesheet also not found.")
             return ""
        path_to_use = default_theme_path

    file = QFile(path_to_use)
    if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
        stream = QTextStream(file)
        stylesheet = stream.readAll()
        file.close()
        return stylesheet
    else:
        print(f"Warning: Could not open stylesheet file: {path_to_use}")
        return ""

def main():
    """Main function to initialize and run the application."""
    # Resolve main icon path early
    resolved_main_icon_path = resource_path_main(MAIN_ICON_PATH_REL)

    # Check if the main icon exists
    if not os.path.exists(resolved_main_icon_path):
        app_check = QApplication.instance()
        if app_check is None:
            app_check = QApplication(sys.argv)

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Initialization Error")
        msg_box.setText(f"Error: Main application icon not found.\nExpected at: {resolved_main_icon_path}\n(Based on relative path: {MAIN_ICON_PATH_REL})\n\nPlease ensure assets are correctly placed.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        sys.exit(1) # Exit if icon is missing

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setQuitOnLastWindowClosed(False) # Keep running in tray

    # Load and set the main application icon
    app_icon = QIcon(resolved_main_icon_path)
    if app_icon.isNull():
         print(f"Warning: Failed to load QIcon from {resolved_main_icon_path}")
         # Optionally show another warning or proceed without icon
    app.setWindowIcon(app_icon)

    # --- Load Initial Theme ---
    # Use QSettings with org/app names set
    settings = QSettings(ORGANIZATION_NAME, APP_NAME)
    current_theme = settings.value("ui/theme", defaultValue='dark', type=str)
    initial_stylesheet = load_stylesheet_main(current_theme)
    if initial_stylesheet:
        app.setStyleSheet(initial_stylesheet)
    else:
        print("Warning: No stylesheet loaded.")
    # ---

    # Create and show main window (let constructor handle showing/hiding)
    main_window = MainWindow()
    # main_window.show() # Let constructor/load_settings decide initial visibility

    sys.exit(app.exec())

if __name__ == "__main__":
    main() 