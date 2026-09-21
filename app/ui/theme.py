"""
PDF Workspace - Application Theme Configuration
Defines colors, fonts, and style constants for the app.
"""

# Color Palette - Modern Material Design inspired
COLORS = {
    # Primary
    'primary': '#1565C0',           # Blue 800
    'primary_light': '#1E88E5',     # Blue 600
    'primary_dark': '#0D47A1',      # Blue 900
    'on_primary': '#FFFFFF',
    
    # Secondary / Accent
    'accent': '#00ACC1',            # Cyan 600
    'accent_light': '#26C6DA',      # Cyan 400
    'on_accent': '#FFFFFF',
    
    # Background
    'background': '#FAFAFA',        # Grey 50
    'surface': '#FFFFFF',
    'surface_variant': '#F5F5F5',   # Grey 100
    
    # Text
    'text_primary': '#212121',      # Grey 900
    'text_secondary': '#757575',    # Grey 600
    'text_hint': '#BDBDBD',         # Grey 400
    
    # Status
    'success': '#43A047',           # Green 600
    'warning': '#FB8C00',           # Orange 600
    'error': '#E53935',             # Red 600
    'info': '#1E88E5',              # Blue 600
    
    # Sidebar
    'sidebar_bg': '#263238',        # Blue Grey 900
    'sidebar_text': '#ECEFF1',      # Blue Grey 50
    'sidebar_active': '#1565C0',    # Blue 800
    'sidebar_hover': '#37474F',     # Blue Grey 800
    
    # Table
    'table_header': '#E3F2FD',      # Blue 50
    'table_row_alt': '#FAFAFA',     # Grey 50
    'table_border': '#E0E0E0',      # Grey 300
    'table_selected': '#BBDEFB',    # Blue 100
    
    # Divider
    'divider': '#E0E0E0',           # Grey 300
    
    # Privacy badge
    'privacy_bg': '#E8F5E9',        # Green 50
    'privacy_text': '#2E7D32',      # Green 800
}

# Font sizes
FONTS = {
    'h1': 24,
    'h2': 20,
    'h3': 18,
    'h4': 16,
    'body': 14,
    'caption': 12,
    'small': 10,
    'button': 14,
}

# Spacing
SPACING = {
    'xs': 4,
    'sm': 8,
    'md': 16,
    'lg': 24,
    'xl': 32,
    'xxl': 48,
}

# Icon mappings (using KivyMD icon names)
ICONS = {
    'open_pdf': 'file-pdf-box',
    'search': 'magnify',
    'convert': 'file-export',
    'category': 'folder',
    'category_open': 'folder-open',
    'filter': 'filter-variant',
    'sort': 'sort',
    'edit': 'pencil',
    'delete': 'delete',
    'add': 'plus',
    'close': 'close',
    'check': 'check',
    'save': 'content-save',
    'export': 'export',
    'settings': 'cog',
    'zoom_in': 'magnify-plus',
    'zoom_out': 'magnify-minus',
    'fit_width': 'arrow-expand-horizontal',
    'fit_page': 'fit-to-page',
    'prev_page': 'chevron-left',
    'next_page': 'chevron-right',
    'privacy': 'lock',
    'table': 'table',
    'record': 'card-text',
    'page': 'file-document',
    'stats': 'chart-bar',
    'home': 'home',
    'recent': 'clock-outline',
    'project': 'briefcase',
    'cancel': 'cancel',
    'warning': 'alert',
    'error': 'alert-circle',
    'success': 'check-circle',
    'info': 'information',
    'merge': 'merge',
    'move': 'arrow-right',
    'copy': 'content-copy',
    'select_all': 'select-all',
    'download': 'download',
    'docx': 'file-word',
    'xlsx': 'file-excel',
    'csv': 'file-delimited',
    'json': 'code-json',
    'html': 'language-html5',
    'txt': 'file-document-outline',
    'markdown': 'language-markdown',
    'pdf': 'file-pdf-box',
}


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple:
    """Convert hex color string to RGBA tuple (0-1 range)."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b, alpha)


def get_color(name: str, alpha: float = 1.0) -> tuple:
    """Get a color by name as RGBA tuple."""
    hex_val = COLORS.get(name, '#000000')
    return hex_to_rgba(hex_val, alpha)
