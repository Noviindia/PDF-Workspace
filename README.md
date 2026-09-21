# PDF Workspace

A fully local, offline-first PDF workspace and converter application for Android.

## Features
- Upload & analyze PDFs locally
- Full-text search with instant results
- Automatic category/section detection
- Table detection & structured data extraction
- OCR for scanned PDF pages (optional)
- Integrated PDF viewer
- Search result highlighting
- Manual record editing & correction
- Category management (create, rename, merge, delete)
- Data filtering & sorting
- Export to 7 formats: XLSX, DOCX, CSV, JSON, HTML, TXT, Markdown
- Export by scope: All, Category, Selected, Search Results
- Project save/load
- 100% offline - no cloud, no API keys, no data upload

## Privacy
🔒 **100% Local & Offline**
- No internet connection required
- No cloud services used
- No API keys needed
- No telemetry or analytics
- Your documents never leave your device

## Requirements
- Python 3.10+ (tested on Python 3.15 macOS arm64)
- Tkinter (standard library for Native Desktop App)
- Android SDK / Buildozer (for Android APK packaging)

## Installation & Running

### 1. macOS / Desktop App (Instant Launch)
The native desktop interface is built using standard Python Tkinter/ttk and PyMuPDF, requiring no heavy external GUI compilation:

```bash
cd pdf-workspace

# Activate virtual environment
source venv/bin/activate

# Launch Native Desktop Application
python main.py
```

Features in Desktop UI:
- **Top Toolbar**: Open PDF (`Cmd+O`), Search Bar (`Cmd+F`), Save Project (`Cmd+S`), Export (`Cmd+E`), and "🔒 Local Only" verification badge.
- **Left Sidebar**: Document list with page/record counts, interactive Category hierarchy tree with record counts, Page navigator listbox, and workspace Statistics.
- **Split Workspace**:
  - **Left Pane (Structured Data Grid)**: Treeview displaying all extracted fields, source page, category, and inline record editing / OCR correction dialog.
  - **Right Pane (PDF Viewer)**: Canvas-based high-resolution page rendering with Zoom controls (`+`/`-`), page navigation, and yellow bounding-box highlighting for search matches.
- **Processing Modal**: Multi-step animated progress checklist (Reading -> Detecting Pages -> Extracting Text -> Detecting Tables -> Detecting Categories -> Indexing FTS5 -> Complete).
- **Export Dialog**: Select format (XLSX, DOCX, CSV, JSON, HTML, Markdown, TXT) and scope (All, Category, Selected, Search Results).

### 2. Android APK Build (Mobile UI)
The mobile UI is built using Kivy / KivyMD and can be packaged into an installable APK using Buildozer:

```bash
# Using the automated build script
./scripts/build_apk.sh

# Or directly with Buildozer:
buildozer android debug

# The APK will be generated at:
# bin/pdfworkspace-1.0.0-arm64-v8a-debug.apk

# Install on connected Android device via ADB:
adb install bin/pdfworkspace-1.0.0-arm64-v8a-debug.apk
```

## Architecture
```text
+-------------------------------------------------------------+
|                        User Interface                       |
|   (Kivy / KivyMD Screens, Views, Widgets)                   |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                       Services Layer                        |
|   (ProjectService, ProcessingService, ExportService)        |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                        Core Domain                          |
|   (PDFProcessor, SearchEngine, Data Models, Exporters)      |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                      Infrastructure                         |
|   (DatabaseManager, Repository, SQLite/FTS5, File IO)       |
+-------------------------------------------------------------+
```

## Technology Stack
| Component | Library | Android Compatible |
|-----------|---------|-------------------|
| UI Framework | Kivy + KivyMD | ✅ |
| PDF Text Extraction | pypdf | ✅ (pure Python) |
| PDF Rendering (Desktop) | PyMuPDF | ❌ (desktop only) |
| PDF Rendering (Android) | Android PdfRenderer | ✅ (native) |
| OCR (Desktop) | Tesseract + pytesseract | ❌ (desktop only) |
| OCR (Android) | ML Kit / Tesseract4Android | ✅ (native) |
| Database | SQLite + FTS5 | ✅ |
| DOCX Export | python-docx | ✅ (pure Python) |
| XLSX Export | openpyxl | ✅ (pure Python) |

## Project Structure
```text
pdf-workspace/
├── app/
│   ├── core/           # Business logic (PDF processing, search)
│   ├── database/       # DB models, repository, schema
│   ├── exporters/      # Export formats (XLSX, DOCX, etc)
│   ├── services/       # Application orchestration layer
│   └── ui/             # Kivy UI views and components
├── tests/              # Unit and integration tests
├── scripts/            # Build and utility scripts
├── requirements.txt    # Python dependencies
├── buildozer.spec      # Android build configuration
├── main.py             # Application entry point
└── README.md           # This file
```

## Database Schema
The core application relies on a robust local SQLite database with the following primary tables:
- **Project/Metadata**: Stores overall project state and current versions.
- **Document**: Represents an imported PDF file.
- **Category**: Allows logical grouping and mapping of document sections.
- **Record**: Contains extracted data, coordinates, page numbers, and relations to categories.
- **Record_FTS**: Full-Text Search virtual table synchronized with the Record table for lightning-fast queries.

## Running Tests
```bash
python -m pytest tests/ -v
```

## Keyboard Shortcuts (Desktop)
| Shortcut | Action |
|----------|--------|
| Cmd/Ctrl+O | Open PDF |
| Cmd/Ctrl+F | Search |
| Cmd/Ctrl+S | Save Project |
| Cmd/Ctrl+E | Export |
| Esc | Close Panel |

## Offline Components
All core features work offline:
- ✅ PDF text extraction
- ✅ Table detection
- ✅ Category detection
- ✅ Full-text search (SQLite FTS5)
- ✅ All exports (DOCX, XLSX, CSV, JSON, HTML, TXT, MD)
- ✅ Project save/load
- ✅ PDF viewing
- ⚠️ OCR requires Tesseract (desktop) or ML Kit (Android) installed separately

## License
MIT License
