from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QSpacerItem,
    QSizePolicy, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter
import os
# Assuming helper functions are available (defined/imported)
# from ..utils import load_and_colorize_svg_content, create_icon_from_svg_data

# --- Define helpers here or import ---
import re
from PySide6.QtGui import QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt

# Import the utility functions (adjust path if necessary)
# Ensure utils is imported relatively
from ..utils import generate_color_from_id # We don't need get_contrasting_text_color anymore
from ..utils import load_and_colorize_svg_content, create_icon_from_svg_data # <<< Already relative, ensure it stays this way

# Assume you have icons for edit/delete in src/assets/icons/
EDIT_ICON_PATH = "src/assets/icons/edit.svg" # Replace with actual path
DELETE_ICON_PATH = "src/assets/icons/trash.svg" # Replace with actual path
# Checkbox icons are handled differently via stylesheet image property

# Import the custom checkbox
# from ..components.custom_checkbox import CustomRuleCheckBox # Adjust path if needed

class RuleItemWidget(QFrame):
    """Widget to display a single domain rule item."""
    # Signals with rule ID payload
    edit_rule = Signal(str)
    delete_rule = Signal(str)
    toggle_enabled = Signal(str, bool)

    def __init__(self, rule_data: dict, proxy_name_map: dict, profile_name_map: dict, parent=None, theme_name='dark'):
        """
        Initialize the rule item widget.
        rule_data (dict): {'id': rule_id, 'domain': 'domain.com', 'proxy_id': proxy_id, 'profile_id': profile_id}
        proxy_name_map (dict): {proxy_id: proxy_name} to display proxy names.
        profile_name_map (dict): {profile_id: profile_name} to display profile names.
        """
        super().__init__(parent)
        self.rule_id = rule_data.get("id", "N/A") # Store the unique ID
        self.domain = rule_data.get("domain", "N/A") # This field holds domain or IP
        self.proxy_id = rule_data.get("proxy_id")
        self.profile_id = rule_data.get("profile_id") # Store profile ID
        self.proxy_name_map = proxy_name_map
        self.profile_name_map = profile_name_map # Store profile map
        self.theme_name = theme_name # Store theme
        self.rule_data = rule_data # Store data
        self.setObjectName("RuleItemWidget") # Use the specific ID for the frame itself
        self.setFixedHeight(65) # Give it a fixed height for consistency

        self._init_ui()
        self._apply_theme_colors() # Apply initial colors
        self.update_data(rule_data, proxy_name_map, profile_name_map) # Update with maps

    def _get_icon_color(self, element_type: str = "default") -> str:
        """Gets the appropriate icon color based on theme."""
        if self.theme_name == 'dark':
            if element_type == "delete_hover": return "#ffffff"
            if element_type == "hover": return "#e0e0e0"
            return "#ffffff"
        else: # Light theme
            if element_type == "delete_hover": return "#d32f2f"
            if element_type == "hover": return "#343a40"
            return "#495057"

    def _init_ui(self):
        """Set up the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5) # Padding
        main_layout.setSpacing(10)

        # --- Left: Checkbox ---
        # Use standard QCheckBox again
        self.enable_checkbox = QCheckBox()
        # Keep object name for QSS
        self.enable_checkbox.setObjectName("RuleEnableCheckbox")
        self.enable_checkbox.setToolTip("Enable/Disable this rule")
        self.enable_checkbox.stateChanged.connect(self._on_toggle)
        main_layout.addWidget(self.enable_checkbox)

        # --- Middle: Info (Vertical) ---
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0,0,0,0)
        info_layout.setSpacing(2) # Reduce spacing between domain and info line

        self.domain_label = QLabel() # Text set in update_data
        self.domain_label.setObjectName("RuleDomainLabel")
        self.domain_label.setStyleSheet("font-weight: bold;") # Make domain bold

        # Info line (Horizontal)
        sub_info_layout = QHBoxLayout()
        sub_info_layout.setContentsMargins(0,0,0,0)
        sub_info_layout.setSpacing(15) # Space between proxy and profile info

        self.proxy_label = QLabel() # Text set in update_data
        self.proxy_label.setObjectName("RuleProxyLabel")

        self.profile_label = QLabel() # Text set in update_data
        self.profile_label.setObjectName("RuleItemProfileLabel") # Different style?
        self.profile_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        sub_info_layout.addWidget(self.proxy_label)
        sub_info_layout.addWidget(self.profile_label)
        sub_info_layout.addStretch() # Push info to the left

        info_layout.addWidget(self.domain_label)
        info_layout.addLayout(sub_info_layout)
        main_layout.addLayout(info_layout, stretch=1) # Allow info section to stretch

        # --- Right: Buttons ---
        self.edit_button = QPushButton()
        self.edit_button.setObjectName("EditRuleButton")
        self.edit_button.setToolTip("Edit Rule")
        self.edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_button.clicked.connect(self._on_edit)

        self.delete_button = QPushButton()
        self.delete_button.setObjectName("DeleteRuleButton")
        self.delete_button.setToolTip("Delete Rule")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.clicked.connect(self._on_delete)

        # Buttons need specific sizing from QSS now

        main_layout.addWidget(self.edit_button)
        main_layout.addWidget(self.delete_button)

    def _apply_theme_colors(self):
        """Set button icons based on theme."""
        icon_color = self._get_icon_color()
        edit_svg = load_and_colorize_svg_content(EDIT_ICON_PATH, icon_color)
        delete_svg = load_and_colorize_svg_content(DELETE_ICON_PATH, icon_color)

        self.edit_button.setIcon(create_icon_from_svg_data(edit_svg))
        self.delete_button.setIcon(create_icon_from_svg_data(delete_svg))

        # Force style refresh for the checkbox indicator (important!)
        self.enable_checkbox.style().unpolish(self.enable_checkbox)
        self.enable_checkbox.style().polish(self.enable_checkbox)

    def set_theme(self, theme_name: str):
        """Updates the theme and forces a refresh of theme-dependent styles."""
        if self.theme_name != theme_name:
            self.theme_name = theme_name
            self._apply_theme_colors() # Recolor buttons

            # --- Force update of label styles based on the new theme ---
            # Re-call update_data to re-apply stylesheets with correct fixed_text_color
            # We need the maps, which should still be stored as attributes
            if hasattr(self, 'proxy_name_map') and hasattr(self, 'profile_name_map'):
                self.update_data(self.rule_data, self.proxy_name_map, self.profile_name_map)
            else:
                # Fallback: just try to update the widget if maps are missing for some reason
                self.update()

    def update_data(self, rule_data: dict, proxy_name_map: dict, profile_name_map: dict):
        """Update the displayed information and label styles with fixed opaque text color."""
        self.rule_data = rule_data # Store updated data
        self.rule_id = rule_data.get("id", self.rule_id)
        self.domain = rule_data.get("domain", self.domain) # Update domain/IP field
        self.proxy_id = rule_data.get("proxy_id")
        self.profile_id = rule_data.get("profile_id") # Update profile ID
        self.proxy_name_map = proxy_name_map
        self.profile_name_map = profile_name_map # Update profile map
        enabled = rule_data.get("enabled", True) # Default to enabled

        self.domain_label.setText(f"<b>{self.domain}</b>") # Display the domain or IP
        self.domain_label.setToolTip(self.domain) # Tooltip shows the full value

        label_alpha = 60 # Keep background transparency

        # --- Determine Fixed Text Color Based on Theme ---
        if self.theme_name == 'dark':
            fixed_text_color = QColor("#e0e0e0") # Light grey for dark theme
        else:
            # Correctly set the dark text color for the light theme
            fixed_text_color = QColor("#1c1c1c") # Default dark text for light theme

        # Ensure the text color is fully opaque (alpha 255)
        fixed_text_color.setAlpha(255)

        # --- Update Proxy Label ---
        proxy_display_name = "Direct Connection"
        proxy_bg_color = generate_color_from_id(self.proxy_id, saturation=0.6, lightness=0.45)
        if self.proxy_id and self.proxy_id in self.proxy_name_map:
            proxy_display_name = self.proxy_name_map[self.proxy_id]
        elif self.proxy_id:
             proxy_display_name = f"Proxy ID: {self.proxy_id[:6]}... (Not Found)"
        self.proxy_label.setText(f"→ {proxy_display_name}")
        proxy_bg_color.setAlpha(label_alpha)
        # Apply style to proxy label with fixed opaque text color
        self.proxy_label.setStyleSheet(f"""
            background-color: {proxy_bg_color.name(QColor.NameFormat.HexArgb)};
            color: {fixed_text_color.name()}; /* Use fixed opaque color */
            padding: 1px 4px;
            border-radius: 4px;
            font-size: 11px;
        """)
        self.proxy_label.setToolTip(f"Proxy: {proxy_display_name}")

        # --- Update Profile Label ---
        profile_display_name = f"Profile ID: {self.profile_id[:6]}... (Not Found)" # Default if map is wrong
        profile_bg_color = generate_color_from_id(self.profile_id, saturation=0.5, lightness=0.6) # Use ID for color
        if self.profile_id and self.profile_id in self.profile_name_map:
            profile_display_name = self.profile_name_map[self.profile_id]
        # elif self.profile_id is None: # This case should no longer happen
        #     profile_display_name = "Default (All)" # Fallback text removed
        #     profile_bg_color = QColor("#888888") # Default color removed

        self.profile_label.setText(f"{profile_display_name}")
        profile_bg_color.setAlpha(label_alpha)
        # Apply style to profile label with fixed opaque text color
        self.profile_label.setStyleSheet(f"""
            background-color: {profile_bg_color.name(QColor.NameFormat.HexArgb)};
            color: {fixed_text_color.name()}; /* Use fixed opaque color */
            padding: 1px 4px;
            border-radius: 4px;
            font-size: 11px;
            font-style: italic;
        """)
        self.profile_label.setToolTip(f"Profile: {profile_display_name}")

        # --- Update Enabled State ---
        self.enable_checkbox.blockSignals(True)
        self.enable_checkbox.setChecked(enabled)
        self.enable_checkbox.blockSignals(False)
        self.set_enabled_style(enabled)

    def set_enabled_style(self, enabled: bool):
        """Applies a visual style based on the enabled state."""
        # Set the dynamic property for the *Frame* styling
        self.setProperty("ruleEnabled", enabled)
        # The QSS will handle the indicator style based on checkbox state and this property

        # Refresh style for the frame and checkbox
        self.style().unpolish(self)
        self.style().polish(self)
        self.enable_checkbox.style().unpolish(self.enable_checkbox)
        self.enable_checkbox.style().polish(self.enable_checkbox)
        # Ensure the checkbox repaints if needed
        self.enable_checkbox.update()

    def _on_edit(self):
        self.edit_rule.emit(self.rule_id)

    def _on_delete(self):
        self.delete_rule.emit(self.rule_id)

    def _on_toggle(self):
        self.toggle_enabled.emit(self.rule_id, self.enable_checkbox.isChecked())
        # Style update is handled by update_data calling set_enabled_style after state change 