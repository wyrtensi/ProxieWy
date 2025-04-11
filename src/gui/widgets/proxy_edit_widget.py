from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QSizePolicy, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator

class ProxyEditWidget(QFrame):
    """Widget for adding or editing a proxy entry."""
    # Signal emitted when save is clicked (passes proxy details dictionary)
    save_proxy = Signal(dict)
    # Signal emitted when cancel is clicked
    cancelled = Signal()

    def __init__(self, main_window, proxy_data=None, parent=None):
        """
        Initialize the edit widget.
        proxy_data (dict, optional): Existing data to populate fields for editing.
        """
        super().__init__(parent)
        self.setObjectName("ProxyEditFrame")
        self.main_window = main_window # Store reference
        # self.setFrameShape(QFrame.Shape.StyledPanel) # Add frame for visual separation
        # self.setFrameShadow(QFrame.Shadow.Raised)

        self._init_ui()

        if proxy_data:
            self.load_data(proxy_data)
        else:
            self.clear_fields() # Ensure fields are empty for adding

    def _init_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(10)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        # Name
        name_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setFixedWidth(80)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., My Home Proxy")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        form_layout.addLayout(name_layout)

        # Type
        type_layout = QHBoxLayout()
        type_label = QLabel("Type:")
        type_label.setFixedWidth(80)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["HTTP", "HTTPS", "SOCKS5"]) # Add more if needed later
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        form_layout.addLayout(type_layout)

        # Address (Host/IP)
        address_layout = QHBoxLayout()
        address_label = QLabel("Address:")
        address_label.setFixedWidth(80)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("e.g., 127.0.0.1 or proxy.example.com")
        address_layout.addWidget(address_label)
        address_layout.addWidget(self.address_input)
        form_layout.addLayout(address_layout)

        # Port
        port_layout = QHBoxLayout()
        port_label = QLabel("Port:")
        port_label.setFixedWidth(80)
        self.port_input = QLineEdit() # Use QLineEdit for now, can add QIntValidator later
        self.port_input.setPlaceholderText("e.g., 8080")
        # Basic input mask or validator could be added
        # self.port_input.setInputMask("00000;") # Example mask
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        port_layout.addStretch()
        form_layout.addLayout(port_layout)

        # Add validator for Port input
        self.port_input.setValidator(QIntValidator(1, 65535, self)) # Add validator

        # --- Authentication Fields (Always Visible, Optional) ---
        # Remove Checkbox and separate widget
        # Add separator
        auth_separator = QFrame()
        auth_separator.setFrameShape(QFrame.Shape.HLine)
        auth_separator.setFrameShadow(QFrame.Shadow.Sunken)
        form_layout.addWidget(auth_separator)

        # Username
        username_layout = QHBoxLayout()
        username_label = QLabel("Username:") # Optional indicated by placeholder
        username_label.setFixedWidth(80)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Optional")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        form_layout.addLayout(username_layout)

        # Password
        password_layout = QHBoxLayout()
        password_label = QLabel("Password:") # Optional indicated by placeholder
        password_label.setFixedWidth(80)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Optional")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        form_layout.addLayout(password_layout)

        input_min_height = 28 # Keep minimum height
        self.username_input.setMinimumHeight(input_min_height)
        self.password_input.setMinimumHeight(input_min_height)
        # --- End Authentication Fields ---

        main_layout.addLayout(form_layout)

        # Add stretch *before* buttons if needed, or rely on parent layout
        main_layout.addStretch(1) # Add stretch to push buttons down

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push buttons to the right

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.clicked.connect(self.cancelled.emit)

        self.save_button = QPushButton("Save Proxy")
        self.save_button.setObjectName("SaveButton") # For specific styling
        self.save_button.clicked.connect(self._on_save)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

    def _on_save(self):
        """Validate input and emit save signal."""
        name = self.name_input.text().strip()
        proxy_type = self.type_combo.currentText()
        address = self.address_input.text().strip()
        port_str = self.port_input.text().strip()

        # Use QMessageBox for validation errors
        if not name:
            QMessageBox.warning(self, "Input Error", "Proxy Name cannot be empty.")
            self.name_input.setFocus()
            return
        if not address:
            QMessageBox.warning(self, "Input Error", "Proxy Address cannot be empty.")
            self.address_input.setFocus()
            return
        if not port_str:
            QMessageBox.warning(self, "Input Error", "Proxy Port cannot be empty.")
            self.port_input.setFocus()
            return

        port_state = self.port_input.validator().validate(port_str, 0)[0]
        if port_state != QIntValidator.State.Acceptable:
            QMessageBox.warning(self, "Input Error", "Invalid Port number (must be 1-65535).")
            self.port_input.setFocus()
            return
        port = int(port_str)

        # Always read username/password
        username = self.username_input.text() # Keep whitespace
        password = self.password_input.text()

        # Determine if auth is 'required' based on if fields are filled
        requires_auth = bool(username or password)

        proxy_details = {
            "name": name,
            "type": proxy_type,
            "address": address,
            "port": port,
            "requires_auth": requires_auth, # Save based on content
            "username": username,
            "password": password,
            "id": getattr(self, "_editing_id", None)
        }

        self.save_proxy.emit(proxy_details)
        # Optionally clear fields after successful save signal emission
        # self.clear_fields()

    def load_data(self, proxy_data: dict):
        """Populate fields with data from a proxy dictionary."""
        self.name_input.setText(proxy_data.get("name", ""))
        self.type_combo.setCurrentText(proxy_data.get("type", "HTTP"))
        self.address_input.setText(proxy_data.get("address", ""))
        self.port_input.setText(str(proxy_data.get("port", "")))
        # Directly load username/password
        self.username_input.setText(proxy_data.get("username", ""))
        self.password_input.setText(proxy_data.get("password", ""))
        self._editing_id = proxy_data.get("id") # Store ID for saving

    def clear_fields(self):
        """Clear all input fields."""
        self.name_input.clear()
        self.type_combo.setCurrentIndex(0) # Default to first type
        self.address_input.clear()
        self.port_input.clear()
        # Directly clear username/password
        self.username_input.clear()
        self.password_input.clear()
        self._editing_id = None # Clear editing ID

    def set_focus_on_name(self):
        """Set focus to the name input field."""
        self.name_input.setFocus() 