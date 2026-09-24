"""
PDF Workspace - OCR Engine
Handles OCR for scanned/image PDF pages.
Supports multiple backends with Android compatibility.

Backends (in priority order):
1. PyMuPDF built-in OCR (desktop only, if Tesseract installed)
2. pytesseract (desktop only, requires Tesseract binary)
3. Android ML Kit (via pyjnius, Android only)
4. Android Tesseract4Android (via pyjnius, Android only)

If no backend is available, OCR is gracefully disabled.
"""

import os
import sys
from typing import Optional, List
from dataclasses import dataclass, field

IS_ANDROID = ('ANDROID_ARGUMENT' in os.environ or 'ANDROID_ENTRYPOINT' in os.environ)



def get_tessdata_dir() -> Optional[str]:
    """Locate the tessdata directory containing .traineddata files."""
    # 1. Check assets/tessdata in project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assets_tessdata = os.path.join(project_root, 'assets', 'tessdata')
    if os.path.isdir(assets_tessdata) and any(f.endswith('.traineddata') for f in os.listdir(assets_tessdata)):
        return assets_tessdata

    # 2. Check TESSDATA_PREFIX env var
    env_dir = os.getenv('TESSDATA_PREFIX')
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    # 3. Check common system paths
    common_paths = [
        '/opt/homebrew/share/tessdata',
        '/usr/local/share/tessdata',
        '/usr/share/tesseract-ocr/5/tessdata',
        '/usr/share/tesseract-ocr/4.00/tessdata',
        '/usr/share/tessdata',
    ]
    for p in common_paths:
        if os.path.isdir(p) and any(f.endswith('.traineddata') for f in os.listdir(p)):
            return p
    return None


@dataclass
class OCRBlock:
    """A block of OCR-recognized text with position."""
    text: str
    x0: float = 0
    y0: float = 0
    x1: float = 0
    y1: float = 0
    confidence: float = 0.0


@dataclass
class OCRResult:
    """Result from OCR processing of a page."""
    text: str
    confidence: float = 0.0
    blocks: List[OCRBlock] = field(default_factory=list)


class OCREngine:
    """Offline OCR engine supporting multiple backends.
    
    All processing happens locally on the device.
    No internet connection or API keys required.
    """

    def __init__(self):
        """Initialize OCR engine and detect available backends."""
        self._backend = 'none'
        self._last_confidence = 0.0
        self._detect_backend()

    def _detect_backend(self):
        """Detect the best available OCR backend."""
        if IS_ANDROID:
            # Try Android-native OCR
            if self._check_android_mlkit():
                self._backend = 'mlkit'
                return
            if self._check_android_tesseract():
                self._backend = 'tesseract4android'
                return
        else:
            # Desktop: try PyMuPDF OCR (with bundled or system tessdata) or pytesseract
            if self._check_fitz_ocr():
                self._backend = 'fitz'
                return
            if self._check_pytesseract():
                self._backend = 'pytesseract'
                return

        self._backend = 'none'
        print("WARNING: No OCR backend available. Scanned PDF pages cannot be processed.")
        print("  Ensure assets/tessdata contains traineddata models or install Tesseract.")

    def _check_fitz_ocr(self) -> bool:
        """Check if PyMuPDF with OCR support is available."""
        try:
            import fitz
            tessdata = get_tessdata_dir()
            return tessdata is not None
        except ImportError:
            return False

    def _check_pytesseract(self) -> bool:
        """Check if pytesseract is available."""
        try:
            import pytesseract
            # Verify tesseract binary exists
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def _check_android_mlkit(self) -> bool:
        """Check if ML Kit Text Recognition is available on Android."""
        try:
            from jnius import autoclass
            autoclass('com.google.mlkit.vision.text.TextRecognition')
            return True
        except Exception:
            return False

    def _check_android_tesseract(self) -> bool:
        """Check if Tesseract4Android is available."""
        try:
            from jnius import autoclass
            autoclass('cz.adaptech.tesseract4android.TessBaseAPI')
            return True
        except Exception:
            return False

    def _check_lens(self) -> bool:
        """Check if chrome-lens-py Google Lens OCR is available."""
        try:
            import chrome_lens_py
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if any OCR backend is available."""
        return self._backend != 'none' or self._check_lens()

    def get_backend_name(self) -> str:
        """Get the name of the active OCR backend."""
        names = {
            'fitz': 'PyMuPDF + Tesseract (Local)',
            'pytesseract': 'Tesseract OCR (Local)',
            'mlkit': 'Google ML Kit (On-Device)',
            'tesseract4android': 'Tesseract4Android',
            'none': 'Google Lens API' if self._check_lens() else 'None (OCR disabled)'
        }
        return names.get(self._backend, 'Unknown')

    def ocr_page_from_file(self, file_path: str, page_number: int, 
                           language: str = 'eng', engine_type: str = 'auto') -> Optional[OCRResult]:
        """OCR a specific page from a PDF file.
        
        Args:
            file_path: Path to the PDF file.
            page_number: Zero-based page index.
            language: OCR language code.
            engine_type: 'lens' (Google Lens High Precision), 'tesseract' (Local Offline), or 'auto'.
            
        Returns:
            OCRResult or None if OCR is unavailable.
        """
        if not self.is_available():
            return None

        engine_clean = (engine_type or 'auto').lower().strip()

        # 1. Try Google Lens if requested or auto-preferred
        if engine_clean in ('lens', 'google_lens', 'google lens') or (engine_clean == 'auto' and self._check_lens()):
            try:
                lens_res = self._ocr_lens(file_path, page_number, language)
                if lens_res and lens_res.text.strip():
                    return lens_res
            except Exception as e:
                print(f"Google Lens OCR error on page {page_number}: {e}. Falling back to local Tesseract.")

        # 2. Local offline backends (fitz / pytesseract / Android)
        try:
            if self._backend == 'fitz':
                return self._ocr_fitz(file_path, page_number, language)
            elif self._backend == 'pytesseract':
                return self._ocr_pytesseract(file_path, page_number, language)
            elif self._backend == 'mlkit':
                return self._ocr_mlkit(file_path, page_number)
            elif self._backend == 'tesseract4android':
                return self._ocr_tesseract4android(file_path, page_number, language)
        except Exception as e:
            print(f"Local OCR error on page {page_number}: {e}")

        return OCRResult(text="", confidence=0.0)

    def _ocr_lens(self, file_path: str, page_number: int, language: str = 'eng+hin') -> OCRResult:
        """OCR using Google Lens API via chrome-lens-py with word-level bounding boxes."""
        try:
            import fitz
            from chrome_lens_py import LensAPI
        except ImportError:
            return OCRResult(text="", confidence=0.0)

        import asyncio
        import concurrent.futures
        import tempfile

        doc = fitz.open(file_path)
        if page_number < 0 or page_number >= len(doc):
            doc.close()
            return OCRResult(text="", confidence=0.0)

        page = doc.load_page(page_number)
        page_width = page.rect.width
        page_height = page.rect.height

        # Render page at 200 DPI for high-precision recognition
        pix = page.get_pixmap(dpi=200)
        temp_img = tempfile.mktemp(suffix=".png")
        pix.save(temp_img)
        doc.close()

        async def _call_lens():
            lens = LensAPI()
            try:
                ocr_lang = 'hin' if 'hin' in language.lower() else 'eng'
                return await lens.process_image(temp_img, output_format='full_text', ocr_language=ocr_lang)
            finally:
                await lens.aclose()

        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    res = executor.submit(asyncio.run, _call_lens()).result()
            else:
                res = loop.run_until_complete(_call_lens())

            if not res or not isinstance(res, dict):
                return OCRResult(text="", confidence=0.0)

            ocr_text = res.get('ocr_text', '') or ''
            words = res.get('word_data', [])
            blocks = []

            for w in words:
                w_text = w.get('word', '').strip()
                if not w_text:
                    continue
                geom = w.get('geometry', {})
                cx = float(geom.get('center_x', 0.0))
                cy = float(geom.get('center_y', 0.0))
                w_norm = float(geom.get('width', 0.0))
                h_norm = float(geom.get('height', 0.0))

                x0 = max(0.0, (cx - w_norm / 2.0) * page_width)
                y0 = max(0.0, (cy - h_norm / 2.0) * page_height)
                x1 = min(page_width, (cx + w_norm / 2.0) * page_width)
                y1 = min(page_height, (cy + h_norm / 2.0) * page_height)

                blocks.append(OCRBlock(
                    text=w_text,
                    x0=x0, y0=y0, x1=x1, y1=y1,
                    confidence=95.0
                ))

            self._last_confidence = 95.0
            return OCRResult(text=ocr_text.strip(), confidence=95.0, blocks=blocks)

        finally:
            if os.path.exists(temp_img):
                try:
                    os.unlink(temp_img)
                except Exception:
                    pass

    def get_available_languages(self) -> List[Dict[str, str]]:
        """Get supported OCR languages."""
        return [
            {'code': 'eng+hin', 'name': 'English + Hindi (Recommended)'},
            {'code': 'eng', 'name': 'English Only'},
            {'code': 'hin', 'name': 'Hindi Only (हिन्दी)'},
        ]

    def _ocr_fitz(self, file_path: str, page_number: int, language: str = 'eng+hin') -> OCRResult:
        """OCR using PyMuPDF's built-in Tesseract engine with local traineddata."""
        import fitz
        tessdata_dir = get_tessdata_dir()
        if not tessdata_dir:
            return OCRResult(text="", confidence=0.0)

        # Normalize language string
        lang_map = {
            'english': 'eng',
            'hindi': 'hin',
            'bilingual': 'eng+hin',
            'auto': 'eng+hin',
            'default': 'eng+hin',
        }
        clean_lang = lang_map.get(language.lower(), language)
        if not clean_lang:
            clean_lang = 'eng+hin'

        doc = fitz.open(file_path)
        try:
            page = doc.load_page(page_number)
            
            # Execute PyMuPDF OCR at 300 DPI with full=True to capture image text
            tpage = None
            try:
                tpage = page.get_textpage_ocr(language=clean_lang, dpi=300, tessdata=tessdata_dir, full=True)
            except Exception as e:
                # If compound language failed (e.g. one model missing), try fallback
                if '+' in clean_lang:
                    for fallback in clean_lang.split('+'):
                        try:
                            tpage = page.get_textpage_ocr(language=fallback, dpi=300, tessdata=tessdata_dir, full=True)
                            break
                        except Exception:
                            continue
                if not tpage:
                    return OCRResult(text="", confidence=0.0)

            text = page.get_text("text", textpage=tpage)
            raw_blocks = page.get_text("blocks", textpage=tpage)
            raw_words = page.get_text("words", textpage=tpage)

            blocks = []
            # 1. Add word-level blocks for precise pinpoint highlights
            if raw_words:
                for w in raw_words:
                    if len(w) >= 5 and str(w[4]).strip():
                        blocks.append(OCRBlock(
                            text=str(w[4]).strip(),
                            x0=float(w[0]),
                            y0=float(w[1]),
                            x1=float(w[2]),
                            y1=float(w[3]),
                            confidence=0.9
                        ))

            # 2. Add line/paragraph blocks for multi-word phrases
            if raw_blocks:
                for b in raw_blocks:
                    if len(b) >= 5 and str(b[4]).strip():
                        blocks.append(OCRBlock(
                            text=str(b[4]).strip(),
                            x0=float(b[0]),
                            y0=float(b[1]),
                            x1=float(b[2]),
                            y1=float(b[3]),
                            confidence=0.9
                        ))

            confidence = 0.9 if text.strip() else 0.0
            self._last_confidence = confidence
            return OCRResult(
                text=text.strip(),
                confidence=confidence,
                blocks=blocks
            )
        finally:
            doc.close()

    def _ocr_pytesseract(self, file_path: str, page_number: int, language: str) -> OCRResult:
        """OCR using pytesseract with PDF rendering via available library."""
        try:
            import pytesseract
            from PIL import Image
            
            # Try rendering with fitz
            try:
                import fitz
                doc = fitz.open(file_path)
                page = doc.load_page(page_number)
                pixmap = page.get_pixmap(dpi=300)
                img_data = pixmap.tobytes("png")
                doc.close()
                
                import io
                image = Image.open(io.BytesIO(img_data))
            except ImportError:
                # Can't render without fitz on desktop - try pdf2image
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(file_path, first_page=page_number + 1,
                                               last_page=page_number + 1, dpi=300)
                    if images:
                        image = images[0]
                    else:
                        return OCRResult(text="", confidence=0.0)
                except ImportError:
                    print("Cannot render PDF pages for OCR without PyMuPDF or pdf2image")
                    return OCRResult(text="", confidence=0.0)

            # OCR the image
            text = pytesseract.image_to_string(image, lang=language)
            data = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT)
            
            blocks = []
            confidences = []
            for i in range(len(data['text'])):
                txt = data['text'][i].strip()
                conf = int(data['conf'][i]) if str(data['conf'][i]) != '-1' else 0
                if txt:
                    confidences.append(conf / 100.0)
                    blocks.append(OCRBlock(
                        text=txt,
                        x0=float(data['left'][i]),
                        y0=float(data['top'][i]),
                        x1=float(data['left'][i] + data['width'][i]),
                        y1=float(data['top'][i] + data['height'][i]),
                        confidence=conf / 100.0
                    ))

            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            self._last_confidence = avg_conf
            
            return OCRResult(text=text, confidence=avg_conf, blocks=blocks)
        except Exception as e:
            print(f"pytesseract OCR error: {e}")
            return OCRResult(text="", confidence=0.0)

    def _ocr_mlkit(self, file_path: str, page_number: int) -> OCRResult:
        """OCR using Google ML Kit on Android (fully offline)."""
        try:
            from jnius import autoclass
            
            PdfRenderer = autoclass('android.graphics.pdf.PdfRenderer')
            ParcelFileDescriptor = autoclass('android.os.ParcelFileDescriptor')
            JavaFile = autoclass('java.io.File')
            Bitmap = autoclass('android.graphics.Bitmap')
            BitmapConfig = autoclass('android.graphics.Bitmap$Config')
            InputImage = autoclass('com.google.mlkit.vision.common.InputImage')
            TextRecognition = autoclass('com.google.mlkit.vision.text.TextRecognition')
            TextRecognizerOptions = autoclass('com.google.mlkit.vision.text.latin.TextRecognizerOptions')

            # Open PDF and render page
            file = JavaFile(file_path)
            fd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
            renderer = PdfRenderer(fd)
            
            page = renderer.openPage(page_number)
            width = page.getWidth() * 2  # 2x for quality
            height = page.getHeight() * 2
            
            bitmap = Bitmap.createBitmap(width, height, BitmapConfig.ARGB_8888)
            page.render(bitmap, None, None, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            page.close()
            renderer.close()
            fd.close()
            
            # Run ML Kit text recognition
            image = InputImage.fromBitmap(bitmap, 0)
            recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            
            # Synchronous wrapper for async ML Kit
            import threading
            result = {'text': '', 'blocks': [], 'done': False}
            event = threading.Event()
            
            class SuccessListener:
                def onSuccess(self, visionText):
                    result['text'] = visionText.getText()
                    for block in visionText.getTextBlocks():
                        for line in block.getLines():
                            rect = line.getBoundingBox()
                            result['blocks'].append(OCRBlock(
                                text=line.getText(),
                                x0=float(rect.left) / 2,
                                y0=float(rect.top) / 2,
                                x1=float(rect.right) / 2,
                                y1=float(rect.bottom) / 2,
                                confidence=line.getConfidence() or 0.8
                            ))
                    event.set()
            
            class FailureListener:
                def onFailure(self, e):
                    print(f"ML Kit OCR failed: {e}")
                    event.set()

            task = recognizer.process(image)
            task.addOnSuccessListener(SuccessListener())
            task.addOnFailureListener(FailureListener())
            
            event.wait(timeout=30)
            bitmap.recycle()
            
            self._last_confidence = 0.85
            return OCRResult(
                text=result['text'],
                confidence=0.85,
                blocks=result['blocks']
            )
        except Exception as e:
            print(f"ML Kit OCR error: {e}")
            return OCRResult(text="", confidence=0.0)

    def _ocr_tesseract4android(self, file_path: str, page_number: int, 
                                language: str) -> OCRResult:
        """OCR using Tesseract4Android native library."""
        try:
            from jnius import autoclass
            
            PdfRenderer = autoclass('android.graphics.pdf.PdfRenderer')
            ParcelFileDescriptor = autoclass('android.os.ParcelFileDescriptor')
            JavaFile = autoclass('java.io.File')
            Bitmap = autoclass('android.graphics.Bitmap')
            BitmapConfig = autoclass('android.graphics.Bitmap$Config')
            TessBaseAPI = autoclass('cz.adaptech.tesseract4android.TessBaseAPI')
            
            # Render PDF page to bitmap
            file = JavaFile(file_path)
            fd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
            renderer = PdfRenderer(fd)
            
            page = renderer.openPage(page_number)
            width = page.getWidth() * 2
            height = page.getHeight() * 2
            
            bitmap = Bitmap.createBitmap(width, height, BitmapConfig.ARGB_8888)
            page.render(bitmap, None, None, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            page.close()
            renderer.close()
            fd.close()
            
            # Run Tesseract
            tess = TessBaseAPI()
            
            # Find tessdata directory (copy bundled assets/tessdata if needed)
            bundled_tess = get_tessdata_dir()
            try:
                from android.storage import app_storage_path  # type: ignore
                tess_data_path = os.path.join(app_storage_path(), 'tessdata')
            except Exception:
                tess_data_path = bundled_tess or '/sdcard/tessdata'

            if bundled_tess and bundled_tess != tess_data_path:
                os.makedirs(tess_data_path, exist_ok=True)
                import shutil
                for fn in os.listdir(bundled_tess):
                    if fn.endswith('.traineddata'):
                        dst = os.path.join(tess_data_path, fn)
                        if not os.path.exists(dst):
                            shutil.copy2(os.path.join(bundled_tess, fn), dst)
            
            if not tess.init(os.path.dirname(tess_data_path), language):
                print("Tesseract4Android init failed - missing traineddata?")
                return OCRResult(text="", confidence=0.0)
            
            tess.setImage(bitmap)
            text = tess.getUTF8Text() or ""
            confidence = tess.meanConfidence() / 100.0
            
            tess.recycle()
            bitmap.recycle()
            
            self._last_confidence = confidence
            return OCRResult(text=text, confidence=confidence)
        except Exception as e:
            print(f"Tesseract4Android OCR error: {e}")
            return OCRResult(text="", confidence=0.0)
