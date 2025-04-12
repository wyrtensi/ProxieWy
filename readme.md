# ProxieWy - Rule-Based Proxy Management

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Qt Version](https://img.shields.io/badge/Qt%20for%20Python-PySide6-green.svg)](https://www.qt.io/qt-for-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ProxieWy** is a versatile desktop application designed to simplify the management of multiple proxy servers and intelligently route your network traffic. Define custom rules based on domain names and assign them to different profiles for seamless switching between network configurations. Built with Python and the modern PySide6 (Qt) framework.

---

![Logo](logo.png)

---

## ✨ Key Features

*   **🚀 Proxy Management:**
    *   Easily **add, edit, and remove** various proxy types: `HTTP`, `HTTPS`, `SOCKS5`.
    *   Built-in support for **authenticated proxies** (username/password).
    *   **Test proxy connectivity** with a single click to ensure they are working.
*   **🚦 Rule-Based Routing:**
    *   Define granular rules to forward traffic for specific **domains** (e.g., `example.com`) or **wildcard patterns** (e.g., `*.example.net`) or **IP address** (e.g., `1.1.1.1`).
    *   Route matched traffic through a **chosen proxy** or allow **direct connection**.
    *   Quickly **enable or disable** individual rules without deleting them.
    *   **(New!)** Quickly add a rule based on **currently selected text** (attempts to copy from focused application) or clipboard content via a **global hotkey**.
*   **🎭 Profiles:**
    *   Organize rules into distinct **profiles** (e.g., "Work VPN", "Home Streaming", "Development").
    *   **Switch active profiles** effortlessly via the UI or global hotkeys.
    *   Designate rules as **global** (apply always) or **profile-specific**.
*   **⌨️ Global Hotkeys:**
    *   Configure and use **system-wide hotkeys** to:
        *   Toggle the proxy engine on/off.
        *   Show/Hide the application window.
        *   Switch to the next/previous profile.
        *   Trigger the "Quick Add Rule" dialog (attempts to copy selected text).
*   **🖥️ System Integration:**
    *   Convenient **system tray icon** displaying the current engine status (Active, Inactive, Error).
    *   Flexible window behavior: **minimize to tray** or **exit** on close.
    *   **(Windows Only)** Seamlessly toggles the **system-wide proxy settings** when the ProxieWy engine is activated/deactivated.
*   **🎨 User Interface:**
    *   Modern and intuitive UI built with **PySide6**.
    *   Choose between **Dark** and **Light** visual themes.
    *   Integrated **filtering** for quickly finding specific proxies or rules.
*   **⚙️ Core Engine:**
    *   Lightweight local proxy server listens for connections (default: `127.0.0.1:8080`).
    *   Intelligently handles `CONNECT` requests (for HTTPS/SOCKS tunnels) and standard HTTP requests based on your defined rules.

## 🛠️ Requirements

*   **Python:** Version 3.10 or newer is recommended.
*   **PySide6:** The official Qt for Python bindings.
*   **PySocks:** (Optional, but required for `SOCKS5` proxy functionality).
*   **pynput:** Required for global hotkey support.
*   **(Windows Only)** **pywin32:** Recommended for more reliable hotkey simulation (copy action).

## 📦 Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/wyrtensi/ProxieWy.git 
    cd ProxieWy
    ```

2.  **Create and Activate a Virtual Environment** (Highly Recommended):
    ```bash
    # Create the environment
    python -m venv venv

    # Activate it:
    # Windows (Command Prompt/PowerShell)
    .\venv\Scripts\activate
    # macOS / Linux (Bash/Zsh)
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    *(Make sure you have a `requirements.txt` file)*
    ```bash
    # Example requirements.txt:
    # PySide6>=6.5
    # PySocks>=1.7 # Optional for SOCKS5
    # pynput>=1.7
    # pywin32>=300 # If on Windows

    pip install -r requirements.txt
    ```

## ▶️ Running ProxieWy

1.  Ensure your virtual environment is activated.
2.  Navigate to the project's root directory (`ProxieWy`).
3.  Execute the main script:
    ```bash
    python main.py
    ```

The application will start, typically minimized to the system tray. Click the tray icon to manage ProxieWy.

## ⚙️ Configuration Guide

*   **Settings Location:** Configuration (`settings.ini`) is stored in your standard user application data folder. You can find the exact path in the application logs on startup or typically at:
    *   *Windows:* `%LOCALAPPDATA%\wyrtensi\ProxieWy\settings.ini`
*   **Adding Proxies:** Use the "Proxies" tab -> "Add Proxy" button. Fill in the details (name, type, address, port, auth). Test proxies using the⚡️ icon.
*   **Creating Rules:** Go to the "Rules" tab. Select the desired `Profile` from the dropdown (or "All Rules" for global). Click "Add Rule(s)", enter domain(s) (one per line), and choose the target proxy or "Direct Connection".
*   **Quick Adding Rules:** Select a URL/domain in *any* application, press the configured "Quick Add Rule" hotkey. ProxieWy will attempt to simulate a Copy command and then open the dialog with the domain parsed from the clipboard. (Note: Simulation reliability depends on OS and focus).
*   **Managing Profiles:** Use the "Settings" tab to add, rename, or delete profiles. The **active profile** (determining which rules are currently used by the engine) is selected via the dropdown on the **"Rules" tab**.
*   **How Profiles Work:** The proxy engine uses rules assigned to the **currently active profile** *plus* any rules assigned to **"All Rules (Default)"**.
*   **Global Hotkeys:** Configure shortcuts in the "Settings" tab for various actions.
*   **System Proxy (Windows):** Toggling the main switch (top-left in the sidebar) automatically attempts to enable/disable the Windows system proxy settings. Network-aware applications might need a restart to recognize the change.

## 🧑‍💻 Development Insights

*   **Project Structure:**
    *   `src/gui/`: User interface components (main window, custom widgets).
    *   `src/core/`: Backend logic (proxy engine, rule matcher, hotkey manager).
    *   `src/assets/`: Static files (icons, images, `.qss` stylesheets).
*   **Styling:** Uses Qt Style Sheets (`.qss`) located in `src/assets/styles` for theming.
*   **Global Hotkeys:** Implemented using `pynput` for listening and platform-specific simulation (like `ctypes` on Windows) for the "copy selected" feature. Requires appropriate permissions (e.g., Accessibility on macOS).

## 🌱 Future Ideas (Potential Enhancements)

*   [ ] Add import/export functionality for proxies and rules.
*   [ ] Visual traffic monitoring/logging within the UI.
*   [ ] Cross-platform system proxy configuration (macOS, Linux).
*   [x] Packaging for easier distribution (pyinstaller --onefile --noconsole --icon=icon.ico --version-file version.txt --add-data "src/assets/;src/assets/" main.py).
*   [xSS] Fast adding selected urls to the proxy rules via hotkey.

Please ensure your code adheres to basic style guidelines and includes appropriate documentation or tests where necessary.

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for full details.

## 🙏 Acknowledgments

*   Vibe-coded and developed using Gemini-2.5-pro-exp.
