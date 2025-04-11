from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QSpacerItem,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter # Keep QPainter for rendering
from PySide6.QtSvg import QSvgRenderer # Keep QSvgRenderer
import os
import re

# Ensure utils is imported relatively
from ..utils import load_and_colorize_svg_content, create_icon_from_svg_data # <<< Already relative, ensure it stays this way

# Assume you have icons for edit/delete/auth in src/assets/icons/
# e.g., edit.svg, trash.svg, key.svg
EDIT_ICON_PATH = "src/assets/icons/edit.svg" # Replace with actual path
DELETE_ICON_PATH = "src/assets/icons/trash.svg" # Replace with actual path
AUTH_ICON_PATH = "src/assets/icons/key.svg" # Example icon for auth
TEST_ICON_PATH = "src/assets/icons/zap.svg" # Example icon for test
TESTING_ICON_PATH = "src/assets/icons/loader.svg" # Loading/spinner icon (optional)

# --- Define load_and_colorize_svg_content here or import ---
def load_and_colorize_svg_content(icon_path: str, color: str) -> bytes:
    """Loads SVG content and replaces/adds stroke with a specific color."""
    try:
        with open(icon_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        # Prioritize replacing existing stroke="currentColor" or any stroke="..."
        modified_content = re.sub(r'(<svg\b[^>]*?)(\bstroke\s*=\s*["\'][^"\']+["\'])', rf'\1 stroke="{color}"', svg_content, 1, re.IGNORECASE | re.DOTALL)
        # If no stroke attribute was replaced, add it
        if f'stroke="{color}"' not in modified_content and '<svg' in modified_content:
             modified_content = re.sub(r'(<svg\b)', rf'\1 stroke="{color}"', modified_content, 1, re.IGNORECASE)
        # Ensure fill is none for elements that shouldn't be filled (like lines/polygons)
        modified_content = re.sub(r'(<(?:line|rect|circle|polygon|path)\b[^>]*?)(\bfill\s*=\s*["\'][^"\']+["\'])', r'\1 fill="none"', modified_content, flags=re.IGNORECASE | re.DOTALL)
        # Ensure main svg tag has fill="none" unless stroke is none
        if f'stroke="{color}"' in modified_content and 'fill="none"' not in modified_content[:modified_content.find('>')]:
             modified_content = re.sub(r'(<svg\b)', r'\1 fill="none"', modified_content, 1, re.IGNORECASE)

        return modified_content.encode('utf-8')
    except FileNotFoundError:
        print(f"Error: Icon file not found at {icon_path}")
        return b""
    except Exception as e:
        print(f"Error loading/colorizing SVG {icon_path}: {e}")
        return b""
# --- End Helper ---

def create_icon_from_svg_data(svg_data: bytes) -> QIcon:
    """Creates QIcon from raw SVG data bytes."""
    if not svg_data:
        return QIcon() # Return empty icon on error
    pixmap = QPixmap()
    if pixmap.loadFromData(svg_data, "svg"):
        return QIcon(pixmap)
    else:
        print("Warning: Failed to load pixmap from SVG data for icon.")
        return QIcon()

class ProxyItemWidget(QFrame):
    """Widget to display a single proxy item in a list."""
    # Signals with proxy ID payload
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    test_requested = Signal(str) # Signal to request a test

    def __init__(self, proxy_data: dict, parent=None, theme_name='dark'):
        super().__init__(parent)
        self.proxy_id = proxy_data.get("id", "N/A")
        self.setObjectName("ProxyItemFrame")
        self._current_status = "unknown" # unknown, testing, active, error, inactive
        self.theme_name = theme_name # Store theme name
        self.proxy_data = proxy_data # Store data

        self._init_ui()            # Creates widgets
        self._apply_theme_colors() # Apply initial colors
        self.set_status("unknown") # Call set_status *after* theme colors (and test_icon_default) are set
        self.update_data(proxy_data) # Populate text fields

    def _get_icon_color(self, element_type: str = "default") -> str:
        """Gets the appropriate icon color based on theme."""
        if self.theme_name == 'dark':
            # For dark theme, most icons are white
            if element_type == "delete_hover": return "#ffffff" # White on red bg
            if element_type == "hover": return "#e0e0e0" # Slightly off-white for hover
            return "#ffffff" # Default white
        else: # Light theme
            if element_type == "delete_hover": return "#d32f2f" # Darker red
            if element_type == "hover": return "#343a40" # Darker grey hover
            return "#495057" # Default dark grey

    def _init_ui(self):
        """Set up the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5) # Padding
        main_layout.setSpacing(8) # Reduced spacing slightly

        # --- Status Indicator ---
        self.status_indicator = QLabel("●")
        self.status_indicator.setFixedWidth(15)
        self.status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Proxy Info ---
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)

        self.name_label = QLabel(f"<b>{self.proxy_data.get('name', 'Unnamed Proxy')}</b>")
        self.name_label.setObjectName("ProxyNameLabel")

        details_text = f"{self.proxy_data.get('type', 'N/A')} | {self.proxy_data.get('address', 'N/A')}:{self.proxy_data.get('port', 'N/A')}"
        self.details_label = QLabel(details_text)
        self.details_label.setObjectName("ProxyDetailsLabel")
        # Make details text smaller/grayer in QSS potentially

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.details_label)

        # --- Auth Indicator ---
        self.auth_indicator_label = QLabel()
        self.auth_indicator_label.setObjectName("AuthIndicatorLabel")
        self.auth_indicator_label.setToolTip("Authentication Enabled")
        self.auth_indicator_label.setVisible(False) # Initially hidden

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)

        # Test Button
        self.test_button = QPushButton()
        self.test_button.setObjectName("TestProxyButton")
        self.test_button.setToolTip("Test Proxy Connection")
        self.test_button.clicked.connect(self._request_test)

        self.edit_button = QPushButton()
        self.edit_button.setObjectName("EditProxyButton")
        self.edit_button.setToolTip("Edit Proxy")
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(self.proxy_id))

        self.delete_button = QPushButton()
        self.delete_button.setObjectName("DeleteProxyButton") # For danger styling
        self.delete_button.setToolTip("Delete Proxy")
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.proxy_id))

        for btn in [self.test_button, self.edit_button, self.delete_button]:
            btn.setFixedSize(28, 28); btn.setIconSize(QSize(16, 16)) # Consistent size

        button_layout.addWidget(self.test_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)

        # --- Assemble Layout ---
        main_layout.addWidget(self.status_indicator)
        main_layout.addLayout(info_layout, stretch=1) # Info takes available space
        main_layout.addWidget(self.auth_indicator_label) # Add auth indicator
        main_layout.addLayout(button_layout)

    def _apply_theme_colors(self):
        """Sets icon colors based on the current theme."""
        # Auth Indicator
        if self.proxy_data.get('requires_auth', False):
             self._update_auth_icon_color()

        # Buttons
        icon_color = self._get_icon_color()
        test_svg = load_and_colorize_svg_content(TEST_ICON_PATH, icon_color)
        edit_svg = load_and_colorize_svg_content(EDIT_ICON_PATH, icon_color)
        delete_svg = load_and_colorize_svg_content(DELETE_ICON_PATH, icon_color)

        self.test_button.setIcon(create_icon_from_svg_data(test_svg))
        self.edit_button.setIcon(create_icon_from_svg_data(edit_svg))
        self.delete_button.setIcon(create_icon_from_svg_data(delete_svg))

        # Store original icons to restore after testing animation
        self.test_icon_default = create_icon_from_svg_data(test_svg) # Store colorized version

        # Update testing icon color
        testing_icon_color = self._get_icon_color("hover") # Use hover color for testing?
        testing_svg = load_and_colorize_svg_content(TESTING_ICON_PATH, testing_icon_color)
        self.testing_icon = create_icon_from_svg_data(testing_svg)

    def _update_auth_icon_color(self):
        """Sets the pixmap for the auth indicator label."""
        if not self.auth_indicator_label.isVisible(): return

        target_color = self._get_icon_color()
        icon_size = 14
        svg_data = load_and_colorize_svg_content(AUTH_ICON_PATH, target_color)
        if svg_data:
            # Render SVG data to QPixmap for QLabel
            renderer = QSvgRenderer(svg_data)
            if renderer.isValid():
                pixmap = QPixmap(icon_size, icon_size); pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap); renderer.render(painter); painter.end()
                self.auth_indicator_label.setPixmap(pixmap)
            else: self.auth_indicator_label.setText("🔒") # Fallback
        else: self.auth_indicator_label.setText("🔒") # Fallback

    def _request_test(self):
        """Handle test button click: update UI, set status, emit signal."""
        self.test_button.setEnabled(False)
        if self.testing_icon and not self.testing_icon.isNull():
             self.test_button.setIcon(self.testing_icon)
        self.test_button.setToolTip("Testing...")
        self.set_status("testing") # Update status indicator
        self.test_requested.emit(self.proxy_id)

    def set_status(self, status: str):
        """Update the visual status indicator and internal state."""
        # Store the logical status
        self._current_status = status

        # Update visual indicator
        color = "#9E9E9E" # Gray (inactive/unknown)
        tooltip = "Unknown / Inactive"
        indicator_char = "●"

        if status == "active":
            color = "#4CAF50"; tooltip = "Active / OK" # Green
        elif status == "error":
            color = "#F44336"; tooltip = "Error" # Red
            indicator_char = "✖" # Different char for error
        elif status == "testing":
             color = "#FFC107"; tooltip = "Testing..." # Amber/Yellow
             indicator_char = "…" # Ellipsis for testing
        elif status == "inactive": # Explicitly inactive (engine off)
             color = "#607D8B"; tooltip = "Inactive (Engine Off)" # Blue Gray
             indicator_char = "○" # Open circle

        self.status_indicator.setText(indicator_char)
        self.status_indicator.setStyleSheet(f"color: {color};")
        self.status_indicator.setToolTip(tooltip)

        # Reset test button appearance when not testing
        is_testing = (status == "testing")
        self.test_button.setEnabled(not is_testing)
        if not is_testing:
             if self.test_icon_default and not self.test_icon_default.isNull():
                  self.test_button.setIcon(self.test_icon_default) # Restore original colorized icon
             else: self.test_button.setText("T") # Restore fallback if no icon
             self.test_button.setToolTip("Test Proxy Connection")
        # (Testing state appearance is handled in _request_test)

    def get_status(self) -> str:
        """Return the current logical status."""
        return self._current_status

    def update_data(self, proxy_data: dict):
        """Update the displayed information."""
        self.proxy_data = proxy_data # Update stored data
        self.proxy_id = proxy_data.get("id", self.proxy_id) # Update ID if changed
        self.name_label.setText(f"<b>{proxy_data.get('name', 'Unnamed Proxy')}</b>")
        details_text = f"{proxy_data.get('type', 'N/A')} | {proxy_data.get('address', 'N/A')}:{proxy_data.get('port', 'N/A')}"
        self.details_label.setText(details_text)
        # Show/hide auth indicator
        self.auth_indicator_label.setVisible(proxy_data.get('requires_auth', False))
        if proxy_data.get('requires_auth', False):
            self._update_auth_icon_color() # Update icon color if visible
        # Set status based on loaded data or keep current if not specified
        last_known_status = proxy_data.get('status', self._current_status) # Use current if not in data
        self.set_status(last_known_status) 

    def set_theme(self, theme_name: str):
        if self.theme_name != theme_name:
            self.theme_name = theme_name
            self._apply_theme_colors() # Recolor all icons
            self.update_data(self.proxy_data) # Update data with new theme

    def update_theme(self, theme_name: str):
        self.set_theme(theme_name)
        self.update_data(self.proxy_data)
        self.update_data(self.proxy_data) 