import hashlib
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt, QSize
import sys
import os
import re

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    # Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in bundle, resolve path using _MEIPASS folder
        # The --add-data "src/assets;src" command copies the contents
        # of the local src/assets into the bundle's 'src/assets' directory.
        # The relative_path variable already contains "src/assets/..."
        base_path = sys._MEIPASS
        return os.path.join(base_path, relative_path)
    else:
        # Running in normal Python environment
        # Assume relative_path is relative to the project root or context where script runs.
        # In dev, this often works if run from the project root.
        return relative_path

def generate_color_from_id(id_str: str, saturation: float = 0.7, lightness: float = 0.5) -> QColor:
    """
    Generates a QColor based on the hash of an ID string.
    Uses HSL color space for better visual separation.
    """
    if not id_str:
        # Return a default color for None or empty IDs (e.g., Direct Connection, Default Profile)
        return QColor("#888888") # Slightly darker Grey for better visibility on light theme

    # Hash the ID string
    hash_object = hashlib.md5(id_str.encode())
    hash_digest = hash_object.digest()

    # Use the first few bytes of the hash to determine Hue
    # Hue ranges from 0 to 359
    hue = int.from_bytes(hash_digest[:2], byteorder='little') % 360

    color = QColor()
    # setHslF takes floats between 0.0 and 1.0
    color.setHslF(hue / 360.0, saturation, lightness)
    return color

# --- SVG Loading/Coloring Functions (Consolidated Here) ---

def load_and_colorize_svg_content(icon_path: str, color: str) -> bytes:
    """
    Loads SVG content from the given path (resolving bundle path if needed),
    and sets the stroke color on the root SVG element, ensuring fill is none.
    """
    resolved_path = resource_path(icon_path) # Use helper to get correct path
    try:
        with open(resolved_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_tag_match = re.search(r'<svg\b[^>]*>', svg_content, re.IGNORECASE)
        if not svg_tag_match:
            print(f"Warning: Could not find <svg> tag in {resolved_path}")
            return svg_content.encode('utf-8')
        svg_tag_original = svg_tag_match.group(0); svg_tag_new = svg_tag_original
        # Clean up existing attributes
        svg_tag_new = re.sub(r'\s?stroke\s*=\s*["\'][^"\']+["\']', '', svg_tag_new, flags=re.IGNORECASE)
        svg_tag_new = re.sub(r'\s?fill\s*=\s*["\'](?!none)[^"\']*["\']', '', svg_tag_new, flags=re.IGNORECASE)
        # Ensure fill="none" and add desired stroke
        if 'fill="none"' not in svg_tag_new: svg_tag_new = svg_tag_new.replace('>', ' fill="none">', 1)
        svg_tag_new = re.sub(r'<svg\b', rf'<svg stroke="{color}"', svg_tag_new, 1, re.IGNORECASE)
        modified_content = svg_content.replace(svg_tag_original, svg_tag_new, 1)
        return modified_content.encode('utf-8')
    except FileNotFoundError:
        print(f"Error: Icon file not found at resolved path {resolved_path} (original: {icon_path})")
        return b""
    except Exception as e:
        print(f"Error loading/colorizing SVG {resolved_path}: {e}")
        return b""

def create_icon_from_svg_data(svg_data: bytes) -> QIcon:
    """Creates QIcon from raw SVG data bytes using QSvgRenderer."""
    if not svg_data: return QIcon()
    renderer = QSvgRenderer(svg_data);
    if not renderer.isValid():
         print(f"Warning: Failed to create valid QSvgRenderer from SVG data.")
         return QIcon()
    default_size = renderer.defaultSize();
    if default_size.isEmpty(): default_size = QSize(32, 32) # Sensible fallback
    pixmap = QPixmap(default_size); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); renderer.render(painter); painter.end()
    if pixmap.isNull():
         print("Warning: Failed to render SVG to pixmap.")
         return QIcon()
    return QIcon(pixmap) 