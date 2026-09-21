"""
PDF Workspace - PDF Viewer Component
Renders PDF pages as images for display in the Kivy UI.

Supports multiple rendering backends:
1. PyMuPDF (fitz) - fastest, desktop only
2. Android PdfRenderer - native Android rendering via pyjnius
3. Fallback: shows text-only view from extracted text in database
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.scatter import Scatter
from kivy.graphics import Color, Rectangle, Line
from kivy.graphics.texture import Texture
from kivy.properties import (NumericProperty, StringProperty, 
                              ObjectProperty, ListProperty, BooleanProperty)
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.utils import platform

import io
import os

# Detect available PDF rendering backend
_RENDER_BACKEND = 'text'  # fallback

try:
    import fitz
    _RENDER_BACKEND = 'fitz'
except ImportError:
    pass

if platform == 'android' and _RENDER_BACKEND == 'text':
    try:
        from jnius import autoclass
        _test = autoclass('android.graphics.pdf.PdfRenderer')
        _RENDER_BACKEND = 'android'
    except Exception:
        pass


class PDFViewer(BoxLayout):
    """Integrated PDF viewer widget that renders PDF pages as images.
    
    Supports PyMuPDF (desktop), Android PdfRenderer (mobile),
    and text-only fallback.
    """

    current_page = NumericProperty(1)
    total_pages = NumericProperty(1)
    zoom_level = NumericProperty(1.0)
    pdf_path = StringProperty("")
    highlight_rects = ListProperty([])
    is_loaded = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(PDFViewer, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self._fitz_doc = None
        self._page_text = {}  # Cache for text-mode viewing
        self._render_backend = _RENDER_BACKEND

        # Background
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Navigation Bar
        self.nav_bar = BoxLayout(
            size_hint_y=None, height=dp(44),
            spacing=dp(4), padding=[dp(8), dp(4), dp(8), dp(4)]
        )

        with self.nav_bar.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            self._nav_bg = Rectangle(pos=self.nav_bar.pos, size=self.nav_bar.size)
        self.nav_bar.bind(
            pos=lambda i, v: setattr(self._nav_bg, 'pos', v),
            size=lambda i, v: setattr(self._nav_bg, 'size', v)
        )

        self.btn_prev = Button(
            text="◀", size_hint_x=None, width=dp(44),
            background_color=(0.3, 0.3, 0.3, 1), color=(1, 1, 1, 1),
            font_size=sp(16)
        )
        self.btn_prev.bind(on_release=lambda x: self.prev_page())

        self.page_input = TextInput(
            text="1", size_hint_x=None, width=dp(50),
            multiline=False, input_filter='int',
            font_size=sp(13), halign='center',
            background_color=(0.15, 0.15, 0.15, 1),
            foreground_color=(1, 1, 1, 1)
        )
        self.page_input.bind(on_text_validate=self._on_page_input)

        self.lbl_page = Label(
            text="/ 1", size_hint_x=None, width=dp(50),
            color=(1, 1, 1, 1), font_size=sp(13)
        )

        self.btn_next = Button(
            text="▶", size_hint_x=None, width=dp(44),
            background_color=(0.3, 0.3, 0.3, 1), color=(1, 1, 1, 1),
            font_size=sp(16)
        )
        self.btn_next.bind(on_release=lambda x: self.next_page())

        # Spacer
        spacer = Label(text="", size_hint_x=0.3)

        self.btn_zoom_out = Button(
            text="−", size_hint_x=None, width=dp(40),
            background_color=(0.3, 0.3, 0.3, 1), color=(1, 1, 1, 1),
            font_size=sp(18)
        )
        self.btn_zoom_out.bind(on_release=lambda x: self.zoom_out())

        self.lbl_zoom = Label(
            text="100%", size_hint_x=None, width=dp(50),
            color=(1, 1, 1, 1), font_size=sp(12)
        )

        self.btn_zoom_in = Button(
            text="+", size_hint_x=None, width=dp(40),
            background_color=(0.3, 0.3, 0.3, 1), color=(1, 1, 1, 1),
            font_size=sp(18)
        )
        self.btn_zoom_in.bind(on_release=lambda x: self.zoom_in())

        self.btn_fit = Button(
            text="Fit", size_hint_x=None, width=dp(44),
            background_color=(0.3, 0.3, 0.3, 1), color=(1, 1, 1, 1),
            font_size=sp(12)
        )
        self.btn_fit.bind(on_release=lambda x: self.fit_page())

        self.nav_bar.add_widget(self.btn_prev)
        self.nav_bar.add_widget(self.page_input)
        self.nav_bar.add_widget(self.lbl_page)
        self.nav_bar.add_widget(self.btn_next)
        self.nav_bar.add_widget(spacer)
        self.nav_bar.add_widget(self.btn_zoom_out)
        self.nav_bar.add_widget(self.lbl_zoom)
        self.nav_bar.add_widget(self.btn_zoom_in)
        self.nav_bar.add_widget(self.btn_fit)

        self.add_widget(self.nav_bar)

        # Content area - scrollable
        self.scroll_view = ScrollView(size_hint=(1, 1), bar_width=dp(8))

        # For image rendering
        self.page_image = Image(
            size_hint=(None, None),
            allow_stretch=True,
            keep_ratio=True
        )

        # For text fallback
        self.text_view = Label(
            text="", size_hint=(1, None),
            text_size=(None, None),
            color=(0, 0, 0, 1), font_size=sp(12),
            halign='left', valign='top',
            markup=True
        )

        if self._render_backend in ('fitz', 'android'):
            self.scroll_view.add_widget(self.page_image)
        else:
            self.scroll_view.add_widget(self.text_view)

        self.add_widget(self.scroll_view)

        # Info label for status
        self.info_label = Label(
            text=f"Renderer: {self._render_backend}",
            size_hint_y=None, height=dp(20),
            color=(0.5, 0.5, 0.5, 1), font_size=sp(10)
        )
        self.add_widget(self.info_label)

        self.bind(current_page=self._on_page_change)
        self.bind(zoom_level=self._on_zoom_change)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def load_pdf(self, path: str):
        """Load a PDF file for viewing.
        
        Args:
            path: Absolute path to the PDF file.
        """
        if not os.path.exists(path):
            self.info_label.text = f"File not found: {path}"
            return

        self.pdf_path = path

        try:
            if self._render_backend == 'fitz':
                self._load_fitz(path)
            elif self._render_backend == 'android':
                self._load_android(path)
            else:
                self._load_text_mode(path)

            self.is_loaded = True
            self.current_page = 1
            self._render_page()
            self.info_label.text = f"Loaded: {os.path.basename(path)} ({self.total_pages} pages)"
        except Exception as e:
            self.info_label.text = f"Error: {str(e)}"
            print(f"PDF load error: {e}")

    def _load_fitz(self, path: str):
        """Load with PyMuPDF."""
        if self._fitz_doc:
            self._fitz_doc.close()
        self._fitz_doc = fitz.open(path)
        self.total_pages = len(self._fitz_doc)

    def _load_android(self, path: str):
        """Get page count on Android."""
        try:
            from jnius import autoclass
            PdfRenderer = autoclass('android.graphics.pdf.PdfRenderer')
            ParcelFileDescriptor = autoclass('android.os.ParcelFileDescriptor')
            JavaFile = autoclass('java.io.File')

            file = JavaFile(path)
            fd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
            renderer = PdfRenderer(fd)
            self.total_pages = renderer.getPageCount()
            renderer.close()
            fd.close()
        except Exception as e:
            print(f"Android PDF load error: {e}")
            # Fallback to pypdf for page count
            try:
                import pypdf
                reader = pypdf.PdfReader(path)
                self.total_pages = len(reader.pages)
            except Exception:
                self.total_pages = 1

    def _load_text_mode(self, path: str):
        """Load in text-only mode using pypdf."""
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            self.total_pages = len(reader.pages)
            # Cache extracted text
            self._page_text = {}
            for i, page in enumerate(reader.pages):
                try:
                    self._page_text[i + 1] = page.extract_text() or "(No text on this page)"
                except Exception:
                    self._page_text[i + 1] = "(Error extracting text)"
        except Exception as e:
            print(f"Text mode load error: {e}")
            self.total_pages = 1
            self._page_text = {1: f"Error loading PDF: {e}"}

    def goto_page(self, page_num: int):
        """Navigate to a specific page.
        
        Args:
            page_num: 1-based page number.
        """
        if 1 <= page_num <= self.total_pages:
            self.current_page = page_num
            self._render_page()

    def next_page(self):
        """Navigate to the next page."""
        self.goto_page(self.current_page + 1)

    def prev_page(self):
        """Navigate to the previous page."""
        self.goto_page(self.current_page - 1)

    def zoom_in(self):
        """Increase zoom level by 20%."""
        self.zoom_level = min(self.zoom_level * 1.2, 5.0)

    def zoom_out(self):
        """Decrease zoom level by 20%."""
        self.zoom_level = max(self.zoom_level / 1.2, 0.3)

    def fit_width(self):
        """Fit page to view width."""
        if self._render_backend == 'fitz' and self._fitz_doc:
            page = self._fitz_doc.load_page(self.current_page - 1)
            rect = page.rect
            if rect.width > 0 and self.scroll_view.width > 0:
                self.zoom_level = (self.scroll_view.width - dp(20)) / rect.width
        else:
            self.zoom_level = 1.0

    def fit_page(self):
        """Fit page to view."""
        if self._render_backend == 'fitz' and self._fitz_doc:
            page = self._fitz_doc.load_page(self.current_page - 1)
            rect = page.rect
            if rect.width > 0 and rect.height > 0:
                zoom_w = (self.scroll_view.width - dp(20)) / rect.width
                zoom_h = (self.scroll_view.height - dp(20)) / rect.height
                self.zoom_level = min(zoom_w, zoom_h)
        else:
            self.zoom_level = 1.0

    def highlight_text(self, text: str, page_num: int):
        """Highlight matching text on a specific page.
        
        Args:
            text: Text to search for.
            page_num: 1-based page number.
        """
        if self._render_backend == 'fitz' and self._fitz_doc:
            page = self._fitz_doc.load_page(page_num - 1)
            rects = page.search_for(text)
            self.highlight_rects = [(r.x0, r.y0, r.x1, r.y1) for r in rects]
        
        if page_num != self.current_page:
            self.goto_page(page_num)

    def clear_highlights(self):
        """Clear all text highlights."""
        self.highlight_rects = []
        self.page_image.canvas.after.clear()

    def _on_page_change(self, instance, value):
        """Update page label when page changes."""
        self.lbl_page.text = f"/ {self.total_pages}"
        self.page_input.text = str(self.current_page)

    def _on_zoom_change(self, instance, value):
        """Re-render when zoom changes."""
        self.lbl_zoom.text = f"{int(self.zoom_level * 100)}%"
        if self.is_loaded:
            self._render_page()

    def _on_page_input(self, instance):
        """Handle manual page number input."""
        try:
            page = int(instance.text)
            self.goto_page(page)
        except (ValueError, TypeError):
            instance.text = str(self.current_page)

    def _render_page(self):
        """Render the current page using the available backend."""
        if not self.is_loaded:
            return

        try:
            if self._render_backend == 'fitz':
                self._render_fitz()
            elif self._render_backend == 'android':
                self._render_android()
            else:
                self._render_text()
        except Exception as e:
            print(f"Render error: {e}")
            self.info_label.text = f"Render error: {e}"

    def _render_fitz(self):
        """Render using PyMuPDF."""
        if not self._fitz_doc:
            return

        page = self._fitz_doc.load_page(self.current_page - 1)
        mat = fitz.Matrix(self.zoom_level * 1.5, self.zoom_level * 1.5)
        pixmap = page.get_pixmap(matrix=mat, alpha=False)

        # Create Kivy texture from pixmap
        texture = Texture.create(
            size=(pixmap.width, pixmap.height), colorfmt='rgb'
        )
        texture.blit_buffer(pixmap.samples, colorfmt='rgb', bufferfmt='ubyte')
        texture.flip_vertical()

        self.page_image.texture = texture
        self.page_image.size = (pixmap.width, pixmap.height)

        # Reset scroll
        self.scroll_view.scroll_x = 0
        self.scroll_view.scroll_y = 1

        # Draw highlights
        self._draw_highlights()

    def _render_android(self):
        """Render using Android PdfRenderer."""
        try:
            from jnius import autoclass
            PdfRenderer = autoclass('android.graphics.pdf.PdfRenderer')
            ParcelFileDescriptor = autoclass('android.os.ParcelFileDescriptor')
            JavaFile = autoclass('java.io.File')
            Bitmap = autoclass('android.graphics.Bitmap')
            BitmapConfig = autoclass('android.graphics.Bitmap$Config')
            ByteArrayOutputStream = autoclass('java.io.ByteArrayOutputStream')
            CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')

            file = JavaFile(self.pdf_path)
            fd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
            renderer = PdfRenderer(fd)

            page = renderer.openPage(self.current_page - 1)

            # Calculate size with zoom
            scale = self.zoom_level * 2  # 2x for retina-like quality
            width = int(page.getWidth() * scale)
            height = int(page.getHeight() * scale)

            bitmap = Bitmap.createBitmap(width, height, BitmapConfig.ARGB_8888)
            page.render(bitmap, None, None, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)

            # Convert bitmap to PNG bytes
            stream = ByteArrayOutputStream()
            bitmap.compress(CompressFormat.PNG, 100, stream)
            png_bytes = bytes(stream.toByteArray())

            page.close()
            renderer.close()
            fd.close()
            bitmap.recycle()

            # Load PNG into Kivy texture via PIL
            from PIL import Image as PILImage
            pil_img = PILImage.open(io.BytesIO(png_bytes)).convert('RGB')
            img_data = pil_img.tobytes()

            texture = Texture.create(size=pil_img.size, colorfmt='rgb')
            texture.blit_buffer(img_data, colorfmt='rgb', bufferfmt='ubyte')
            texture.flip_vertical()

            self.page_image.texture = texture
            self.page_image.size = pil_img.size

            self.scroll_view.scroll_x = 0
            self.scroll_view.scroll_y = 1

        except Exception as e:
            print(f"Android render error: {e}")
            # Fallback to text
            self._render_text()

    def _render_text(self):
        """Render as text (fallback mode)."""
        text = self._page_text.get(self.current_page, "")
        if not text:
            # Try loading from pypdf on-the-fly
            try:
                import pypdf
                reader = pypdf.PdfReader(self.pdf_path)
                if self.current_page - 1 < len(reader.pages):
                    text = reader.pages[self.current_page - 1].extract_text() or ""
                    self._page_text[self.current_page] = text
            except Exception:
                text = "(Could not extract text from this page)"

        # Apply zoom to font size
        base_size = 12
        self.text_view.font_size = sp(base_size * self.zoom_level)
        self.text_view.text = text
        self.text_view.text_size = (self.scroll_view.width - dp(20), None)
        self.text_view.texture_update()
        if self.text_view.texture:
            self.text_view.height = self.text_view.texture.height + dp(40)

    def _draw_highlights(self):
        """Draw highlight overlays on the rendered page."""
        self.page_image.canvas.after.clear()
        if not self.highlight_rects:
            return

        with self.page_image.canvas.after:
            Color(1, 1, 0, 0.35)  # Semi-transparent yellow
            for rect in self.highlight_rects:
                x0, y0, x1, y1 = rect
                scale = self.zoom_level * 1.5
                w = (x1 - x0) * scale
                h = (y1 - y0) * scale

                ix, iy = self.page_image.pos
                rx = ix + x0 * scale
                ry = iy + self.page_image.height - (y1 * scale)

                Rectangle(pos=(rx, ry), size=(w, h))

    def __del__(self):
        """Clean up resources."""
        if self._fitz_doc:
            try:
                self._fitz_doc.close()
            except Exception:
                pass
