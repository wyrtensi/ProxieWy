import os
import sys # Needed for access to QApplication instance
import uuid # For generating unique proxy/rule IDs
import json # Make sure json is imported
import platform # Added import for platform-specific functionality
import winreg # Added import for Windows registry access
import ctypes # Added import for ctypes
from ctypes import wintypes # Added import for ctypes
import re
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QKeySequence, QShortcut # Added QPainter
from PySide6.QtCore import (Qt, QSize, QSettings, QByteArray, QFile, QTextStream, Signal, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QStandardPaths,
                           QRect, QPoint, QEvent) # Added QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QSizePolicy, QSystemTrayIcon, QMenu, QApplication,
    QComboBox, QSpacerItem, QScrollArea, QToolButton, QCheckBox, QFormLayout, QKeySequenceEdit, QInputDialog, QMessageBox, QLineEdit, QTextEdit # Added QLineEdit, QTextEdit
)
from PySide6.QtSvg import QSvgRenderer # Added QSvgRenderer
import subprocess # Add subprocess

# Import new widgets using relative paths
from .widgets.proxy_item_widget import ProxyItemWidget
from .widgets.proxy_edit_widget import ProxyEditWidget
from .widgets.rule_item_widget import RuleItemWidget # Added
from .widgets.rule_edit_widget import RuleEditWidget # Added

# Import Core components using relative paths
from ..core.proxy_engine import ProxyEngine # <<< Changed to relative import
# RuleMatcher will likely be used internally by the engine, but good to have the file

# Get base paths reliably
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # This is src/
ASSETS_DIR = os.path.join(script_dir, 'assets')
IMAGES_DIR = os.path.join(ASSETS_DIR, 'images')
ICONS_DIR = os.path.join(ASSETS_DIR, 'icons') # Added Icons Dir
STYLES_DIR = os.path.join(ASSETS_DIR, 'styles') # Added

# Icon Paths - Make sure these files exist in src/assets/images/
MAIN_ICON_PATH = os.path.join(IMAGES_DIR, "icon.png")
TRAY_ICON_INACTIVE_PATH = os.path.join(IMAGES_DIR, "icon_inactive.png")
TRAY_ICON_ACTIVE_PATH = os.path.join(IMAGES_DIR, "icon_active.png")
TRAY_ICON_ERROR_PATH = os.path.join(IMAGES_DIR, "icon_error.png")

# SVG Icon Paths
RULES_ICON_PATH = os.path.join(ICONS_DIR, "rules.svg")
PROXIES_ICON_PATH = os.path.join(ICONS_DIR, "proxies.svg")
SETTINGS_ICON_PATH = os.path.join(ICONS_DIR, "settings.svg")
ADD_ICON_PATH = os.path.join(ICONS_DIR, "plus.svg")
TOGGLE_OFF_ICON_PATH = os.path.join(ICONS_DIR, "toggle-left.svg") # e.g., Feather Icons
TOGGLE_ON_ICON_PATH = os.path.join(ICONS_DIR, "toggle-right.svg") # e.g., Feather Icons

# Stylesheet Paths
DARK_THEME_PATH = os.path.join(STYLES_DIR, "dark.qss")
LIGHT_THEME_PATH = os.path.join(STYLES_DIR, "light.qss")

# Helper function for creating SVG Buttons
def create_svg_button(size: int = 30, object_name: str = None) -> QPushButton:
    """Creates a QPushButton placeholder for SVG icons."""
    button = QPushButton()
    button.setFixedSize(size + 10, size + 10)
    button.setIconSize(QSize(size, size))
    button.setCheckable(True)
    if object_name:
        button.setObjectName(object_name)
    return button

# Helper function from main.py, duplicated here for use in apply_theme
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

def load_and_colorize_svg_content(icon_path: str, color: str) -> bytes:
    """Loads SVG content and sets the stroke color on the root SVG element, ensuring fill is none."""
    try:
        with open(icon_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()

        # Find the opening <svg> tag
        svg_tag_match = re.search(r'<svg\b[^>]*>', svg_content, re.IGNORECASE)
        if not svg_tag_match:
            print(f"Warning: Could not find <svg> tag in {icon_path}")
            return svg_content.encode('utf-8') # Return original content

        svg_tag_original = svg_tag_match.group(0)
        svg_tag_new = svg_tag_original

        # 1. Remove existing stroke attribute(s) if present
        svg_tag_new = re.sub(r'\s?stroke\s*=\s*["\'][^"\']+["\']', '', svg_tag_new, flags=re.IGNORECASE)

        # 2. Remove existing fill attribute(s) IF NOT "none"
        svg_tag_new = re.sub(r'\s?fill\s*=\s*["\'](?!none)[^"\']*["\']', '', svg_tag_new, flags=re.IGNORECASE)

        # 3. Add/Ensure fill="none"
        if 'fill="none"' not in svg_tag_new:
            svg_tag_new = svg_tag_new.replace('>', ' fill="none">', 1)

        # 4. Add the desired stroke attribute
        # Insert it right after '<svg '
        svg_tag_new = re.sub(r'<svg\b', rf'<svg stroke="{color}"', svg_tag_new, 1, re.IGNORECASE)

        # Replace the old tag with the new one in the content
        modified_content = svg_content.replace(svg_tag_original, svg_tag_new, 1)

        return modified_content.encode('utf-8')

    except FileNotFoundError:
        print(f"Error: Icon file not found at {icon_path}")
        return b"" # Return empty bytes on error
    except Exception as e:
        print(f"Error loading/colorizing SVG {icon_path}: {e}")
        return b"" # Return empty bytes on error

def create_icon_from_svg_data(svg_data: bytes) -> QIcon:
    """Creates QIcon from raw SVG data bytes using QSvgRenderer."""
    if not svg_data:
        return QIcon()

    renderer = QSvgRenderer(svg_data)
    if not renderer.isValid():
        print(f"Warning: Failed to create valid QSvgRenderer from SVG data.")
        return QIcon()

    # Get default size or set a fallback
    default_size = renderer.defaultSize()
    if default_size.isEmpty():
        default_size = QSize(32, 32) # Sensible fallback size

    # Create pixmap and render SVG onto it
    pixmap = QPixmap(default_size)
    pixmap.fill(Qt.GlobalColor.transparent) # Ensure background is transparent
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    if pixmap.isNull():
        print("Warning: Failed to render SVG to pixmap.")
        return QIcon()

    return QIcon(pixmap)

class MainWindow(QMainWindow):
    """Main application window."""

    NEW_DEFAULT_WIDTH = 550 # Define constant
    DEFAULT_HEIGHT = 800

    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("ProxieWy")
        # Set application details for QSettings
        QApplication.setOrganizationName("wyrtensi") # Example name
        QApplication.setApplicationName("ProxieWy")
        QApplication.setApplicationVersion("1.0.0") # Example version

        self.resize(self.NEW_DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        if os.path.exists(MAIN_ICON_PATH):
            self.setWindowIcon(QIcon(MAIN_ICON_PATH))

        # --- Define Settings File Path ---
        # Use standard config location
        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        self.settings_file = os.path.join(config_dir, "settings.ini")
        print(f"Using settings file: {self.settings_file}")
        # --- End Settings File Path ---

        # Data Stores (Initialize before load_settings)
        self.sidebar_buttons = []
        self.current_theme = 'dark'
        self.proxies = {}
        self.proxy_widgets = {}
        self.rules = {}
        self.rule_widgets = {}
        self.profiles = {"__default__": {"name": "Default"}} # Initialize with default
        self.active_profile_id = "__default__" # Default active
        self.engine_active_profile_id = "__default__" # Default engine active

        self.ALL_RULES_PROFILE_ID = "__all__"
        self.ALL_RULES_PROFILE_NAME = "All Rules (Default)"

        self.proxy_engine = ProxyEngine(self)
        self.proxy_editor_animation = None
        self.rule_editor_animation = None
        # Track close behavior
        self.close_behavior = "minimize" # Default
        self._force_quit = False # Flag for actual quit action

        self._create_widgets()
        self._create_layouts()
        self._create_connections()
        self._create_tray_icon()

        self._center_window()

        # Before calling load_settings
        self.active_profile_id = "__default__"
        self.engine_active_profile_id = "__default__"

        self.load_settings() # Load profiles, rules, proxies etc.
        print(f"[UI Init] Loaded {len(self.rules)} rules from settings.")
        self._update_profile_selectors() # Populate selectors

        # Set the initial state of the toggle button based on loaded setting *before* potentially starting engine
        self._update_toggle_button_state("inactive") # Assume inactive initially
        # Ensure start_engine_checkbox is available before accessing it
        if hasattr(self, 'start_engine_checkbox'):
            start_checked = self.start_engine_checkbox.isChecked()
            print(f"[UI Init] Engine auto-start setting: {start_checked}")
            # Set button state *without* triggering toggle signal yet
            self.toggle_proxy_button.blockSignals(True)
            self.toggle_proxy_button.setChecked(start_checked)
            self.toggle_proxy_button.blockSignals(False)
            self._update_toggle_button_state("starting" if start_checked else "inactive") # Update visual icon/tooltip

            # If auto-start is enabled, *now* explicitly call the toggle handler
            if start_checked:
                print("[UI Init] Auto-starting engine...")
                # Use QTimer.singleShot to allow the event loop to process before starting
                QTimer.singleShot(100, lambda: self._handle_toggle_proxy(True))
            else:
                # Ensure engine internal state matches UI if not auto-starting
                self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.active_profile_id) # Ensure engine has initial config

        # Populate lists after potentially loading data
        self._populate_proxy_list()
        self._populate_rule_list()
        self._set_initial_active_view()

        # Windows Proxy Init (Moved after load_settings)
        if platform.system() == "Windows":
            import winreg
            import ctypes
            from ctypes import wintypes
            self.INTERNET_SETTINGS_KEY = r'Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings'
            self.INTERNET_OPTION_SETTINGS_CHANGED = 39
            self.INTERNET_OPTION_REFRESH = 37

            try:
                 self.InternetSetOptionW = ctypes.windll.Wininet.InternetSetOptionW
                 self.InternetSetOptionW.argtypes = [wintypes.HINTERNET, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
                 self.InternetSetOptionW.restype = wintypes.BOOL
                 print("[WinProxy] Successfully loaded InternetSetOptionW.")
            except AttributeError:
                 print("[WinProxy] Warning: wininet.dll or InternetSetOptionW not found. Cannot refresh system proxy settings automatically.")
                 self.InternetSetOptionW = None
        else:
            self.InternetSetOptionW = None

    def get_active_rules(self) -> dict:
        """
        Returns rules for the currently active engine profile,
        INCLUDING rules assigned to 'All' (profile_id=None).
        """
        target_profile_id = self.engine_active_profile_id
        print(f"[UI Rules] Getting rules for engine profile: '{target_profile_id}'")

        active_rules = {}
        # Always include rules with profile_id=None (Global/Default rules)
        for rule_id, rule_data in self.rules.items():
            if not rule_data.get("profile_id"): # Check if profile_id is None or empty
                active_rules[rule_id] = rule_data

        # If a specific profile is active (not None or __all__), add its rules
        if target_profile_id and target_profile_id != self.ALL_RULES_PROFILE_ID:
            print(f"[UI Rules] Additionally including rules specifically for profile '{target_profile_id}'.")
            for rule_id, rule_data in self.rules.items():
                if rule_data.get("profile_id") == target_profile_id:
                    # Avoid adding duplicates if already added as a global rule (though shouldn't happen with UUIDs)
                    if rule_id not in active_rules:
                        active_rules[rule_id] = rule_data
        # If target profile is __all__ or None, we already added all rules implicitly via the first loop if logic demands it
        # However, the first loop adding profile_id=None covers the 'global' aspect better.
        # Let's refine: If target is '__all__', just return everything.
        elif not target_profile_id or target_profile_id == self.ALL_RULES_PROFILE_ID:
             print(f"[UI Rules] Engine target profile is 'All', returning all rules.")
             return self.rules.copy() # Return a copy of all rules


        print(f"[UI Rules] Found {len(active_rules)} applicable rules (Globals + Profile Specific) for engine profile '{target_profile_id}'.")
        return active_rules

    def _create_widgets(self):
        """Create all the widgets for the main window."""
        # --- Left Sidebar (Navigation) ---
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(60) # Example width

        # Create SVG buttons
        self.nav_button_rules = create_svg_button(object_name="navButtonRules")
        self.nav_button_proxies = create_svg_button(object_name="navButtonProxies")
        self.nav_button_settings = create_svg_button(object_name="navButtonSettings")

        self.sidebar_buttons = [self.nav_button_rules, self.nav_button_proxies, self.nav_button_settings]
        self.nav_button_rules.setToolTip("Manage Domain Routing Rules")
        self.nav_button_proxies.setToolTip("Manage Proxy Servers")
        self.nav_button_settings.setToolTip("Application Settings")

        # --- Master Toggle Button (e.g., in sidebar or status bar) ---
        # Let's add it to the top of the sidebar for prominence
        self.toggle_proxy_button = QToolButton()
        self.toggle_proxy_button.setObjectName("ToggleProxyButton")
        self.toggle_proxy_button.setCheckable(True)
        self.toggle_proxy_button.setIconSize(QSize(32, 32)) # Larger icon
        self.toggle_proxy_button.setToolTip("Toggle Proxy Engine On/Off")
        # Set initial icon (off)
        if os.path.exists(TOGGLE_OFF_ICON_PATH):
            self.toggle_proxy_button.setIcon(QIcon(TOGGLE_OFF_ICON_PATH))
        else:
            self.toggle_proxy_button.setText("Off")

        # --- Main Content Area (Stacked Widget) ---
        self.main_content_area = QStackedWidget()
        self.main_content_area.setObjectName("MainContentArea")

        # --- Rules Page ---
        self.rules_page = QWidget()
        self.rules_page.setObjectName("RulesPage")
        rules_page_layout = QVBoxLayout(self.rules_page)
        rules_page_layout.setContentsMargins(0, 0, 0, 0)
        rules_page_layout.setSpacing(0)

        # Top Bar (Add Rule Button)
        rules_top_bar = QHBoxLayout()
        rules_top_bar.setContentsMargins(15, 10, 15, 10)
        rules_top_bar.addWidget(QLabel("Profile:    ")) # Simplified label
        self.rule_profile_selector = QComboBox()
        self.rule_profile_selector.setObjectName("RuleProfileSelector")
        self.rule_profile_selector.setToolTip("Select profile to view/add rules") # Updated tooltip
        rules_top_bar.addWidget(self.rule_profile_selector) # Selector first
        self.rules_count_label = QLabel("(0 Rules)") # Label to show rule count
        self.rules_count_label.setObjectName("RuleCountLabel")
        rules_top_bar.addWidget(self.rules_count_label)
        rules_top_bar.addStretch()
        self.add_rule_button = QPushButton("Add Rule(s)")
        if os.path.exists(ADD_ICON_PATH):
            self.add_rule_button.setIcon(QIcon(ADD_ICON_PATH))
        self.add_rule_button.setObjectName("AddRuleButton")
        self.add_rule_button.clicked.connect(self._show_add_rule_editor)
        self.add_rule_button.setToolTip("Add new domain rule(s) to the selected profile")
        rules_top_bar.addWidget(self.add_rule_button)
        rules_page_layout.addLayout(rules_top_bar)

        # ADD RULE FILTER BAR
        self.rule_filter_bar = self._create_filter_bar("Filter rules (domain, proxy, profile)...", self._filter_rule_list)
        rules_page_layout.addWidget(self.rule_filter_bar)

        # Rule Editor
        self.rule_edit_widget = RuleEditWidget(self, self.proxies, self.profiles)
        self.rule_edit_widget.setVisible(False)
        self.rule_edit_widget.setFixedHeight(0) # Start with zero height for animation
        self.rule_edit_widget.save_rules.connect(self._save_rule_entry)
        self.rule_edit_widget.cancelled.connect(self._cancel_rule_edit)
        rules_page_layout.addWidget(self.rule_edit_widget)

        # Rule List Area (Scrollable)
        self.rule_scroll_area = QScrollArea()
        self.rule_scroll_area.setObjectName("RuleScrollArea")
        self.rule_scroll_area.setWidgetResizable(True)
        self.rule_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rule_scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.rule_list_container = QWidget()
        self.rule_list_layout = QVBoxLayout(self.rule_list_container)
        self.rule_list_layout.setContentsMargins(15, 5, 15, 15)
        self.rule_list_layout.setSpacing(8)
        self.rule_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.rule_scroll_area.setWidget(self.rule_list_container)
        rules_page_layout.addWidget(self.rule_scroll_area, stretch=1)

        # --- Proxies Page (Layout unchanged from previous step) ---
        self.proxies_page = QWidget()
        self.proxies_page.setObjectName("ProxiesPage")
        proxies_page_layout = QVBoxLayout(self.proxies_page)
        proxies_page_layout.setContentsMargins(0, 0, 0, 0)
        proxies_page_layout.setSpacing(0)
        # Top Bar
        proxies_top_bar = QHBoxLayout()
        proxies_top_bar.setContentsMargins(15, 10, 15, 10)
        proxies_top_bar.addWidget(QLabel("Managed Proxies   "))
        self.proxies_count_label = QLabel("(0 Proxies)") # Label to show proxy count
        self.proxies_count_label.setObjectName("ProxyCountLabel")
        proxies_top_bar.addWidget(self.proxies_count_label)
        proxies_top_bar.addStretch()
        self.add_proxy_button = QPushButton("Add Proxy")
        if os.path.exists(ADD_ICON_PATH):
            self.add_proxy_button.setIcon(QIcon(ADD_ICON_PATH))
        self.add_proxy_button.setObjectName("AddProxyButton")
        self.add_proxy_button.clicked.connect(self._show_add_proxy_editor)
        self.add_proxy_button.setToolTip("Add a new proxy server configuration")
        proxies_top_bar.addWidget(self.add_proxy_button)
        proxies_page_layout.addLayout(proxies_top_bar)

        # <<< MOVE PROXY FILTER BAR HERE >>>
        self.proxy_filter_bar = self._create_filter_bar("Filter proxies (name, address, type)...", self._filter_proxy_list)
        proxies_page_layout.addWidget(self.proxy_filter_bar) # Add filter bar below top bar

        # Proxy Editor
        self.proxy_edit_widget = ProxyEditWidget(self) # Pass main window ref
        self.proxy_edit_widget.setVisible(False)
        self.proxy_edit_widget.setFixedHeight(0) # Start with zero height for animation
        self.proxy_edit_widget.save_proxy.connect(self._save_proxy_entry)
        self.proxy_edit_widget.cancelled.connect(self._cancel_proxy_edit)
        proxies_page_layout.addWidget(self.proxy_edit_widget)
        # Proxy List
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("ProxyScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.proxy_list_container = QWidget()
        self.proxy_list_layout = QVBoxLayout(self.proxy_list_container)
        self.proxy_list_layout.setContentsMargins(15, 5, 15, 15)
        self.proxy_list_layout.setSpacing(8)
        self.proxy_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Keep AlignTop
        self.scroll_area.setWidget(self.proxy_list_container)
        proxies_page_layout.addWidget(self.scroll_area, stretch=1)

        # <<< REMOVE PROXY FILTER BAR FROM HERE >>>
        # self.proxy_filter_bar = self._create_filter_bar("Filter proxies (name, address, type)...", self._filter_proxy_list)
        # proxies_page_layout.addWidget(self.proxy_filter_bar)

        # --- Settings Page (Layout unchanged) ---
        self.settings_page = QWidget()
        self.settings_page.setObjectName("SettingsPage")
        settings_layout = QVBoxLayout(self.settings_page)
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter) # Align top-center

        # Create a container widget for settings content to control width
        settings_content_widget = QWidget()
        settings_content_layout = QVBoxLayout(settings_content_widget)
        settings_content_layout.setContentsMargins(15, 15, 15, 15) # Padding inside the content
        settings_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Optional: Limit the width of the settings content
        settings_content_widget.setMaximumWidth(450) # Example max width

        # Theme Switcher
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("ThemeComboBox")
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setToolTip("Select the application theme")
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        settings_content_layout.addLayout(theme_layout)
        settings_content_layout.addSpacing(15)

        # Close Button Behavior
        self.close_to_tray_checkbox = QCheckBox("Minimize to tray on close (instead of exiting)")
        self.close_to_tray_checkbox.setObjectName("CloseToTrayCheckbox")
        self.close_to_tray_checkbox.setToolTip("If unchecked, closing the window will exit the application.")
        settings_content_layout.addWidget(self.close_to_tray_checkbox)
        # Removed default checked state, load_settings handles it

        # Engine Startup Setting
        self.start_engine_checkbox = QCheckBox("Enable proxy engine on application startup")
        self.start_engine_checkbox.setObjectName("StartEngineCheckbox")
        settings_content_layout.addWidget(self.start_engine_checkbox)
        settings_content_layout.addSpacing(20)

        # Profile Management Section
        profile_label = QLabel("Profiles:")
        profile_label.setObjectName("SettingsHeaderLabel")
        settings_content_layout.addWidget(profile_label)
        profile_management_layout = QHBoxLayout()
        self.profile_list_widget = QComboBox()
        self.profile_list_widget.setObjectName("ProfileListCombo")
        self.profile_list_widget.setToolTip("Select profile to manage")
        self.add_profile_button = QPushButton("Add")
        self.add_profile_button.setObjectName("AddProfileButton")
        self.add_profile_button.setToolTip("Add a new profile")
        self.rename_profile_button = QPushButton("Rename")
        self.rename_profile_button.setObjectName("RenameProfileButton")
        self.rename_profile_button.setToolTip("Rename selected profile")
        self.delete_profile_button = QPushButton("Delete")
        self.delete_profile_button.setObjectName("DeleteProfileButton")
        self.delete_profile_button.setToolTip("Delete selected profile")
        profile_management_layout.addWidget(self.profile_list_widget, stretch=1)
        profile_management_layout.addWidget(self.add_profile_button)
        profile_management_layout.addWidget(self.rename_profile_button)
        profile_management_layout.addWidget(self.delete_profile_button)
        settings_content_layout.addLayout(profile_management_layout)
        settings_content_layout.addSpacing(20)


        # Hotkey Settings
        hotkey_label = QLabel("Global Hotkeys (Requires Restart):")
        hotkey_label.setObjectName("SettingsHeaderLabel")
        hotkey_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        settings_content_layout.addWidget(hotkey_label)
        hotkey_form_layout = QFormLayout()
        hotkey_form_layout.setContentsMargins(10, 5, 10, 5) # Indent form
        hotkey_form_layout.setSpacing(8)
        hotkey_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.toggle_hotkey_edit = QKeySequenceEdit()
        self.toggle_hotkey_edit.setObjectName("ToggleHotkeyEdit")
        self.toggle_hotkey_edit.setToolTip("Set global hotkey to toggle the proxy engine on/off")
        toggle_hotkey_clear_btn = QToolButton()
        toggle_hotkey_clear_btn.setText("Clear") # Or use an icon
        toggle_hotkey_clear_btn.setObjectName("ClearHotkeyButton")
        toggle_hotkey_clear_btn.setToolTip("Clear Toggle Proxy hotkey")
        toggle_hotkey_clear_btn.clicked.connect(lambda: self._clear_hotkey(self.toggle_hotkey_edit))
        toggle_hotkey_layout = QHBoxLayout()
        toggle_hotkey_layout.setContentsMargins(0,0,0,0)
        toggle_hotkey_layout.addWidget(self.toggle_hotkey_edit, stretch=1)
        toggle_hotkey_layout.addWidget(toggle_hotkey_clear_btn)
        hotkey_form_layout.addRow("Toggle Proxy Engine:", toggle_hotkey_layout) # Add layout instead of just edit

        # Show/Hide Window Hotkey
        self.show_hide_hotkey_edit = QKeySequenceEdit()
        self.show_hide_hotkey_edit.setObjectName("ShowHideHotkeyEdit")
        self.show_hide_hotkey_edit.setToolTip("Set global hotkey to show/hide the application window")
        show_hide_hotkey_clear_btn = QToolButton()
        show_hide_hotkey_clear_btn.setText("Clear") # Or use an icon
        show_hide_hotkey_clear_btn.setObjectName("ClearHotkeyButton")
        show_hide_hotkey_clear_btn.setToolTip("Clear Show/Hide Window hotkey")
        show_hide_hotkey_clear_btn.clicked.connect(lambda: self._clear_hotkey(self.show_hide_hotkey_edit))
        show_hide_hotkey_layout = QHBoxLayout()
        show_hide_hotkey_layout.setContentsMargins(0,0,0,0)
        show_hide_hotkey_layout.addWidget(self.show_hide_hotkey_edit, stretch=1)
        show_hide_hotkey_layout.addWidget(show_hide_hotkey_clear_btn)
        hotkey_form_layout.addRow("Show/Hide Window:", show_hide_hotkey_layout) # Add layout

        # Add Next/Previous Profile Hotkeys
        self.next_profile_hotkey_edit = QKeySequenceEdit()
        self.next_profile_hotkey_edit.setObjectName("NextProfileHotkeyEdit")
        self.next_profile_hotkey_edit.setToolTip("Set global hotkey to switch to the next profile")
        next_profile_clear_btn = QToolButton(); next_profile_clear_btn.setText("Clear"); next_profile_clear_btn.setObjectName("ClearHotkeyButton")
        next_profile_clear_btn.setToolTip("Clear Next Profile hotkey")
        next_profile_clear_btn.clicked.connect(lambda: self._clear_hotkey(self.next_profile_hotkey_edit))
        next_profile_layout = QHBoxLayout(); next_profile_layout.setContentsMargins(0,0,0,0)
        next_profile_layout.addWidget(self.next_profile_hotkey_edit, stretch=1); next_profile_layout.addWidget(next_profile_clear_btn)
        hotkey_form_layout.addRow("Next Profile:", next_profile_layout) # Add layout

        self.prev_profile_hotkey_edit = QKeySequenceEdit()
        self.prev_profile_hotkey_edit.setObjectName("PrevProfileHotkeyEdit")
        self.prev_profile_hotkey_edit.setToolTip("Set global hotkey to switch to the previous profile")
        prev_profile_clear_btn = QToolButton(); prev_profile_clear_btn.setText("Clear"); prev_profile_clear_btn.setObjectName("ClearHotkeyButton")
        prev_profile_clear_btn.setToolTip("Clear Previous Profile hotkey")
        prev_profile_clear_btn.clicked.connect(lambda: self._clear_hotkey(self.prev_profile_hotkey_edit))
        prev_profile_layout = QHBoxLayout(); prev_profile_layout.setContentsMargins(0,0,0,0)
        prev_profile_layout.addWidget(self.prev_profile_hotkey_edit, stretch=1); prev_profile_layout.addWidget(prev_profile_clear_btn)
        hotkey_form_layout.addRow("Previous Profile:", prev_profile_layout) # Add layout

        settings_content_layout.addLayout(hotkey_form_layout)
        # Updated note
        hotkey_note = QLabel("<small><i>Note: Setting hotkeys here saves the preference. Actual global registration requires additional setup and platform-specific libraries (not currently implemented).</i></small>")
        hotkey_note.setWordWrap(True)
        settings_content_layout.addWidget(hotkey_note)
        settings_content_layout.addSpacing(20)

        # --- Add Action Buttons ---
        settings_content_layout.addStretch(1) # Push buttons towards bottom

        # Reset Settings Button
        self.reset_settings_button = QPushButton("Reset All Settings")
        self.reset_settings_button.setObjectName("ResetSettingsButton") # For specific styling (e.g., danger color)
        self.reset_settings_button.setToolTip("Resets all proxies, rules, profiles, and settings to default.")
        settings_content_layout.addWidget(self.reset_settings_button)

        settings_content_layout.addSpacing(15) # Space below buttons

        # Version Info
        app_version = QApplication.applicationVersion()
        developer_name = QApplication.organizationName()
        version_label = QLabel(f"Version: {app_version}\nDeveloper: {developer_name}")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignLeft) # Align left
        version_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        settings_content_layout.addWidget(version_label) # Add version info

        # Add the content widget to the main settings page layout
        settings_layout.addWidget(settings_content_widget)

        # --- Add Pages to Stack ---
        self.main_content_area.addWidget(self.rules_page)
        self.main_content_area.addWidget(self.proxies_page)
        self.main_content_area.addWidget(self.settings_page)

        # --- Status Bar ---
        # Use QMainWindow's built-in status bar
        self.status_bar_label = QLabel("Ready") # Use a label for more flexibility
        self.statusBar().addWidget(self.status_bar_label, stretch=1)
        self.statusBar().setObjectName("StatusBar")

        # --- Settings Page Widgets ---
        self.settings_page = QWidget()
        self.settings_page.setObjectName("SettingsPage")
        settings_layout = QVBoxLayout(self.settings_page)
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ... existing Theme, Close Behavior, Startup checkboxes ...

        # ... existing Hotkey Settings, Profile Management, Version Info ...

    def _create_layouts(self):
        """Create and arrange layouts."""
        # --- Central Widget & Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) # No margins for the main layout
        main_layout.setSpacing(0) # No spacing between sidebar and content

        # --- Sidebar Layout ---
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar_layout.setContentsMargins(5, 15, 5, 10) # Adjusted margins for toggle
        sidebar_layout.setSpacing(10)

        # Add Toggle Button at the top
        sidebar_layout.addWidget(self.toggle_proxy_button, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addSpacing(20) # Space below toggle

        # Add Navigation buttons
        sidebar_layout.addWidget(self.nav_button_rules, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.nav_button_proxies, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addStretch() # Push settings to bottom
        sidebar_layout.addWidget(self.nav_button_settings, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Add Sidebar and Content Area to Main Layout ---
        main_layout.addWidget(self.sidebar_frame)
        main_layout.addWidget(self.main_content_area, stretch=1) # Content area takes remaining space

        # No need for placeholder layout setup here anymore, stack handles it

    def _create_connections(self):
        """Connect signals and slots."""
        self.nav_button_rules.clicked.connect(lambda: self._handle_nav_click(0, self.nav_button_rules))
        self.nav_button_proxies.clicked.connect(lambda: self._handle_nav_click(1, self.nav_button_proxies))
        self.nav_button_settings.clicked.connect(lambda: self._handle_nav_click(2, self.nav_button_settings))

        # Connect theme switcher
        self.theme_combo.currentIndexChanged.connect(self._handle_theme_change)

        # Proxy Engine Toggle Button directly triggers the handler
        self.toggle_proxy_button.toggled.connect(self._handle_toggle_proxy)

        # Engine signals update UI status *only*
        self.proxy_engine.status_changed.connect(self._handle_engine_status_update_ui) # Renamed target slot
        self.proxy_engine.error_occurred.connect(self._handle_engine_error)
        self.proxy_engine.proxy_test_result.connect(self._handle_proxy_test_result)

        # Settings checkboxes save on change
        self.close_to_tray_checkbox.stateChanged.connect(self.save_settings)
        self.start_engine_checkbox.stateChanged.connect(self.save_settings)

        # Hotkey edits save on finish
        # ... (hotkey connections) ...

        # Profiles
        # ... (profile connections) ...

        # Connect Rule Profile Selector (View Selector)
        self.rule_profile_selector.currentIndexChanged.connect(self._handle_active_profile_change)

        # Connect Profile Management Buttons (Settings Page)
        self.add_profile_button.clicked.connect(self._add_profile)
        self.rename_profile_button.clicked.connect(self._rename_profile)
        self.delete_profile_button.clicked.connect(self._delete_profile)
        # Connect selection changes in the settings profile list to update button states
        self.profile_list_widget.currentIndexChanged.connect(self._update_profile_button_states)

        # --- Connect New Settings Buttons ---
        self.reset_settings_button.clicked.connect(self._reset_all_settings)
        # --- End Connect Buttons ---

    def _handle_nav_click(self, index: int, clicked_button: QPushButton):
        """Handles clicks on navigation buttons."""
        # Cancel any ongoing edits (use animation=False for instant close)
        self._cancel_proxy_edit(animate=False)
        self._cancel_rule_edit(animate=False)

        self.main_content_area.setCurrentIndex(index)
        self._update_active_button_style(clicked_button)

    def _update_active_button_style(self, active_button: QPushButton):
        """ Visually marks the active navigation button. """
        for button in self.sidebar_buttons:
            # Check if it's the active one and ensure it's checked
            is_active = (button == active_button)
            button.setChecked(is_active)
            # Optionally, apply a distinct style to the active button if needed,
            # beyond the default :checked state provided by QSS.
            # Example: button.setProperty("isActive", is_active)
            # Then use QSS like: QPushButton[isActive="true"] { ... }
            # For now, relying on :checked pseudo-state in QSS.

    def _handle_theme_change(self, index: int):
        """Applies the selected theme."""
        theme_name = 'dark' if index == 0 else 'light'
        if theme_name != self.current_theme:
            self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str):
        """Loads QSS, updates internal theme name, and recolors icons."""
        stylesheet = load_stylesheet(theme_name)
        if stylesheet:
            QApplication.instance().setStyleSheet(stylesheet)
            self.current_theme = theme_name
            print(f"Applied {theme_name} theme.")

            # --- Recolor all theme-dependent elements ---
            self._apply_theme_colors()

            # Notify child widgets that might need recoloring
            for widget in self.proxy_widgets.values():
                if hasattr(widget, 'set_theme'):
                    widget.set_theme(theme_name)
            for widget in self.rule_widgets.values():
                 if hasattr(widget, 'set_theme'):
                     widget.set_theme(theme_name)


    def _get_main_icon_color(self, element_type: str = "default", state: str = "default") -> str:
         """Gets icon colors specifically for MainWindow elements."""
         if self.current_theme == 'dark':
             # Sidebar nav buttons
             if element_type == "nav":
                 if state == "checked": return "#ffffff"
                 if state == "hover": return "#e0e0e0"
                 return "#ffffff"
             # Toggle button
             if element_type == "toggle":
                 if state == "checked_hover": return "#ffffff"
                 if state == "checked": return "#ffffff"
                 if state == "hover": return "#e0e0e0"
                 return "#ffffff"
             # Add/Clear buttons etc.
             return "#ffffff" # Default white
         else: # Light theme
             if element_type == "nav":
                 if state == "checked": return "#0056b3" # Darker blue
                 if state == "hover": return "#343a40" # Dark grey hover
                 return "#495057" # Dark grey default
             if element_type == "toggle":
                 if state == "checked_hover": return "#000000" # Black
                 if state == "checked": return "#1c1c1c" # Dark
                 if state == "hover": return "#343a40" # Dark grey hover
                 return "#495057" # Dark grey default
             # Add/Clear buttons etc.
             return "#495057" # Default dark grey

    def _apply_theme_colors(self):
         """(Re)apply colors to icons in the MainWindow itself."""
         print(f"Applying main window colors for theme: {self.current_theme}")

         # --- Sidebar Navigation Buttons ---
         nav_icon_color = self._get_main_icon_color("nav")
         rules_svg = load_and_colorize_svg_content(RULES_ICON_PATH, nav_icon_color)
         proxies_svg = load_and_colorize_svg_content(PROXIES_ICON_PATH, nav_icon_color)
         settings_svg = load_and_colorize_svg_content(SETTINGS_ICON_PATH, nav_icon_color)
         self.nav_button_rules.setIcon(create_icon_from_svg_data(rules_svg))
         self.nav_button_proxies.setIcon(create_icon_from_svg_data(proxies_svg))
         self.nav_button_settings.setIcon(create_icon_from_svg_data(settings_svg))
         # Note: Hover/Checked state icon changes need more complex handling
         # (e.g., custom paintEvent or swapping icons on state change signals)
         # For now, QSS background changes provide visual feedback.

         # --- Toggle Button ---
         # State needs to be checked to determine the correct icon
         is_checked = self.toggle_proxy_button.isChecked()
         toggle_state = "checked" if is_checked else "default"
         toggle_icon_color = self._get_main_icon_color("toggle", state=toggle_state)
         toggle_icon_path = TOGGLE_ON_ICON_PATH if is_checked else TOGGLE_OFF_ICON_PATH
         toggle_svg = load_and_colorize_svg_content(toggle_icon_path, toggle_icon_color)
         self.toggle_proxy_button.setIcon(create_icon_from_svg_data(toggle_svg))

         # --- Add Proxy/Rule Buttons (if they have icons) ---
         add_icon_color = self._get_main_icon_color("add_button")
         add_svg = load_and_colorize_svg_content(ADD_ICON_PATH, add_icon_color)
         add_icon = create_icon_from_svg_data(add_svg)
         if hasattr(self, 'add_rule_button'): self.add_rule_button.setIcon(add_icon)
         if hasattr(self, 'add_proxy_button'): self.add_proxy_button.setIcon(add_icon)

         # --- Other icons (e.g., filter bar) ---
         # if hasattr(self, 'filter_icon'): # Assuming filter_icon is a QLabel
         #    filter_svg = load_and_colorize_svg_content(SEARCH_ICON_PATH, self._get_main_icon_color())
         #    # Render to pixmap and set on label...


    def _update_toggle_button_state(self, status: str):
        """Updates the visual state AND ICON of the main toggle button."""
        is_active = (status == 'active')
        self.toggle_proxy_button.setChecked(is_active) # Set checked state first

        # Determine color and icon path based on NEW state
        toggle_state = "checked" if is_active else "default"
        toggle_icon_color = self._get_main_icon_color("toggle", state=toggle_state)
        toggle_icon_path = TOGGLE_ON_ICON_PATH if is_active else TOGGLE_OFF_ICON_PATH

        # Load and set the correctly colored icon
        toggle_svg = load_and_colorize_svg_content(toggle_icon_path, toggle_icon_color)
        self.toggle_proxy_button.setIcon(create_icon_from_svg_data(toggle_svg))

        tooltip = "Proxy Engine is ON" if is_active else "Proxy Engine is OFF"
        self.toggle_proxy_button.setToolTip(tooltip)

    def _create_tray_icon(self):
        """Create the system tray icon and its context menu."""
        # Check if required icons exist
        if not all(os.path.exists(p) for p in [TRAY_ICON_INACTIVE_PATH, TRAY_ICON_ACTIVE_PATH, TRAY_ICON_ERROR_PATH]):
             print(f"Warning: One or more tray icons not found in {IMAGES_DIR}. Tray functionality may be limited.")
             # Fallback: Use main icon if specific ones are missing
             self.icon_inactive = QIcon(MAIN_ICON_PATH)
             self.icon_active = QIcon(MAIN_ICON_PATH)
             self.icon_error = QIcon(MAIN_ICON_PATH)
        else:
            self.icon_inactive = QIcon(TRAY_ICON_INACTIVE_PATH)
            self.icon_active = QIcon(TRAY_ICON_ACTIVE_PATH)
            self.icon_error = QIcon(TRAY_ICON_ERROR_PATH)

        # Create Tray Icon Menu
        self.tray_menu = QMenu(self)
        show_action = QAction("Show Window", self)

        # --- Add Toggle Action ---
        self.toggle_engine_tray_action = QAction("Enable Engine", self)
        self.toggle_engine_tray_action.setCheckable(True)
        self.toggle_engine_tray_action.triggered.connect(self._handle_toggle_proxy) # Reuse existing handler
        # --- End Add Toggle Action ---

        quit_action = QAction("Exit", self)

        show_action.triggered.connect(self.toggle_visibility)
        quit_action.triggered.connect(self.quit_application)

        self.tray_menu.addAction(show_action)
        self.tray_menu.addSeparator()
        # --- Add Action to Menu ---
        self.tray_menu.addAction(self.toggle_engine_tray_action)
        self.tray_menu.addSeparator()
        # --- End Add Action to Menu ---
        self.tray_menu.addAction(quit_action)

        # Create Tray Icon
        self.tray_icon = QSystemTrayIcon(self.icon_inactive, self) # Start inactive
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.setToolTip("ProxieWy (Inactive)")

        # Connect activation signal (e.g., left-click)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        self.tray_icon.show()
        self.update_tray_status('inactive') # Set initial state

    def on_tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        # Show/Hide on left-click (Trigger)
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()
        # Context menu is handled automatically by setContextMenu

    def toggle_visibility(self):
        """Toggle the main window's visibility."""
        if self.isVisible():
            # Cancel any ongoing edits (use animation=False for instant close)
            self._cancel_proxy_edit(animate=False)
            self._cancel_rule_edit(animate=False)
            self.hide()
        else:
            # Restore geometry before showing
            settings = QSettings()
            geometry_bytes = settings.value("ui/window_geometry")
            if isinstance(geometry_bytes, QByteArray):
                 self.restoreGeometry(geometry_bytes)
            else:
                 self.resize(self.NEW_DEFAULT_WIDTH, self.DEFAULT_HEIGHT) # Use constants
                 self._center_window()
            self.showNormal() # Show and restore if minimized
            self.activateWindow() # Bring to front

    def update_tray_status(self, status: str):
        """Updates the tray icon and tooltip based on status."""
        tooltip_base = "ProxieWy"
        icon = self.icon_inactive # Default
        state_text = "Inactive"

        if status == 'active':
            icon = self.icon_active; state_text = "Active"
        elif status == 'error':
            icon = self.icon_error; state_text = "Error"
        elif status == 'starting':
            # Maybe use active icon while starting? Or a specific one?
            icon = self.icon_active; state_text = "Starting..."
        elif status == 'stopping':
            # Maybe use inactive icon while stopping?
            icon = self.icon_inactive; state_text = "Stopping..."
        # else: # inactive state uses defaults

        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(f"{tooltip_base} ({state_text})")
        # Status bar text handled separately

    def _center_window(self):
        """Center the window on the screen. (Use only if no geometry saved)."""
        screen = QApplication.primaryScreen().geometry()
        # Use the current frame geometry (which might be default or set by resize)
        frame_geo = self.frameGeometry()
        x = (screen.width() - frame_geo.width()) // 2
        y = (screen.height() - frame_geo.height()) // 2
        self.move(x, y)

    def load_settings(self):
        # Use the defined settings_file path
        settings = QSettings(self.settings_file, QSettings.Format.IniFormat)
        print(f"[Settings] Loading from: {self.settings_file}")

        # --- Load Theme Preference FIRST ---
        loaded_theme_name = settings.value("ui/theme", defaultValue="dark", type=str)
        # ---

        # Load Geometry
        geometry_bytes = settings.value("ui/window_geometry")
        if isinstance(geometry_bytes, QByteArray):
             self.restoreGeometry(geometry_bytes)
        else:
             self.resize(self.NEW_DEFAULT_WIDTH, self.DEFAULT_HEIGHT) # Fallback size
             self._center_window()

        # Load Close Behavior
        self.close_behavior = settings.value("app/close_behavior", defaultValue="minimize", type=str)
        self.close_to_tray_checkbox.blockSignals(True) # <<< Block signals
        self.close_to_tray_checkbox.setChecked(self.close_behavior == "minimize")
        self.close_to_tray_checkbox.blockSignals(False) # <<< Unblock signals

        # Load Last View
        last_index = settings.value("ui/last_view_index", defaultValue=0, type=int)
        # We'll apply this in _set_initial_active_view after widgets are ready

        # Load Profiles
        profiles_json = settings.value("profiles/list", defaultValue="{}", type=str)
        try:
            loaded_profiles = json.loads(profiles_json)
            if isinstance(loaded_profiles, dict):
                 self.profiles = loaded_profiles
                 print(f"[Settings] Loaded {len(self.profiles)} profiles.")
            else:
                 print("[Settings] Warning: Invalid format for profiles in settings, resetting.")
                 self.profiles = {"__default__": {"name": "Default"}}
        except json.JSONDecodeError:
            print("[Settings] Warning: Failed to decode profiles JSON, resetting.")
            self.profiles = {"__default__": {"name": "Default"}}
        if "__default__" not in self.profiles:
             self.profiles["__default__"] = {"name": "Default"}


        # Load Active Profile ID
        self.active_profile_id = settings.value("profiles/active_id", defaultValue="__default__", type=str)
        if self.active_profile_id not in self.profiles:
             print(f"[Settings] Warning: Active profile ID '{self.active_profile_id}' not found, reverting to default.")
             self.active_profile_id = "__default__"
        print(f"[Settings] Loaded active profile ID: {self.active_profile_id}")


        # Load Proxies
        proxies_json = settings.value("proxies/list", defaultValue="{}", type=str)
        try:
             loaded_proxies = json.loads(proxies_json)
             if isinstance(loaded_proxies, dict):
                  self.proxies = loaded_proxies
                  print(f"[Settings] Loaded {len(self.proxies)} proxies.")
             else:
                  print("[Settings] Warning: Invalid format for proxies in settings, resetting.")
                  self.proxies = {}
        except json.JSONDecodeError:
             print("[Settings] Warning: Failed to decode proxies JSON, resetting.")
             self.proxies = {}


        # Load Rules
        rules_json = settings.value("rules/list", defaultValue="{}", type=str)
        try:
            loaded_rules = json.loads(rules_json)
            if isinstance(loaded_rules, dict):
                 self.rules = loaded_rules
                 print(f"[Settings] Loaded {len(self.rules)} rules.")
            else:
                 print("[Settings] Warning: Invalid format for rules in settings, resetting.")
                 self.rules = {}
        except json.JSONDecodeError:
            print("[Settings] Warning: Failed to decode rules JSON, resetting.")
            self.rules = {}

        # Load Hotkey Settings Preferences
        toggle_seq_str = settings.value("hotkeys/toggle_proxy", defaultValue="", type=str)
        show_hide_seq_str = settings.value("hotkeys/show_hide_window", defaultValue="", type=str)
        next_prof_seq_str = settings.value("hotkeys/next_profile", defaultValue="", type=str) # Load new hotkey
        prev_prof_seq_str = settings.value("hotkeys/prev_profile", defaultValue="", type=str) # Load new hotkey

        self.toggle_hotkey_edit.setKeySequence(QKeySequence.fromString(toggle_seq_str))
        self.show_hide_hotkey_edit.setKeySequence(QKeySequence.fromString(show_hide_seq_str))
        self.next_profile_hotkey_edit.setKeySequence(QKeySequence.fromString(next_prof_seq_str)) # Set sequence
        self.prev_profile_hotkey_edit.setKeySequence(QKeySequence.fromString(prev_prof_seq_str)) # Set sequence

        # Load Startup Setting
        start_on_startup = settings.value("app/start_engine_on_startup", defaultValue=False, type=bool)
        self.start_engine_checkbox.blockSignals(True) # <<< Block signals
        self.start_engine_checkbox.setChecked(start_on_startup)
        self.start_engine_checkbox.blockSignals(False) # <<< Unblock signals

        settings.endGroup()

        # --- Apply Theme AFTER loading other data ---
        self.apply_theme(loaded_theme_name)
        theme_index = 0 if self.current_theme == "dark" else 1
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index)
        self.theme_combo.blockSignals(False)
        # ---

    def save_settings(self):
        # Use the defined settings_file path
        settings = QSettings(self.settings_file, QSettings.Format.IniFormat)
        print(f"[Settings] Saving to: {self.settings_file}")

        # Save Geometry
        settings.setValue("ui/window_geometry", self.saveGeometry())

        # Save Theme
        settings.setValue("ui/theme", self.current_theme)

        # Save Close Behavior
        self.close_behavior = "minimize" if self.close_to_tray_checkbox.isChecked() else "exit"
        settings.setValue("app/close_behavior", self.close_behavior)

        # Save Last View
        settings.setValue("ui/last_view_index", self.main_content_area.currentIndex())

        # Save Profiles
        profiles_json = json.dumps(self.profiles, indent=4)
        settings.setValue("profiles/list", profiles_json)
        print(f"[Settings] Saved {len(self.profiles)} profiles.")

        # Save Active Profile ID (make sure it's valid before saving)
        if self.active_profile_id in self.profiles:
            settings.setValue("profiles/active_id", self.active_profile_id)
            print(f"[Settings] Saved active profile ID: {self.active_profile_id}")
        else:
            settings.setValue("profiles/active_id", "__default__") # Fallback save
            print(f"[Settings] Warning: Active profile ID '{self.active_profile_id}' invalid, saving default.")


        # Save Proxies
        proxies_json = json.dumps(self.proxies, indent=4)
        settings.setValue("proxies/list", proxies_json)
        print(f"[Settings] Saved {len(self.proxies)} proxies.")

        # Save Rules
        rules_json = json.dumps(self.rules, indent=4)
        settings.setValue("rules/list", rules_json)
        print(f"[Settings] Saved {len(self.rules)} rules.")

        # Save Hotkeys
        settings.setValue("hotkeys/toggle_proxy", self.toggle_hotkey_edit.keySequence().toString())
        settings.setValue("hotkeys/show_hide_window", self.show_hide_hotkey_edit.keySequence().toString())
        settings.setValue("hotkeys/next_profile", self.next_profile_hotkey_edit.keySequence().toString()) # Save new hotkey
        settings.setValue("hotkeys/prev_profile", self.prev_profile_hotkey_edit.keySequence().toString()) # Save new hotkey

        # Save Startup Setting
        settings.setValue("app/start_engine_on_startup", self.start_engine_checkbox.isChecked())

        settings.sync() # Force writing to file
        print("[Settings] Sync complete.")

    def quit_application(self):
        """Save settings and quit the application."""
        self.save_settings()
        print("Quit requested. Stopping engine...")
        self.proxy_engine.stop() # Ensure engine is stopped cleanly
        print("Exiting.")
        QApplication.instance().quit()

    def _set_initial_active_view(self):
        """Sets the active view based on loaded settings or default."""
        settings = QSettings()
        last_index = settings.value("ui/last_view_index", defaultValue=0, type=int)
        # Ensure index is valid
        last_index = max(0, min(last_index, self.main_content_area.count() - 1))

        if 0 <= last_index < len(self.sidebar_buttons):
            self.main_content_area.setCurrentIndex(last_index)
            button_to_activate = self.sidebar_buttons[last_index]
            button_to_activate.setChecked(True)
            self._update_active_button_style(button_to_activate)
        elif self.sidebar_buttons: # Fallback to first button if index invalid
             self.main_content_area.setCurrentIndex(0)
             self.sidebar_buttons[0].setChecked(True)
             self._update_active_button_style(self.sidebar_buttons[0])

    def _get_proxy_name_map(self) -> dict:
        """Helper to get a map of {proxy_id: proxy_name}."""
        return {pid: pdata.get('name', 'Unnamed') for pid, pdata in self.proxies.items()}

    def _get_profile_name_map(self) -> dict:
        """Helper to get {profile_id: profile_name} including the conceptual 'All'."""
        # Start with existing profiles
        names = {pid: pdata.get('name', 'Unnamed') for pid, pdata in self.profiles.items()}
        # Add the conceptual "All" profile name mapping (using None as key internally)
        names[None] = self.ALL_RULES_PROFILE_NAME # Map None ID to the display name
        return names

    def _show_add_rule_editor(self):
        if self.proxy_edit_widget.isVisible(): self._cancel_proxy_edit(animate=False)

        # Ensure both proxy and profile lists are up-to-date
        print(f"[UI Add Rule] Updating rule editor. Proxies available: {len(self.proxies)}, Profiles available: {len(self.profiles)}") # Debug print
        print(f"[UI Add Rule] Profiles data: {self.profiles}") # Debug print profiles dict
        self.rule_edit_widget.update_proxies(self.proxies)
        self.rule_edit_widget.update_profiles(self.profiles) # Ensure this is called

        self.rule_edit_widget.clear_fields()
        # Pre-select the profile currently viewed in the list
        current_view_profile_id = self.rule_profile_selector.currentData()
        target_profile_id = None if current_view_profile_id == self.ALL_RULES_PROFILE_ID else current_view_profile_id
        profile_idx = self.rule_edit_widget.profile_combo.findData(target_profile_id)
        self.rule_edit_widget.profile_combo.setCurrentIndex(max(0, profile_idx))

        target_height = self._calculate_editor_height(self.rule_edit_widget)
        self.add_rule_button.setEnabled(False)
        self.rule_editor_animation = self._animate_widget_height(self.rule_edit_widget, 0, target_height)
        self.rule_editor_animation.finished.connect(self.rule_edit_widget.set_focus_on_domains)
        self.rule_editor_animation.start()

    def _show_edit_rule_editor(self, rule_id: str):
        """Shows the editor pre-filled for editing a rule's proxy with animation."""
        # If proxy editor is open, close it first
        if self.proxy_edit_widget.isVisible():
             self._cancel_proxy_edit(animate=False) # Close instantly

        if rule_id in self.rules:
             target_height = self.rule_edit_widget.sizeHint().height()
             if target_height <= 0: target_height = 250 # Fallback height

             self.rule_edit_widget.update_proxies(self.proxies)
             edit_data = { # Prepare data for editor
                 "ids": [rule_id],
                 "domain": self.rules[rule_id]["domain"],
                 "proxy_id": self.rules[rule_id]["proxy_id"]
             }
             self.rule_edit_widget.load_data(edit_data)
             self.add_rule_button.setEnabled(False)

             # Run animation
             self.rule_editor_animation = self._animate_widget_height(self.rule_edit_widget, 0, target_height)
             # Focus might not be desired when editing proxy only
             # self.rule_editor_animation.finished.connect(self.rule_edit_widget.set_focus_on_domains)
             self.rule_editor_animation.start() # Removed DeletionPolicy
        else:
            print(f"Error: Cannot edit rule with unknown ID: {rule_id}")

    def _cancel_rule_edit(self, animate=True):
        """Hides the rule editor without saving, optionally animating."""
        if not self.rule_edit_widget.isVisible():
            self.add_rule_button.setEnabled(True)
            return

        current_height = self.rule_edit_widget.height()

        # Stop previous animation if it exists and hasn't been cleared
        if self.rule_editor_animation:
             self.rule_editor_animation.stop()
             self.rule_editor_animation = None # Clear immediately after stopping

        if animate and current_height > 0:
            self.rule_editor_animation = self._animate_widget_height(self.rule_edit_widget, current_height, 0)
            self.rule_editor_animation.finished.connect(lambda: self.add_rule_button.setEnabled(True))
            self.rule_editor_animation.finished.connect(self.rule_edit_widget.clear_fields)
            # Clear reference *after* this animation finishes
            self.rule_editor_animation.finished.connect(self._clear_rule_animation_ref)
            self.rule_editor_animation.start() # Removed DeletionPolicy
        else:
            self.rule_edit_widget.setMaximumHeight(0)
            self.rule_edit_widget.setVisible(False)
            self.rule_edit_widget.clear_fields()
            self.add_rule_button.setEnabled(True)
            self.rule_editor_animation = None # Clear reference if hidden instantly

    def _clear_rule_animation_ref(self):
        """Clear the animation reference."""
        self.rule_editor_animation = None

    def _save_rule_entry(self, domains: list, proxy_id: str, profile_id: str):
        """
        Handles saving new rules or updating existing ones.
        If called in 'Add' mode (editing_id is None) and a domain
        already exists, it overwrites the existing rule for that domain.
        """
        editing_id = self.rule_edit_widget._editing_rule_id # ID from the editor state
        print(f"[UI Save Rule] Entry called. editing_id='{editing_id}', domains={domains}")

        config_changed = False
        rules_changed = False
        needs_list_repopulation = False # Flag to check if UI list needs full refresh

        if not domains:
            print("[UI Save Rule] Error: No valid domains provided.")
            return

        if editing_id: # --- EDIT Mode (Existing logic - should be mostly correct) ---
            if len(domains) > 1:
                 QMessageBox.warning(self, "Input Error", "Cannot edit multiple domains at once.")
                 return
            domain = domains[0]

            # Check if the NEW domain conflicts with ANY OTHER existing rule
            conflict_found = False
            for existing_id_check, existing_rule_check in self.rules.items():
                 if existing_rule_check.get('domain') == domain and existing_id_check != editing_id:
                      conflict_found = True; break
            if conflict_found:
                 QMessageBox.warning(self, "Duplicate Rule", f"Another rule for the domain '{domain}' already exists."); return

            # Proceed with update
            if editing_id in self.rules:
                 old_rule = self.rules[editing_id].copy()
                 new_data = {"domain": domain, "proxy_id": proxy_id, "profile_id": profile_id, "enabled": old_rule.get("enabled", True)}
                 data_actually_changed = (
                     old_rule.get('domain') != domain or
                     old_rule.get('proxy_id') != proxy_id or
                     old_rule.get('profile_id') != profile_id
                 )

                 if data_actually_changed:
                     print(f"[UI Save Rule {editing_id}] Data changed. Updating rule '{domain}'.")
                     rules_changed = True
                     self.rules[editing_id].update(new_data)

                     # Check engine update need
                     if old_rule.get('profile_id') != profile_id:
                        if old_rule.get('profile_id') == self.engine_active_profile_id or \
                           profile_id == self.engine_active_profile_id or \
                           old_rule.get('profile_id') is None or \
                           profile_id is None:
                              config_changed = True

                     # Update UI widget or flag for repopulation
                     if editing_id in self.rule_widgets:
                         self.rule_widgets[editing_id].update_data(self.rules[editing_id], self._get_proxy_name_map(), self._get_profile_name_map())
                         self._filter_rule_list(self.rule_filter_bar.findChild(QLineEdit).text()) # Re-filter needed if profile affects visibility
                     else:
                         needs_list_repopulation = True # Widget wasn't visible, refresh list
                 else:
                     print(f"[UI Save Rule {editing_id}] No changes detected.")
            else:
                 print(f"[UI Save Rule] Error: Cannot update rule with unknown ID: {editing_id}"); return

        else: # --- ADD or OVERWRITE Mode ---
            added_count = 0
            overwritten_count = 0

            for domain in domains:
                existing_rule_id_to_overwrite = None
                # Find if a rule with this exact domain already exists
                for rule_id_check, rule_data_check in self.rules.items():
                    if rule_data_check.get('domain') == domain:
                        existing_rule_id_to_overwrite = rule_id_check
                        break

                if existing_rule_id_to_overwrite: # --- Overwrite Existing Rule ---
                    print(f"[UI Save Rule] Overwriting existing rule for domain '{domain}' (ID: {existing_rule_id_to_overwrite})")
                    old_rule = self.rules[existing_rule_id_to_overwrite].copy()
                    # Use new data, keep existing enabled state unless explicitly changing it (default to True on overwrite?)
                    # Let's default to True on overwrite, as if adding anew.
                    new_data = {"domain": domain, "proxy_id": proxy_id, "profile_id": profile_id, "enabled": True}

                    data_actually_changed = ( # Check if overwrite changes anything relevant
                        old_rule.get('proxy_id') != proxy_id or
                        old_rule.get('profile_id') != profile_id or
                        old_rule.get('enabled', True) != True # Check if it was disabled before
                    )

                    if data_actually_changed:
                        rules_changed = True # Mark that a change occurred
                        self.rules[existing_rule_id_to_overwrite].update(new_data) # Update data store
                        overwritten_count += 1

                        # Check if engine config needs update (profile changed, rule enabled, scope changed)
                        if old_rule.get('profile_id') != profile_id or \
                           not old_rule.get('enabled', True) or \
                           old_rule.get('profile_id') is None or \
                           profile_id is None:
                             # Check if the rule (old or new state) affects the active engine profile
                             if profile_id == self.engine_active_profile_id or profile_id is None or \
                                old_rule.get('profile_id') == self.engine_active_profile_id:
                                  config_changed = True

                        # Update UI widget or flag for repopulation
                        if existing_rule_id_to_overwrite in self.rule_widgets:
                            self.rule_widgets[existing_rule_id_to_overwrite].update_data(self.rules[existing_rule_id_to_overwrite], self._get_proxy_name_map(), self._get_profile_name_map())
                        else:
                            needs_list_repopulation = True # Widget wasn't visible

                    else:
                         print(f"[UI Save Rule] Overwrite for '{domain}' resulted in no data change.")

                else: # --- Add New Rule ---
                    print(f"[UI Save Rule] Adding new rule for domain: {domain}")
                    new_rule_id = str(uuid.uuid4())
                    rule_data = {"id": new_rule_id, "domain": domain, "proxy_id": proxy_id, "profile_id": profile_id, "enabled": True}
                    self.rules[new_rule_id] = rule_data
                    rules_changed = True
                    added_count += 1
                    needs_list_repopulation = True # Adding new rules always requires repopulation for sorting/visibility

                    # Check if engine config needs update
                    if profile_id == self.engine_active_profile_id or profile_id is None:
                         config_changed = True

            # User feedback after processing all domains
            if added_count > 0:
                 profile_display_name = "Global (All Profiles)" if profile_id is None else self.profiles.get(profile_id, {}).get("name", "Unknown")
                 print(f"Added {added_count} new rule(s) to profile: '{profile_display_name}'.")
            if overwritten_count > 0:
                 # Optional: QMessageBox.information(...)
                 print(f"Overwrote {overwritten_count} existing rule(s) with new settings.")


        # --- Post-Save Actions ---
        if rules_changed:
             self._cancel_rule_edit(animate=True) # Close editor on successful change

             if needs_list_repopulation:
                 print("[UI Save Rule] Repopulating rule list.")
                 self._populate_rule_list() # Refresh the whole list display if needed
             else:
                  # If only editing visible items, just filter/update count
                   if editing_id and editing_id in self.rule_widgets:
                        self._filter_rule_list(self.rule_filter_bar.findChild(QLineEdit).text())
                   self._update_rule_count_label() # Still update count

             if config_changed:
                  print("[UI] Rule change affects engine, updating config.")
                  self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)
             self.save_settings() # Save changes to disk

    def _delete_rule_entry(self, rule_id: str):
        """Deletes a rule entry."""
        if rule_id in self.rules:
            rule_data = self.rules[rule_id]
            domain = rule_data.get("domain", "Unknown")
            rule_profile_id = rule_data.get('profile_id')

            # Remove widget from layout
            if rule_id in self.rule_widgets:
                widget_to_remove = self.rule_widgets.pop(rule_id)
                self.rule_list_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()

            # Remove data from store
            del self.rules[rule_id]
            print(f"Deleted rule for: {domain} (ID: {rule_id})")
            self._update_rule_count_label()

            # Update engine if the deleted rule belonged to the currently active profile
            if rule_profile_id == self.engine_active_profile_id:
                 print("[UI] Deleted rule was in active profile, updating engine.")
                 self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)

            self.save_settings() # Persist deletion
        else:
             print(f"Error: Cannot delete rule with unknown ID: {rule_id}")

    def _add_rule_widget(self, rule_data):
        """Creates and adds a RuleItemWidget to the list layout."""
        if rule_data['id'] in self.rule_widgets: return # Avoid duplicates

        widget = RuleItemWidget(rule_data, self._get_proxy_name_map(), self._get_profile_name_map(), self, theme_name=self.current_theme)
        widget.edit_rule.connect(self._show_edit_rule_editor)
        widget.delete_rule.connect(self._delete_rule_entry)
        widget.toggle_enabled.connect(self._toggle_rule_enabled) # Connect new signal
        self.rule_list_layout.addWidget(widget)
        self.rule_widgets[rule_data['id']] = widget
        # Initial visibility is handled by the calling function (_populate_rule_list -> _filter_rule_list)

    def _toggle_rule_enabled(self, rule_id: str, enabled: bool):
        """Handles the enable/disable toggle for a rule."""
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            if rule.get("enabled", True) != enabled: # Check if state actually changed
                print(f"[UI Rule Toggle] Setting rule '{rule['domain']}' (ID: {rule_id}) enabled={enabled}")
                rule["enabled"] = enabled
                rules_changed = True

                # Check if this rule affects the active engine profile
                profile_id = rule.get("profile_id")
                config_changed = (profile_id == self.engine_active_profile_id or profile_id is None)

                if config_changed:
                    print("[UI] Rule toggle affects engine, updating config.")
                    self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)

                self.save_settings() # Save the change

                # Update the specific widget's visual state (optional, if checkbox doesn't auto-update style)
                if rule_id in self.rule_widgets:
                     self.rule_widgets[rule_id].update_data(rule, self._get_proxy_name_map(), self._get_profile_name_map())


        else:
             print(f"[UI Rule Toggle] Error: Rule ID {rule_id} not found.")

    def _populate_rule_list(self):
        """
        Clears and repopulates the list with rules for the VIEWED profile,
        INCLUDING global rules (profile_id=None).
        """
        view_profile_id = self.rule_profile_selector.currentData()
        print(f"[UI Populate Rules] Populating for view profile: '{view_profile_id}'")

        # Clear existing widgets first
        for i in reversed(range(self.rule_list_layout.count())):
            widget = self.rule_list_layout.itemAt(i).widget()
            if widget is not None: widget.deleteLater()
        self.rule_widgets.clear()

        # Determine which rules to display based on VIEW selection
        rules_to_display = {}
        if view_profile_id == self.ALL_RULES_PROFILE_ID:
            # Show all rules when "All" is selected
            rules_to_display = self.rules.copy()
            print(f"[UI Populate Rules] Showing all {len(rules_to_display)} rules.")
        else:
            # Show rules for the specific profile PLUS global rules (profile_id=None)
            print(f"[UI Populate Rules] Showing rules for specific profile '{view_profile_id}' and global rules.")
            for rule_id, rule_data in self.rules.items():
                rule_assigned_profile = rule_data.get('profile_id')
                if rule_assigned_profile == view_profile_id or not rule_assigned_profile: # Match specific OR global
                    rules_to_display[rule_id] = rule_data
            print(f"[UI Populate Rules] Found {len(rules_to_display)} rules to display.")


        # Apply text filter *after* profile filter
        filter_text = ""
        if hasattr(self, 'rule_filter_bar'): # Check if filter bar exists
            filter_input_widget = self.rule_filter_bar.findChild(QLineEdit)
            if filter_input_widget: filter_text = filter_input_widget.text()

        # Add widgets for rules matching the current view filter
        sorted_rule_ids = sorted(rules_to_display.keys(), key=lambda rid: rules_to_display[rid].get("domain", "").lower())
        for rule_id in sorted_rule_ids:
             self._add_rule_widget(rules_to_display[rule_id]) # This adds widget to layout and self.rule_widgets

        # Apply text filter AFTER adding widgets
        self._filter_rule_list(filter_text)
        # Update count label AFTER filtering
        self._update_rule_count_label()

    def _update_rule_count_label(self):
        """Updates the label showing the number of rules matching the current view and filter."""
        visible_count = 0
        view_profile_id = self.rule_profile_selector.currentData()
        filter_text = ""
        if hasattr(self, 'rule_filter_bar'):
            filter_input_widget = self.rule_filter_bar.findChild(QLineEdit)
            if filter_input_widget: filter_text = filter_input_widget.text().lower()

        # Iterate through the actual rules data
        for rule_id, rule_data in self.rules.items():
            # 1. Check if rule belongs to the currently VIEWED profile
            rule_assigned_profile = rule_data.get('profile_id')
            profile_match = (
                view_profile_id == self.ALL_RULES_PROFILE_ID or # Viewing "All"
                rule_assigned_profile == view_profile_id or      # Rule matches specific profile
                not rule_assigned_profile                        # Rule is global (and view isn't "All") - Should this be included if specific profile selected? Yes.
            )
            # Refined profile match: Must match view, OR be global, OR view is "All"
            profile_match_refined = (
                view_profile_id == self.ALL_RULES_PROFILE_ID or
                rule_assigned_profile == view_profile_id or
                not rule_assigned_profile
            )


            if not profile_match_refined:
                 continue # Skip rule if it doesn't belong to the current view

            # 2. Check if rule matches the filter text (using logic similar to _filter_list)
            text_match = True # Assume match if filter is empty
            if filter_text:
                search_string = ""
                # Build search string from rule data
                for key, value in rule_data.items():
                    if key not in ['id', 'password', 'status', 'proxy_id', 'profile_id', 'requires_auth', 'enabled'] and value:
                         search_string += str(value).lower() + " "
                # Add proxy name
                if rule_data.get('proxy_id') and rule_data['proxy_id'] in self.proxies:
                     search_string += self.proxies[rule_data['proxy_id']].get('name', '').lower() + " "
                # Add profile name (even if None, map has entry for it)
                search_string += self._get_profile_name_map().get(rule_assigned_profile, '').lower() + " "

                text_match = filter_text in search_string

            # 3. Increment count if both profile and text match
            if text_match: # Already checked profile_match_refined above
                visible_count += 1

        self.rules_count_label.setText(f"   ({visible_count} Visible)")

    def _calculate_editor_height(self, editor_widget: QWidget) -> int:
        """Calculate the required height for the editor widget."""
        # Ensure the widget is visible to get an accurate size hint
        # Temporarily set max height very large to allow it to expand fully
        editor_widget.setMaximumHeight(10000) # Allow it to grow
        editor_widget.layout().activate()
        editor_widget.adjustSize()
        height = editor_widget.sizeHint().height()
        height += 15 # Increased buffer
        min_height = 180 # Slightly increased minimum
        calculated_height = max(height, min_height)
        # Reset max height immediately after calculation (important!)
        # If it was previously 0 (hidden), keep it 0 until animation starts
        if editor_widget.maximumHeight() != 0:
             editor_widget.setMaximumHeight(0) # Reset for animation start
        print(f"Calculated target height: {calculated_height}") # Debug print
        return calculated_height

    def _show_add_proxy_editor(self):
        if self.rule_edit_widget.isVisible(): self._cancel_rule_edit(animate=False)

        self.proxy_edit_widget.clear_fields()
        target_height = self._calculate_editor_height(self.proxy_edit_widget)
        self.add_proxy_button.setEnabled(False)

        # Store the new animation object
        self.proxy_editor_animation = self._animate_widget_height(self.proxy_edit_widget, 0, target_height)
        self.proxy_editor_animation.finished.connect(self.proxy_edit_widget.set_focus_on_name)
        self.proxy_editor_animation.start() # Removed DeletionPolicy

    def _show_edit_proxy_editor(self, proxy_id: str):
        if self.rule_edit_widget.isVisible(): self._cancel_rule_edit(animate=False)

        if proxy_id in self.proxies:
             self.proxy_edit_widget.load_data(self.proxies[proxy_id])
             # Crucial: ensure widget recalculates layout *after* potential visibility change in load_data
             QApplication.processEvents() # Process visibility change event
             target_height = self._calculate_editor_height(self.proxy_edit_widget)

             self.add_proxy_button.setEnabled(False)
             self.proxy_editor_animation = self._animate_widget_height(self.proxy_edit_widget, 0, target_height)
             self.proxy_editor_animation.finished.connect(self.proxy_edit_widget.set_focus_on_name)
             self.proxy_editor_animation.start() # Removed DeletionPolicy
        else:
            print(f"Error: Cannot edit proxy with unknown ID: {proxy_id}")

    def _cancel_proxy_edit(self, animate=True):
        if not self.proxy_edit_widget.isVisible():
             self.add_proxy_button.setEnabled(True)
             return

        current_height = self.proxy_edit_widget.height()

        # Stop previous animation if it exists and hasn't been cleared
        if self.proxy_editor_animation:
             self.proxy_editor_animation.stop()
             self.proxy_editor_animation = None # Clear immediately after stopping

        if animate and current_height > 0:
             # Create and store the new animation object
             self.proxy_editor_animation = self._animate_widget_height(self.proxy_edit_widget, current_height, 0)
             self.proxy_editor_animation.finished.connect(lambda: self.add_proxy_button.setEnabled(True))
             self.proxy_editor_animation.finished.connect(self._clear_proxy_editor_on_cancel)
             # Clear reference *after* this animation finishes
             self.proxy_editor_animation.finished.connect(self._clear_proxy_animation_ref)
             # Remove DeletionPolicy
             self.proxy_editor_animation.start() # Removed DeletionPolicy
        else:
             # Hide instantly
             self.proxy_edit_widget.setMaximumHeight(0)
             self.proxy_edit_widget.setVisible(False)
             self._clear_proxy_editor_on_cancel()
             self.add_proxy_button.setEnabled(True)
             self.proxy_editor_animation = None # Clear reference if hidden instantly

    def _clear_proxy_animation_ref(self):
        """Clear the animation reference."""
        self.proxy_editor_animation = None

    def _clear_proxy_editor_on_cancel(self):
         """Helper to clear fields and manage visibility state after cancel."""
         # If an item was hidden during edit, show it again (needed if we implement that)
         # editing_id = getattr(self.proxy_edit_widget, '_editing_id', None)
         # if editing_id and editing_id in self.proxy_widgets:
         #      self.proxy_widgets[editing_id].setVisible(True)
         self.proxy_edit_widget.clear_fields()

    def _save_proxy_entry(self, proxy_data: dict):
        is_new = proxy_data.get("id") is None
        if is_new:
            proxy_id = str(uuid.uuid4())
            proxy_data["id"] = proxy_id
            self.proxies[proxy_id] = proxy_data
            self._add_proxy_widget(proxy_data)
            print(f"Added proxy: {proxy_data['name']} (ID: {proxy_id})")
        else:
            proxy_id = proxy_data["id"]
            if proxy_id in self.proxies:
                self.proxies[proxy_id].update(proxy_data)
                if proxy_id in self.proxy_widgets:
                    self.proxy_widgets[proxy_id].update_data(self.proxies[proxy_id])
                    self.proxy_widgets[proxy_id].setVisible(True)
                print(f"Updated proxy: {proxy_data['name']} (ID: {proxy_id})")
            else:
                print(f"Error: Cannot update proxy with unknown ID: {proxy_id}")
                self._cancel_proxy_edit()
                return

        self._cancel_proxy_edit(animate=True) # Use cancel to animate closed
        # Update dependencies
        self.rule_edit_widget.update_proxies(self.proxies)
        self._update_rule_widgets_proxy_names()
        self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)
        self.save_settings() # Save settings after updates

        # Add or update the widget in the UI
        self._add_proxy_widget(self.proxies[proxy_id])

        # Update other UI elements that might depend on proxy names (like rules)
        self._update_rule_widgets_proxy_names()
        self.rule_edit_widget.update_proxies(self.proxies) # Ensure editor dropdown is updated

        self.show_status_message(f"Saved proxy: {proxy_data['name']}") # Use generic "Saved"
        self._cancel_proxy_edit(animate=False) # Close editor without animation

        # --- Add this line ---
        self._update_proxy_count_label()
        # ---

    def _delete_proxy_entry(self, proxy_id: str):
        if proxy_id in self.proxies:
            # Check if proxy is used by any rules before deleting
            used_by_rules = [rid for rid, rdata in self.rules.items() if rdata.get('proxy_id') == proxy_id]
            if used_by_rules:
                 print(f"[UI] Warning: Proxy '{self.proxies[proxy_id].get('name')}' is used by {len(used_by_rules)} rule(s). They will now use Direct Connection.")
                 # Optionally, could update rules to use None (Direct) here
                 # for rule_id_to_update in used_by_rules:
                 #     self.rules[rule_id_to_update]['proxy_id'] = None
                 # If updating rules, need to update corresponding widgets too

            proxy_name = self.proxies[proxy_id].get("name", "Unknown")
            if proxy_id in self.proxy_widgets:
                widget_to_remove = self.proxy_widgets.pop(proxy_id)
                self.proxy_list_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()
            del self.proxies[proxy_id]
            print(f"Deleted proxy: {proxy_name} (ID: {proxy_id})")
            self.rule_edit_widget.update_proxies(self.proxies)
            self._update_rule_widgets_proxy_names()
            self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)
            self.save_settings()
        else:
             print(f"Error: Cannot delete proxy with unknown ID: {proxy_id}")

    def _add_proxy_widget(self, proxy_data: dict):
        proxy_id = proxy_data["id"]
        if proxy_id in self.proxy_widgets:
            # If widget already exists, just update it and potentially bring it to top
            widget = self.proxy_widgets[proxy_id]
            widget.update_data(proxy_data)
            # Check if it's already at the top
            if self.proxy_list_layout.indexOf(widget) != 0:
                 self.proxy_list_layout.insertWidget(0, widget) # Move to top
            return

        item_widget = ProxyItemWidget(proxy_data, parent=self, theme_name=self.current_theme)
        item_widget.edit_requested.connect(self._show_edit_proxy_editor)
        item_widget.delete_requested.connect(self._delete_proxy_entry)
        item_widget.test_requested.connect(self.proxy_engine.test_proxy)
        item_widget.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_widget.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # <<< CHANGE HERE: Insert new widgets at the top (index 0) >>>
        self.proxy_list_layout.insertWidget(0, item_widget)
        self.proxy_widgets[proxy_id] = item_widget
        # Set initial status based on last saved status or default to unknown
        last_status = proxy_data.get('status', 'unknown')
        item_widget.set_status(last_status)

    def _update_rule_widgets_proxy_names(self):
        """Update proxy names displayed in existing RuleItemWidgets when a proxy is saved/edited."""
        proxy_name_map = self._get_proxy_name_map()
        # Fetch the profile name map as well
        profile_name_map = self._get_profile_name_map()

        for rule_id, rule_widget in self.rule_widgets.items():
            # Assuming rule_widget stores its own data
            if hasattr(rule_widget, 'rule_data'):
                 rule_data = rule_widget.rule_data
                 # Pass the profile_name_map to update_data
                 rule_widget.update_data(rule_data, proxy_name_map, profile_name_map)
            else:
                 print(f"[Warn] Rule widget {rule_id} missing rule_data attribute during update.")
                 # Fallback or error handling if needed

    def _handle_toggle_proxy(self, checked: bool):
        """Handles the toggle button click: Starts/Stops Engine & Sets Proxy"""
        print(f"[UI Toggle] Request received. Checked: {checked}")
        if checked:
            # --- Enable Windows Proxy ---
            if platform.system() == "Windows" and hasattr(self, '_set_windows_proxy'):
                port_to_set = self.proxy_engine.listening_port
                self._set_windows_proxy(enable=True, proxy_host="127.0.0.1", proxy_port=port_to_set)
            # --- Start Engine ---
            print(f"[UI Toggle] Starting engine with profile: {self.active_profile_id}")
            self.engine_active_profile_id = self.active_profile_id # Ensure engine uses the correct active profile
            active_rules = self.get_active_rules()
            print(f"[UI Toggle] Passing {len(active_rules)} active rules to engine on start.")
            self.proxy_engine.update_config(active_rules, self.proxies, self.engine_active_profile_id)
            if not self.proxy_engine.start(): # Check if start succeeded
                 print("[UI Toggle] Engine failed to start.")
                 # Optional: show error message to user
                 # Reset toggle button state if start fails
                 self.toggle_proxy_button.blockSignals(True)
                 self.toggle_proxy_button.setChecked(False)
                 self.toggle_proxy_button.blockSignals(False)
                 self._handle_engine_status_update_ui("error") # Update UI to error state
                 # Also disable windows proxy again if it was enabled
                 if platform.system() == "Windows" and hasattr(self, '_set_windows_proxy'):
                      self._set_windows_proxy(enable=False)

        else:
            # --- Stop Engine ---
            self.proxy_engine.stop()
            # --- Disable Windows Proxy ---
            if platform.system() == "Windows" and hasattr(self, '_set_windows_proxy'):
                self._set_windows_proxy(enable=False)
            # --- End Disable ---

    # Renamed method
    def _handle_engine_status_update_ui(self, status: str):
        """Updates UI elements based on engine status (Tray, Status Bar, Toggle Buttons).""" # Updated docstring
        print(f"[UI] Engine status UI update: {status}")
        self.update_tray_status(status) # Update tray icon/tooltip
        # Update status bar message
        status_text = "Proxy Engine: " + status.capitalize()
        self.status_bar_label.setText(status_text)

        is_active = (status == 'active')

        # --- Update Main Window Toggle Button ---
        self.toggle_proxy_button.blockSignals(True)
        self.toggle_proxy_button.setChecked(is_active)
        self.toggle_proxy_button.blockSignals(False)
        self._update_toggle_button_state(status) # Update icon/tooltip

        # --- Update Tray Menu Toggle Action ---
        if hasattr(self, 'toggle_engine_tray_action'):
            self.toggle_engine_tray_action.blockSignals(True) # Prevent signal loop
            self.toggle_engine_tray_action.setChecked(is_active)
            self.toggle_engine_tray_action.setText("Disable Engine" if is_active else "Enable Engine")
            self.toggle_engine_tray_action.blockSignals(False) # Re-enable signals
        # --- End Update Tray Menu ---

        # Trigger proxy tests only when engine becomes *active*
        if status == 'active':
              print("[UI] Engine is active, testing all proxies...")
              # Use a short delay to ensure engine is fully ready
              QTimer.singleShot(200, self.proxy_engine.test_all_proxies)


    def _handle_engine_error(self, error_message: str):
        """Displays an error message from the engine and updates UI state."""
        print(f"[UI] Engine error reported: {error_message}")
        # Show error in status bar
        self.status_bar_label.setText(f"Proxy Engine Error: {error_message[:100]}...")
        # Ensure UI reflects error state
        self._handle_engine_status_update_ui("error")
        # Optionally show a message box
        # QMessageBox.critical(self, "Proxy Engine Error", error_message)

    def _update_toggle_button_state(self, status: str):
        """Updates the visual state AND ICON of the main toggle button."""
        is_active = (status == 'active')
        self.toggle_proxy_button.setChecked(is_active) # Set checked state first

        # Determine color and icon path based on NEW state
        toggle_state = "checked" if is_active else "default"
        toggle_icon_color = self._get_main_icon_color("toggle", state=toggle_state)
        toggle_icon_path = TOGGLE_ON_ICON_PATH if is_active else TOGGLE_OFF_ICON_PATH

        # Load and set the correctly colored icon
        toggle_svg = load_and_colorize_svg_content(toggle_icon_path, toggle_icon_color)
        self.toggle_proxy_button.setIcon(create_icon_from_svg_data(toggle_svg))

        tooltip = "Proxy Engine is ON" if is_active else "Proxy Engine is OFF"
        self.toggle_proxy_button.setToolTip(tooltip)

    def _handle_close_setting_change(self):
        """Save the changed close behavior setting immediately."""
        self.save_settings() # Save all settings when this changes

    def _handle_proxy_test_result(self, proxy_id: str, is_ok: bool):
        """Update the status of the specific proxy widget and save it."""
        if proxy_id in self.proxy_widgets:
             new_status = "active" if is_ok else "error"
             self.proxy_widgets[proxy_id].set_status(new_status)

             if not is_ok:
                 proxy_name = self.proxies.get(proxy_id, {}).get('name', proxy_id)
                 # Show non-critical warning message box for test failure
                 # Keep it brief, details are in the console log
                 QMessageBox.warning(self, "Proxy Test Failed",
                                     f"Connection test failed for proxy:\n'{proxy_name}'\n\n"
                                     f"(Check console log for detailed errors)")

             # Persist the test result status
             if proxy_id in self.proxies:
                 self.proxies[proxy_id]['status'] = new_status
                 self.save_settings() # Save changes

    # Added method to show status messages
    def show_status_message(self, message: str, timeout: int = 4000):
        """Displays a message in the status bar for a specified timeout."""
        self.status_bar_label.setText(message)
        if hasattr(self, "_status_clear_timer") and self._status_clear_timer: self._status_clear_timer.stop()
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        current_engine_status_text = self.status_bar_label.text()
        if "Error" in message: # Keep error messages displayed longer or indefinitely?
             # Don't set a timer to clear error messages from status bar
             pass
        else:
             clear_text = "Proxy Engine: " + self.proxy_engine.get_status().capitalize()
             self._status_clear_timer.timeout.connect(lambda: self.status_bar_label.setText(clear_text))
             self._status_clear_timer.start(timeout)

    def _save_hotkey_setting(self):
        """Save the current hotkey settings preference."""
        # Check for potential conflicts (simple check)
        sequences = [
            self.toggle_hotkey_edit.keySequence(),
            self.show_hide_hotkey_edit.keySequence(),
            self.next_profile_hotkey_edit.keySequence(),
            self.prev_profile_hotkey_edit.keySequence()
        ]
        active_sequences = [s for s in sequences if not s.isEmpty()]
        if len(active_sequences) != len(set(active_sequences)):
             QMessageBox.warning(self, "Hotkey Conflict", "One or more assigned hotkeys conflict. Please ensure all assigned hotkeys are unique.")
             # Don't save if conflict detected? Or just warn? Let's just warn for now.

        print("Hotkey preference saved.")
        self.save_settings()
        # Actual registration update is not implemented

    # --- Placeholder functions for profile switching ---
    def _switch_to_next_profile(self):
        """Switches the active profile to the next one in the list (wraps around)."""
        # This would be called by the global hotkey listener (not implemented)
        print("[Hotkey Action] Switching to next profile (Not fully implemented)")
        current_index = self.rule_profile_selector.currentIndex()
        count = self.rule_profile_selector.count()
        if count <= 1: return # No profiles or only "All"

        next_index = (current_index + 1) % count
        # If "All" is first, skip it when cycling from last profile
        if current_index == count - 1 and self.rule_profile_selector.itemData(0) == self.ALL_RULES_PROFILE_ID:
             next_index = 1 % count # Go to the first *real* profile

        self.rule_profile_selector.setCurrentIndex(next_index) # Triggers _handle_active_profile_change

    def _switch_to_prev_profile(self):
        """Switches the active profile to the previous one (wraps around)."""
        # This would be called by the global hotkey listener (not implemented)
        print("[Hotkey Action] Switching to previous profile (Not fully implemented)")
        current_index = self.rule_profile_selector.currentIndex()
        count = self.rule_profile_selector.count()
        if count <= 1: return

        prev_index = (current_index - 1 + count) % count
        # If "All" is first, handle wrap-around from first real profile
        if current_index == 1 and self.rule_profile_selector.itemData(0) == self.ALL_RULES_PROFILE_ID:
            prev_index = count - 1 # Go to last profile
        elif current_index == 0 and self.rule_profile_selector.itemData(0) == self.ALL_RULES_PROFILE_ID:
            prev_index = count -1 # Wrap from "All" to last

        self.rule_profile_selector.setCurrentIndex(prev_index) # Triggers _handle_active_profile_change

    # --- Profile Management Methods ---

    def _update_profile_selectors(self):
        """Update profile dropdowns in Rules page and Settings page."""
        # Preserve current selections
        current_rule_profile_id = self.rule_profile_selector.currentData()
        current_settings_profile_id = self.profile_list_widget.currentData()

        self.rule_profile_selector.blockSignals(True) # <<< Block rule selector signals
        self.profile_list_widget.blockSignals(True)
        self.rule_profile_selector.clear()
        self.profile_list_widget.clear()

        # Add "All Rules" option to Rules page selector ONLY
        self.rule_profile_selector.addItem(self.ALL_RULES_PROFILE_NAME, self.ALL_RULES_PROFILE_ID)

        # Add actual profiles, sorted by name
        sorted_profiles = sorted(self.profiles.items(), key=lambda item: item[1].get('name', '').lower())
        for profile_id, profile_data in sorted_profiles:
            name = profile_data.get('name', f"Profile {profile_id[:6]}...")
            self.rule_profile_selector.addItem(name, profile_id)
            self.profile_list_widget.addItem(name, profile_id)

        # Restore selection if possible, defaulting intelligently
        rule_idx = self.rule_profile_selector.findData(current_rule_profile_id or self.active_profile_id or self.ALL_RULES_PROFILE_ID)
        settings_idx = self.profile_list_widget.findData(current_settings_profile_id)

        self.rule_profile_selector.setCurrentIndex(max(0, rule_idx))
        self.profile_list_widget.setCurrentIndex(max(0, settings_idx))

        self.rule_profile_selector.blockSignals(False) # <<< Unblock rule selector signals
        self.profile_list_widget.blockSignals(False)

        self._update_profile_button_states()
        self._update_rule_count_label()

    def _update_profile_button_states(self):
        """Enable/disable Rename/Delete buttons based on selection."""
        selected_profile_id = self.profile_list_widget.currentData()
        # Can only rename/delete actual profiles, not the "All Rules" concept
        can_modify = selected_profile_id is not None and selected_profile_id != self.ALL_RULES_PROFILE_ID
        self.rename_profile_button.setEnabled(can_modify)
        self.delete_profile_button.setEnabled(can_modify)

    def _handle_active_profile_change(self, index: int):
        """Handles selection change in the main profile selector."""
        selected_profile_id = self.rule_profile_selector.itemData(index)
        if selected_profile_id is None: # This case should ideally not happen if setup correctly
             print("[UI Profile Change] Error: Selected profile data is None.")
             return

        # Update the active profile ID used for display and potentially saving
        # "__all__" is for viewing, the actual saved active profile is a specific one or default
        if selected_profile_id != self.ALL_RULES_PROFILE_ID:
             self.active_profile_id = selected_profile_id
             print(f"[UI Profile Change] View changed. Set active profile to: {self.active_profile_id}")
             self.save_settings() # Save the newly selected active profile
        else:
             # Don't change self.active_profile_id when viewing "All", but maybe update engine?
             # Decide if engine should switch to "All" or stay on last selected profile?
             # Let's keep engine on the *specifically selected* active profile.
             print(f"[UI Profile Change] Viewing 'All Rules'. Engine remains on profile: {self.engine_active_profile_id}")
             pass # Keep self.active_profile_id as the last *real* selected profile

        # Option 1: Update Engine immediately when VIEW changes
        # self.engine_active_profile_id = selected_profile_id if selected_profile_id != self.ALL_RULES_PROFILE_ID else "__all__" # Use __all__ for engine if viewing All
        # print(f"[UI Profile Change] Updating engine to use rules from profile: {self.engine_active_profile_id}")
        # self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)

        # Option 2: Engine only uses the explicitly saved `self.active_profile_id`
        # (Handled by `_handle_toggle_proxy` and initial load) - Let's stick with this for now.

        # Repopulate rule list based on the *selected view*
        self._populate_rule_list() # Filters based on selected_profile_id
        self._update_rule_count_label()

    def _add_profile(self):
        text, ok = QInputDialog.getText(self, "New Profile", "Enter profile name:")
        if ok and text:
             profile_name = text.strip()
             if profile_name:
                  # Check for duplicate name
                  if any(p.get('name') == profile_name for p in self.profiles.values()):
                       QMessageBox.warning(self, "Duplicate Name", f"A profile named '{profile_name}' already exists.")
                       return
                  profile_id = str(uuid.uuid4())
                  self.profiles[profile_id] = {'name': profile_name}
                  print(f"Added profile '{profile_name}' (ID: {profile_id})")
                  self._update_profile_selectors()
                  # Select the newly added profile in settings list
                  new_index = self.profile_list_widget.findData(profile_id)
                  if new_index != -1: self.profile_list_widget.setCurrentIndex(new_index)
                  self.save_settings()

    def _rename_profile(self):
        current_id = self.profile_list_widget.currentData()
        if not current_id or current_id not in self.profiles: return

        current_name = self.profiles[current_id].get('name', '')
        text, ok = QInputDialog.getText(self, "Rename Profile", "Enter new profile name:", text=current_name)
        if ok and text:
             new_name = text.strip()
             if new_name and new_name != current_name:
                  # Check for duplicate name
                  if any(p_id != current_id and p.get('name') == new_name for p_id, p in self.profiles.items()):
                       QMessageBox.warning(self, "Duplicate Name", f"A profile named '{new_name}' already exists.")
                       return
                  self.profiles[current_id]['name'] = new_name
                  print(f"Renamed profile ID {current_id} to '{new_name}'")
                  self._update_profile_selectors()
                  # Re-select the renamed profile
                  renamed_index = self.profile_list_widget.findData(current_id)
                  if renamed_index != -1: self.profile_list_widget.setCurrentIndex(renamed_index)
                  self.save_settings()

    def _delete_profile(self):
        profile_id = self.profile_list_widget.currentData()
        if not profile_id or profile_id not in self.profiles: return

        profile_name = self.profiles[profile_id].get('name', 'Unknown')
        reply = QMessageBox.question(self, "Delete Profile",
                                     f"Are you sure you want to delete the profile '{profile_name}'?\n"
                                     f"Rules associated with this profile will be kept but become inactive unless reassigned.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
             print(f"Deleting profile '{profile_name}' (ID: {profile_id})")
             del self.profiles[profile_id]

             # Find rules associated with this profile
             rules_to_clear_profile = [rid for rid, rdata in self.rules.items() if rdata.get('profile_id') == profile_id]
             if rules_to_clear_profile:
                  print(f"Setting profile to 'None' for {len(rules_to_clear_profile)} rules.")
                  for rule_id in rules_to_clear_profile:
                       if rule_id in self.rules:
                            self.rules[rule_id]['profile_id'] = None

             # If the deleted profile was active, switch active profile VIEW and ENGINE to "All"
             if self.active_profile_id == profile_id:
                  print("[UI] Deleted profile was active, switching to 'All Rules'.")
                  self._set_active_profile(self.ALL_RULES_PROFILE_ID) # Use the conceptual ID for setting

             self._update_profile_selectors() # Update UI lists
             self._populate_rule_list() # Repopulate rules (will now show rules for active profile)
             self.save_settings() # Save changes

    # --- Animation Helper ---
    def _animate_widget_height(self, widget, start_height, end_height, duration=250):
        """Animates the maximumHeight of a widget."""
        if end_height > 0 and not widget.isVisible():
             widget.setVisible(True)

        # Use a local variable for the animation
        animation = QPropertyAnimation(widget, b"maximumHeight")
        animation.setDuration(duration)
        animation.setStartValue(start_height)
        animation.setEndValue(end_height)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        if end_height == 0:
            # Use lambda to capture the widget, not self.animation object
            animation.finished.connect(lambda w=widget: w.setVisible(False))

        return animation

    # --- Hotkey Methods ---
    def _clear_hotkey(self, key_sequence_edit_widget: QKeySequenceEdit):
        """Clears the key sequence in the specified widget."""
        key_sequence_edit_widget.clear()
        self._save_hotkey_setting() # Save the cleared setting

    # --- Filter Widgets ---
    def _create_filter_bar(self, placeholder_text: str, filter_slot) -> QWidget:
        """Creates a simple filter bar widget."""
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(15, 5, 15, 5) # Less vertical margin
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(placeholder_text)
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(filter_slot)
        filter_layout.addWidget(self.filter_input)
        return filter_widget

    # --- Filtering Methods ---
    def _filter_list(self, filter_text: str, item_widgets: dict, get_widget_data_func):
        """Generic list filtering logic."""
        filter_lower = filter_text.lower()
        for item_id, widget in item_widgets.items():
            data_dict = get_widget_data_func(item_id)
            if not data_dict:
                 widget.setVisible(False) # Hide if data missing
                 continue

            # Combine relevant fields into a searchable string
            search_string = ""
            for key, value in data_dict.items():
                 # Include relevant fields like name, domain, address, type, profile name etc.
                 # Exclude sensitive or irrelevant fields like password, id
                 if key not in ['id', 'password', 'status', 'proxy_id', 'profile_id', 'requires_auth'] and value:
                      search_string += str(value).lower() + " "
            # Add related names (proxy/profile) if applicable
            if 'proxy_id' in data_dict and data_dict['proxy_id'] in self.proxies:
                 search_string += self.proxies[data_dict['proxy_id']].get('name', '').lower() + " "
            if 'profile_id' in data_dict and data_dict['profile_id'] in self.profiles:
                 search_string += self.profiles[data_dict['profile_id']].get('name', '').lower() + " "

            widget.setVisible(filter_lower in search_string)
        # Update counts after filtering (optional, or keep total count?)
        # self._update_rule_count_label()
        # self._update_proxy_count_label()

    def _filter_rule_list(self, text: str):
        """Filters the visible rule widgets based on input text."""
        self._filter_list(text, self.rule_widgets, lambda item_id: self.rules.get(item_id))
        # --- Add this line ---
        self._update_rule_count_label() # Update count after filtering
        # ---

    def _filter_proxy_list(self, text: str):
        """Filters the visible proxy widgets based on input text."""
        self._filter_list(text, self.proxy_widgets, lambda item_id: self.proxies.get(item_id))
        # --- Add this line ---
        self._update_proxy_count_label() # Update count after filtering (Good to have here too)
        # ---

    def _populate_proxy_list(self):
        """Clear and repopulate the proxy list UI."""
        # Clear existing widgets first
        while self.proxy_list_layout.count():
            item = self.proxy_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.proxy_widgets.clear() # Clear the reference dictionary

        # Add widgets for current proxies, sorted alphabetically
        # Note: They will be inserted in reverse sorted order visually due to insertWidget(0) in _add_proxy_widget
        # If you want them displayed alphabetically top-to-bottom, _add_proxy_widget should use addWidget()
        # and this loop should process sorted_proxies normally.
        # Current implementation adds new items to top, and full refresh shows reverse alphabetical.
        sorted_proxies = sorted(self.proxies.items(), key=lambda item: item[1].get('name', '').lower())
        for proxy_id, proxy_data in sorted_proxies:
            self._add_proxy_widget(proxy_data) # _add_proxy_widget now handles insertion order

        # No need for addStretch here if using AlignTop and inserting at 0

        # Update count after populating
        self._update_proxy_count_label()

    def _update_proxy_count_label(self):
        """Updates the label showing the number of proxies matching the current filter."""
        visible_count = 0
        filter_text = ""
        if hasattr(self, 'proxy_filter_bar'):
            filter_input_widget = self.proxy_filter_bar.findChild(QLineEdit)
            if filter_input_widget: filter_text = filter_input_widget.text().lower()

        # Iterate through the actual proxies data
        for proxy_id, proxy_data in self.proxies.items():
            # 1. Check if proxy matches the filter text
            text_match = True # Assume match if filter is empty
            if filter_text:
                search_string = ""
                # Build search string from proxy data
                for key, value in proxy_data.items():
                    if key not in ['id', 'password', 'status', 'requires_auth'] and value:
                         search_string += str(value).lower() + " "
                # Add username if auth is required? Might be sensitive. Let's skip for now.

                text_match = filter_text in search_string

            # 2. Increment count if text matches
            if text_match:
                visible_count += 1

        self.proxies_count_label.setText(f"({visible_count} Visible)")

    def closeEvent(self, event):
        """Handle window close event (X button) based on setting."""
        # Ensure editors are closed instantly before hide/quit
        self._cancel_proxy_edit(animate=False)
        self._cancel_rule_edit(animate=False)

        # ... (rest of closeEvent as before) ...

        # If fully exiting (not hiding to tray):
        if self.close_behavior == "exit" or self._force_quit:
             print("[App] Exiting application...")
             # Stop the engine
             self.proxy_engine.stop()
             # --- Add Windows Proxy Disable on Exit ---
             if platform.system() == "Windows":
                  print("[App Exit] Disabling system proxy before exiting...")
                  self._set_windows_proxy(enable=False)
             # --- End Add ---
             # ... (rest of exit logic) ...
             event.accept()
        # ... (else hide to tray) ...

    # ... (rest of MainWindow methods) ... 

    # --- Windows Proxy Settings Method (Ensure this exists and is correctly indented) ---
    def _set_windows_proxy(self, enable: bool, proxy_host: str = "127.0.0.1", proxy_port: int = 8080, bypass: str = "<local>"):
        """Configures Windows system proxy settings via the registry."""
        if platform.system() != "Windows":
            # print("[WinProxy] Not on Windows, skipping system proxy settings.") # Optional print
            return

        print(f"[WinProxy] Attempting to set system proxy enable={enable}")
        try:
            # Define registry access constants locally or access them via self if defined in __init__
            INTERNET_SETTINGS_KEY_PATH = r'Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings'
            INTERNET_OPTION_SETTINGS_CHANGED = 39
            INTERNET_OPTION_REFRESH = 37

            # Open the Internet Settings registry key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS_KEY_PATH, 0, winreg.KEY_WRITE)

            if enable:
                proxy_server = f"{proxy_host}:{proxy_port}"
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
                if bypass:
                     winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, bypass)
                print(f"[WinProxy] System proxy ENABLED: {proxy_server}, Bypass: '{bypass}'")
            else:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                print("[WinProxy] System proxy DISABLED.")

            winreg.CloseKey(key)

            # Notify Windows that settings have changed (requires self.InternetSetOptionW check)
            # Ensure InternetSetOptionW is loaded correctly in __init__ for Windows
            if hasattr(self, 'InternetSetOptionW') and self.InternetSetOptionW:
                print("[WinProxy] Refreshing system settings...")
                settings_changed = self.InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
                refresh = self.InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0)
                if settings_changed and refresh:
                     print("[WinProxy] System refresh notification sent successfully.")
                else:
                     print("[WinProxy] Warning: Failed to send system refresh notification.")
            elif platform.system() == "Windows": # Only warn if on Windows and function is missing
                 print("[WinProxy] InternetSetOptionW not available, manual browser/app restart might be needed.")

        except FileNotFoundError:
            print(f"[WinProxy] Error: Registry key not found: {INTERNET_SETTINGS_KEY_PATH}")
            # Avoid UI block on startup errors if possible, just log
            # QMessageBox.warning(self, "Registry Error", f"Could not find Internet Settings registry key.\nAutomatic proxy configuration failed.")
        except PermissionError:
            print("[WinProxy] Error: Permission denied writing to registry.")
            # QMessageBox.warning(self, "Registry Error", f"Permission denied writing to registry.\nAutomatic proxy configuration failed.\nTry running as administrator (not recommended for daily use).")
        except Exception as e:
            print(f"[WinProxy] Error setting system proxy: {e}", exc_info=True)
            # QMessageBox.warning(self, "Registry Error", f"An unexpected error occurred while configuring system proxy:\n{e}")

    # ... (rest of MainWindow methods like _handle_toggle_proxy, closeEvent, etc.) ... 

    def _open_settings_folder(self):
        """Opens the folder containing the settings.ini file in the system's file explorer."""
        settings_dir = os.path.dirname(self.settings_file)
        if not os.path.exists(settings_dir):
            QMessageBox.warning(self, "Error", f"Settings directory not found:\n{settings_dir}")
            return

        print(f"Opening settings folder: {settings_dir}")
        try:
            if platform.system() == "Windows":
                os.startfile(settings_dir)
            elif platform.system() == "Darwin": # macOS
                subprocess.run(['open', settings_dir], check=True)
            else: # Linux and other Unix-like
                subprocess.run(['xdg-open', settings_dir], check=True)
        except FileNotFoundError:
             QMessageBox.warning(self, "Error", f"Could not open folder.\n'{'xdg-open' if platform.system() != 'Darwin' else 'open'}' command not found.")
        except Exception as e:
             QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")
             print(f"Error opening folder {settings_dir}: {e}")

    # --- Add Reset Method ---
    def _reset_all_settings(self):
        """Resets all application data and settings to defaults."""
        reply = QMessageBox.question(self, "Reset Settings",
                                     "Are you sure you want to reset ALL settings?\n"
                                     "This will delete all your proxies, rules, and profiles, and restore default UI settings.\n"
                                     "This action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            print("[Settings] Resetting all settings...")

            # 1. Reset Internal Data Structures
            self.proxies.clear()
            self.rules.clear()
            self.profiles.clear()
            self.profiles = {"__default__": {"name": "Default"}} # Reset to only default profile
            self.active_profile_id = "__default__"
            self.engine_active_profile_id = "__default__" # Also reset engine's target

            # 2. Clear Widgets
            # Proxy List
            while self.proxy_list_layout.count():
                item = self.proxy_list_layout.takeAt(0)
                widget = item.widget()
                if widget: widget.deleteLater()
            self.proxy_widgets.clear()
            # Rule List
            while self.rule_list_layout.count():
                item = self.rule_list_layout.takeAt(0)
                widget = item.widget()
                if widget: widget.deleteLater()
            self.rule_widgets.clear()

            # 3. Clear Settings File
            settings = QSettings(self.settings_file, QSettings.Format.IniFormat)
            settings.clear()
            settings.sync() # Ensure cleared state is written
            print("[Settings] Cleared settings file.")

            # 4. Reset UI Elements to Defaults
            # Theme
            self.current_theme = 'dark' # Default theme
            self.apply_theme(self.current_theme) # Apply stylesheet
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(0) # Set combo to Dark
            self.theme_combo.blockSignals(False)
            # Close Behavior
            self.close_behavior = "minimize" # Default
            self.close_to_tray_checkbox.setChecked(True)
            # Startup
            self.start_engine_checkbox.setChecked(False) # Default off
            # Hotkeys
            self.toggle_hotkey_edit.clear()
            self.show_hide_hotkey_edit.clear()
            self.next_profile_hotkey_edit.clear()
            self.prev_profile_hotkey_edit.clear()

            # 5. Re-populate selectors/counts
            self._update_profile_selectors() # Populate with only Default profile
            self._update_proxy_count_label()
            self._update_rule_count_label()
            # No need to call populate lists as they are now empty

            # 6. Save the default settings back
            self.save_settings() # This will save the current (default) state

            # 7. Update Engine Config (with empty rules/proxies)
            self.proxy_engine.update_config(self.get_active_rules(), self.proxies, self.engine_active_profile_id)

            self.show_status_message("All settings have been reset.", 5000)
            QMessageBox.information(self, "Reset Complete", "All settings have been reset to default values.")

    # --- End Reset Method ---