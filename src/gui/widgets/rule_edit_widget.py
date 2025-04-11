from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QComboBox,
    QPushButton, QSpacerItem, QSizePolicy, QFrame, QCheckBox, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal
import re # For domain validation

class RuleEditWidget(QFrame):
    """Widget for adding or editing domain routing rules."""
    # Change signal back
    save_rules = Signal(list, str, str) # domains_list, proxy_id, profile_id
    cancelled = Signal()

    # Add profile_map parameter
    def __init__(self, main_window, available_proxies: dict, available_profiles: dict, rule_data=None, parent=None):
        """
        Initialize the edit widget.
        available_proxies (dict): {proxy_id: proxy_name} for the dropdown.
        available_profiles (dict): {profile_id: profile_name} for the dropdown.
        rule_data (dict, optional): Existing data for editing (e.g., {'id': id, 'domain': 'example.com', 'proxy_id': id, 'profile_id': id}).
        """
        super().__init__(parent)
        self.setObjectName("RuleEditFrame")
        self.main_window = main_window # Store reference
        self.available_proxies = available_proxies
        self.available_profiles = available_profiles # Store profile map {id: name}
        self._editing_rule_id = None # Store ID of rule being edited

        self._init_ui()

        if rule_data:
            self.load_data(rule_data)
        else:
            self.clear_fields() # Ensure fields are empty for adding

    def _init_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(10)

        # --- Form Fields ---
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        # Domain (Revert to QTextEdit for bulk add)
        domains_label = QLabel("Domain(s):") # Changed label slightly
        self.domain_input = QTextEdit() # Changed back to QTextEdit
        self.domain_input.setPlaceholderText("Enter domains, one per line (e.g., example.com, *.example.net)\n(Note: Editing affects first domain only)") # Update placeholder
        self.domain_input.setAcceptRichText(False)
        self.domain_input.setMinimumHeight(80) # Allow space for multiple lines
        form_layout.addWidget(domains_label)
        form_layout.addWidget(self.domain_input)
        # Remove previous QLineEdit layout

        # Proxy Selection
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel("Forward via:")
        proxy_label.setFixedWidth(80)
        self.proxy_combo = QComboBox()
        # Populate below in update_proxies
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_combo)
        proxy_layout.addStretch()
        form_layout.addLayout(proxy_layout)
        self.update_proxies(self.available_proxies) # Initial population

        # Profile Selection
        profile_layout = QHBoxLayout()
        profile_label = QLabel("Profile:")
        profile_label.setFixedWidth(80)
        self.profile_combo = QComboBox() # Added profile combo
        self.profile_combo.setToolTip("Assign rule to this profile")
        # Populate below in update_profiles
        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        form_layout.addLayout(profile_layout)
        self.update_profiles(self.available_profiles) # Initial population

        main_layout.addLayout(form_layout)
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.clicked.connect(self.cancelled.emit)

        self.save_button = QPushButton("Save Rule(s)") # Changed back
        self.save_button.setObjectName("SaveButton")
        self.save_button.clicked.connect(self._on_save)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

    def _validate_domain(self, domain: str) -> bool:
        """Basic domain name validation (allows wildcards at start)."""
        if not domain: return False
        # Allow *. at the start, then standard domain characters
        # Handles Internationalized Domain Names (IDN) with broader character set after initial ASCII check
        # Simple pattern: allows letters, numbers, hyphen, dot, and wildcard start.
        # More robust validation might be needed depending on requirements.
        pattern = r"^(\*\.)?([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        # Basic check for common invalid patterns
        if ".." in domain or domain.endswith("-") or domain.startswith("-"):
             return False
        return bool(re.match(pattern, domain, re.IGNORECASE)) # Ignore case for matching

    def _on_save(self):
        """Validate input and emit save signal with list of domains."""
        domains_text = self.domain_input.toPlainText().strip()
        selected_proxy_index = self.proxy_combo.currentIndex()
        selected_proxy_id = self.proxy_combo.itemData(selected_proxy_index)
        selected_profile_index = self.profile_combo.currentIndex()
        selected_profile_id = self.profile_combo.itemData(selected_profile_index)

        if not domains_text:
            QMessageBox.warning(self, "Input Error", "Domain(s) cannot be empty.")
            self.domain_input.setFocus()
            return

        # Split by comma, space, newline, semicolon and filter empty strings
        raw_domains = [d.strip() for d in re.split(r'[,\s\n;]+', domains_text) if d.strip()]

        valid_domains = []
        invalid_domains = []

        # Validate and filter domains
        for domain in raw_domains:
            # Basic cleanup: remove http(s):// prefix if present
            if domain.startswith("http://"): domain = domain[7:]
            if domain.startswith("https://"): domain = domain[8:]
            # Remove trailing slashes or paths
            domain = domain.split('/')[0]

            if self._validate_domain(domain):
                # Add domain in lowercase to avoid case sensitivity issues later
                domain_lower = domain.lower()
                if domain_lower not in valid_domains:
                    valid_domains.append(domain_lower)
            else:
                invalid_domains.append(domain) # Show original invalid input

        if invalid_domains:
             error_msg = f"Invalid domain format for:\n - " + "\n - ".join(invalid_domains)
             QMessageBox.warning(self, "Input Error", error_msg)
             self.domain_input.setFocus()
             return
        if not valid_domains:
            # This might happen if only invalid domains were entered
            QMessageBox.warning(self, "Input Error", "No valid domains entered after cleanup.")
            self.domain_input.setFocus()
            return

        # If editing, only allow saving if exactly one domain is present
        if self._editing_rule_id and len(valid_domains) > 1:
             QMessageBox.warning(self, "Input Error", "Cannot edit multiple domains at once. Please enter only one domain when editing.")
             self.domain_input.setFocus()
             return

        # Emit signal with list of valid domains, proxy ID, and profile ID
        print(f"[Rule Edit Save] Emitting save_rules with domains: {valid_domains}")
        self.save_rules.emit(valid_domains, selected_proxy_id, selected_profile_id)

    def update_proxies(self, available_proxies: dict):
        """Updates the list of proxies in the dropdown."""
        # available_proxies is now {proxy_id: proxy_data_dict}
        self.available_proxies = available_proxies
        current_data = self.proxy_combo.currentData()
        self.proxy_combo.blockSignals(True)
        self.proxy_combo.clear()
        self.proxy_combo.addItem("Direct Connection", None)
        # Sort by proxy name from the data dict
        sorted_proxies = sorted(available_proxies.items(), key=lambda item: item[1].get('name', '').lower())
        for proxy_id, proxy_details in sorted_proxies:
            # Get name from proxy_details (the dictionary value)
            display_name = proxy_details.get('name', f"Proxy {proxy_id[:6]}...")
            self.proxy_combo.addItem(display_name, proxy_id) # Store ID as user data
        index_to_select = self.proxy_combo.findData(current_data)
        self.proxy_combo.setCurrentIndex(max(0, index_to_select)) # Default to Direct if not found
        self.proxy_combo.blockSignals(False)

    def update_profiles(self, available_profiles: dict):
        """Updates the list of profiles in the profile dropdown."""
        print(f"[RuleEditWidget] update_profiles called with {len(available_profiles)} profiles.") # Debug print
        self.available_profiles = available_profiles
        current_data = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        # Profile selection should allow assigning to "None" (All Rules / Default)
        print(f"[RuleEditWidget] Adding profile item: '{self.main_window.ALL_RULES_PROFILE_NAME}' (Data: None)") # Debug print
        self.profile_combo.addItem(self.main_window.ALL_RULES_PROFILE_NAME, None) # Use main window constant name
        sorted_profiles = sorted(available_profiles.items(), key=lambda item: item[1].get('name', '').lower())
        for profile_id, profile_data in sorted_profiles:
            name = profile_data.get('name', f"Profile {profile_id[:6]}...")
            print(f"[RuleEditWidget] Adding profile item: '{name}' (Data: {profile_id})") # Debug print
            self.profile_combo.addItem(name, profile_id)
        index_to_select = self.profile_combo.findData(current_data)
        self.profile_combo.setCurrentIndex(max(0, index_to_select)) # Default to "All" if not found
        print(f"[RuleEditWidget] Profile combo count after update: {self.profile_combo.count()}") # Debug print
        self.profile_combo.blockSignals(False)

    def load_data(self, rule_data: dict):
        """Populate fields for editing a single rule."""
        self._editing_rule_id = rule_data.get("id")
        domain = rule_data.get("domain", "") # Load only the specific domain being edited
        proxy_id = rule_data.get("proxy_id")
        profile_id = rule_data.get("profile_id")

        self.domain_input.setPlainText(domain) # Set text in QTextEdit
        self.domain_input.setReadOnly(False) # Domain editing is allowed (but save checks for single domain)

        # Select Proxy
        proxy_idx = self.proxy_combo.findData(proxy_id)
        self.proxy_combo.setCurrentIndex(max(0, proxy_idx))

        # Select Profile
        profile_idx = self.profile_combo.findData(profile_id) # Find by ID (None for 'All')
        self.profile_combo.setCurrentIndex(max(0, profile_idx))

    def clear_fields(self):
        """Clear all input fields and reset state."""
        self._editing_rule_id = None
        self.domain_input.clear()
        self.domain_input.setReadOnly(False)
        self.proxy_combo.setCurrentIndex(0)
        self.profile_combo.setCurrentIndex(0) # Default to "All"

    def set_focus_on_domains(self):
        """Set focus to the domains input field."""
        self.domain_input.setFocus() 