import os
import sys # Needed for access to QApplication instance
import uuid # For generating unique proxy/rule IDs
import json # Make sure json is imported
import platform # Added import for platform-specific functionality
import winreg # Added import for Windows registry access
import ctypes # Added import for ctypes
from ctypes import wintypes # Added import for ctypes
import re
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QKeySequence, QShortcut, QActionGroup, QTextCursor # Added QPainter, QKeySequence, QTextCursor
from PySide6.QtCore import (Qt, QSize, QSettings, QByteArray, QFile, QTextStream, Signal, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QStandardPaths,
                           QRect, QPoint, QEvent, QAbstractAnimation, QObject) # Added QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QSizePolicy, QSystemTrayIcon, QMenu, QApplication,
    QComboBox, QSpacerItem, QScrollArea, QToolButton, QCheckBox, QFormLayout, QKeySequenceEdit, QInputDialog, QMessageBox, QLineEdit, QTextEdit, QDialogButtonBox, QDialog, QListWidgetItem, QListWidget, QGraphicsOpacityEffect, QAbstractItemView # <<< Change CustomListWidget to QListWidget
)
from PySide6.QtSvg import QSvgRenderer # Added QSvgRenderer
import subprocess # Add subprocess
import time # Added import for time.sleep
import io # Import io for stream redirection

# Import new widgets using relative paths
from .widgets.proxy_item_widget import ProxyItemWidget
from .widgets.proxy_edit_widget import ProxyEditWidget
from .widgets.rule_item_widget import RuleItemWidget # Added
from .widgets.rule_edit_widget import RuleEditWidget # Added
from .widgets.quick_rule_add_dialog import QuickRuleAddDialog
# Import Core components using relative paths
from ..core.proxy_engine import ProxyEngine # <<< Changed to relative import
from ..core.hotkey_manager import IS_WINDOWS, HotkeyManager # <<< Import HotkeyManager
# RuleMatcher will likely be used internally by the engine, but good to have the file

# Get base paths reliably
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # This is src/
ASSETS_DIR = os.path.join(script_dir, 'assets')
IMAGES_DIR = os.path.join(ASSETS_DIR, 'images')
ICONS_DIR = os.path.join(ASSETS_DIR, 'icons') # Added Icons Dir
STYLES_DIR = os.path.join(ASSETS_DIR, 'styles') # Added

# Icon Paths - Make sure these files exist in src/assets/images/ and src/assets/icons/
MAIN_ICON_PATH = os.path.join(IMAGES_DIR, "icon.png")
TRAY_ICON_INACTIVE_PATH = os.path.join(IMAGES_DIR, "icon_inactive.png")
TRAY_ICON_ACTIVE_PATH = os.path.join(IMAGES_DIR, "icon_active.png")
TRAY_ICON_ERROR_PATH = os.path.join(IMAGES_DIR, "icon_error.png")
# --- Corrected Toggle Icon Paths ---
TOGGLE_ON_ICON_PATH = os.path.join(ICONS_DIR, "toggle-right.svg") # Use toggle-right for ON
TOGGLE_OFF_ICON_PATH = os.path.join(ICONS_DIR, "toggle-left.svg")  # Use toggle-left for OFF
TOGGLE_ERROR_ICON_PATH = os.path.join(ICONS_DIR, "toggle-left.svg") # Use toggle-left for ERROR state as well
# --- End Correction ---

# SVG Icon Paths
RULES_ICON_PATH = os.path.join(ICONS_DIR, "rules.svg")
PROXIES_ICON_PATH = os.path.join(ICONS_DIR, "proxies.svg")
SETTINGS_ICON_PATH = os.path.join(ICONS_DIR, "settings.svg")
ADD_ICON_PATH = os.path.join(ICONS_DIR, "plus.svg")
CLEAR_ICON_PATH = os.path.join(ICONS_DIR, "x.svg") # For clear button if needed
FOLDER_ICON_PATH = os.path.join(ICONS_DIR, "folder.svg")
RESET_ICON_PATH = os.path.join(ICONS_DIR, "reset.svg")
SAVE_ICON_PATH = os.path.join(ICONS_DIR, "save.svg")
CANCEL_ICON_PATH = os.path.join(ICONS_DIR, "x-circle.svg")
EDIT_ICON_PATH = os.path.join(ICONS_DIR, "edit.svg")
DELETE_ICON_PATH = os.path.join(ICONS_DIR, "trash.svg")
LOGS_ICON_PATH = os.path.join(ICONS_DIR, "logs.svg") # Add new icon path
CLEAR_LOGS_ICON_PATH = os.path.join(ICONS_DIR, "clear-logs.svg") # Add new icon path

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

# --- Stream Redirection ---
class StreamEmitter(QObject):
    """Emits text written to it via a signal AND writes to original stream."""
    textWritten = Signal(str)

    def __init__(self, original_stream, parent=None): # Accept original stream
        super().__init__(parent)
        self.buffer = ""
        self.original_stream = original_stream # Store original stream

    def write(self, text):
        try:
            # Write to the original stream first
            if self.original_stream:
                self.original_stream.write(str(text))
                self.original_stream.flush() # Ensure it appears in console immediately
        except Exception as e:
            # Avoid crashing if original stream is somehow closed/invalid
            print(f"[StreamEmitter Error] Failed to write to original stream: {e}", file=sys.__stderr__) # Use original stderr for this error

        # Emit the signal for the UI
        self.textWritten.emit(str(text))


    def flush(self):
        # Flushing the original stream is handled in write
        pass
# --- End Stream Redirection ---

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
        QApplication.setApplicationVersion("1.1.3") # Example version

        self.resize(self.NEW_DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        if os.path.exists(MAIN_ICON_PATH):
            self.setWindowIcon(QIcon(MAIN_ICON_PATH))

        # ---> Load Tray Icons Early <---
        self.icon_active = QIcon(TRAY_ICON_ACTIVE_PATH) if os.path.exists(TRAY_ICON_ACTIVE_PATH) else QIcon(MAIN_ICON_PATH)
        self.icon_inactive = QIcon(TRAY_ICON_INACTIVE_PATH) if os.path.exists(TRAY_ICON_INACTIVE_PATH) else QIcon(MAIN_ICON_PATH)
        self.icon_error = QIcon(TRAY_ICON_ERROR_PATH) if os.path.exists(TRAY_ICON_ERROR_PATH) else QIcon(MAIN_ICON_PATH)
        # Check if fallback main icon exists
        if not os.path.exists(MAIN_ICON_PATH):
             print("Warning: Main application icon not found, tray icons might be missing.")
             # Use default Qt icon as ultimate fallback?
             # self.icon_active = self.icon_inactive = self.icon_error = QIcon() # Or leave as potentially invalid QIcon(MAIN_ICON_PATH)

        # --- Define Settings File Path ---
        # Use standard config location
        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        self.settings_file = os.path.join(config_dir, "settings.ini")
        print(f"Using settings file: {self.settings_file}")
        # --- End Settings File Path ---

        # --- Add Stream Redirection BEFORE creating log widget ---
        # ---> Pass original streams to StreamEmitter <---
        self._stdout_emitter = StreamEmitter(sys.__stdout__) # Pass original stdout
        self._stderr_emitter = StreamEmitter(sys.__stderr__) # Pass original stderr
        sys.stdout = self._stdout_emitter
        sys.stderr = self._stderr_emitter
        # --- End Stream Redirection ---

        # Data Stores (Initialize early)
        self.sidebar_buttons = []
        self.current_theme = 'dark'
        self.proxies = {}
        self.proxy_widgets = {}
        self.rules = {}
        self.rule_widgets = {}
        self.profiles = {} # Initialize empty, load_settings will handle default
        self._current_active_profile_id = None # Initialize profile ID

        self.proxy_editor_animation = None
        self.rule_editor_animation = None
        self.close_behavior = "minimize" # Default
        self._force_quit = False # Flag for actual quit action

        # Initialize Core Components (Needed before connections)
        self.proxy_engine = ProxyEngine()
        self.hotkey_manager = HotkeyManager()
        
        # Flag to track if we're in the middle of a profile switch
        self._is_switching_profiles = False

        # Create UI Elements FIRST
        self._create_widgets()
        self._create_layouts()
        # ---> Create Tray Icon BEFORE Connecting Signals <---
        self._create_tray_icon()
        # ---> Now connect signals/slots <---
        self._create_connections()

        # Load settings AFTER UI widgets are created AND connections established
        self.load_settings() # Load profiles, rules, proxies, UI state etc.

        # Apply initial UI state based on loaded settings
        self._update_profile_selectors() # Populate selectors with loaded profiles/active ID
        self._populate_proxy_list() # Populate with loaded proxies
        self._populate_rule_list() # Populate with loaded rules for the active profile
        self._set_initial_active_view() # Set the correct sidebar view

        # Load and Register Hotkeys (After settings are loaded and connections made)
        self._load_and_register_hotkeys()

        # Center window after potential size changes from loading settings
        self._center_window()

        # Start engine on startup if configured
        if self.start_engine_checkbox.isChecked():
            print("[Startup] Auto-starting engine...")
            # Use a QTimer to allow the event loop to start first
            QTimer.singleShot(100, lambda: self._handle_toggle_proxy(True))
            # Note: The system proxy setting will be handled in _handle_toggle_proxy
            # when engine is started, based on the enable_system_proxy_checkbox state

        self._log_auto_clear_timer = QTimer(self)
        self._log_auto_clear_timer.setInterval(30_000)  # 30 seconds
        self._log_auto_clear_timer.timeout.connect(self._auto_clear_logs_if_engine_running)

        self.proxy_engine.status_changed.connect(self._handle_engine_status_for_log_timer)

    def _create_widgets(self):
        """Create all the widgets for the main window."""
        # --- Left Sidebar (Navigation) ---
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(60) # Example width

        # ---> ADD Master Toggle Button Creation <---
        self.toggle_proxy_button = QToolButton()
        self.toggle_proxy_button.setObjectName("ToggleProxyButton")
        self.toggle_proxy_button.setCheckable(True) # Make it checkable
        self.toggle_proxy_button.setFixedSize(40, 40) # Adjust size as needed
        self.toggle_proxy_button.setIconSize(QSize(28, 28)) # Adjust icon size
        # Initial icon/tooltip will be set by _update_toggle_button_state via status signals
        # --- END Toggle Button Creation ---

        # Create SVG buttons for main navigation
        self.nav_button_rules = create_svg_button(object_name="navButtonRules")
        self.nav_button_proxies = create_svg_button(object_name="navButtonProxies")
        self.nav_button_logs = create_svg_button(object_name="navButtonLogs") # Add logs button
        self.nav_button_settings = create_svg_button(object_name="navButtonSettings")

        # Update sidebar_buttons list
        self.sidebar_buttons = [self.nav_button_rules, self.nav_button_proxies, self.nav_button_logs, self.nav_button_settings]
        self.nav_button_rules.setToolTip("Manage Domain Routing Rules")
        self.nav_button_proxies.setToolTip("Manage Proxy Servers")
        self.nav_button_logs.setToolTip("View Application Logs") # Add tooltip
        self.nav_button_settings.setToolTip("Application Settings")

        # --- Main Content Area (Stacked Widget) ---
        self.main_content_area = QStackedWidget()
        self.main_content_area.setObjectName("MainContentArea")

        # --- Rules Page ---
        self.rules_page = QWidget()
        self.rules_page.setObjectName("RulesPage")
        rules_page_layout = QVBoxLayout(self.rules_page)
        rules_page_layout.setContentsMargins(0, 0, 0, 0)
        rules_page_layout.setSpacing(0)
        
        # --- Top Header Area ---
        rule_header_container = QWidget()
        rule_header_container.setObjectName("PageHeaderContainer")
        rule_header_layout = QHBoxLayout(rule_header_container)
        rule_header_layout.setContentsMargins(15, 10, 15, 10)
        rule_header_layout.setSpacing(10)
        
        self.rules_title_label = QLabel("All Domain Rules (Active Profile: None)")
        self.rules_title_label.setObjectName("ViewTitleLabel")
        rule_header_layout.addWidget(self.rules_title_label, stretch=1) # Allow title to stretch

        # ---> Change Add Rule Button to QPushButton <---
        self.add_rule_button = QPushButton("Add Rule") # Changed from _create_tool_button
        if os.path.exists(ADD_ICON_PATH): # Optionally keep icon
             self.add_rule_button.setIcon(QIcon(ADD_ICON_PATH))
        self.add_rule_button.setObjectName("AddRuleButton") # Use this for styling if needed
        self.add_rule_button.setToolTip("Add new routing rule(s) to the active profile")
        self.add_rule_button.clicked.connect(self._show_add_rule_editor) # Connect here
        rule_header_layout.addWidget(self.add_rule_button)

        rules_page_layout.addWidget(rule_header_container)
        # --- End Rule Header ---

        # --- Rule Editor Placeholder ---
        self.rule_editor_container = QWidget()
        self.rule_editor_container.setObjectName("EditorContainer")
        self.editor_container_layout = QVBoxLayout(self.rule_editor_container)
        self.editor_container_layout.setContentsMargins(15, 0, 15, 5)
        self.editor_container_layout.setSpacing(0)
        # ---> Create Rule Edit Widget Instance Here <---
        self.rule_edit_widget = RuleEditWidget(self, self.proxies, self.profiles) # Create instance
        # ---> Add Opacity Effect for Fade Animation <---
        self.rule_edit_opacity_effect = QGraphicsOpacityEffect(self.rule_edit_widget)
        self.rule_edit_widget.setGraphicsEffect(self.rule_edit_opacity_effect)
        self.rule_edit_opacity_effect.setOpacity(0.0) # Start transparent
        # ---> End Opacity Effect <---
        self.rule_edit_widget.save_rules.connect(self._save_rule_entry)
        self.rule_edit_widget.cancelled.connect(self._cancel_rule_edit)
        self.editor_container_layout.addWidget(self.rule_edit_widget) # Add to layout
        self.rule_edit_widget.setVisible(False) # Start hidden
        self.rule_editor_container.setMaximumHeight(0) # Collapsed initially
        rules_page_layout.addWidget(self.rule_editor_container)
        # --- End Editor ---

        # --- Rule Filter Bar ---
        self.rule_filter_bar = self._create_filter_bar("Filter rules...", self._filter_rule_list, include_count_label=True)
        rules_page_layout.addWidget(self.rule_filter_bar)
        # --- End Filter Bar ---

        # --- Rule List Area ---
        # Use QListWidget for rules (temporarily, until CustomListWidget is defined/imported)
        self.rules_list_widget = QListWidget() # <<< Changed from CustomListWidget
        self.rules_list_widget.setObjectName("RuleListWidget")
        # Add styling for item spacing if needed (QSS is better)
        # self.rules_list_widget.setSpacing(5) # Example spacing
        rules_page_layout.addWidget(self.rules_list_widget, stretch=1) # List takes remaining space
        # --- End Rule List ---

        # Placeholder for empty list
        self.rules_placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.rules_placeholder_widget)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label = QLabel("No rules defined in any profile.")
        placeholder_label.setObjectName("PlaceholderLabel")
        placeholder_layout.addWidget(placeholder_label)
        self.rules_placeholder_widget.setVisible(False) # Initially hidden
        rules_page_layout.addWidget(self.rules_placeholder_widget, stretch=1)
        rules_page_layout.setStretchFactor(self.rules_list_widget, 1)
        rules_page_layout.setStretchFactor(self.rules_placeholder_widget, 1)

        # --- Proxies Page ---
        self.proxies_page = QWidget()
        self.proxies_page.setObjectName("ProxiesPage")
        proxies_page_layout = QVBoxLayout(self.proxies_page)
        proxies_page_layout.setContentsMargins(0, 0, 0, 0)
        proxies_page_layout.setSpacing(0)
        # Top Bar
        proxies_top_bar = QHBoxLayout()
        proxies_top_bar.setContentsMargins(15, 10, 15, 10)
        proxies_top_bar.addWidget(QLabel("Managed Proxies   "))
        proxies_top_bar.addStretch()
        self.add_proxy_button = QPushButton("Add Proxy")
        if os.path.exists(ADD_ICON_PATH):
            self.add_proxy_button.setIcon(QIcon(ADD_ICON_PATH))
        self.add_proxy_button.setObjectName("AddProxyButton")
        self.add_proxy_button.clicked.connect(self._show_add_proxy_editor)
        self.add_proxy_button.setToolTip("Add a new proxy server configuration")
        proxies_top_bar.addWidget(self.add_proxy_button)
        proxies_page_layout.addLayout(proxies_top_bar)

        # ---> Create Proxy Editor CONTAINER <---
        self.proxy_editor_container = QWidget()
        self.proxy_editor_container.setObjectName("EditorContainer") # Same name OK? Yes.
        proxy_editor_container_layout = QVBoxLayout(self.proxy_editor_container)
        proxy_editor_container_layout.setContentsMargins(15, 0, 15, 5)
        proxy_editor_container_layout.setSpacing(0)

        # Create Proxy Edit Widget Instance and add to CONTAINER
        self.proxy_edit_widget = ProxyEditWidget(self)
        self.proxy_edit_widget.save_proxy.connect(self._save_proxy_entry)
        self.proxy_edit_widget.cancelled.connect(self._cancel_proxy_edit)
        proxy_editor_container_layout.addWidget(self.proxy_edit_widget) # Add EDITOR to CONTAINER layout
        self.proxy_edit_widget.setVisible(False) # Start hidden

        self.proxy_editor_container.setMaximumHeight(0) # Start CONTAINER collapsed
        proxies_page_layout.addWidget(self.proxy_editor_container) # Add CONTAINER to PAGE layout
        # ---> End Proxy Editor Container Setup <---

        # Filter Bar
        self.proxy_filter_bar = self._create_filter_bar("Filter proxies...", self._filter_proxy_list, include_count_label=True)
        proxies_page_layout.addWidget(self.proxy_filter_bar)
        proxies_page_layout.addSpacing(6)  # Add vertical space to match rules filter-to-list gap

        # Proxy List (Scroll Area)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("ProxyScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.proxy_list_container = QWidget()
        self.proxy_list_container.setObjectName("ProxyListContainer")
        self.proxy_list_layout = QVBoxLayout(self.proxy_list_container)
        self.proxy_list_layout.setContentsMargins(15, 0, 15, 15) # Top margin 0 to match rules
        self.proxy_list_layout.setSpacing(5) # Remove extra spacing between filter and first item
        self.proxy_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.proxy_list_container)
        proxies_page_layout.addWidget(self.scroll_area)
        # --- End Proxies Page ---

        # --- Logs Page ---
        self.logs_page = QWidget()
        self.logs_page.setObjectName("LogsPage")
        logs_page_layout = QVBoxLayout(self.logs_page)
        logs_page_layout.setContentsMargins(0, 0, 0, 0)
        logs_page_layout.setSpacing(0)

        # Add a header with a clear button
        log_header_widget = QWidget()
        log_header_widget.setObjectName("PageHeaderContainer")
        log_header_layout = QHBoxLayout(log_header_widget)
        log_header_layout.setContentsMargins(15, 10, 15, 10)
        log_header_layout.addWidget(QLabel("Application Logs"), stretch=1)
        self.clear_logs_button = QPushButton(" Clear Logs") # Added space for icon
        self.clear_logs_button.setObjectName("ClearLogsButton") # Style if needed
        # ---> Apply the new icon <---
        if os.path.exists(CLEAR_LOGS_ICON_PATH):
            # We'll set the actual QIcon in _apply_theme_colors
            self.clear_logs_button.setProperty("iconPath", CLEAR_LOGS_ICON_PATH)
            # self.clear_logs_button.setIcon(QIcon(CLEAR_LOGS_ICON_PATH)) # Placeholder icon
        self.clear_logs_button.setToolTip("Clear the log view") # Tooltip
        log_header_layout.addWidget(self.clear_logs_button)
        logs_page_layout.addWidget(log_header_widget)

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setObjectName("LogTextEdit")
        self.log_text_edit.setReadOnly(True)
        # Optional: Set monospace font
        # from PySide6.QtGui import QFontDatabase
        # font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        # self.log_text_edit.setFont(font)
        logs_page_layout.addWidget(self.log_text_edit, stretch=1) # Log area takes remaining space

        # --- Settings Page ---
        self.settings_page = QWidget()
        settings_page_layout = QVBoxLayout(self.settings_page)
        settings_page_layout.setContentsMargins(15, 10, 15, 10)
        settings_page_layout.setSpacing(15)

        # Use QScrollArea for settings content if it gets long
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setObjectName("SettingsScrollArea")
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_content_widget = QWidget()
        # ---> Set object name for QSS targeting <---
        settings_content_widget.setObjectName("settings_content_widget")
        settings_form_layout = QVBoxLayout(settings_content_widget) # Main layout for settings content
        settings_form_layout.setSpacing(10)

        # --- General Settings ---
        general_group_label = QLabel("<b>General</b>")
        settings_form_layout.addWidget(general_group_label)

        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        settings_form_layout.addLayout(theme_layout)

        self.close_to_tray_checkbox = QCheckBox("Minimize to system tray on close")
        self.close_to_tray_checkbox.setObjectName("CloseToTrayCheckbox")
        settings_form_layout.addWidget(self.close_to_tray_checkbox)

        self.start_engine_checkbox = QCheckBox("Start proxy engine on application startup")
        self.start_engine_checkbox.setObjectName("StartEngineCheckbox")
        settings_form_layout.addWidget(self.start_engine_checkbox)

        # System Proxy (Windows Only)
        if IS_WINDOWS:
            self.enable_system_proxy_checkbox = QCheckBox("Set as system proxy when engine is active")
            self.enable_system_proxy_checkbox.setToolTip("Automatically configure Windows proxy settings (requires admin rights potentially)")
            self.enable_system_proxy_checkbox.setObjectName("SystemProxyCheckbox")
            settings_form_layout.addWidget(self.enable_system_proxy_checkbox)

        settings_form_layout.addWidget(self._create_separator())

        # --- Profiles Settings ---
        profiles_group_layout = QHBoxLayout()
        profiles_group_label = QLabel("<b>Profiles</b>")
        profiles_group_layout.addWidget(profiles_group_label)
        profiles_group_layout.addStretch()

        # ---> Change Profile Buttons to QPushButton with text <---
        self.add_profile_button = QPushButton(" Add") # Changed from tool button
        self.add_profile_button.setToolTip("Add New Profile")
        self.add_profile_button.setObjectName("SettingsButton") # General settings button style

        self.rename_profile_button = QPushButton(" Rename") # Changed from tool button
        self.rename_profile_button.setToolTip("Rename Selected Profile")
        self.rename_profile_button.setObjectName("SettingsButton")

        self.delete_profile_button = QPushButton(" Delete") # Changed from tool button
        self.delete_profile_button.setToolTip("Delete Selected Profile")
        self.delete_profile_button.setObjectName("DangerButton") # Keep danger style if defined

        profiles_group_layout.addWidget(self.add_profile_button)
        profiles_group_layout.addWidget(self.rename_profile_button)
        profiles_group_layout.addWidget(self.delete_profile_button)
        settings_form_layout.addLayout(profiles_group_layout)
        # Connections are done in _create_connections

        # ---> Create self.profile_list_widget as QListWidget <---
        self.profile_list_widget = QListWidget()
        self.profile_list_widget.setObjectName("ProfileListWidget")
        self.profile_list_widget.setMaximumHeight(150) # Limit height
        settings_form_layout.addWidget(self.profile_list_widget)

        settings_form_layout.addWidget(self._create_separator())

        # --- Hotkeys Settings ---
        hotkeys_group_label = QLabel("<b>Global Hotkeys</b>")
        settings_form_layout.addWidget(hotkeys_group_label)
        hotkeys_form = QFormLayout()
        hotkeys_form.setSpacing(8)
        hotkeys_form.setContentsMargins(10,0,0,0) # Indent hotkey form

        self.toggle_hotkey_edit = QKeySequenceEdit()
        self.show_hide_hotkey_edit = QKeySequenceEdit()
        self.next_profile_hotkey_edit = QKeySequenceEdit()
        self.prev_profile_hotkey_edit = QKeySequenceEdit()
        self.quick_add_rule_hotkey_edit = QKeySequenceEdit()

        # Create clear buttons
        clear_toggle_btn = self._create_clear_hotkey_button(self.toggle_hotkey_edit, "Toggle Engine")
        clear_show_hide_btn = self._create_clear_hotkey_button(self.show_hide_hotkey_edit, "Show/Hide Window")
        clear_next_prof_btn = self._create_clear_hotkey_button(self.next_profile_hotkey_edit, "Next Profile")
        clear_prev_prof_btn = self._create_clear_hotkey_button(self.prev_profile_hotkey_edit, "Previous Profile")
        clear_quick_add_btn = self._create_clear_hotkey_button(self.quick_add_rule_hotkey_edit, "Quick Add Rule")

        # Add rows to form layout
        hotkeys_form.addRow("Toggle Engine:", self._create_hotkey_row(self.toggle_hotkey_edit, clear_toggle_btn))
        hotkeys_form.addRow("Show/Hide Window:", self._create_hotkey_row(self.show_hide_hotkey_edit, clear_show_hide_btn))
        hotkeys_form.addRow("Next Profile:", self._create_hotkey_row(self.next_profile_hotkey_edit, clear_next_prof_btn))
        hotkeys_form.addRow("Previous Profile:", self._create_hotkey_row(self.prev_profile_hotkey_edit, clear_prev_prof_btn))
        hotkeys_form.addRow("Quick Add Rule:", self._create_hotkey_row(self.quick_add_rule_hotkey_edit, clear_quick_add_btn))
        settings_form_layout.addLayout(hotkeys_form)

        settings_form_layout.addWidget(self._create_separator())

        # --- Advanced Settings ---
        advanced_group_label = QLabel("<b>Advanced</b>")
        settings_form_layout.addWidget(advanced_group_label)

        # Listening Port
        # ... (port setting - if needed) ...

        # Settings Folder/Reset
        folder_reset_layout = QHBoxLayout()
        self.open_settings_folder_button = QPushButton("Open Config Folder")
        if os.path.exists(FOLDER_ICON_PATH): self.open_settings_folder_button.setIcon(QIcon(FOLDER_ICON_PATH))
        folder_reset_layout.addWidget(self.open_settings_folder_button)
        folder_reset_layout.addStretch()
        self.reset_settings_button = QPushButton("Reset All Settings")
        if os.path.exists(RESET_ICON_PATH): self.reset_settings_button.setIcon(QIcon(RESET_ICON_PATH))
        self.reset_settings_button.setObjectName("DangerButton") # For danger styling
        folder_reset_layout.addWidget(self.reset_settings_button)
        settings_form_layout.addLayout(folder_reset_layout)


        settings_form_layout.addStretch() # Push content up

        settings_scroll.setWidget(settings_content_widget)
        settings_page_layout.addWidget(settings_scroll)
        # --- End Settings Page ---


        # --- Add Pages to Stack ---
        self.main_content_area.addWidget(self.rules_page)
        self.main_content_area.addWidget(self.proxies_page)
        self.main_content_area.addWidget(self.logs_page)
        self.main_content_area.addWidget(self.settings_page)

        # --- Status Bar ---
        self.status_bar_widget = QWidget()
        self.status_bar_widget.setObjectName("StatusBar")
        status_bar_layout = QHBoxLayout(self.status_bar_widget)
        status_bar_layout.setContentsMargins(15, 5, 15, 5) # Padding

        # Engine status label
        self.status_bar_label = QLabel("Proxy Engine: Inactive")
        self.status_bar_label.setObjectName("StatusLabel")
        status_bar_layout.addWidget(self.status_bar_label)
        status_bar_layout.addStretch(1) # Add stretch BEFORE profile selector

        # First separator
        first_separator = self._create_vertical_separator()
        status_bar_layout.addWidget(first_separator)

        # Active Profile section
        active_profile_label = QLabel("Active Profile:  ")
        active_profile_label.setObjectName("StatusBarLabel") # Style for status bar
        self.active_profile_combo = QComboBox()
        self.active_profile_combo.setMinimumWidth(150) # Adjust width as needed
        self.active_profile_combo.setToolTip("Select the currently active profile for the proxy engine")
        self.active_profile_combo.setObjectName("StatusBarComboBox") # Style for status bar
        status_bar_layout.addWidget(active_profile_label)
        status_bar_layout.addWidget(self.active_profile_combo)

        # Second separator
        second_separator = self._create_vertical_separator()
        status_bar_layout.addWidget(second_separator)

        # Version label in a container to center it
        version_container = QWidget()
        version_container.setObjectName("VersionContainer")  # Add object name for CSS targeting
        version_layout = QHBoxLayout(version_container)
        version_layout.setContentsMargins(10, 0, 10, 0)
        version_label = QLabel(f"v{QApplication.applicationVersion()}")
        version_label.setObjectName("CountLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignCenter)
        status_bar_layout.addWidget(version_container)

    def _create_layouts(self):
        """Create and arrange layouts."""
        # --- Central Widget & Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # Main layout is now just the content layout + status bar
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Content Layout (Sidebar + StackedWidget) ---
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # --- Sidebar Layout ---
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar_layout.setContentsMargins(5, 15, 5, 10)
        sidebar_layout.setSpacing(10)

        # ---> Add the toggle button (it now exists) <---
        sidebar_layout.addWidget(self.toggle_proxy_button, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addSpacing(20) # Space below toggle

        # Add Navigation buttons
        sidebar_layout.addWidget(self.nav_button_rules, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.nav_button_proxies, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.nav_button_logs, alignment=Qt.AlignmentFlag.AlignCenter) # Add logs button
        sidebar_layout.addStretch() # Push settings to bottom
        sidebar_layout.addWidget(self.nav_button_settings, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Add Sidebar and Content Area to Content Layout ---
        content_layout.addWidget(self.sidebar_frame)
        content_layout.addWidget(self.main_content_area, stretch=1)

        # --- Assemble Main Layout ---
        # ---> REMOVE Header <---
        # main_layout.addWidget(self.header_widget)
        main_layout.addLayout(content_layout, stretch=1) # Content takes most space
        main_layout.addWidget(self.status_bar_widget) # Add status bar

    def _create_connections(self):
        """Connect signals and slots."""
        # Navigation Buttons
        self.nav_button_rules.clicked.connect(lambda: self._handle_nav_click(0, self.nav_button_rules))
        self.nav_button_proxies.clicked.connect(lambda: self._handle_nav_click(1, self.nav_button_proxies))
        self.nav_button_logs.clicked.connect(lambda: self._handle_nav_click(2, self.nav_button_logs)) # Connect logs button
        self.nav_button_settings.clicked.connect(lambda: self._handle_nav_click(3, self.nav_button_settings)) # Update index

        # Main Toggle Button
        self.toggle_proxy_button.clicked.connect(self._handle_toggle_proxy)

        # Proxy Engine Signals
        self.proxy_engine.status_changed.connect(self._handle_engine_status_update_ui)
        self.proxy_engine.error_occurred.connect(self._handle_engine_error)
        self.proxy_engine.proxy_test_result.connect(self._handle_proxy_test_result)

        # Tray Icon Actions
        if self.tray_icon: # Check if tray icon was successfully created
            self.tray_icon.activated.connect(self.on_tray_icon_activated)
            self.show_action.triggered.connect(self.toggle_visibility) # Connect show action
            self.quit_action.triggered.connect(self.quit_application) # Connect quit action
            # Connect toggle action from tray menu
            if hasattr(self, 'toggle_engine_tray_action'):
                # Use lambda to pass checked state to handler if needed, or just call toggle proxy
                self.toggle_engine_tray_action.triggered.connect(lambda checked=self.toggle_engine_tray_action.isChecked(): self._handle_toggle_proxy(checked))
                # self.toggle_engine_tray_action.triggered.connect(self._handle_toggle_proxy) # Simpler if handler checks state
        else:
            print("[Connect] Tray icon not available, skipping tray connections.")

        # Settings Page connections
        self.theme_combo.currentIndexChanged.connect(self._handle_theme_change)
        self.close_to_tray_checkbox.stateChanged.connect(self._handle_close_setting_change)
        self.start_engine_checkbox.stateChanged.connect(self.save_settings) # Save immediately on change
        # Hotkey Edits (Connect saving to editingFinished or textChanged?)
        # Using editingFinished is better to avoid saving on every keystroke
        self.toggle_hotkey_edit.editingFinished.connect(self._save_hotkey_setting)
        self.show_hide_hotkey_edit.editingFinished.connect(self._save_hotkey_setting)
        self.next_profile_hotkey_edit.editingFinished.connect(self._save_hotkey_setting)
        self.prev_profile_hotkey_edit.editingFinished.connect(self._save_hotkey_setting)
        self.quick_add_rule_hotkey_edit.editingFinished.connect(self._save_hotkey_setting)

        # Profile Management buttons
        # print(f"DEBUG: Type of self.profile_list_widget before connection: {type(self.profile_list_widget)}") # Keep debug line
        # Connect based on the error message, assuming it's currently seen as QComboBox
        # ---> Revert connection to use QListWidget signal <---
        # try:
        #     # Use currentIndexChanged as the error suggests for now
        #     # self.profile_list_widget.currentIndexChanged.connect(self._update_profile_button_states)
        #     # print("INFO: Connected profile_list_widget using currentIndexChanged.")
        # except AttributeError:
        #      # Fallback if it *is* correctly identified as QListWidget later
        #      print("WARNING: Connecting profile_list_widget using currentItemChanged as fallback.")
        # ---> Correct connection for QListWidget <---
        self.profile_list_widget.currentItemChanged.connect(self._update_profile_button_states)
        print("INFO: Connected profile_list_widget using currentItemChanged.")


        self.add_profile_button.clicked.connect(self._add_profile)
        self.rename_profile_button.clicked.connect(self._rename_profile)
        self.delete_profile_button.clicked.connect(self._delete_profile)

        # Active Profile Selector (Main Header)
        self.active_profile_combo.currentIndexChanged.connect(self._handle_active_profile_change)

        # System Proxy Checkbox (Windows only)
        if IS_WINDOWS:
            self.enable_system_proxy_checkbox.stateChanged.connect(self._handle_system_proxy_toggle)

        # Settings Folder/Reset Buttons
        self.open_settings_folder_button.clicked.connect(self._open_settings_folder)
        self.reset_settings_button.clicked.connect(self._reset_all_settings)

        # Connect Hotkey Manager signals
        self.hotkey_manager.toggle_engine_triggered.connect(self._handle_toggle_hotkey_action)
        self.hotkey_manager.show_hide_triggered.connect(self.toggle_visibility)
        self.hotkey_manager.next_profile_triggered.connect(self._switch_to_next_profile) # Connect profile switching
        self.hotkey_manager.prev_profile_triggered.connect(self._switch_to_prev_profile) # Connect profile switching
        self.hotkey_manager.quick_add_rule_triggered.connect(self._trigger_quick_add_rule) # Connect quick add
        self.hotkey_manager.error_occurred.connect(self._handle_hotkey_error)

        # Logs Page Connections
        self._stdout_emitter.textWritten.connect(self._append_log_text)
        self._stderr_emitter.textWritten.connect(self._append_log_text)
        self.clear_logs_button.clicked.connect(self.log_text_edit.clear)

    def _handle_nav_click(self, index: int, clicked_button: QPushButton):
        """Handles clicks on navigation buttons."""
        # Cancel any ongoing edits (use animation=False for instant close)
        # Check if index is not the proxy page before canceling proxy edit
        if index != 1: # Index 1 is Proxies page
             self._cancel_proxy_edit(animate=False)
        # Check if index is not the rules page before canceling rule edit
        if index != 0: # Index 0 is Rules page
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
         logs_svg = load_and_colorize_svg_content(LOGS_ICON_PATH, nav_icon_color) # Add logs icon
         settings_svg = load_and_colorize_svg_content(SETTINGS_ICON_PATH, nav_icon_color)
         self.nav_button_rules.setIcon(create_icon_from_svg_data(rules_svg))
         self.nav_button_proxies.setIcon(create_icon_from_svg_data(proxies_svg))
         self.nav_button_logs.setIcon(create_icon_from_svg_data(logs_svg)) # Set logs icon
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

         # --- Clear Logs Button ---
         if hasattr(self, 'clear_logs_button') and self.clear_logs_button.property("iconPath"):
             # ---> Use the same color key as Add buttons for consistency <---
             clear_logs_icon_color = self._get_main_icon_color("add_button")
             clear_logs_svg = load_and_colorize_svg_content(self.clear_logs_button.property("iconPath"), clear_logs_icon_color)
             self.clear_logs_button.setIcon(create_icon_from_svg_data(clear_logs_svg))
             # ---> Set Icon Size Explicitly to Match Add Buttons (Optional, if needed) <---
             # icon_size = QSize(16, 16) # Or whatever size Add button uses
             # self.clear_logs_button.setIconSize(icon_size)


    def _update_toggle_button_state(self, status: str):
        """Updates the visual state AND ICON of the main toggle button."""
        is_active = (status == 'active' or status == 'starting' or status == 'switching')
        is_error = (status == 'error')
        is_starting = (status == 'starting')
        is_stopping = (status == 'stopping')
        is_switching = (status == 'switching')
        
        self.toggle_proxy_button.setChecked(is_active) # Set checked state first

        # Determine color and icon path based on NEW state
        toggle_state = "checked" if is_active else ("error" if is_error else "default")
        toggle_icon_color = self._get_main_icon_color("toggle", state=toggle_state)

        # Choose the correct icon path based on status
        toggle_icon_path = None  # For toggle itself
        if is_error:
            toggle_icon_path = TOGGLE_ERROR_ICON_PATH # Will now point to toggle-error.svg
        elif is_active or is_starting or is_switching:
            toggle_icon_path = TOGGLE_ON_ICON_PATH  # Will now point to toggle-right.svg
        else: # inactive or stopping
            toggle_icon_path = TOGGLE_OFF_ICON_PATH # Will now point to toggle-left.svg

        # ---> Check if icon file exists before loading <---
        if os.path.exists(toggle_icon_path):
            toggle_svg = load_and_colorize_svg_content(toggle_icon_path, toggle_icon_color)
            if toggle_svg:
                self.toggle_proxy_button.setIcon(create_icon_from_svg_data(toggle_svg))
            else:
                print(f"Warning: Failed to load/colorize toggle icon: {toggle_icon_path}")
                self.toggle_proxy_button.setIcon(QIcon()) # Clear icon
                self.toggle_proxy_button.setText("?") # Fallback text
        else:
            print(f"Error: Icon file not found at {toggle_icon_path}")
            self.toggle_proxy_button.setIcon(QIcon()) # Clear icon
            # Set fallback text based on state
            fallback_text = "ON" if is_active else ("ERR" if is_error else "OFF")
            self.toggle_proxy_button.setText(fallback_text)
        # ---> End check <---

        # Update tooltip
        if is_error:
            tooltip = "Proxy Engine ERROR"
        elif is_switching:
            tooltip = "Switching Active Profile..."
        elif is_active:
            tooltip = "Proxy Engine is ON"
        elif is_starting:
            tooltip = "Proxy Engine is Starting..."
        elif is_stopping:
            tooltip = "Proxy Engine is Stopping..."
        else:
            tooltip = "Proxy Engine is OFF"
        
        self.toggle_proxy_button.setToolTip(tooltip)

    def _create_tray_icon(self):
        """Creates the system tray icon and menu."""
        # Check if tray icon is already created
        if hasattr(self, 'tray_icon') and self.tray_icon:
             print("[Tray] Tray icon already exists.")
             return

        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[Tray] System tray not available on this system.")
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip(f"{QApplication.applicationName()} - Inactive")

        # Set initial icon (inactive)
        inactive_icon_path = TRAY_ICON_INACTIVE_PATH # Use constant
        if os.path.exists(inactive_icon_path):
             self.tray_icon.setIcon(QIcon(inactive_icon_path))
        else:
             print(f"[Tray] Warning: Inactive tray icon not found at {inactive_icon_path}")
             # Fallback: use main icon if available
             if os.path.exists(MAIN_ICON_PATH):
                  self.tray_icon.setIcon(QIcon(MAIN_ICON_PATH))

        # --- Create Tray Menu ---
        self.tray_menu = QMenu(self)

        # Show/Hide Action
        self.show_action = QAction("Show Window", self)
        # Connection moved to _create_connections

        # Toggle Engine Action
        self.toggle_engine_tray_action = QAction("Enable Engine", self)
        self.toggle_engine_tray_action.setCheckable(True)
        # Connection moved to _create_connections
        
        # Profiles Submenu
        self.profiles_menu = QMenu("Active Profile", self)
        self.profile_action_group = QActionGroup(self)
        self.profile_action_group.setExclusive(True)
        # Will be populated in _update_profile_selectors
        
        # Quit Action
        self.quit_action = QAction("Quit", self)
        # Connection moved to _create_connections

        # Add actions to menu
        self.tray_menu.addAction(self.show_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.toggle_engine_tray_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addMenu(self.profiles_menu) # Add profiles submenu
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        # Connection (activated signal) moved to _create_connections
        print("[Tray] System tray icon created.")

    def on_tray_icon_activated(self, reason):
         """Handles activation of the tray icon."""
         # Show window on left click, show menu on right click/context
         if reason == QSystemTrayIcon.ActivationReason.Trigger: # Left click
              self.toggle_visibility()
         elif reason == QSystemTrayIcon.ActivationReason.Context: # Right click
              # Menu is handled by setContextMenu, but you could add logic here
              pass

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
        if not self.tray_icon: return # Don't do anything if tray isn't available

        tooltip_base = QApplication.applicationName() # Use dynamic app name
        icon = self.icon_inactive # Default to loaded inactive icon

        if status == 'active':
            icon = self.icon_active; state_text = "Active"
        elif status == 'error':
            icon = self.icon_error; state_text = "Error"
        elif status == 'starting':
            icon = self.icon_active; state_text = "Starting..." # Use active icon
        elif status == 'stopping':
            icon = self.icon_inactive; state_text = "Stopping..." # Use inactive icon
        elif status == 'switching':
            icon = self.icon_active; state_text = "Switching Profile..." # Use active icon during profile switch
        else: # inactive
             state_text = "Inactive"
             # icon = self.icon_inactive (already default)

        self.tray_icon.setIcon(icon) # Use the loaded QIcon object
        self.tray_icon.setToolTip(f"{tooltip_base} ({state_text})")
        # Status bar text handled separately in _handle_engine_status_update_ui

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

        # Load Last View (Adjust index check for new button count)
        last_index = settings.value("ui/last_view_index", defaultValue=0, type=int)
        # We'll apply this in _set_initial_active_view after widgets are ready

        # --- Load Profiles (support new and old format) ---
        settings.beginGroup("profiles")
        child_groups = settings.childGroups()
        profiles = {}
        if child_groups:
            # New format: each profile is a group
            for group in child_groups:
                settings.beginGroup(group)
                profile = {}
                for k in settings.childKeys():
                    profile[k] = settings.value(k, type=str)
                # Convert id to string if present
                if 'id' in profile:
                    profile['id'] = str(profile['id'])
                profiles[profile.get('id', group)] = profile
                settings.endGroup()
        else:
            # Old format: JSON blob
            profiles_json = settings.value("data_json", defaultValue="{}", type=str)
            try:
                profiles = json.loads(profiles_json)
                if not isinstance(profiles, dict):
                    print("[Settings] Warning: Loaded profiles data is not a dictionary. Resetting.")
                    profiles = {}
            except json.JSONDecodeError:
                print("[Settings] Warning: Failed to decode profiles JSON. Resetting profiles.")
                profiles = {}
        settings.endGroup()
        self.profiles = profiles

        # ---> Ensure at least one profile exists <---
        if not self.profiles:
             default_profile_id = str(uuid.uuid4())
             self.profiles = {
                 default_profile_id: {"id": default_profile_id, "name": "Default Profile"}
             }
             print("[Settings] No profiles found or loaded correctly, created 'Default Profile'.")

        # Load Active Profile ID
        loaded_active_id = settings.value("ui/active_profile_id", defaultValue=None, type=str)
        if loaded_active_id and loaded_active_id in self.profiles:
             self._current_active_profile_id = loaded_active_id
        else:
             self._current_active_profile_id = next(iter(self.profiles.keys()), None)
             print(f"[Settings] Invalid/missing active profile ID, defaulting to: {self._current_active_profile_id}")

        # --- Load Proxies (support new and old format) ---
        settings.beginGroup("proxies")
        child_groups = settings.childGroups()
        proxies = {}
        if child_groups:
            for group in child_groups:
                settings.beginGroup(group)
                proxy = {}
                for k in settings.childKeys():
                    proxy[k] = settings.value(k, type=str)
                if 'id' in proxy:
                    proxy['id'] = str(proxy['id'])
                proxies[proxy.get('id', group)] = proxy
                settings.endGroup()
        else:
            proxies_json = settings.value("data_json", defaultValue="{}", type=str)
            try:
                proxies = json.loads(proxies_json)
                if not isinstance(proxies, dict):
                    print("[Settings] Warning: Loaded proxies data is not a dictionary. Resetting.")
                    proxies = {}
                for proxy_id, proxy_data in proxies.items():
                    if isinstance(proxy_data, dict) and 'status' not in proxy_data:
                        proxy_data['status'] = 'unknown'
            except json.JSONDecodeError:
                print("[Settings] Warning: Failed to decode proxies JSON. Resetting proxies.")
                proxies = {}
        settings.endGroup()
        self.proxies = proxies

        # --- Load Rules (support new and old format) ---
        settings.beginGroup("rules")
        child_groups = settings.childGroups()
        loaded_rules = {}
        if child_groups:
            for group in child_groups:
                settings.beginGroup(group)
                rule = {}
                for k in settings.childKeys():
                    rule[k] = settings.value(k, type=str)
                if 'id' in rule:
                    rule['id'] = str(rule['id'])
                loaded_rules[rule.get('id', group)] = rule
                settings.endGroup()
        else:
            rules_json = settings.value("data_json", defaultValue="{}", type=str)
            try:
                loaded_rules = json.loads(rules_json)
                if not isinstance(loaded_rules, dict):
                    print("[Settings] Warning: Loaded rules data is not a dictionary. Resetting.")
                    loaded_rules = {}
            except json.JSONDecodeError:
                print("[Settings] Warning: Failed to decode rules JSON. Resetting rules.")
                loaded_rules = {}
        settings.endGroup()

        # --- > Process and Validate Rules < ---
        self.rules = {}
        if self._current_active_profile_id:
            for rule_id, rule_data in loaded_rules.items():
                rule_profile_id = rule_data.get("profile_id")
                if rule_profile_id is None or rule_profile_id not in self.profiles:
                    print(f"[Settings] Rule '{rule_id}' ({rule_data.get('domain')}) has invalid/missing profile ID '{rule_profile_id}'. Assigning to active profile '{self._current_active_profile_id}'.")
                    rule_data["profile_id"] = self._current_active_profile_id
                if "enabled" not in rule_data:
                    rule_data["enabled"] = True
                self.rules[rule_id] = rule_data
        else:
            print("[Settings] Warning: No active profile ID available, cannot load/assign rules.")

        # --- Load Hotkeys (support new and old format) ---
        settings.beginGroup("hotkeys")
        toggle_seq_str = settings.value("toggle_engine", defaultValue="", type=str)
        show_hide_seq_str = settings.value("show_hide_window", defaultValue="", type=str)
        next_prof_seq_str = settings.value("next_profile", defaultValue="", type=str)
        prev_prof_seq_str = settings.value("prev_profile", defaultValue="", type=str)
        quick_add_seq_str = settings.value("quick_add_rule", defaultValue="", type=str)
        settings.endGroup()
        # Fallback to old keys if new ones are empty
        if not toggle_seq_str:
            toggle_seq_str = settings.value("hotkeys/toggle_proxy", defaultValue="", type=str)
        if not show_hide_seq_str:
            show_hide_seq_str = settings.value("hotkeys/show_hide_window", defaultValue="", type=str)
        if not next_prof_seq_str:
            next_prof_seq_str = settings.value("hotkeys/next_profile", defaultValue="", type=str)
        if not prev_prof_seq_str:
            prev_prof_seq_str = settings.value("hotkeys/prev_profile", defaultValue="", type=str)
        if not quick_add_seq_str:
            quick_add_seq_str = settings.value("hotkeys/quick_add_rule", defaultValue="", type=str)

        self.toggle_hotkey_edit.setKeySequence(QKeySequence.fromString(toggle_seq_str))
        self.show_hide_hotkey_edit.setKeySequence(QKeySequence.fromString(show_hide_seq_str))
        self.next_profile_hotkey_edit.setKeySequence(QKeySequence.fromString(next_prof_seq_str))
        self.prev_profile_hotkey_edit.setKeySequence(QKeySequence.fromString(prev_prof_seq_str))
        self.quick_add_rule_hotkey_edit.setKeySequence(QKeySequence.fromString(quick_add_seq_str))

        # Load Startup Setting
        start_on_startup = settings.value("app/start_engine_on_startup", defaultValue=False, type=bool)
        self.start_engine_checkbox.blockSignals(True) # <<< Block signals
        self.start_engine_checkbox.setChecked(start_on_startup)
        self.start_engine_checkbox.blockSignals(False) # <<< Unblock signals

        # Load System Proxy Setting (Windows only)
        if hasattr(self, 'enable_system_proxy_checkbox'):
            use_system_proxy = settings.value("app/set_system_proxy", defaultValue=False, type=bool)
            self.enable_system_proxy_checkbox.blockSignals(True)
            self.enable_system_proxy_checkbox.setChecked(use_system_proxy)
            self.enable_system_proxy_checkbox.blockSignals(False)

        # --- Note: Don't need settings.endGroup() for QSettings ---

        # --- Apply Theme AFTER loading other data ---
        self.apply_theme(loaded_theme_name)
        theme_index = 0 if self.current_theme == "dark" else 1
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index)
        self.theme_combo.blockSignals(False)
        # ---

        print(f"[Settings] Loaded {len(self.profiles)} profiles, {len(self.proxies)} proxies, {len(self.rules)} rules.")
        print(f"[Settings] Active profile set to: {self._current_active_profile_id} ({self.profiles.get(self._current_active_profile_id, {}).get('name', 'N/A')})")

        # Final updates after loading all settings
        self._update_profile_selectors() # Refresh profile UI elements
        self._update_rules_title_label() # Update rules title with active profile

        # --- Ensure requires_auth is always a bool for proxies (fixes UI crash) ---
        for proxy in self.proxies.values():
            if 'requires_auth' in proxy:
                v = proxy['requires_auth']
                if isinstance(v, bool):
                    continue
                if isinstance(v, str):
                    proxy['requires_auth'] = v.lower() in ('true', '1', 'yes')
                else:
                    proxy['requires_auth'] = bool(v)
        # --- End patch ---

        # --- Ensure enabled is always a bool for rules (fixes UI crash) ---
        for rule in self.rules.values():
            if 'enabled' in rule:
                v = rule['enabled']
                if isinstance(v, bool):
                    continue
                if isinstance(v, str):
                    rule['enabled'] = v.lower() in ('true', '1', 'yes')
                else:
                    rule['enabled'] = bool(v)
        # --- End patch ---

        return True

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

        # Save Last View (Index might have changed)
        settings.setValue("ui/last_view_index", self.main_content_area.currentIndex())

        # --- Save Profiles (Human-friendly, sorted) ---
        settings.beginGroup("profiles")
        # Remove old keys
        for key in settings.childGroups():
            settings.remove(key)
        # Sort profiles by name
        sorted_profiles = sorted(self.profiles.values(), key=lambda p: p.get('name', '').lower())
        for profile in sorted_profiles:
            group_name = f"profile:{profile.get('name', profile.get('id', 'Unknown'))}"
            settings.beginGroup(group_name)
            for k, v in profile.items():
                settings.setValue(k, v)
            settings.endGroup()
        settings.endGroup()

        # Save Active Profile ID
        if self._current_active_profile_id and self._current_active_profile_id in self.profiles:
            settings.setValue("ui/active_profile_id", self._current_active_profile_id)
        elif self.profiles:
            first_profile_id = next(iter(self.profiles.keys()), None)
            settings.setValue("ui/active_profile_id", first_profile_id)
            print(f"[Settings] Warning: Saving fallback active profile ID: {first_profile_id}")
        else:
            settings.remove("ui/active_profile_id")
            print("[Settings] Warning: No profiles exist, clearing active profile ID.")

        # --- Save Proxies (Human-friendly, sorted) ---
        settings.beginGroup("proxies")
        for key in settings.childGroups():
            settings.remove(key)
        sorted_proxies = sorted(self.proxies.values(), key=lambda p: p.get('name', '').lower())
        for proxy in sorted_proxies:
            group_name = f"proxy:{proxy.get('name', proxy.get('id', 'Unknown'))}"
            settings.beginGroup(group_name)
            for k, v in proxy.items():
                settings.setValue(k, v)
            settings.endGroup()
        settings.endGroup()

        # --- Save Rules (Human-friendly, sorted) ---
        settings.beginGroup("rules")
        for key in settings.childGroups():
            settings.remove(key)
        # Only save rules with valid profile_id
        valid_rules_to_save = [r for r in self.rules.values() if r.get("profile_id") in self.profiles]
        sorted_rules = sorted(valid_rules_to_save, key=lambda r: r.get('domain', '').lower())
        for rule in sorted_rules:
            group_name = f"rule:{rule.get('domain', rule.get('id', 'Unknown'))}"
            settings.beginGroup(group_name)
            for k, v in rule.items():
                settings.setValue(k, v)
            settings.endGroup()
        settings.endGroup()

        # --- Save Hotkeys (Human-friendly) ---
        settings.beginGroup("hotkeys")
        settings.setValue("toggle_engine", self.toggle_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.NativeText))
        settings.setValue("show_hide_window", self.show_hide_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.NativeText))
        settings.setValue("next_profile", self.next_profile_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.NativeText))
        settings.setValue("prev_profile", self.prev_profile_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.NativeText))
        settings.setValue("quick_add_rule", self.quick_add_rule_hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.NativeText))
        settings.endGroup()

        # Save Startup Setting
        settings.setValue("app/start_engine_on_startup", self.start_engine_checkbox.isChecked())

        # Save System Proxy Setting (Windows only)
        if hasattr(self, 'enable_system_proxy_checkbox'):
            settings.setValue("app/set_system_proxy", self.enable_system_proxy_checkbox.isChecked())

        settings.sync() # Force writing to file
        print(f"[Settings] Saved {len(self.profiles)} profiles, {len(self.proxies)} proxies, {len(valid_rules_to_save)} rules.")
        print("[Settings] Sync complete.")

    def quit_application(self):
        """Save settings, stop listener, and quit the application."""
        print("Quit requested.")
        # --- Stop Hotkey Listener ---
        print("Stopping hotkey listener...")
        self.hotkey_manager.stop_listener()
        # ---
        self.save_settings()
        print("Stopping engine...")
        self.proxy_engine.stop() # Ensure engine is stopped cleanly
        print("Exiting.")
        QApplication.instance().quit()

    def _set_initial_active_view(self):
        """Sets the active view based on loaded settings or default."""
        settings = QSettings(self.settings_file, QSettings.Format.IniFormat)
        # Default to Rules (index 0) if nothing saved
        last_index = settings.value("ui/last_view_index", defaultValue=0, type=int)
        # Ensure index is valid for the *current* number of buttons/views
        last_index = max(0, min(last_index, self.main_content_area.count() - 1))

        if 0 <= last_index < len(self.sidebar_buttons):
            self.main_content_area.setCurrentIndex(last_index)
            button_to_activate = self.sidebar_buttons[last_index]
            # Check if button exists before setting checked state
            if button_to_activate:
                button_to_activate.setChecked(True)
                self._update_active_button_style(button_to_activate)
        elif self.sidebar_buttons: # Fallback to first button if index invalid or button missing
             default_index = 0
             self.main_content_area.setCurrentIndex(default_index)
             if self.sidebar_buttons[default_index]:
                self.sidebar_buttons[default_index].setChecked(True)
                self._update_active_button_style(self.sidebar_buttons[default_index])

    def _get_proxy_name_map(self) -> dict:
        """Helper to get a map of {proxy_id: proxy_name}."""
        return {pid: pdata.get('name', 'Unnamed') for pid, pdata in self.proxies.items()}

    def _get_profile_name_map(self) -> dict:
        """Helper to get {profile_id: profile_name} for existing profiles."""
        # Start with existing profiles
        names = {pid: pdata.get('name', 'Unnamed') for pid, pdata in self.profiles.items()}
        # ---> Remove the line adding the non-existent constant <---
        # names[None] = self.ALL_RULES_PROFILE_NAME # Map None ID to the display name
        return names

    def _show_add_rule_editor(self):
        """Display the rule editor for adding a new rule."""
        # Close proxy editor if open
        if self.proxy_edit_widget and self.proxy_edit_widget.isVisible():
            self._cancel_proxy_edit(animate=False)

        # Check if rule editor is already visible
        if hasattr(self, 'rule_edit_widget') and self.rule_edit_widget and self.rule_edit_widget.isVisible():
             print("[_show_add_rule_editor] Editor already visible.")
             # Optionally clear fields if clicked again while open?
             # self.rule_edit_widget.clear_fields()
             # self.rule_edit_widget.set_focus_on_domains()
             return

        # Ensure there is an active profile
        if not self._current_active_profile_id or self._current_active_profile_id not in self.profiles:
             QMessageBox.warning(self, "Cannot Add Rule", "Please select or create a valid profile before adding rules.")
             return
             
        # If we don't have a rule edit widget, create one
        if not hasattr(self, 'rule_edit_widget') or self.rule_edit_widget is None:
            print("[_show_add_rule_editor] Creating new rule editor widget...")
            self.rule_edit_widget = RuleEditWidget(self, self.proxies, self.profiles)
            self.rule_edit_widget.save_rules.connect(self._save_rule_entry)
            self.rule_edit_widget.cancelled.connect(lambda: self._cancel_rule_edit(animate=True))
            
            # Add the new widget to the container
            layout = self.rule_editor_container.layout()
            if layout:
                while layout.count():
                    item = layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                layout.addWidget(self.rule_edit_widget)

        # --- Prepare the existing editor ---
        print("[_show_add_rule_editor] Preparing rule editor...")
        self.rule_edit_widget.update_proxies(self.proxies)
        self.rule_edit_widget.update_profiles(self.profiles)
        self.rule_edit_widget.clear_fields() # Clear for adding
        # Set the profile combo to the current active profile
        profile_idx = self.rule_edit_widget.profile_combo.findData(self._current_active_profile_id)
        self.rule_edit_widget.profile_combo.setCurrentIndex(max(0, profile_idx if profile_idx != -1 else 0))
        # --- End Preparation ---

        # --- Prepare for animation ---
        # Make sure the container exists
        if not hasattr(self, 'rule_editor_container') or not self.rule_editor_container:
            print("[_show_add_rule_editor] Error: Rule editor container doesn't exist")
            QMessageBox.critical(self, "Error", "Rule editor container missing")
            return
            
        # Always create a new opacity effect to avoid using a deleted C++ object
        print("[_show_add_rule_editor] Creating new opacity effect")
        self.rule_edit_opacity_effect = QGraphicsOpacityEffect(self.rule_edit_widget)
        self.rule_edit_widget.setGraphicsEffect(self.rule_edit_opacity_effect)
            
        # Show the widget and make it fully opaque
        self.rule_edit_widget.setVisible(True)      # Make inner widget visible
        self.rule_edit_opacity_effect.setOpacity(1.0) # Ensure fully opaque
        
        # Make sure the container is visible
        self.rule_editor_container.setVisible(True)
        self.rule_editor_container.setMaximumHeight(1) # Allow container expansion
        QApplication.processEvents()

        target_height = self._calculate_editor_height(self.rule_edit_widget)
        if target_height <= 0:
            print("Warning: Calculated zero height for rule editor, cannot animate open.")
            self.rule_edit_widget.setVisible(False) # Hide it again
            self.rule_editor_container.setMaximumHeight(0) # Collapse container
            self.add_rule_button.setEnabled(True) # Re-enable button
            return

        self.add_rule_button.setEnabled(False)

        # --- Animate open ---
        if hasattr(self, 'rule_editor_animation') and self.rule_editor_animation and self.rule_editor_animation.state() == QPropertyAnimation.State.Running:
            self.rule_editor_animation.stop()
            self._clear_rule_animation_ref()

        print("[_show_add_rule_editor] Starting container height animation...")
        # Animate container height ONLY
        self.rule_editor_container.setMaximumHeight(0) # Ensure starting height is 0
        self.rule_editor_animation = QPropertyAnimation(self.rule_editor_container, b"maximumHeight")
        self.rule_editor_animation.setDuration(250) # Adjust duration if needed
        self.rule_editor_animation.setStartValue(0)
        self.rule_editor_animation.setEndValue(target_height)
        self.rule_editor_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # --- Connect finished signals ---
        # Ensure inner widget's max height allows it to be seen after container animates
        self.rule_editor_animation.finished.connect(lambda: self.rule_edit_widget.setMaximumHeight(target_height))
        self.rule_editor_animation.finished.connect(self.rule_edit_widget.set_focus_on_domains)
        self.rule_editor_animation.finished.connect(self._clear_rule_animation_ref)
        # --- Start ---
        self.rule_editor_animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped) # Auto-delete anim

    def _show_edit_rule_editor(self, rule_id: str):
        """Opens the editor pane pre-filled with data for a specific rule."""
        print(f"[_show_edit_rule_editor] Request to edit rule ID: {rule_id}")
        # Close proxy editor if open
        if self.proxy_edit_widget:
            self._cancel_proxy_edit(animate=False)

        # Close existing rule editor immediately if a different one is open
        if self.rule_edit_widget and getattr(self.rule_edit_widget, '_editing_rule_id', None) != rule_id:
            print(f"[_show_edit_rule_editor] Closing existing editor for rule {getattr(self.rule_edit_widget, '_editing_rule_id', None)}.")
            self._cancel_rule_edit(animate=False)
        elif self.rule_edit_widget:
            print(f"[_show_edit_rule_editor] Editor for rule {rule_id} already open.")
            self.rule_edit_widget.set_focus_on_domains() # Just focus if already open
            return

        rule_data = self.rules.get(rule_id)
        if not rule_data:
            QMessageBox.warning(self, "Error", f"Rule with ID '{rule_id}' not found.")
            return

        print(f"[_show_edit_rule_editor] Found rule data: {rule_data}")

        # Create and configure the editor widget
        self.rule_edit_widget = RuleEditWidget(self, self.proxies, self.profiles, rule_data, self)
        self.rule_edit_widget.save_rules.connect(self._save_rule_entry)
        self.rule_edit_widget.cancelled.connect(lambda: self._cancel_rule_edit(animate=True))

        # ---> ADD CHECK HERE <---
        if not self.rule_edit_widget:
             print("[_show_edit_rule_editor] Error: Failed to create RuleEditWidget instance.")
             QMessageBox.critical(self, "Error", "Failed to create rule editor widget.")
             return
        # ---> END CHECK <---

        # Create a new opacity effect for this editor
        self.rule_edit_opacity_effect = QGraphicsOpacityEffect(self.rule_edit_widget)
        self.rule_edit_widget.setGraphicsEffect(self.rule_edit_opacity_effect)
        self.rule_edit_opacity_effect.setOpacity(1.0) # Ensure fully opaque

        print("[_show_edit_rule_editor] Rule editor widget created.")
        # Make sure combo boxes are up-to-date *before* loading data
        self.rule_edit_widget.update_proxies(self.proxies)
        self.rule_edit_widget.update_profiles(self.profiles)
        self.rule_edit_widget.load_data(rule_data) # Load data *after* combos are populated

        # Clear existing layout content safely
        layout = self.rule_editor_container.layout()
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        # Add the new editor
        layout.addWidget(self.rule_edit_widget)
        print("[_show_edit_rule_editor] Added rule editor to container layout.")

        # ---> Check/Set container visibility/height <---
        target_height = self._calculate_editor_height(self.rule_edit_widget)
        print(f"Calculated target height: {target_height}")

        if not self.rule_editor_container.isVisible() or self.rule_editor_container.height() == 0:
            print("[_show_edit_rule_editor] Container hidden, animating open.")
            self.rule_editor_container.setMaximumHeight(0) # Ensure starting height is 0
            self.rule_editor_container.show()
            self._clear_rule_animation_ref() # Clear previous before starting new
            self.rule_editor_animation = self._animate_widget_height(self.rule_editor_container, 0, target_height)
            print("[_show_edit_rule_editor] Starting container height animation...")
        else:
            # Already visible, potentially resizing (e.g., switching editors)
            print("[_show_edit_rule_editor] Container visible, animating resize.")
            start_height = self.rule_editor_container.height()
            if start_height != target_height:
                self._clear_rule_animation_ref() # Clear previous before starting new
                self.rule_editor_animation = self._animate_widget_height(self.rule_editor_container, start_height, target_height)
                print("[_show_edit_rule_editor] Starting container resize animation...")
            else:
                 # Already at target height, just ensure focus
                 print("[_show_edit_rule_editor] Container already at target height.")
                 self.rule_edit_widget.set_focus_on_domains()
                 self.rule_editor_animation = None # No animation needed

        # Only connect/start if an animation was created
        if self.rule_editor_animation:
            # --- Connect finished signals ---
            # Ensure inner widget's max height allows it to be seen after container animates
            self.rule_editor_animation.finished.connect(lambda: self.rule_edit_widget.setMaximumHeight(target_height))
            self.rule_editor_animation.finished.connect(self.rule_edit_widget.set_focus_on_domains)
            self.rule_editor_animation.finished.connect(self._clear_rule_animation_ref)
            # --- Start ---
            self.rule_editor_animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped) # Auto-delete anim
        else:
             # No animation, ensure widget is sized correctly immediately
             self.rule_edit_widget.setMaximumHeight(target_height)

    def _cancel_rule_edit(self, animate=True):
        """Hides and cleans up the rule editor widget."""
        print(f"[Cancel Rule Edit] Called with animate={animate}")
        if not self.rule_edit_widget or not self.rule_editor_container:
            print("[Cancel Rule Edit] No editor or container to cancel.")
            return

        editor_to_close = self.rule_edit_widget
        container_to_hide = self.rule_editor_container

        # Clear internal reference FIRST
        self.rule_edit_widget = None

        if animate:
            print("[Cancel Rule Edit] Animating closed.")
            start_height = container_to_hide.height()
            end_height = 0
            self._clear_rule_animation_ref() # Clear previous before starting new

            self.rule_edit_animation = self._animate_widget_height(container_to_hide, start_height, end_height)

            def cleanup_after_animation():
                try:
                    if container_to_hide: # Check if container still exists
                        container_to_hide.hide()
                    if editor_to_close: # Check if editor still exists
                        print("[Cancel Rule Edit] Deleting editor after animation.")
                        editor_to_close.deleteLater()
                    # Set focus back to list only after animation finishes
                    if self.rules_list_widget: # Check if list widget exists
                        self.rules_list_widget.setFocus()
                    # Re-enable the add rule button
                    if hasattr(self, 'add_rule_button'):
                        self.add_rule_button.setEnabled(True)
                except RuntimeError as e:
                     # This can happen if the window is closed during animation
                     print(f"[Animation Warning] Error in cleanup: {e}")
                finally:
                     self._clear_rule_animation_ref() # Clear ref on finish/error

            self.rule_edit_animation.finished.connect(cleanup_after_animation)
            self.rule_edit_animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        else:
            # No animation, just hide and delete immediately and reliably
            print("[Cancel Rule Edit] Hiding and deleting immediately (no animation).")
            container_to_hide.hide() # Hide container first

            # Remove the editor widget from its layout *before* deleting
            container_layout = container_to_hide.layout()
            if editor_to_close and container_layout:
                print("[Cancel Rule Edit] Removing editor widget from layout.")
                container_layout.removeWidget(editor_to_close)
                # Explicitly set parent to None before deleteLater
                editor_to_close.setParent(None)
                print("[Cancel Rule Edit] Editor widget parent set to None.")

            container_to_hide.setFixedHeight(0) # Set height after potentially removing content

            if editor_to_close:
                print("[Cancel Rule Edit] Scheduling editor deletion (deleteLater).")
                editor_to_close.deleteLater()

            # Set focus back to list
            if self.rules_list_widget:
                self.rules_list_widget.setFocus()
                # Ensure list updates its layout if needed
                self.rules_list_widget.updateGeometry()

        # Always clear focus from any potential leftover input field
        # Add try-except as the widget might be deleted by the time this runs
        if editor_to_close and hasattr(editor_to_close, 'domain_input') and editor_to_close.domain_input:
            try:
                 # Check if the widget still exists/has C++ peer before accessing clearFocus
                 if editor_to_close and editor_to_close.isVisible(): # Basic check
                      editor_to_close.domain_input.clearFocus()
                      print("[Cancel Rule Edit] Cleared focus from domain input.")
                 else:
                      print("[Cancel Rule Edit] Domain input focus clear skipped (widget likely hidden/deleted).")
            except RuntimeError: # Catches "Internal C++ object already deleted"
                 print("[Cancel Rule Edit] Could not clear focus, editor already deleted.")
                 pass # Ignore if already deleted

        # Re-enable the add rule button (whether animated or not)
        if hasattr(self, 'add_rule_button'):
            self.add_rule_button.setEnabled(True)
            print("[Cancel Rule Edit] Re-enabled Add Rule button.")

    def _clear_rule_animation_ref(self):
        """Clear the rule animation reference."""
        print("[Animation] Clearing rule animation reference.")
        try:
            # Ensure container stays open and visible if animation finished successfully at non-zero height
            if self.rule_editor_animation and self.rule_editor_animation.endValue() > 0:
                self.rule_editor_container.setMaximumHeight(self.rule_editor_animation.endValue())
                # Make sure the container is visible
                self.rule_editor_container.setVisible(True)
                # Ensure the widget itself is visible too
                if hasattr(self, 'rule_edit_widget') and self.rule_edit_widget:
                    self.rule_edit_widget.setVisible(True)
                    # Set maximum height on widget to match container
                    self.rule_edit_widget.setMaximumHeight(self.rule_editor_animation.endValue())
            
            # Safely disconnect any remaining connections
            if self.rule_editor_animation and hasattr(self.rule_editor_animation, 'finished'):
                try:
                    self.rule_editor_animation.finished.disconnect()
                except:
                    pass 
                 
        except Exception as e:
            print(f"[Animation Warning] Error in cleanup: {e}")
        
        # Always clear the reference
        self.rule_editor_animation = None

    def _save_rule_entry(self, domain_port_tuples: list, proxy_id: str, profile_id: str):
        """Handles saving a new or edited rule entry, with port/port range support."""
        print(f"[Rule Edit Save] Received save request: {domain_port_tuples}, Proxy={proxy_id}, Profile={profile_id}")

        if not profile_id:
             QMessageBox.warning(self, "Save Error", "Cannot save rule: Profile ID is missing.")
             return

        editing_existing = bool(self.rule_edit_widget and self.rule_edit_widget._editing_rule_id)
        rule_id_to_select = None # ID of the rule to scroll to

        if editing_existing:
            rule_id = self.rule_edit_widget._editing_rule_id
            if rule_id not in self.rules:
                 QMessageBox.critical(self, "Error", f"Cannot save: Rule ID '{rule_id}' not found in internal data.")
                 return
            if len(domain_port_tuples) != 1:
                 QMessageBox.warning(self, "Save Error", "Cannot edit multiple domains. Please provide only one.")
                 return
            domain, port = domain_port_tuples[0]
            self.rules[rule_id]['domain'] = domain
            self.rules[rule_id]['proxy_id'] = proxy_id
            self.rules[rule_id]['profile_id'] = profile_id
            if port:
                self.rules[rule_id]['port'] = port
            elif 'port' in self.rules[rule_id]:
                del self.rules[rule_id]['port']
            print(f"[Rules] Updated rule ID {rule_id}: Domain='{domain}', Proxy='{proxy_id}', Profile='{profile_id}', Port={port}")
            rule_id_to_select = rule_id
        else:
            new_rule_ids = []
            for domain, port in domain_port_tuples:
                 existing_id = self._find_rule_by_domain_and_profile(domain, profile_id)
                 if existing_id:
                      reply = QMessageBox.question(self, "Duplicate Rule",
                                                f"A rule for '{domain}' already exists in profile '{self.profiles.get(profile_id, {}).get('name', profile_id)}'.\n\nDo you want to overwrite it?",
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                QMessageBox.StandardButton.No)
                      if reply == QMessageBox.StandardButton.Yes:
                           self.rules[existing_id]['proxy_id'] = proxy_id
                           if port:
                               self.rules[existing_id]['port'] = port
                           elif 'port' in self.rules[existing_id]:
                               del self.rules[existing_id]['port']
                           print(f"[Rules] Overwrote rule ID {existing_id} for domain '{domain}'.")
                           if rule_id_to_select is None:
                                rule_id_to_select = existing_id
                      else:
                           print(f"[Rules] Skipped adding duplicate rule for domain '{domain}'.")
                           continue
                 else:
                      new_id = str(uuid.uuid4())
                      rule = {
                          "id": new_id,
                          "domain": domain,
                          "proxy_id": proxy_id,
                          "profile_id": profile_id,
                          "enabled": True
                      }
                      if port:
                          rule["port"] = port
                      self.rules[new_id] = rule
                      print(f"[Rules] Added new rule ID {new_id} for domain '{domain}', Port={port}.")
                      if rule_id_to_select is None:
                           rule_id_to_select = new_id
        def complete_save_process():
            print("[Save Rule] Rebuilding rule list...")
            self._rebuild_rule_list_safely()
            if rule_id_to_select:
                print(f"[Save Rule] Scheduling scroll to rule ID: {rule_id_to_select}")
                self._safely_scroll_to_rule(rule_id_to_select)
            print("[Save Rule] Closing rule editor...")
            if self.rule_edit_widget:
                 self._cancel_rule_edit(animate=False)
            else:
                 print("[Save Rule] Editor already closed/None.")
            print("[Save Rule] Saving settings...")
            self.save_settings()
            action = "Updated" if editing_existing else "Added"
            domain_text = domain_port_tuples[0][0] if len(domain_port_tuples) == 1 else f"{len(domain_port_tuples)} domains"
            self.show_status_message(f"Rule(s) {action}: {domain_text}", 3000)
            if hasattr(self, 'add_rule_button'):
                self.add_rule_button.setEnabled(True)
                print("[Save Rule] Re-enabled Add Rule button.")
        complete_save_process()

    def _safely_scroll_to_rule(self, rule_id):
        """Safely attempt to scroll to a rule, with error handling."""
        try:
            if rule_id and hasattr(self, 'rules_list_widget'):
                self._scroll_to_item(self.rules_list_widget, rule_id)
        except Exception as e:
            print(f"[Error] Failed to scroll to rule {rule_id}: {e}")
            # Just log the error, don't affect the user experience

    def _delete_rule_entry(self, rule_id: str):
        """Deletes a rule entry with seamless UI update."""
        if rule_id in self.rules:
            try:
                print(f"[Rules] Deleting rule ID: {rule_id}")
                rule_profile_id = self.rules[rule_id].get('profile_id')
                rule_domain = self.rules[rule_id].get('domain', 'unknown')
                
                # Store the profile ID for engine update
                profile_id = rule_profile_id
                
                # First, find and remove the list item directly (without clearing the entire list)
                target_item = None
                target_row = -1
                
                # Find the list item with this rule_id
                for row in range(self.rules_list_widget.count()):
                    item = self.rules_list_widget.item(row)
                    if item and item.data(Qt.ItemDataRole.UserRole) == rule_id:
                        target_item = item
                        target_row = row
                        break
                
                # Remove from the data model first
                del self.rules[rule_id]
                print(f"[Rules] Deleted rule ID: {rule_id} (domain: {rule_domain})")
                
                # Remove the specific widget and list item
                if target_item:
                    # Take the item from the list without deleting the entire list
                    self.rules_list_widget.takeItem(target_row)
                    
                    # Clean up the associated widget
                    if rule_id in self.rule_widgets:
                        widget = self.rule_widgets.pop(rule_id, None)
                        if widget:
                            # Detach from parent and schedule for deletion
                            if widget.parent():
                                widget.setParent(None)
                            widget.deleteLater()
                    
                    # Ensure the item is deleted 
                    del target_item
                
                # Save settings
                self.save_settings()
                
                # Update engine if running and the rule was in the active profile
                if self.proxy_engine.is_active and profile_id == self._current_active_profile_id:
                    self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)
                
                # Update the rule count label
                self._update_rule_count_label()
                
                # Update the rules title label
                self._update_rules_title_label()
                
                # Show confirmation message
                self.show_status_message("Rule deleted.")
                
                # Process events to ensure UI updates
                QApplication.processEvents()
                
            except Exception as e:
                print(f"[Error] Exception during rule deletion: {e}")
                self.show_status_message(f"Error deleting rule: {e}")
        else:
            self.show_status_message(f"Error: Rule ID '{rule_id}' not found for deletion.")

    def _toggle_rule_enabled(self, rule_id: str, enabled: bool):
        """Handles the toggle signal from RuleItemWidget."""
        if rule_id in self.rules:
            if self.rules[rule_id].get("enabled") == enabled:
                return # No change

            self.rules[rule_id]["enabled"] = enabled
            print(f"[Rules] Toggled rule '{rule_id}' to enabled={enabled}")

            # Update the specific widget's style immediately
            if rule_id in self.rule_widgets:
                self.rule_widgets[rule_id].set_enabled_style(enabled)

            # Update engine if running and the rule is in the active profile
            rule_profile_id = self.rules[rule_id].get('profile_id')
            if self.proxy_engine.is_active and rule_profile_id == self._current_active_profile_id:
                 self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)

            self.save_settings()
            self.show_status_message(f"Rule {'enabled' if enabled else 'disabled'}.")
        else:
            print(f"Error: Cannot toggle rule - ID '{rule_id}' not found.")

    def _populate_rule_list(self):
        """Populates the QListWidget with rule items for all profiles, regardless of active profile."""
        try:
            # Clear list first - disconnects widgets
            self.rules_list_widget.clear()
            
            # Delete old widgets if necessary 
            widgets_to_remove = []
            for rule_id, widget in self.rule_widgets.items():
                try:
                    if widget.parent():
                        widget.setParent(None)
                    # Mark for removal if the rule no longer exists
                    if rule_id not in self.rules:
                        widgets_to_remove.append(rule_id)
                except Exception as e:
                    print(f"[Error] Widget cleanup error for rule {rule_id}: {e}")
                    widgets_to_remove.append(rule_id)
            
            # Clean up deleted rules' widgets
            for rule_id in widgets_to_remove:
                try:
                    widget = self.rule_widgets.pop(rule_id, None)
                    if widget:
                        widget.deleteLater()
                except Exception as e:
                    print(f"[Error] Failed to remove widget for rule {rule_id}: {e}")
            
            # Don't filter rules by active profile ID - show all rules
            all_rules = list(self.rules.values())

            # Sort rules (e.g., by domain)
            all_rules.sort(key=lambda r: r.get('domain', '').lower())

            proxy_map = self._get_proxy_name_map()
            profile_map = self._get_profile_name_map() # Contains all profile names

            print(f"[Populate] Adding {len(all_rules)} rules to list.")
            
            for rule_data in all_rules:
                rule_id = rule_data.get('id')
                if not rule_id:
                    continue
                    
                try:
                    # Create or update the widget
                    widget = None
                    if rule_id in self.rule_widgets:
                        # Update existing widget
                        widget = self.rule_widgets[rule_id]
                        widget.update_data(rule_data, proxy_map, profile_map)
                        widget.set_theme(self.current_theme)
                    else:
                        # Create a new widget
                        widget = RuleItemWidget(rule_data, proxy_map, profile_map, theme_name=self.current_theme)
                        widget.edit_rule.connect(self._show_edit_rule_editor)
                        widget.delete_rule.connect(self._delete_rule_entry)
                        widget.toggle_enabled.connect(self._toggle_rule_enabled)
                        self.rule_widgets[rule_id] = widget
                    
                    # Create list item and add widget to it
                    item = QListWidgetItem()
                    item.setData(Qt.ItemDataRole.UserRole, rule_id)
                    item.setSizeHint(widget.sizeHint())
                    self.rules_list_widget.addItem(item)
                    self.rules_list_widget.setItemWidget(item, widget)
                except Exception as e:
                    print(f"[Error] Failed to create/add rule widget for {rule_id}: {e}")

            # Update count and visibility AFTER all items are added
            QTimer.singleShot(0, self._update_rule_count_label)
            
            # Make sure the list always stays visible if it has items
            has_rules = len(all_rules) > 0
            if has_rules:
                self.rules_list_widget.setVisible(True)
                self.rules_placeholder_widget.setVisible(False)
            else:
                self.rules_list_widget.setVisible(False)
                self.rules_placeholder_widget.setVisible(True)
                
            # If we have a filter applied, re-apply it to update visibility
            if hasattr(self, 'rule_filter_bar'):
                filter_input = self.rule_filter_bar.findChild(QLineEdit)
                if filter_input and filter_input.text():
                    QTimer.singleShot(10, lambda: self._filter_rule_list(filter_input.text()))
        except Exception as e:
            print(f"[Error] Rule list population failed: {e}")
            # Make sure list is still visible in case of error
            self.rules_list_widget.setVisible(True)
            self.rules_placeholder_widget.setVisible(False)

    def _update_rule_count_label(self):
        """Updates the label showing the number of rules visible in the list."""
        try:
            # Count only items that are not hidden
            visible_count = 0
            for i in range(self.rules_list_widget.count()):
                item = self.rules_list_widget.item(i)
                if item and not item.isHidden():
                    visible_count += 1

            # Get total count of rules from data model
            total_count = len(self.rules)

            # Update the count label text
            self.rules_count_label.setText(f"{visible_count} rule{'s' if visible_count != 1 else ''}")
            
            print(f"[Count] Rules - visible: {visible_count}, total in model: {total_count}")
            
            # Determine visibility based on:
            # 1. Are there any rules in the data model?
            # 2. Are any rules visible in the list widget?
            has_rules_in_model = (total_count > 0)
            has_visible_rules = (visible_count > 0)
            
            # Show placeholder when:
            # - No rules exist at all, OR
            # - We have rules but none are visible (filtered out)
            should_show_placeholder = not has_rules_in_model or (has_rules_in_model and not has_visible_rules)
            
            # Rules list should be visible when:
            # - We have at least one visible rule, OR
            # - We have rules but just need to rebuild the UI (happens during deletion)
            should_show_list = has_visible_rules or (has_rules_in_model and self.rules_list_widget.count() == 0)
            
            # Force correct visibility of UI elements
            self.rules_list_widget.setVisible(should_show_list and not should_show_placeholder)
            self.rules_placeholder_widget.setVisible(should_show_placeholder)
            
            print(f"[UI] Rule visibility updated - visible: {visible_count}, total: {total_count}, " 
                  f"showing placeholder: {should_show_placeholder}, showing list: {should_show_list}")
            
            # If there are rules in the model but none in the list widget, 
            # trigger a safe rebuild to ensure UI is in sync with data
            if has_rules_in_model and self.rules_list_widget.count() == 0:
                print("[UI] Data model has rules but list widget is empty, triggering rebuild")
                QTimer.singleShot(0, self._rebuild_rule_list_safely)
                
        except Exception as e:
            print(f"[Error] Failed to update rule count/visibility: {e}")
            # In case of error, default to showing the list widget
            self.rules_list_widget.setVisible(True)
            self.rules_placeholder_widget.setVisible(False)

    def _calculate_editor_height(self, editor_widget: QWidget) -> int:
        """Calculate the required height for the editor widget."""
        # Ensure layout is updated
        editor_widget.layout().activate()
        # Use layout size hint as it's often more reliable
        height = editor_widget.layout().sizeHint().height()
        height += 15 # Buffer
        # Ensure a minimum height in case calculation fails
        height = max(height, 150) # Example minimum height
        print(f"Calculated target height: {height}")
        return height

    def _show_add_proxy_editor(self):
        """Display the proxy editor for adding a new proxy."""
        # Close rule editor if open
        if self.rule_edit_widget and self.rule_edit_widget.isVisible():
            self._cancel_rule_edit(animate=False)

        # Check if already visible
        if self.proxy_edit_widget.isVisible():
            return

        self.proxy_edit_widget.clear_fields()
        self.proxy_edit_widget.setVisible(True)
        self.proxy_editor_container.setMaximumHeight(1) # Allow container expansion
        QApplication.processEvents()

        target_height = self._calculate_editor_height(self.proxy_edit_widget)
        if target_height <= 0:
             print("Warning: Calculated zero height for proxy editor.")
             self.proxy_edit_widget.setVisible(False); self.proxy_editor_container.setMaximumHeight(0)
             return

        self.add_proxy_button.setEnabled(False)

        if self.proxy_editor_animation and self.proxy_editor_animation.state() == QPropertyAnimation.State.Running:
            self.proxy_editor_animation.stop(); self._clear_proxy_animation_ref()

        # ---> Animate the proxy container <---
        self.proxy_editor_container.setMaximumHeight(0) # Start at 0
        self.proxy_editor_animation = QPropertyAnimation(self.proxy_editor_container, b"maximumHeight")
        self.proxy_editor_animation.setDuration(250)
        self.proxy_editor_animation.setStartValue(0)
        self.proxy_editor_animation.setEndValue(target_height)
        self.proxy_editor_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.proxy_editor_animation.finished.connect(lambda: self.proxy_edit_widget.setMaximumHeight(target_height))
        self.proxy_editor_animation.finished.connect(self.proxy_edit_widget.set_focus_on_name)
        self.proxy_editor_animation.finished.connect(self._clear_proxy_animation_ref)
        self.proxy_editor_animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _show_edit_proxy_editor(self, proxy_id: str):
        # ... (check proxy_id, close rule editor) ...
        # ---> Check/Set container visibility/height <---
        if not self.proxy_edit_widget.isVisible():
             self.proxy_edit_widget.setVisible(True) # Make inner widget visible
             self.proxy_editor_container.setMaximumHeight(1) # Allow container expansion
             start_height = 0
        else:
            start_height = self.proxy_editor_container.height()

        QApplication.processEvents()
        self.proxy_edit_widget.load_data(self.proxies[proxy_id])
        target_height = self._calculate_editor_height(self.proxy_edit_widget)
        if target_height <= 0: return

        self.add_proxy_button.setEnabled(False)

        if self.proxy_editor_animation and self.proxy_editor_animation.state() == QPropertyAnimation.State.Running:
            self.proxy_editor_animation.stop(); self._clear_proxy_animation_ref()

        # ---> Animate container <---
        self.proxy_editor_container.setMaximumHeight(start_height)
        self.proxy_editor_animation = QPropertyAnimation(self.proxy_editor_container, b"maximumHeight")
        self.proxy_editor_animation.setDuration(250)
        self.proxy_editor_animation.setStartValue(start_height)
        self.proxy_editor_animation.setEndValue(target_height)
        self.proxy_editor_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.proxy_editor_animation.finished.connect(lambda: self.proxy_edit_widget.setMaximumHeight(target_height))
        self.proxy_editor_animation.finished.connect(self.proxy_edit_widget.set_focus_on_name)
        self.proxy_editor_animation.finished.connect(self._clear_proxy_animation_ref)
        self.proxy_editor_animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _cancel_proxy_edit(self, animate=True):
        """Hides the proxy editor without saving, optionally animating."""
        if not self.proxy_edit_widget or not self.proxy_edit_widget.isVisible():
             if hasattr(self, 'add_proxy_button'): self.add_proxy_button.setEnabled(True)
             return

        # ---> Use correct container variable <---
        current_height = self.proxy_editor_container.height()
        if self.proxy_editor_animation and self.proxy_editor_animation.state() == QPropertyAnimation.State.Running:
            self.proxy_editor_animation.stop(); self._clear_proxy_animation_ref()

        if hasattr(self, 'add_proxy_button'): self.add_proxy_button.setEnabled(True)

        if animate and current_height > 0:
            # ---> Animate correct container <---
            local_animation = QPropertyAnimation(self.proxy_editor_container, b"maximumHeight")
            local_animation.setDuration(250)
            local_animation.setStartValue(current_height)
            local_animation.setEndValue(0)
            local_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

            self.proxy_editor_animation = local_animation
            local_animation.finished.connect(self.proxy_edit_widget.clear_fields)
            local_animation.finished.connect(lambda: self.proxy_edit_widget.setVisible(False))
            # Set inner widget max height to 0 AFTER animation
            local_animation.finished.connect(lambda: self.proxy_edit_widget.setMaximumHeight(0))
            local_animation.finished.connect(self._clear_proxy_animation_ref)
            local_animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        else:
            self.proxy_edit_widget.setVisible(False)
            # ---> Set correct container height <---
            self.proxy_editor_container.setMaximumHeight(0)
            self.proxy_edit_widget.setMaximumHeight(0) # Also set inner widget max height
            self.proxy_edit_widget.clear_fields()
            self._clear_proxy_animation_ref()

    def _clear_proxy_animation_ref(self):
        """Clear the proxy animation reference and ensure final state."""
        print("[Animation] Clearing proxy animation reference.")
        # Ensure container stays open if animation finished successfully at non-zero height
        if self.proxy_editor_animation and self.proxy_editor_animation.endValue() > 0:
             self.proxy_editor_container.setMaximumHeight(16777215)
        self.proxy_editor_animation = None

    def _clear_proxy_editor_on_cancel(self):
         """Helper to clear fields and manage visibility state after cancel."""
         # If an item was hidden during edit, show it again (needed if we implement that)
         # editing_id = getattr(self.proxy_edit_widget, '_editing_id', None)
         # if editing_id and editing_id in self.proxy_widgets:
         #      self.proxy_widgets[editing_id].setVisible(True)
         self.proxy_edit_widget.clear_fields()

    def _save_proxy_entry(self, proxy_data: dict):
        """Saves a new or updated proxy entry."""
        is_new = proxy_data.get("id") is None
        proxy_id = proxy_data["id"] or str(uuid.uuid4())
        proxy_data["id"] = proxy_id # Ensure ID is set

        # Add or update status (default to unknown if new)
        proxy_data['status'] = self.proxies.get(proxy_id, {}).get('status', 'unknown') if not is_new else 'unknown'

        self.proxies[proxy_id] = proxy_data
        print(f"[Proxies] {'Added' if is_new else 'Updated'} proxy: {proxy_data.get('name')} (ID: {proxy_id})")

        # Update or add the widget in the list
        self._add_proxy_widget(proxy_data)

        # Update rules view if proxy names changed
        if not is_new:
            self._update_rule_widgets_proxy_names()

        # --- Update Engine Config ALWAYS ---
        print("[UI] Updating engine config after proxy save...")
        self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)
        # ---

        self._cancel_proxy_edit()
        self.save_settings()
        self.proxy_engine.test_proxy(proxy_id)
        self.show_status_message(f"Proxy '{proxy_data['name']}' saved.")

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
            if self.rule_edit_widget is not None:
                self.rule_edit_widget.update_proxies(self.proxies)
            self._update_rule_widgets_proxy_names()
            self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)
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
        # --- Patch: Ensure engine config is up-to-date before testing ---
        def _safe_test_proxy(proxy_id):
            self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)
            self.proxy_engine.test_proxy(proxy_id)
        item_widget.test_requested.connect(_safe_test_proxy)
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
        """Handles the main toggle button click."""
        if checked: # User wants to turn ON
            if not self._current_active_profile_id:
                 QMessageBox.warning(self, "Cannot Start Engine", "No active profile selected. Please select or create a profile.")
                 self._update_toggle_button_state("inactive") # Force button back visually
                 return
            # Update engine with current config before starting
            # ---> Pass the active profile ID to update_config <---
            self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)
            success = self.proxy_engine.start()
            if success:
                 # Test proxies only if explicitly requested or on first start?
                 # self.proxy_engine.test_all_proxies() # Optional: test on start
                 pass
            else:
                 self._update_toggle_button_state("error") # Reflect start failure

            # System proxy (Windows)
            if IS_WINDOWS and self.enable_system_proxy_checkbox.isChecked():
                self._set_windows_proxy(True, proxy_port=self.proxy_engine.listening_port)

        else: # User wants to turn OFF
            self.proxy_engine.stop()
            # System proxy (Windows)
            if IS_WINDOWS and self.enable_system_proxy_checkbox.isChecked():
                self._set_windows_proxy(False) # Disable system proxy

        # Update UI based on actual engine state via signals
        # The status_changed signal will call _handle_engine_status_update_ui


    def _handle_engine_status_update_ui(self, status: str):
        """Update UI elements based on engine status changes."""
        print(f"[UI] Engine status changed to: {status}")
        
        # If we're in the middle of switching profiles, don't show intermediate states
        if self._is_switching_profiles and (status == "inactive" or status == "stopping"):
            print("[UI] Ignoring intermediate status during profile switch")
            return
        
        self._update_toggle_button_state(status)
        self.update_tray_status(status)

        # Update proxy item statuses
        status_to_set = "unknown"
        if status == "active":
             status_to_set = "unknown" # Reset to unknown, let tests update
             # Optionally trigger tests when engine becomes active
             # self.proxy_engine.test_all_proxies()
        elif status == "inactive" or status == "error" or status == "stopping":
             status_to_set = "inactive" # Set all to inactive visually
             # Reset test button states if engine stops/errors
             for proxy_widget in self.proxy_widgets.values():
                 proxy_widget.set_status(status_to_set)


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
        is_active = (status == 'active' or status == 'starting' or status == 'switching')
        is_error = (status == 'error')
        is_starting = (status == 'starting')
        is_stopping = (status == 'stopping')
        is_switching = (status == 'switching')
        
        self.toggle_proxy_button.setChecked(is_active) # Set checked state first

        # Determine color and icon path based on NEW state
        toggle_state = "checked" if is_active else ("error" if is_error else "default")
        toggle_icon_color = self._get_main_icon_color("toggle", state=toggle_state)

        # Choose the correct icon path based on status
        toggle_icon_path = None  # For toggle itself
        if is_error:
            toggle_icon_path = TOGGLE_ERROR_ICON_PATH # Will now point to toggle-error.svg
        elif is_active or is_starting or is_switching:
            toggle_icon_path = TOGGLE_ON_ICON_PATH  # Will now point to toggle-right.svg
        else: # inactive or stopping
            toggle_icon_path = TOGGLE_OFF_ICON_PATH # Will now point to toggle-left.svg

        # ---> Check if icon file exists before loading <---
        if os.path.exists(toggle_icon_path):
            toggle_svg = load_and_colorize_svg_content(toggle_icon_path, toggle_icon_color)
            if toggle_svg:
                self.toggle_proxy_button.setIcon(create_icon_from_svg_data(toggle_svg))
            else:
                print(f"Warning: Failed to load/colorize toggle icon: {toggle_icon_path}")
                self.toggle_proxy_button.setIcon(QIcon()) # Clear icon
                self.toggle_proxy_button.setText("?") # Fallback text
        else:
            print(f"Error: Icon file not found at {toggle_icon_path}")
            self.toggle_proxy_button.setIcon(QIcon()) # Clear icon
            # Set fallback text based on state
            fallback_text = "ON" if is_active else ("ERR" if is_error else "OFF")
            self.toggle_proxy_button.setText(fallback_text)
        # ---> End check <---

        # Update tooltip
        if is_error:
            tooltip = "Proxy Engine ERROR"
        elif is_switching:
            tooltip = "Switching Active Profile..."
        elif is_active:
            tooltip = "Proxy Engine is ON"
        elif is_starting:
            tooltip = "Proxy Engine is Starting..."
        elif is_stopping:
            tooltip = "Proxy Engine is Stopping..."
        else:
            tooltip = "Proxy Engine is OFF"
        
        self.toggle_proxy_button.setToolTip(tooltip)

    def _handle_close_setting_change(self):
        """Update close behavior based on checkbox."""
        self.close_behavior = "minimize" if self.close_to_tray_checkbox.isChecked() else "exit"
        self.save_settings() # Save setting immediately

    def _handle_proxy_test_result(self, proxy_id: str, is_ok: bool):
        """Updates the status of a specific proxy item in the list."""
        if proxy_id in self.proxy_widgets:
            widget = self.proxy_widgets[proxy_id]
            new_status = "active" if is_ok else "error"
            widget.set_status(new_status)
            # Also update the status in the main data dictionary
            if proxy_id in self.proxies:
                 self.proxies[proxy_id]['status'] = new_status
                 # Optionally save settings immediately after a test result? Probably not necessary.
                 # self.save_settings()
        else:
            print(f"[UI Update] Received test result for unknown/hidden proxy ID: {proxy_id}")

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
        """Save the current hotkey settings preference, checking for conflicts."""
        sequences = [
            (self.toggle_hotkey_edit.keySequence(), "Toggle Engine"),
            (self.show_hide_hotkey_edit.keySequence(), "Show/Hide Window"),
            (self.next_profile_hotkey_edit.keySequence(), "Next Profile"),
            (self.prev_profile_hotkey_edit.keySequence(), "Previous Profile"),
            (self.quick_add_rule_hotkey_edit.keySequence(), "Quick Add Rule") # Add new hotkey to check
        ]
        active_sequences = {}
        conflict = False
        for seq, name in sequences:
            if not seq.isEmpty():
                # Use NativeText for saving/displaying, but pynput string for conflict check
                pynput_str = self._qkeysequence_to_pynput(seq)
                if pynput_str:
                    if pynput_str in active_sequences:
                        QMessageBox.warning(self, "Hotkey Conflict", f"The hotkey '{seq.toString(QKeySequence.SequenceFormat.NativeText)}' conflicts with '{active_sequences[pynput_str]}'.\nPlease ensure all assigned hotkeys are unique.")
                        conflict = True
                        break # Stop checking after first conflict
                    active_sequences[pynput_str] = name
                else:
                     # Handle case where conversion failed but sequence wasn't empty
                     print(f"[Hotkey Save] Warning: Could not convert '{seq.toString()}' for conflict check.")


        # Only save and re-register if no conflicts found
        if not conflict:
            print("[Hotkey Save] Hotkey preferences saved. Re-registering.")
            self.save_settings() # Save the preferences to file
            self._load_and_register_hotkeys() # Re-register with the manager
        else:
             print("[Hotkey Save] Hotkey preferences not saved or re-registered due to conflict.")

    # --- Placeholder functions for profile switching ---
    def _switch_to_next_profile(self):
        """Switches the active profile to the next one in the list."""
        if not self.profiles:
            self.show_status_message("No profiles available to switch.", 3000)
            return

        # Use active_profile_combo for cycling
        current_index = self.active_profile_combo.currentIndex()
        count = self.active_profile_combo.count()

        if count <= 1:
            self.show_status_message("Only one profile exists.", 3000)
            return

        next_index = (current_index + 1) % count
        self.active_profile_combo.setCurrentIndex(next_index)
        # Trigger the handler manually as programmatic changes might not emit currentIndexChanged
        self._handle_active_profile_change(next_index)
        new_profile_name = self.active_profile_combo.currentText()
        self.show_status_message(f"Switched to profile: {new_profile_name}", 3000)
        print(f"[Hotkey Action] Switched to next profile: {new_profile_name}")


    def _switch_to_prev_profile(self):
        """Switches the active profile to the previous one in the list."""
        if not self.profiles:
            self.show_status_message("No profiles available to switch.", 3000)
            return

        # Use active_profile_combo for cycling
        current_index = self.active_profile_combo.currentIndex()
        count = self.active_profile_combo.count()

        if count <= 1:
            self.show_status_message("Only one profile exists.", 3000)
            return

        prev_index = (current_index - 1 + count) % count
        self.active_profile_combo.setCurrentIndex(prev_index)
        # Trigger the handler manually
        self._handle_active_profile_change(prev_index)
        new_profile_name = self.active_profile_combo.currentText()
        self.show_status_message(f"Switched to profile: {new_profile_name}", 3000)
        print(f"[Hotkey Action] Switched to previous profile: {new_profile_name}")

    # --- Profile Management Methods ---

    def _update_profile_selectors(self):
        """Updates profile selectors (main active combo and profile list widget)."""
        print("[UI] Updating profile selectors...")

        # Store current selections to restore if possible
        current_active_id = self._current_active_profile_id # Use the internal state variable

        # ---> Correctly get data from QListWidget's current *item* <---
        current_list_item = self.profile_list_widget.currentItem()
        current_list_id = current_list_item.data(Qt.ItemDataRole.UserRole) if current_list_item else None
        # <--- End correction ---

        # --- Update Main Active Profile ComboBox ---
        self.active_profile_combo.blockSignals(True)
        self.active_profile_combo.clear()
        if self.profiles:
            sorted_profiles = sorted(self.profiles.items(), key=lambda item: item[1].get('name', '').lower())
            for profile_id, profile_data in sorted_profiles:
                self.active_profile_combo.addItem(profile_data.get('name', 'Unnamed'), profile_id)
            # Restore selection
            idx = self.active_profile_combo.findData(current_active_id)
            self.active_profile_combo.setCurrentIndex(max(0, idx)) # Select first if not found
        else:
             self.active_profile_combo.addItem("No Profiles", None) # Placeholder
        self.active_profile_combo.blockSignals(False)

        # --- Update Settings Page Profile List Widget ---
        self.profile_list_widget.blockSignals(True)
        self.profile_list_widget.clear()
        if self.profiles:
            sorted_profiles_list = sorted(self.profiles.items(), key=lambda item: item[1].get('name', '').lower())
            for profile_id, profile_data in sorted_profiles_list:
                item = QListWidgetItem(profile_data.get('name', 'Unnamed'))
                item.setData(Qt.ItemDataRole.UserRole, profile_id)
                self.profile_list_widget.addItem(item)
            # Restore selection
            new_row_to_select = -1
            for i in range(self.profile_list_widget.count()):
                if self.profile_list_widget.item(i).data(Qt.ItemDataRole.UserRole) == current_list_id:
                     new_row_to_select = i
                     break
            self.profile_list_widget.setCurrentRow(max(0, new_row_to_select)) # Select first if not found
        self.profile_list_widget.blockSignals(False)
        
        # --- Update Tray Menu Profiles ---
        if hasattr(self, 'profiles_menu'):
            # Clear previous actions
            self.profiles_menu.clear()
            if hasattr(self, 'profile_action_group'):
                # Remove old actions from the group
                for action in self.profile_action_group.actions():
                    self.profile_action_group.removeAction(action)
            
            # Add profile actions
            if self.profiles:
                sorted_profiles = sorted(self.profiles.items(), key=lambda item: item[1].get('name', '').lower())
                for profile_id, profile_data in sorted_profiles:
                    profile_name = profile_data.get('name', 'Unnamed')
                    profile_action = QAction(profile_name, self)
                    profile_action.setCheckable(True)
                    profile_action.setData(profile_id)
                    # Check if this is the current active profile
                    if profile_id == current_active_id:
                        profile_action.setChecked(True)
                    # Add to action group and menu
                    self.profile_action_group.addAction(profile_action)
                    self.profiles_menu.addAction(profile_action)
                    # Connect action to handler - using a method to avoid variable capture issues
                    profile_action.triggered.connect(self._create_profile_action_handler(profile_id))

        # Update button states based on list selection AFTER repopulating
        # Pass the current item itself to the handler
        self._update_profile_button_states(self.profile_list_widget.currentItem(), None) # Call with current item

        # Update rules title label AFTER selectors are updated
        self._update_rules_title_label()

        print(f"[UI] Profile selectors updated. Active: {self.active_profile_combo.currentText()}, List Selected: {self.profile_list_widget.currentItem().text() if self.profile_list_widget.currentItem() else 'None'}")

    def _handle_tray_profile_selection(self, profile_id: str):
        """Handle profile selection from the tray menu."""
        if not profile_id or profile_id not in self.profiles:
            print(f"[Profile] Error: Invalid profile ID selected from tray: {profile_id}")
            return
        
        if profile_id == self._current_active_profile_id:
            print(f"[Profile] Profile '{profile_id}' already active.")
            return
        
        print(f"[Tray] Profile selected from tray menu: {self.profiles[profile_id].get('name', 'Unknown')}")
        
        # Find the profile index in the combo box
        idx = self.active_profile_combo.findData(profile_id)
        if idx >= 0:
            # This will trigger the normal profile change handler
            self.active_profile_combo.setCurrentIndex(idx)
        else:
            print(f"[Profile] Error: Could not find profile '{profile_id}' in combo box")

    def _update_profile_button_states(self, current_item: QListWidgetItem | None, previous_item: QListWidgetItem | None):
        """
        Enable/disable Rename/Delete buttons based on selection in QListWidget.
        Accepts QListWidgetItem arguments.
        """
        selected_profile_id = None
        if current_item: # Check if the current item is valid (not None)
            selected_profile_id = current_item.data(Qt.ItemDataRole.UserRole)
        print(f"DEBUG: _update_profile_button_states (QListWidget) - Selected ID: {selected_profile_id}")

        # Determine if buttons should be enabled (only for actual profiles)
        # Check if the selected_profile_id exists in our profiles dictionary
        can_modify = selected_profile_id is not None and selected_profile_id in self.profiles

        # Ensure buttons exist before trying to enable/disable them
        if hasattr(self, 'rename_profile_button'):
            self.rename_profile_button.setEnabled(can_modify)
        if hasattr(self, 'delete_profile_button'):
            # Add extra check: Don't allow deleting the *last* profile
            can_delete = can_modify and len(self.profiles) > 1
            self.delete_profile_button.setEnabled(can_delete)

    def _handle_active_profile_change(self, index: int):
        """Called when the active profile combo box selection changes."""
        if index < 0: return # Should not happen with valid combo

        new_profile_id = self.active_profile_combo.itemData(index)

        if not new_profile_id or new_profile_id not in self.profiles:
             print(f"[Profile] Error: Selected invalid profile ID '{new_profile_id}' at index {index}.")
             # Revert selection? Find first valid? For now, do nothing.
             return

        if new_profile_id == self._current_active_profile_id:
            print(f"[Profile] Profile '{new_profile_id}' already active.")
            return # No change

        # --- Update State ---
        print(f"[Profile] Switching active profile to: {new_profile_id} ({self.profiles[new_profile_id].get('name', 'N/A')})")
        self._current_active_profile_id = new_profile_id
        
        # --- Update Tray Menu ---
        if hasattr(self, 'profile_action_group'):
            for action in self.profile_action_group.actions():
                action_profile_id = action.data()
                action.setChecked(action_profile_id == new_profile_id)

        # --- Update Engine (if active) ---
        engine_was_active = self.proxy_engine.is_active
        if engine_was_active:
            # Set profile switching flag
            self._is_switching_profiles = True
            
            # Immediately update UI to "switching" status to avoid flickering
            # This prevents "stopping" and "inactive" states from being shown to the user
            self._handle_engine_status_update_ui("switching")
            self.show_status_message(f"Switching to profile: {self.profiles[new_profile_id]['name']}...", 5000)
            
            print("[Profile] Restarting proxy engine to close all connections and use new active profile rules...")
            # First stop the engine to close all connections
            self.proxy_engine.stop()
            # Wait a brief moment to ensure all connections are properly closed
            QTimer.singleShot(100, lambda: self._restart_engine_with_new_profile())
        else:
            # If engine wasn't active, just update the configuration
            self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)

        # --- Update UI ---
        # Rules display doesn't change when switching profiles since we show all rules
        # BUT we need to update the title label to show active profile
        self._update_rules_title_label()
        
        # ---> Pass current item from profile_list_widget to the handler <---
        self._update_profile_button_states(self.profile_list_widget.currentItem(), None)
        # Clear rule filter text if applicable
        if hasattr(self, 'rule_filter_bar'):
            filter_input = self.rule_filter_bar.findChild(QLineEdit)
            if filter_input:
                filter_input.clear()

        # --- Persist Change ---
        self.save_settings()
        if not engine_was_active:
            self.show_status_message(f"Switched to profile: {self.profiles[new_profile_id]['name']}")

    def _restart_engine_with_new_profile(self):
        """Helper method to restart the engine with the current active profile after stopping it."""
        # Update the engine with the new profile's rules
        self.proxy_engine.update_config(self.rules, self.proxies, self._current_active_profile_id)
        # Start the engine again
        self.proxy_engine.start()
        # Update system proxy settings if enabled
        if hasattr(self, 'enable_system_proxy_checkbox') and self.enable_system_proxy_checkbox.isChecked():
            self._set_windows_proxy(True, "127.0.0.1", self.proxy_engine.listening_port, "<local>")
        
        # We will let the normal engine status signal handling update the UI when the engine is fully active
        # This avoids setting the status prematurely
        
        # Clear profile switching flag only after the engine is restarted
        # The status signal will update the UI accordingly
        self._is_switching_profiles = False
        
        # Show success message
        self.show_status_message(f"Successfully switched to profile: {self.profiles[self._current_active_profile_id]['name']}", 3000)

    def _add_profile(self):
        """Adds a new profile."""
        profile_name, ok = QInputDialog.getText(self, "New Profile", "Enter name for the new profile:")
        if ok and profile_name:
            profile_name = profile_name.strip()
            if not profile_name:
                 QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
                 return
            # Check for duplicate names
            if any(p.get('name', '').lower() == profile_name.lower() for p in self.profiles.values()):
                 QMessageBox.warning(self, "Duplicate Name", "A profile with this name already exists.")
                 return

            new_id = str(uuid.uuid4())
            self.profiles[new_id] = {"id": new_id, "name": profile_name}
            print(f"[Profile] Added profile: {profile_name} (ID: {new_id})")

            # Refresh UI selectors
            self._update_profile_selectors()
            # Set the new profile as active
            new_index = self.active_profile_combo.findData(new_id)
            if new_index != -1:
                self.active_profile_combo.setCurrentIndex(new_index)
                # Trigger the handler to update everything else
                # self._handle_active_profile_change(new_index) # setCurrentIndex should trigger it

            self.save_settings()
        elif ok: # User pressed OK but entered no name
             QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")

    def _rename_profile(self):
        """Handles renaming the selected profile."""
        selected_item = self.profile_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Rename Profile", "Please select a profile to rename.")
            return

        # ---> Correctly get data from QListWidget <---
        profile_id = selected_item.data(Qt.ItemDataRole.UserRole) # Get data using UserRole
        if not profile_id or profile_id not in self.profiles:
            QMessageBox.critical(self, "Error", "Could not find data for the selected profile.")
            return

        current_name = self.profiles[profile_id].get('name', '')
        new_name, ok = QInputDialog.getText(self, "Rename Profile",
                                            f"Enter new name for '{current_name}':",
                                            QLineEdit.EchoMode.Normal, current_name)

        if ok and new_name:
            if new_name != current_name:
                # Check for duplicate name
                if any(p_id != profile_id and p.get('name', '').lower() == new_name.lower() for p_id, p in self.profiles.items()): # Case-insensitive check
                    QMessageBox.warning(self, "Duplicate Name", f"A profile named '{new_name}' already exists.")
                    return
                self.profiles[profile_id]['name'] = new_name
                print(f"Renamed profile ID {profile_id} to '{new_name}'")
                self._update_profile_selectors() # This will re-select the current item
                self._update_rule_widgets_proxy_names()  # <-- Add this line to update rule widgets with new profile names
                self.save_settings()

    def _delete_profile(self):
        """Deletes the currently selected profile."""
        # Get selected profile from profile_list_widget
        selected_item = self.profile_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Profile Selected", "Please select a profile to delete.")
            return

        # Get the profile ID from the selected item
        profile_to_delete_id = selected_item.data(Qt.ItemDataRole.UserRole)
        if not profile_to_delete_id or profile_to_delete_id not in self.profiles:
            QMessageBox.warning(self, "Error", "Could not find data for the selected profile.")
            return

        # Check if this is the active profile
        if profile_to_delete_id == self._current_active_profile_id:
            QMessageBox.warning(self, "Cannot Delete Active Profile", 
                               "You cannot delete the currently active profile.\nPlease switch to another profile first.")
            return

        # Prevent deleting the last profile
        if len(self.profiles) <= 1:
             QMessageBox.warning(self, "Cannot Delete", "Cannot delete the last profile.")
             return

        profile_to_delete_name = self.profiles[profile_to_delete_id].get('name', 'N/A')

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the profile '{profile_to_delete_name}'?\n\n"
            f"All rules associated with this profile will also be permanently deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Yes:
            print(f"[Profile] Deleting profile: {profile_to_delete_name} (ID: {profile_to_delete_id})")
            del self.profiles[profile_to_delete_id]

            # Delete associated rules
            rules_to_delete = [rule_id for rule_id, rule_data in self.rules.items()
                               if rule_data.get('profile_id') == profile_to_delete_id]
            if rules_to_delete:
                 print(f"[Profile] Deleting {len(rules_to_delete)} rules associated with profile '{profile_to_delete_name}'.")
                 for rule_id in rules_to_delete:
                      del self.rules[rule_id]
                 # Clear corresponding widgets if they exist (though list will be repopulated)
                 for rule_id in rules_to_delete:
                      if rule_id in self.rule_widgets:
                           self.rule_widgets.pop(rule_id).deleteLater()

            # Update UI
            self._update_profile_selectors() # Update combo box content
            self._populate_rule_list()       # <-- Add this to refresh rule widgets and counts

            # Persist
            self.save_settings()
            self.show_status_message(f"Profile '{profile_to_delete_name}' deleted.")

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
        """Clears the key sequence in the specified widget and saves."""
        key_sequence_edit_widget.clear()
        # Call the specific save function for hotkeys to check conflicts
        self._save_hotkey_setting()

    # --- Filter Widgets ---
    def _create_filter_bar(self, placeholder_text: str, filter_slot, include_count_label=False) -> QWidget:
        """Creates a simple filter bar widget with optional count label."""
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(15, 5, 15, 5) # Less vertical margin
        filter_input = QLineEdit()  # Local variable instead of self attribute
        filter_input.setPlaceholderText(placeholder_text)
        filter_input.setClearButtonEnabled(True)
        filter_input.textChanged.connect(filter_slot)
        filter_layout.addWidget(filter_input)
        
        # Add a count label if requested
        if include_count_label:
            # Create a label to show count (will be populated elsewhere)
            count_label = QLabel("0")
            count_label.setObjectName("CountLabel")
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            count_label.setContentsMargins(0, 0, 0, 0)
            filter_layout.addWidget(count_label)
            # Store this so it can be updated from the appropriate update method
            if placeholder_text.lower().startswith("filter rules"):
                self.rules_count_label = count_label
            else:
                self.proxies_count_label = count_label
        
        return filter_widget

    # --- Specific filtering methods directly implemented for each list ---
    def _filter_rule_list(self, text: str):
        """Filters the visible rule widgets based on input text."""
        try:
            filter_lower = text.lower().strip() if text else ""
            print(f"[Filter] Filtering rules with text: '{filter_lower}'")
            
            # Track if we're hiding/showing any items
            any_visible = False
            visible_count = 0
            total_count = 0
            
            # Process all items in the list widget
            for i in range(self.rules_list_widget.count()):
                item = self.rules_list_widget.item(i)
                if not item:
                    continue
                    
                total_count += 1
                    
                # Get the rule ID stored in the item's data
                rule_id = item.data(Qt.ItemDataRole.UserRole)
                if not rule_id or rule_id not in self.rules:
                    item.setHidden(True)
                    continue
                
                # Get rule data
                rule_data = self.rules.get(rule_id)
                if not rule_data:
                    item.setHidden(True)
                    continue
                
                # Build search string from rule data
                search_string = ""
                
                # Add domain (most important for searching)
                domain = rule_data.get('domain', '')
                if domain:
                    search_string += domain.lower() + " "
                    
                # Add proxy name if applicable
                proxy_id = rule_data.get('proxy_id')
                if proxy_id and proxy_id in self.proxies:
                    search_string += self.proxies[proxy_id].get('name', '').lower() + " "
                    
                # Add profile name if applicable
                profile_id = rule_data.get('profile_id')
                if profile_id and profile_id in self.profiles:
                    search_string += self.profiles[profile_id].get('name', '').lower() + " "
                
                # Check if the filter text is in the search string
                # If no filter text, show everything
                is_visible = not filter_lower or filter_lower in search_string
                item.setHidden(not is_visible)
                
                # Track if we have any visible items
                if is_visible:
                    any_visible = True
                    visible_count += 1
            
            # Update the count label only after all items have been processed
            self._update_rule_count_label()
            
            # Update visibility of placeholder based on whether we have any visible items
            if self.rules_list_widget.count() > 0:
                show_placeholder = not any_visible
                self.rules_placeholder_widget.setVisible(show_placeholder)
                self.rules_list_widget.setVisible(not show_placeholder)
            
            # Debug information
            print(f"[UI] Rule visibility updated - visible: {visible_count}, total: {total_count}, showing placeholder: {not any_visible}")
            print(f"[Filter] Filter completed, any_visible: {any_visible}")
            
        except Exception as e:
            print(f"[Error] Rule filtering failed: {e}")
            # In case of filtering error, make all items visible
            for i in range(self.rules_list_widget.count()):
                item = self.rules_list_widget.item(i)
                if item:
                    item.setHidden(False)
            self._update_rule_count_label()
            # Always ensure list is visible in case of error
            self.rules_list_widget.setVisible(True)
            self.rules_placeholder_widget.setVisible(False)

    def _filter_proxy_list(self, text: str):
        """Filters the visible proxy widgets based on input text."""
        filter_lower = text.lower()
        
        # Process all proxy widgets
        for proxy_id, widget in self.proxy_widgets.items():
            if proxy_id not in self.proxies:
                widget.setVisible(False)
                continue
                
            # Get proxy data
            proxy_data = self.proxies.get(proxy_id)
            if not proxy_data:
                widget.setVisible(False)
                continue
                
            # Build search string from proxy data
            search_string = ""
            
            # Add name, address, and other relevant fields
            for key, value in proxy_data.items():
                if key not in ['id', 'password', 'status', 'requires_auth'] and value:
                    search_string += str(value).lower() + " "
            
            # Check if the filter text is in the search string
            # If no filter text, show everything
            is_visible = not filter_lower or filter_lower in search_string
            widget.setVisible(is_visible)
        
        # Update the count label
        self._update_proxy_count_label()

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
        # Count visible proxies by checking widget visibility
        visible_count = 0
        for proxy_widget in self.proxy_widgets.values():
            if proxy_widget.isVisible():
                visible_count += 1
                
        # Also show total count of proxies for clarity
        total_count = len(self.proxies)
        self.proxies_count_label.setText(f"{total_count} proxy{'ies' if total_count != 1 else ''}")

    def closeEvent(self, event):
        """Handle window close event (X button) based on setting."""
        # Ensure editors are closed instantly before hide/quit
        self._cancel_proxy_edit(animate=False)
        self._cancel_rule_edit(animate=False)

        # If fully exiting (not hiding to tray):
        if self.close_behavior == "exit" or self._force_quit:
             print("[App] Exiting application...")
             # Stop the hotkey listener first
             print("[App Exit] Stopping hotkey listener...")
             self.hotkey_manager.stop_listener()
             # Stop the engine
             self.proxy_engine.stop()
             # --- Add Windows Proxy Disable on Exit ---
             if platform.system() == "Windows":
                  print("[App Exit] Disabling system proxy before exiting...")
                  self._set_windows_proxy(enable=False)
             # --- End Add ---
             # Save settings one last time
             self.save_settings()
             print("[App Exit] Settings saved. Accepting close event.")
             event.accept()
        else:
            # Hide to tray behavior
            print("[App] Hiding window to system tray.")
            event.ignore() # Prevent closing
            self.hide() # Hide the main window

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
        """Opens the folder containing the settings.ini file."""
        config_dir = os.path.dirname(self.settings_file)
        print(f"Opening settings folder: {config_dir}")
        if os.path.exists(config_dir):
            try:
                if platform.system() == "Windows":
                    os.startfile(config_dir) # Use os.startfile on Windows
                elif platform.system() == "Darwin": # macOS
                    subprocess.Popen(["open", config_dir])
                else: # Linux and other Unix-like
                    subprocess.Popen(["xdg-open", config_dir])
            except Exception as e:
                print(f"Error opening settings folder: {e}")
                QMessageBox.warning(self, "Error", f"Could not open settings folder automatically.\nPath: {config_dir}\nError: {e}")
        else:
            QMessageBox.warning(self, "Error", f"Settings folder does not exist:\n{config_dir}")

    # --- Add Reset Method ---
    def _reset_all_settings(self):
        """Resets all settings to default values."""
        reply = QMessageBox.warning(
            self, "Confirm Reset",
            "Are you sure you want to reset ALL settings?\n"
            "This will clear all profiles, proxies, rules, hotkeys, and UI preferences.\n"
            "The application will close after reset.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Yes:
            print("[Settings] Resetting all settings...")

            # Stop engine and listeners
            if self.proxy_engine.is_active: self.proxy_engine.stop()
            self.hotkey_manager.stop_listener()

            # Clear data stores
            self.profiles.clear()
            self.proxies.clear()
            self.rules.clear()
            self._current_active_profile_id = None

            # Clear UI widgets
            # ---> Correctly clear rule list and widgets <---
            self.rules_list_widget.clear() # Clear the list widget items
            # Delete the actual widget instances we stored
            for rule_id, widget in self.rule_widgets.items():
                 widget.deleteLater()
            self.rule_widgets.clear() # Clear the dictionary holding the widgets
            # ---> Correctly clear proxy list and widgets <---
            # Clear widgets from the layout first
            while self.proxy_list_layout.count():
                 item = self.proxy_list_layout.takeAt(0)
                 widget = item.widget()
                 if widget:
                      widget.deleteLater()
            # Clear the dictionary holding the proxy widgets
            self.proxy_widgets.clear()
            # Update counts
            self._update_proxy_count_label()
            self._update_rule_count_label()
            # ---> End list clearing correction <---

            # Clear settings file
            settings = QSettings(self.settings_file, QSettings.Format.IniFormat)
            settings.clear()
            settings.sync() # Ensure cleared state is written

            # Reset UI elements to default states
            self.theme_combo.setCurrentIndex(0) # Default to Dark
            self.apply_theme('dark')
            self.close_to_tray_checkbox.setChecked(True) # Default to minimize
            self.start_engine_checkbox.setChecked(False) # Default to off
            if IS_WINDOWS:
                self.enable_system_proxy_checkbox.setChecked(False)
            self.toggle_hotkey_edit.clear()
            self.show_hide_hotkey_edit.clear()
            self.next_profile_hotkey_edit.clear()
            self.prev_profile_hotkey_edit.clear()
            self.quick_add_rule_hotkey_edit.clear()

            # Re-run initial setup steps? Or just quit? Quit is safer.
            QMessageBox.information(self, "Reset Complete", "Settings have been reset. The application will now close.")
            self._force_quit = True # Set flag to ensure quit
            self.close() # Close the window, which will trigger quit
    # --- End Reset Method ---

    # --- Quick Add Rule Implementation ---

    def _trigger_quick_add_rule(self):
        """
        Handles the hotkey/action to open the Quick Add Rule dialog.
        Attempts copy simulation *before* reading clipboard.
        """
        print("[Quick Add] Triggered in MainWindow.")

        # --- Simulate Copy FIRST ---
        copy_success = False
        if self.hotkey_manager and self.hotkey_manager._listener_worker:
            print("[Quick Add] Attempting copy simulation via HotkeyManager worker...")
            try:
                # Access the simulation method on the worker instance
                copy_success = self.hotkey_manager._listener_worker._simulate_copy_combined()
                print(f"[Quick Add] Copy simulation result: {copy_success}")
            except Exception as e:
                print(f"[Quick Add] Error calling copy simulation: {e}")
        else:
            print("[Quick Add] HotkeyManager or worker not available for copy simulation.")

        # --- Wait briefly for clipboard to potentially update ---
        print("[Quick Add] Waiting briefly for clipboard...")
        time.sleep(0.2) # Adjust delay if needed (0.1 to 0.3 is typical)

        # --- Now, proceed to get rule from clipboard (which just reads) ---
        print("[Quick Add] Calling QuickRuleAddDialog.get_rule_from_clipboard...")
        QuickRuleAddDialog.get_rule_from_clipboard(self)

    def _handle_quick_rule_save(self, domain: str, proxy_id: str | None, profile_id: str | None):
        """Handles saving a rule from the QuickRuleAddDialog."""
        # ---> Corrected Log Message <---
        print(f"[Quick Save] Received: Domain='{domain}', Proxy='{proxy_id}', Profile='{profile_id}'") # Directly print proxy_id

        if not profile_id:
            QMessageBox.warning(self, "Save Error", "Cannot save rule: No profile selected or profile invalid.")
            print("[Quick Save] Error: profile_id is missing.")
            return
        if not domain:
             QMessageBox.warning(self, "Save Error", "Cannot save rule: Domain/IP cannot be empty.")
             print("[Quick Save] Error: domain is missing.")
             return

        # Check if a rule with the same domain/IP already exists IN THIS PROFILE
        existing_rule_id = self._find_rule_by_domain_and_profile(domain, profile_id)

        # ---> Add Logging for Existing Check <---
        print(f"[Quick Save] Check result for existing rule: ID='{existing_rule_id}'")

        if existing_rule_id:
            # ---> Add Logging for Update Path <---
            print(f"[Quick Save] Updating existing rule '{existing_rule_id}'...")
            # Update existing rule: only change the proxy_id
            self.rules[existing_rule_id]['proxy_id'] = proxy_id
            # Optionally update 'enabled' status if needed, but typically quick add shouldn't disable
            # self.rules[existing_rule_id]['enabled'] = True
            QTimer.singleShot(50, lambda: self.show_status_message(f"Rule updated for '{domain}'"))
            rule_id_to_scroll = existing_rule_id
        else:
            # ---> Add Logging for Add Path <---
            print(f"[Quick Save] No existing rule found. Adding new rule...")
            # Add new rule
            new_rule_id = str(uuid.uuid4())
            self.rules[new_rule_id] = {
                "id": new_rule_id,
                "domain": domain, # Store the validated/cleaned domain
                "proxy_id": proxy_id, # Can be None for Direct
                "profile_id": profile_id, # Assign to the selected profile
                "enabled": True # Default to enabled
            }
            print(f"[Quick Save] Added new rule '{new_rule_id}' for domain '{domain}' in profile '{profile_id}'.")
            QTimer.singleShot(50, lambda: self.show_status_message(f"Rule added for '{domain}'"))
            rule_id_to_scroll = new_rule_id

        # Debounce populate/save/scroll
        self._rebuild_rule_list_safely() # Handles populate, filter, counts
        self.save_settings() # Save changes
        # Scroll after list is rebuilt and potentially filtered
        QTimer.singleShot(100, lambda: self._safely_scroll_to_rule(rule_id_to_scroll))

    # --- End Quick Add Rule Implementation ---

    # --- >> Ensure these helpers are indented correctly within the MainWindow class << ---
    def _create_separator(self) -> QFrame:
        """Creates a horizontal line separator."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("SettingsSeparator") # For styling
        return separator

    def _create_clear_hotkey_button(self, target_edit: QKeySequenceEdit, hotkey_name: str) -> QToolButton:
        """Creates a clear button for a hotkey."""
        button = QToolButton()
        button.setText("X") # Use a clear symbol
        button.setObjectName("ClearHotkeyButton")
        button.setToolTip(f"Clear {hotkey_name} hotkey")
        # Use lambda to ensure correct target_edit is passed
        button.clicked.connect(lambda: self._clear_hotkey(target_edit))
        return button

    def _create_hotkey_row(self, key_edit: QKeySequenceEdit, clear_button: QToolButton) -> QWidget:
         """Creates a widget containing the key edit and clear button."""
         widget = QWidget()
         layout = QHBoxLayout(widget)
         layout.setContentsMargins(0,0,0,0)
         layout.setSpacing(5)
         layout.addWidget(key_edit, stretch=1)
         layout.addWidget(clear_button)
         return widget
    # --- End Helper Methods ---

    def _qkeysequence_to_pynput(self, q_sequence: QKeySequence) -> str | None:
        """Converts a QKeySequence (first combo) to a pynput-compatible string."""
        if q_sequence.isEmpty():
            return None

        # QKeySequence can represent multiple combinations (e.g., Ctrl+A, Ctrl+B)
        # We only support the first one for global hotkeys for simplicity.
        key_combination = q_sequence[0] # Get the first QKeyCombination

        modifiers = key_combination.keyboardModifiers()
        key = key_combination.key()

        pynput_modifiers = []
        # Order might matter for pynput. Let's try Ctrl, Alt, Shift, Meta.
        if modifiers & Qt.KeyboardModifier.ControlModifier: pynput_modifiers.append("<ctrl>")
        if modifiers & Qt.KeyboardModifier.AltModifier: pynput_modifiers.append("<alt>")
        if modifiers & Qt.KeyboardModifier.ShiftModifier: pynput_modifiers.append("<shift>")
        if modifiers & Qt.KeyboardModifier.MetaModifier: pynput_modifiers.append("<cmd>") # Use <cmd> for Meta/Win key

        # --- Key Mapping ---
        # This map needs to be comprehensive for common keys
        qt_to_pynput_map = {
            # Letters (lowercase)
            Qt.Key.Key_A: 'a', Qt.Key.Key_B: 'b', Qt.Key.Key_C: 'c', Qt.Key.Key_D: 'd',
            Qt.Key.Key_E: 'e', Qt.Key.Key_F: 'f', Qt.Key.Key_G: 'g', Qt.Key.Key_H: 'h',
            Qt.Key.Key_I: 'i', Qt.Key.Key_J: 'j', Qt.Key.Key_K: 'k', Qt.Key.Key_L: 'l',
            Qt.Key.Key_M: 'm', Qt.Key.Key_N: 'n', Qt.Key.Key_O: 'o', Qt.Key.Key_P: 'p',
            Qt.Key.Key_Q: 'q', Qt.Key.Key_R: 'r', Qt.Key.Key_S: 's', Qt.Key.Key_T: 't',
            Qt.Key.Key_U: 'u', Qt.Key.Key_V: 'v', Qt.Key.Key_W: 'w', Qt.Key.Key_X: 'x',
            Qt.Key.Key_Y: 'y', Qt.Key.Key_Z: 'z',
            # Numbers
            Qt.Key.Key_0: '0', Qt.Key.Key_1: '1', Qt.Key.Key_2: '2', Qt.Key.Key_3: '3',
            Qt.Key.Key_4: '4', Qt.Key.Key_5: '5', Qt.Key.Key_6: '6', Qt.Key.Key_7: '7',
            Qt.Key.Key_8: '8', Qt.Key.Key_9: '9',
            # Function Keys
            Qt.Key.Key_F1: '<f1>', Qt.Key.Key_F2: '<f2>', Qt.Key.Key_F3: '<f3>', Qt.Key.Key_F4: '<f4>',
            Qt.Key.Key_F5: '<f5>', Qt.Key.Key_F6: '<f6>', Qt.Key.Key_F7: '<f7>', Qt.Key.Key_F8: '<f8>',
            Qt.Key.Key_F9: '<f9>', Qt.Key.Key_F10: '<f10>', Qt.Key.Key_F11: '<f11>', Qt.Key.Key_F12: '<f12>',
            # Add F13-F24 if needed and supported by pynput - pynput uses vk codes for these usually
            # Navigation & Editing
            Qt.Key.Key_Space: '<space>',
            Qt.Key.Key_Enter: '<enter>', Qt.Key.Key_Return: '<enter>', # Map both Qt variants
            Qt.Key.Key_Tab: '<tab>', Qt.Key.Key_Backtab: '<shift>+<tab>', # Handle Shift+Tab
            Qt.Key.Key_Backspace: '<backspace>',
            Qt.Key.Key_Delete: '<delete>',
            Qt.Key.Key_Insert: '<insert>',
            Qt.Key.Key_Escape: '<esc>',
            Qt.Key.Key_Home: '<home>',
            Qt.Key.Key_End: '<end>',
            Qt.Key.Key_PageUp: '<page_up>',
            Qt.Key.Key_PageDown: '<page_down>',
            Qt.Key.Key_Up: '<up>',
            Qt.Key.Key_Down: '<down>',
            Qt.Key.Key_Left: '<left>',
            Qt.Key.Key_Right: '<right>',
            # Punctuation & Symbols (use literal character)
            Qt.Key.Key_Comma: ',', Qt.Key.Key_Period: '.', Qt.Key.Key_Slash: '/',
            Qt.Key.Key_Semicolon: ';', Qt.Key.Key_Colon: ':', # Qt usually gives base key, shift handled by modifier
            Qt.Key.Key_Apostrophe: "'", Qt.Key.Key_QuoteDbl: '"',
            Qt.Key.Key_BracketLeft: '[', Qt.Key.Key_BracketRight: ']',
            Qt.Key.Key_BraceLeft: '{', Qt.Key.Key_BraceRight: '}',
            Qt.Key.Key_Backslash: '\\', Qt.Key.Key_Minus: '-', Qt.Key.Key_Equal: '=',
            Qt.Key.Key_Plus: '+', Qt.Key.Key_Underscore: '_',
            Qt.Key.Key_AsciiTilde: '~', Qt.Key.Key_QuoteLeft: '`', # Backtick
            # Add more mappings as needed...
        }
        # Special case for Shift+Tab from Qt.Key_Backtab
        pynput_key = None
        if key == Qt.Key.Key_Backtab:
            if "<shift>" not in pynput_modifiers:
                pynput_modifiers.append("<shift>")
            pynput_key = "<tab>"
        else:
            pynput_key = qt_to_pynput_map.get(key)

        if pynput_key is None:
            print(f"[Hotkey Conversion] Warning: Unmapped Qt key code: {key}. Hotkey might not work.")
            return None

        # Combine modifiers and key
        # Ensure key is added last
        full_combo = "+".join(pynput_modifiers + [pynput_key])
        print(f"[Hotkey Conversion] Converted '{q_sequence.toString()}' to '{full_combo}'")
        return full_combo
    # --- End Converter ---

    def _load_and_register_hotkeys(self):
        """Loads hotkeys from settings, translates, and registers them."""
        settings = QSettings(self.settings_file, QSettings.Format.IniFormat)
        hotkey_map = {} # {pynput_string: manager_signal_name}

        # Load sequence strings from settings
        toggle_seq_str = settings.value("hotkeys/toggle_proxy", "", type=str)
        show_hide_seq_str = settings.value("hotkeys/show_hide_window", "", type=str)
        next_prof_seq_str = settings.value("hotkeys/next_profile", "", type=str)
        prev_prof_seq_str = settings.value("hotkeys/prev_profile", "", type=str)
        quick_add_seq_str = settings.value("hotkeys/quick_add_rule", "", type=str)

        # Convert and map to signal names
        seq_map = {
            toggle_seq_str: 'toggle_engine_triggered',
            show_hide_seq_str: 'show_hide_triggered',
            next_prof_seq_str: 'next_profile_triggered',
            prev_prof_seq_str: 'prev_profile_triggered',
            quick_add_seq_str: 'quick_add_rule_triggered',
        }

        for seq_str, signal_name in seq_map.items():
            if seq_str: # Only process if a sequence string exists
                q_seq = QKeySequence.fromString(seq_str, QKeySequence.SequenceFormat.NativeText)
                pynput_str = self._qkeysequence_to_pynput(q_seq)
                if pynput_str:
                    # Simple conflict check within this load cycle
                    if pynput_str in hotkey_map:
                         conflicting_signal = hotkey_map[pynput_str]
                         print(f"[Hotkey Load] Conflict detected: '{pynput_str}' used by '{signal_name}' and '{conflicting_signal}'. Skipping '{signal_name}'.")
                         QMessageBox.warning(self, "Hotkey Conflict", f"Hotkey '{seq_str}' conflicts with another hotkey.\n'{signal_name.replace('_triggered','').replace('_',' ').title()}' hotkey will not be registered.")
                    else:
                         hotkey_map[pynput_str] = signal_name

        # Register the valid, non-conflicting hotkeys
        self.hotkey_manager.update_hotkeys(hotkey_map)

    def _handle_toggle_hotkey_action(self):
        """Handles the signal from HotkeyManager for toggling the engine."""
        print("[Hotkey Action] Toggle engine triggered.")
        # Simulate a click on the main toggle button
        # This ensures the state change logic (_handle_toggle_proxy) is executed correctly
        current_state = self.toggle_proxy_button.isChecked()
        self.toggle_proxy_button.setChecked(not current_state) # This will trigger the connected _handle_toggle_proxy slot

    def _handle_hotkey_error(self, error_message: str):
        """Displays errors reported by the HotkeyManager."""
        print(f"[Hotkey Error] Received from manager: {error_message}")
        self.show_status_message(f"Hotkey Error: {error_message}", 8000)
        # Optionally show a persistent warning if critical (e.g., listener failed to start)
        if "Error starting" in error_message:
             QMessageBox.warning(self, "Hotkey Listener Error",
                                f"Failed to start the global hotkey listener:\n{error_message}\n\n"
                                "Global hotkeys will not function.")

    # ... _switch_to_next_profile, _switch_to_prev_profile ...
    # ... Profile Management Methods ...
    # ... _update_profile_selectors, _update_profile_button_states, _handle_active_profile_change ...
    # ... _add_profile, _rename_profile, _delete_profile ...
    # ... Animation Helper ...
    # ... Hotkey Helper Methods (_clear_hotkey) ...
    # ... Filter Widgets, Filtering Methods ...
    # ... Proxy List Methods (_populate_proxy_list, _update_proxy_count_label) ...

    def _find_rule_by_domain_and_profile(self, domain: str, profile_id: str) -> str | None:
        """Finds the FIRST rule matching the domain and profile ID."""
        domain_lower = domain.lower()
        # ---> Add Logging for Input <---
        print(f"[Find Rule Debug] Searching for: domain='{domain_lower}', profile_id='{profile_id}'")
        for rule_id, rule_data in self.rules.items():
            # Match domain case-insensitively and check profile_id
            # ---> Add Logging for Comparison <---
            rule_domain_lower = rule_data.get('domain', '').lower()
            rule_profile_id = rule_data.get('profile_id')
            print(f"[Find Rule Debug] Comparing with rule '{rule_id}': domain='{rule_domain_lower}', profile='{rule_profile_id}'")
            if rule_domain_lower == domain_lower and rule_profile_id == profile_id:
                print(f"[Find Rule] Found existing rule '{rule_id}' for domain '{domain}' in profile '{profile_id}'.")
                return rule_id
        print(f"[Find Rule] No existing rule found for domain '{domain}' in profile '{profile_id}'.")
        return None

    def _update_rules_title_label(self):
        """Updates the rules title label to show which profile is active."""
        if hasattr(self, 'rules_title_label'):
            active_profile_name = "None"
            if self._current_active_profile_id and self._current_active_profile_id in self.profiles:
                active_profile_name = self.profiles[self._current_active_profile_id].get('name', 'Unknown')
            # Use the all rules title format
            self.rules_title_label.setText(f"All Domain Rules (Active Profile: {active_profile_name})")

    # ---> ADD _create_tool_button METHOD HERE <---
    def _create_tool_button(self, icon_path: str, tooltip: str, connection_slot) -> QToolButton:
        """Helper to create a QToolButton with an SVG icon."""
        button = QToolButton()
        button.setObjectName("ToolButton") # General class for styling
        # Load icon (color will be set by theme application)
        # Use a placeholder color initially, _apply_theme_colors will fix it
        # svg_data = load_and_colorize_svg_content(icon_path, "#ffffff") # Placeholder color
        # if svg_data:
        #     button.setIcon(create_icon_from_svg_data(svg_data))
        # For now, just set icon path, theme application will handle loading/coloring
        button.setProperty("iconPath", icon_path) # Store path for theme update
        button.setIconSize(QSize(18, 18)) # Adjust size as needed
        button.setToolTip(tooltip)
        if connection_slot:
            button.clicked.connect(connection_slot)
        return button
    # ---> END METHOD ADDITION <---

    # ---> ADD the missing handler method <---
    def _handle_system_proxy_toggle(self, state: int):
        """
        Handles the change in the 'Set as system proxy' checkbox state (Windows only).
        Applies the change immediately only if the engine is currently active.
        Saves the setting regardless.
        """
        if not IS_WINDOWS:
             return # Should not be reachable if checkbox isn't created

        checked = (state == Qt.CheckState.Checked.value) # Convert state to boolean
        print(f"[System Proxy] Checkbox toggled: {'Checked' if checked else 'Unchecked'}")

        # Apply the change only if the engine is currently active
        if self.proxy_engine.is_active:
            print(f"[System Proxy] Engine is active, applying setting: enable={checked}")
            self._set_windows_proxy(enable=checked, proxy_port=self.proxy_engine.listening_port)
        else:
             # If engine is not active, ensuring the proxy is disabled when unchecking might be desirable
             # especially if the app crashed previously leaving it enabled.
             if not checked:
                  print("[System Proxy] Engine not active, ensuring system proxy is disabled on uncheck.")
                  self._set_windows_proxy(enable=False)
             else:
                  print("[System Proxy] Engine not active, setting will apply on next engine start.")

        # Save the preference immediately
        self.save_settings()
    # ---> END of added method <---

    def _create_vertical_separator(self) -> QFrame:
        """Creates a vertical separator line for the UI."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("StatusBarSeparator")
        separator.setFixedWidth(1)
        return separator

    def _create_profile_action_handler(self, profile_id):
        return lambda: self._handle_tray_profile_selection(profile_id)

    def _rebuild_rule_list_safely(self):
        """Safely rebuilds the rule list with full error handling."""
        try:
            print("[Rules] Safely rebuilding rule list...")
            
            # First, block signals to prevent unwanted UI updates during rebuild
            self.rules_list_widget.blockSignals(True)
            
            # Safely clear the list widget
            self.rules_list_widget.clear()
            
            # Clean up old widgets first, before creating new ones
            try:
                # Schedule old widgets for deletion
                for rule_id, widget in list(self.rule_widgets.items()):
                    if widget:
                        try:
                            if widget.parent():
                                widget.setParent(None)
                            widget.deleteLater()
                        except RuntimeError:
                            # Widget might already be deleted
                            print(f"[Warning] Widget for rule {rule_id} already deleted")
                # Clear the dictionary
                self.rule_widgets.clear()
            except Exception as e:
                print(f"[Error] Error cleaning up old widgets: {e}")
            
            # Process deletion events before continuing
            QApplication.processEvents()
            
            # Don't filter rules by active profile ID - show all rules
            all_rules = list(self.rules.values())
            
            # Sort rules (e.g., by domain)
            all_rules.sort(key=lambda r: r.get('domain', '').lower())
            
            proxy_map = self._get_proxy_name_map()
            profile_map = self._get_profile_name_map() # Contains all profile names
            
            print(f"[Rebuild] Adding {len(all_rules)} rules to list. Rules exist: {len(all_rules) > 0}")
            
            # Add items to the list
            for rule_data in all_rules:
                try:
                    rule_id = rule_data.get('id')
                    if not rule_id:
                        continue
                    
                    # Create a new widget
                    widget = RuleItemWidget(rule_data, proxy_map, profile_map, theme_name=self.current_theme)
                    widget.edit_rule.connect(self._show_edit_rule_editor)
                    widget.delete_rule.connect(self._delete_rule_entry)
                    widget.toggle_enabled.connect(self._toggle_rule_enabled)
                    self.rule_widgets[rule_id] = widget
                    
                    # Create list item and add widget to it
                    item = QListWidgetItem()
                    item.setData(Qt.ItemDataRole.UserRole, rule_id)
                    item.setSizeHint(widget.sizeHint())
                    self.rules_list_widget.addItem(item)
                    self.rules_list_widget.setItemWidget(item, widget)
                except Exception as e:
                    print(f"[Error] Failed to create/add rule widget for {rule_id}: {e}")
            
            # Update count label and ensure visibility
            any_rules = len(all_rules) > 0
            self.rules_list_widget.setVisible(any_rules)
            self.rules_placeholder_widget.setVisible(not any_rules)
            
            self.rules_count_label.setText(f"{len(all_rules)} rule{'s' if len(all_rules) != 1 else ''}")
            
            # Unblock signals after update
            self.rules_list_widget.blockSignals(False)
            
            # Adjust layout if needed
            self.rules_list_widget.update()
            QApplication.processEvents()
            
            print("[Rules] List rebuild complete.")
        except Exception as e:
            print(f"[Error] Failed to rebuild rule list: {e}")
            # Make sure list is visible in case of error
            self.rules_list_widget.setVisible(True)
            self.rules_placeholder_widget.setVisible(False)
            
            # Unblock signals in case of error
            self.rules_list_widget.blockSignals(False)

    def _scroll_to_item(self, list_widget, item_id):
        """Scrolls to make the item with the given ID visible in the list widget."""
        try:
            # Find the item with the given ID
            target_item = None
            target_index = -1
            
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == item_id:
                    target_item = item
                    target_index = i
                    break
                    
            if target_item:
                # Scroll to make the item visible
                list_widget.scrollToItem(target_item, QAbstractItemView.ScrollHint.PositionAtCenter)
                
                # Optionally highlight/select the item
                list_widget.setCurrentItem(target_item)
                print(f"[UI] Scrolled to item {item_id} at index {target_index}")
            else:
                print(f"[UI] Item {item_id} not found for scrolling")
                
        except Exception as e:
            print(f"[Error] Failed to scroll to item: {e}")

    # --- Add Slot for Appending Log Text ---
    def _append_log_text(self, text):
        """Appends text to the log view QTextEdit."""
        # Use insertPlainText to avoid automatic newline addition by append()
        cursor = self.log_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End) # Move cursor to the end
        self.log_text_edit.setTextCursor(cursor)          # Apply cursor position
        self.log_text_edit.insertPlainText(text)          # Insert text exactly as received

        # Optional: Auto-scroll to bottom
        sb = self.log_text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ... (rest of MainWindow methods) ...

    def _handle_engine_status_for_log_timer(self, status):
        """Start/stop log auto-clear timer based on engine status."""
        if status == "active":
            if not self._log_auto_clear_timer.isActive():
                self._log_auto_clear_timer.start()
        else:
            if self._log_auto_clear_timer.isActive():
                self._log_auto_clear_timer.stop()

    def _auto_clear_logs_if_engine_running(self):
        """Clear logs if the engine is running (called by timer)."""
        if self.proxy_engine.is_active:
            self.log_text_edit.clear()