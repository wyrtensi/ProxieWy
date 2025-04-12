from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QDialogButtonBox, QMessageBox, QWidget, QSpacerItem, QSizePolicy,
    QApplication
)
from PySide6.QtCore import Qt, Signal
import re
from urllib.parse import urlparse, ParseResult
import time
import platform
import ipaddress # For IP validation

# Assuming utils provides validation or other helpers if needed
# from ..utils import some_validation_function

class QuickRuleAddDialog(QDialog):
    """A compact dialog to quickly add a domain routing rule."""
    # Signal: Emits (domain_str, proxy_id_or_none, profile_id_or_none)
    save_rule = Signal(str, object, str)

    def __init__(self, main_window_ref, available_proxies: dict, available_profiles: dict, initial_domain: str = "", parent=None):
        super().__init__(parent)
        self.main_window = main_window_ref # Keep reference for constants etc.
        self.available_proxies = available_proxies
        self.available_profiles = available_profiles
        self.setWindowTitle("Quick Add Rule")
        self.setMinimumWidth(400)
        self.setModal(True) # Make it a modal dialog
        self.setObjectName("QuickRuleAddDialog") # For QSS styling

        self._init_ui(initial_domain)
        self._connect_signals()
        # ---> Select the main window's current active profile initially <---
        active_profile_id = getattr(self.main_window, '_current_active_profile_id', None)
        if active_profile_id:
             idx = self.profile_combo.findData(active_profile_id)
             if idx != -1:
                  self.profile_combo.setCurrentIndex(idx)

    def _init_ui(self, initial_domain: str):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(10)

        # Domain Input
        domain_layout = QHBoxLayout()
        domain_label = QLabel("Domain/IP:")
        domain_label.setFixedWidth(60)
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("e.g., example.com, *.net, 1.1.1.1")
        if initial_domain:
            self.domain_input.setText(initial_domain)
        domain_layout.addWidget(domain_label)
        domain_layout.addWidget(self.domain_input)
        main_layout.addLayout(domain_layout)

        # Proxy Selection
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel("Proxy:")
        proxy_label.setFixedWidth(60)
        self.proxy_combo = QComboBox()
        self.proxy_combo.setToolTip("Select proxy or 'Direct Connection'")
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_combo)
        proxy_layout.addStretch()
        main_layout.addLayout(proxy_layout)

        # Profile Selection
        profile_layout = QHBoxLayout()
        profile_label = QLabel("Profile:")
        profile_label.setFixedWidth(60)
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("Assign rule to a profile (or All)")
        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        main_layout.addLayout(profile_layout)

        # Add some space before buttons
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Dialog Buttons (Save/Cancel)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setObjectName("SaveButton") # For QSS
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("CancelButton") # For QSS
        main_layout.addWidget(self.button_box)

        # --- Populate Combos AFTER button_box is created ---
        self._populate_proxies() # Populate combo
        self._populate_profiles() # Populate combo

    def _connect_signals(self):
        """Connect signals to slots."""
        self.button_box.accepted.connect(self._on_save) # Save maps to accepted
        self.button_box.rejected.connect(self.reject)  # Cancel maps to rejected

    def _populate_proxies(self):
        """Populates the proxy combo box."""
        self.proxy_combo.clear()
        self.proxy_combo.addItem("Direct Connection", None) # User data is None
        # Sort by name
        sorted_proxies = sorted(self.available_proxies.items(), key=lambda item: item[1].get('name', '').lower())
        for proxy_id, proxy_details in sorted_proxies:
            display_name = proxy_details.get('name', f"Proxy {proxy_id[:6]}...")
            self.proxy_combo.addItem(display_name, proxy_id) # User data is proxy_id

    def _populate_profiles(self):
        """Populates the profile combo box."""
        self.profile_combo.clear()

        # ---> REMOVE "All Rules" item <---
        # Use main window constants for consistency
        # all_rules_name = getattr(self.main_window, 'ALL_RULES_PROFILE_NAME', 'All Rules (Default)')
        # Use None as data for the "All/Global" assignment
        # self.profile_combo.addItem(all_rules_name, None)

        if not self.available_profiles:
             print("[Quick Add] No profiles available.")
             # Add a placeholder item? Or disable the dialog? Disable save?
             self.profile_combo.addItem("No Profiles Available", None)
             self.profile_combo.setEnabled(False)
             # Disable save button if needed
             save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
             if save_button: save_button.setEnabled(False)
             return

        self.profile_combo.setEnabled(True)
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_button: save_button.setEnabled(True)

        # Sort by name
        sorted_profiles = sorted(self.available_profiles.items(), key=lambda item: item[1].get('name', '').lower())
        for profile_id, profile_data in sorted_profiles:
            name = profile_data.get('name', f"Profile {profile_id[:6]}...")
            self.profile_combo.addItem(name, profile_id) # User data is profile_id

        # Select the first profile by default if none was pre-selected in __init__
        if self.profile_combo.currentIndex() == -1:
             self.profile_combo.setCurrentIndex(0)

    def _is_valid_domain_or_ip(self, value: str) -> bool:
        """Checks if a string is a valid domain name (allowing wildcard start) or a valid IP address."""
        if not value: return False

        # 1. Check for valid IP address (IPv4 or IPv6)
        try:
            ipaddress.ip_address(value)
            # IP addresses cannot have wildcards or be purely numeric
            if '*' in value or '?' in value or value.isdigit():
                 return False
            return True # It's a valid IP
        except ValueError:
            pass # Not a valid IP, proceed to domain check

        # 2. Check for valid domain name (reuse RuleEditWidget logic for consistency)
        pattern = r"^(\*\.)?([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        if ".." in value or value.endswith("-") or value.startswith("-") or value.endswith("."):
             return False
        if value.isdigit():
            return False
        return bool(re.match(pattern, value, re.IGNORECASE))

    def _on_save(self):
        """Validate input and emit signal if valid."""
        entry_raw = self.domain_input.text().strip()

        # Basic cleanup: remove http(s):// prefix if present
        if entry_raw.startswith("http://"): entry_raw = entry_raw[7:]
        if entry_raw.startswith("https://"): entry_raw = entry_raw[8:]
        # Remove trailing slashes or paths
        entry_raw = entry_raw.split('/')[0]
        # Remove port number
        entry = entry_raw.split(':')[0].lower() # Use lower case

        # ---> Use updated validation <---
        if not self._is_valid_domain_or_ip(entry):
            # ---> Update error message <---
            QMessageBox.warning(self, "Invalid Input", f"The format for '{entry}' is not a valid domain or IP address.")
            self.domain_input.setFocus()
            self.domain_input.selectAll()
            return # Keep dialog open

        selected_proxy_id = self.proxy_combo.currentData() # Returns data (ID or None)
        selected_profile_id = self.profile_combo.currentData() # Returns data (ID)

        if selected_profile_id is None or selected_profile_id not in self.available_profiles:
             QMessageBox.warning(self, "Invalid Profile", "Please select a valid profile.")
             self.profile_combo.setFocus()
             return

        # Emit the data
        # ---> Update print statement <---
        print(f"[Quick Add] Emitting save: Entry='{entry}', Proxy='{selected_proxy_id}', Profile='{selected_profile_id}'")
        self.save_rule.emit(entry, selected_proxy_id, selected_profile_id)
        self.accept() # Close the dialog successfully

    @staticmethod
    def get_rule_from_clipboard(main_window_ref):
        """
        Static method to create and execute the dialog, fetching data from clipboard.
        Connects the save signal internally before execution.
        The copy simulation should happen BEFORE this method is called.
        """
        # ---> Check for profiles before showing dialog <---
        if not main_window_ref.profiles:
             QMessageBox.warning(main_window_ref, "Cannot Add Rule", "No profiles exist. Please create a profile first.")
             return False

        # --- Read clipboard directly ---
        clipboard = QApplication.clipboard()
        clipboard_text = clipboard.text()
        print(f"[Quick Add] Clipboard content: '{clipboard_text}'")

        parsed_domain = QuickRuleAddDialog.parse_domain_from_text(clipboard_text)
        print(f"[Quick Add] Parsed domain: '{parsed_domain}'")

        dialog = QuickRuleAddDialog(
            main_window_ref,
            main_window_ref.proxies,
            main_window_ref.profiles, # Pass available profiles
            initial_domain=parsed_domain,
            parent=main_window_ref
        )
        # Connect signal here before exec()
        dialog.save_rule.connect(main_window_ref._handle_quick_rule_save)

        result = dialog.exec() # Executes the dialog loop

        # No need to return anything specific, signal handles the data transfer
        if result == QDialog.DialogCode.Accepted:
            print("[Quick Add] Dialog accepted (rule saved via signal).")
            return True # Indicate success if needed
        else:
            print("[Quick Add] Dialog cancelled.")
            return False # Indicate cancellation

    @staticmethod
    def parse_domain_from_text(text: str) -> str:
        """
        Attempts to extract a valid domain name or IP address from a string.
        """
        if not text:
            return ""

        cleaned_text = text.strip().lower()

        # --- Step 1: Handle file URIs explicitly ---
        if cleaned_text.startswith("file://"):
             # File URIs generally don't make sense for proxy rules unless they have a hostname
             try:
                 parsed_file_uri = urlparse(cleaned_text)
                 if parsed_file_uri.hostname:
                      potential_host = parsed_file_uri.hostname.lower()
                      # Validate if the extracted hostname is a valid domain/IP
                      try:
                          ipaddress.ip_address(potential_host)
                          print(f"[Parse Entry] Extracted IP from file URI: '{potential_host}'")
                          return potential_host # It's an IP
                      except ValueError:
                          domain_pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$|^localhost$"
                          if re.fullmatch(domain_pattern, potential_host):
                               print(f"[Parse Entry] Extracted domain from file URI: '{potential_host}'")
                               return potential_host # It's a domain
                      print(f"[Parse Entry] Ignoring file URI, invalid hostname: '{text}'")
                      return ""
                 else:
                      print(f"[Parse Entry] File URI without hostname, ignoring: '{text}'")
                      return ""
             except Exception as e:
                  print(f"[Parse Entry] Error parsing file URI: {e}")
                  return ""

        # --- Step 2: Use urlparse for standard URLs ---
        entry = None
        try:
            parse_target = cleaned_text
            # Ensure scheme for urlparse, handles domains and IPs better
            if '://' not in parse_target and ('.' in parse_target or ':' in parse_target or parse_target == 'localhost'):
                 parse_target = 'http://' + parse_target

            parsed: ParseResult = urlparse(parse_target)

            if parsed.hostname:
                 potential_entry = parsed.hostname.lower() # Use lowercase hostname
                 # Validate if it's an IP or Domain
                 try:
                      ipaddress.ip_address(potential_entry)
                      print(f"[Parse Entry] Parsed IP via urlparse: '{potential_entry}' from '{parse_target}'")
                      entry = potential_entry # It's a valid IP
                 except ValueError:
                      # Check if it's a valid domain structure
                      domain_pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$|^localhost$"
                      if re.fullmatch(domain_pattern, potential_entry):
                           print(f"[Parse Entry] Parsed Domain via urlparse: '{potential_entry}' from '{parse_target}'")
                           entry = potential_entry # It's a valid domain

                 # Basic sanity check (avoid common junk)
                 if entry and not any(char in entry for char in [' ', '\t', '\n', '<', '>']):
                      return entry # Return valid entry found by urlparse

            # Clear if urlparse didn't yield a valid domain/IP
            entry = None

        except Exception as e:
            print(f"[Parse Entry] urlparse failed or produced invalid result: {e}")
            entry = None # Ensure entry is None for fallback

        # --- Step 3: Fallback for plain domains/IPs or failed parsing ---
        if entry is None:
             print(f"[Parse Entry] Falling back to simple extraction for: '{cleaned_text}'")
             potential_entry = cleaned_text
             # Remove common prefixes if they weren't handled
             if potential_entry.startswith("http://"): potential_entry = potential_entry[7:]
             if potential_entry.startswith("https://"): potential_entry = potential_entry[8:]

             # Remove anything after '/', '?', '#', ':' (port)
             potential_entry = potential_entry.split('/')[0].split('?')[0].split('#')[0].split(':')[0]

             # Validate as IP first
             try:
                  ipaddress.ip_address(potential_entry)
                  if '*' not in potential_entry and '?' not in potential_entry: # IPs can't have wildcards
                      print(f"[Parse Entry] Fallback successful (IP): '{potential_entry}'")
                      return potential_entry
             except ValueError:
                 # Validate as Domain
                 # Allows letters, numbers, hyphens in parts, ending with letters.
                 domain_pattern = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$|^localhost$"
                 if re.fullmatch(domain_pattern, potential_entry):
                      print(f"[Parse Entry] Fallback successful (Domain): '{potential_entry}'")
                      return potential_entry

             print(f"[Parse Entry] Fallback failed, no valid domain or IP pattern found in: '{potential_entry}'")
             return ""

        return "" # Default return empty if all else fails 