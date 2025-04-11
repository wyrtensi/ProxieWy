import hashlib
from PySide6.QtGui import QColor

def generate_color_from_id(id_str: str, saturation: float = 0.7, lightness: float = 0.5) -> QColor:
    """
    Generates a QColor based on the hash of an ID string.
    Uses HSL color space for better visual separation.
    """
    if not id_str:
        # Return a default color for None or empty IDs (e.g., Direct Connection, Default Profile)
        return QColor("#777777") # Grey

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

def get_contrasting_text_color(bg_color: QColor) -> QColor:
    """
    Determines whether black or white text provides better contrast against a given background color.
    """
    # Calculate luminance using the standard formula (Y = 0.2126*R + 0.7152*G + 0.0722*B)
    # Values are normalized (0.0 to 1.0)
    r = bg_color.redF()
    g = bg_color.greenF()
    b = bg_color.blueF()
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b

    # Threshold can be adjusted, 0.5 is a common starting point
    if luminance > 0.5:
        return QColor(Qt.GlobalColor.black)
    else:
        return QColor(Qt.GlobalColor.white)

# Add colorize/icon functions if they aren't already here or easily importable
import re
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt, QSize

def load_and_colorize_svg_content(icon_path: str, color: str) -> bytes:
    """Loads SVG content and sets the stroke color on the root SVG element, ensuring fill is none."""
    try:
        with open(icon_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_tag_match = re.search(r'<svg\b[^>]*>', svg_content, re.IGNORECASE)
        if not svg_tag_match: return svg_content.encode('utf-8')
        svg_tag_original = svg_tag_match.group(0); svg_tag_new = svg_tag_original
        svg_tag_new = re.sub(r'\s?stroke\s*=\s*["\'][^"\']+["\']', '', svg_tag_new, flags=re.IGNORECASE)
        svg_tag_new = re.sub(r'\s?fill\s*=\s*["\'](?!none)[^"\']*["\']', '', svg_tag_new, flags=re.IGNORECASE)
        if 'fill="none"' not in svg_tag_new: svg_tag_new = svg_tag_new.replace('>', ' fill="none">', 1)
        svg_tag_new = re.sub(r'<svg\b', rf'<svg stroke="{color}"', svg_tag_new, 1, re.IGNORECASE)
        modified_content = svg_content.replace(svg_tag_original, svg_tag_new, 1)
        return modified_content.encode('utf-8')
    except FileNotFoundError: return b""
    except Exception as e: return b""

def create_icon_from_svg_data(svg_data: bytes) -> QIcon:
    """Creates QIcon from raw SVG data bytes using QSvgRenderer."""
    if not svg_data: return QIcon()
    renderer = QSvgRenderer(svg_data);
    if not renderer.isValid(): return QIcon()
    default_size = renderer.defaultSize();
    if default_size.isEmpty(): default_size = QSize(32, 32)
    pixmap = QPixmap(default_size); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); renderer.render(painter); painter.end()
    if pixmap.isNull(): return QIcon()
    return QIcon(pixmap) 