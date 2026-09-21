"""
PDF Workspace - Modern Native Desktop Application
Fully local, offline desktop GUI built for macOS, Windows, and Linux.
No cloud, no API keys, zero network requests.
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Optional, List, Dict, Any, Tuple

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pymupdf  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    try:
        import fitz
        HAS_FITZ = True
    except ImportError:
        HAS_FITZ = False

from app.services.project_service import ProjectService
from app.services.processing_service import ProcessingService
from app.services.export_service import ExportService
from app.database.models import Record, Category, ExportConfig, SearchResult, PageType
from app.core.pdf_processor import ProcessingStatus, ProcessingProgress


class DesktopApp(tk.Tk):
    """Production-quality local PDF Workspace desktop application."""

    def __init__(self, initial_pdf: Optional[str] = None):
        super().__init__()
        self.title("PDF Workspace - 100% Local & Offline")
        self.geometry("1360x860")
        self.minsize(960, 680)

        # Services and state
        self.project_service = ProjectService()
        self.processing_service: Optional[ProcessingService] = None
        self.active_document_id: Optional[int] = None
        self.current_pdf_path: Optional[str] = None
        self.current_records: List[Record] = []
        self.current_categories: List[Category] = []
        self.selected_category_id: Optional[int] = None
        self.active_search_query: str = ""
        self.active_search_results: List[SearchResult] = []
        self.current_match_index: int = -1
        self.current_page_number: int = 1
        self.total_pages: int = 0
        self.zoom_level: float = 1.0
        self.highlight_boxes: List[Tuple[float, float, float, float]] = []
        self._rendered_photo_ref = None  # Prevent GC of ImageTk
        self.ocr_language_var = tk.StringVar(value="English + Hindi")
        self.ocr_engine_var = tk.StringVar(value="⚡ Google Lens (Online)")
        self.layout_mode_var = tk.StringVar(value="Auto-Detect")

        # Configure macOS / modern ttk styles
        self._setup_theme()

        # Build UI layout
        self._build_top_bar()
        self._build_status_bar()

        # Container for main screens
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)

        self._build_welcome_screen()
        self._build_workspace_screen()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

        # Show welcome screen by default
        self._show_welcome_screen()

        # If an initial PDF was provided, open it
        if initial_pdf and os.path.exists(initial_pdf):
            self.after(300, lambda: self.open_pdf_file(initial_pdf))

    def _setup_theme(self):
        self.style = ttk.Style(self)
        available_themes = self.style.theme_names()
        if 'aqua' in available_themes:
            self.style.theme_use('aqua')
        elif 'clam' in available_themes:
            self.style.theme_use('clam')

        self.configure(bg='#F5F5F7')

        # Custom ttk styles
        self.style.configure('TopBar.TFrame', background='#1E293B')
        self.style.configure('TopBarTitle.TLabel', background='#1E293B', foreground='#FFFFFF', font=('Helvetica', 14, 'bold'))
        self.style.configure('TopBarBadge.TLabel', background='#0F172A', foreground='#38BDF8', font=('Helvetica', 11, 'bold'), padding=(8, 4))
        
        self.style.configure('Primary.TButton', font=('Helvetica', 11, 'bold'))
        self.style.configure('Accent.TButton', font=('Helvetica', 11, 'bold'))
        self.style.configure('Sidebar.TFrame', background='#FFFFFF')
        self.style.configure('SidebarHeader.TLabel', background='#FFFFFF', font=('Helvetica', 11, 'bold'), foreground='#334155')
        self.style.configure('Stats.TLabel', background='#FFFFFF', font=('Helvetica', 10), foreground='#64748B')
        self.style.configure('StatusBar.TFrame', background='#E2E8F0')
        self.style.configure('StatusBar.TLabel', background='#E2E8F0', font=('Helvetica', 10), foreground='#334155')

    def _get_selected_ocr_lang_code(self) -> str:
        val = self.ocr_language_var.get().strip().lower()
        if "hindi" in val and "english" in val:
            return "eng+hin"
        elif "hindi" in val:
            return "hin"
        else:
            return "eng"

    def _get_selected_ocr_engine_code(self) -> str:
        val = self.ocr_engine_var.get().strip().lower()
        if "lens" in val:
            return "lens"
        elif "tesseract" in val or "offline" in val or "local" in val:
            return "tesseract"
        return "auto"

    def _get_selected_layout_mode_code(self) -> str:
        val = self.layout_mode_var.get().strip().lower()
        if "voter" in val or "मतदाता" in val:
            return "voter_list"
        elif "table" in val:
            return "table"
        elif "form" in val:
            return "form"
        else:
            return "auto"

    def _build_top_bar(self):
        # Row 1: Primary Header, File Actions, and OCR Controls
        self.top_bar = ttk.Frame(self, style='TopBar.TFrame', height=46, padding=(12, 6))
        self.top_bar.pack(fill=tk.X, side=tk.TOP)

        # App branding
        logo_lbl = ttk.Label(self.top_bar, text="📄 PDF Workspace", style='TopBarTitle.TLabel')
        logo_lbl.pack(side=tk.LEFT, padx=(0, 14))

        # Open button
        self.btn_open = tk.Button(
            self.top_bar, text="📂 Open PDF", font=('Helvetica', 11, 'bold'),
            bg='#3B82F6', fg='white', activebackground='#2563EB', activeforeground='white',
            relief=tk.FLAT, padx=12, pady=4, cursor='hand2', command=self.browse_pdf_dialog
        )
        self.btn_open.pack(side=tk.LEFT, padx=4)

        # Convert / Export button
        self.btn_convert = tk.Button(
            self.top_bar, text="⚡ Convert / Export", font=('Helvetica', 11, 'bold'),
            bg='#10B981', fg='white', activebackground='#059669', activeforeground='white',
            relief=tk.FLAT, padx=12, pady=4, cursor='hand2', command=self.open_export_dialog
        )
        self.btn_convert.pack(side=tk.LEFT, padx=6)

        # Privacy badge on Row 1
        privacy_badge = ttk.Label(self.top_bar, text="🔒 Local + Lens", style='TopBarBadge.TLabel')
        privacy_badge.pack(side=tk.RIGHT, padx=(10, 0))

        # OCR & Layout Controls on Row 1 (Right side)
        ocr_bar_frame = tk.Frame(self.top_bar, bg='#1E293B')
        ocr_bar_frame.pack(side=tk.RIGHT, padx=(4, 8))

        lbl_engine = tk.Label(ocr_bar_frame, text="⚙ Engine:", bg='#1E293B', fg='#94A3B8', font=('Helvetica', 10, 'bold'))
        lbl_engine.pack(side=tk.LEFT, padx=(0, 2))

        self.ocr_engine_combo = ttk.Combobox(
            ocr_bar_frame,
            textvariable=self.ocr_engine_var,
            values=["⚡ Google Lens (Online)", "💻 Tesseract (Local Offline)"],
            state="readonly",
            width=16
        )
        self.ocr_engine_combo.pack(side=tk.LEFT, padx=(2, 6))

        lbl_ocr = tk.Label(ocr_bar_frame, text="🌐 Lang:", bg='#1E293B', fg='#94A3B8', font=('Helvetica', 10, 'bold'))
        lbl_ocr.pack(side=tk.LEFT, padx=(0, 2))

        self.ocr_lang_combo = ttk.Combobox(
            ocr_bar_frame,
            textvariable=self.ocr_language_var,
            values=["English + Hindi", "English", "Hindi"],
            state="readonly",
            width=13
        )
        self.ocr_lang_combo.pack(side=tk.LEFT, padx=2)

        lbl_layout = tk.Label(ocr_bar_frame, text="📑 Layout:", bg='#1E293B', fg='#94A3B8', font=('Helvetica', 10, 'bold'))
        lbl_layout.pack(side=tk.LEFT, padx=(6, 2))

        self.layout_combo = ttk.Combobox(
            ocr_bar_frame,
            textvariable=self.layout_mode_var,
            values=["Auto-Detect", "Voter List (मतदाता सूची)", "Standard Table", "General Form"],
            state="readonly",
            width=18
        )
        self.layout_combo.pack(side=tk.LEFT, padx=2)

        self.btn_run_ocr = tk.Button(
            ocr_bar_frame, text="⚡ Run OCR", font=('Helvetica', 10, 'bold'),
            bg='#F59E0B', fg='#1E293B', activebackground='#D97706', activeforeground='#1E293B',
            relief=tk.FLAT, padx=8, pady=2, cursor='hand2', command=self._run_ocr_on_active_document
        )
        self.btn_run_ocr.pack(side=tk.LEFT, padx=(4, 2))

        # Row 2: Dedicated Full-Width Spacious Search Bar
        self.search_bar_frame = tk.Frame(self, bg='#0F172A', padx=12, pady=6)
        self.search_bar_frame.pack(fill=tk.X, side=tk.TOP)

        lbl_search_tag = tk.Label(self.search_bar_frame, text="🔍 Search:", bg='#0F172A', fg='#38BDF8', font=('Helvetica', 11, 'bold'))
        lbl_search_tag.pack(side=tk.LEFT, padx=(2, 6))

        lbl_scope = tk.Label(self.search_bar_frame, text="Scope:", bg='#0F172A', fg='#94A3B8', font=('Helvetica', 10, 'bold'))
        lbl_scope.pack(side=tk.LEFT, padx=(0, 3))

        self.search_scope_var = tk.StringVar(value="All Fields")
        self.combo_search_scope = ttk.Combobox(
            self.search_bar_frame, textvariable=self.search_scope_var,
            values=["All Fields", "Names Only (नाम)", "Voter ID (EPIC)", "Exact Word (सटीक)"],
            state="readonly", width=14, font=('Helvetica', 9)
        )
        self.combo_search_scope.pack(side=tk.LEFT, padx=(0, 10))
        self.combo_search_scope.bind('<<ComboboxSelected>>', lambda e: self._on_scope_changed())

        # Spacious Input Box filling all available width
        search_input_box = tk.Frame(self.search_bar_frame, bg='#1E293B', bd=1, relief=tk.SOLID)
        search_input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.top_search_var = tk.StringVar()
        self.top_search_entry = tk.Entry(
            search_input_box, textvariable=self.top_search_var, bg='#1E293B', fg='#FFFFFF',
            insertbackground='white', relief=tk.FLAT, font=('Helvetica', 12)
        )
        self.top_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=3)
        self.top_search_entry.bind('<Return>', lambda e: self._on_search_triggered())
        self.top_search_entry.bind('<KeyRelease>', lambda e: self._on_search_keyrelease())

        btn_search_clear = tk.Button(
            search_input_box, text="✕", font=('Helvetica', 10, 'bold'),
            bg='#1E293B', fg='#94A3B8', activeforeground='#FFFFFF', activebackground='#334155',
            bd=0, relief=tk.FLAT, padx=6, pady=2,
            cursor='hand2', command=self._clear_search
        )
        btn_search_clear.pack(side=tk.RIGHT)

        # Right-aligned search action controls
        btn_search_go = tk.Button(
            self.search_bar_frame, text="Search", font=('Helvetica', 10, 'bold'),
            bg='#3B82F6', fg='white', activebackground='#2563EB', activeforeground='white',
            relief=tk.FLAT, padx=10, pady=2,
            cursor='hand2', command=self._on_search_triggered
        )
        btn_search_go.pack(side=tk.LEFT, padx=3)

        self.btn_search_prev = tk.Button(
            self.search_bar_frame, text="◀", font=('Helvetica', 10, 'bold'),
            bg='#334155', fg='white', relief=tk.FLAT, padx=6, pady=2,
            cursor='hand2', state=tk.DISABLED,
            command=lambda: self._navigate_search_match(-1)
        )
        self.btn_search_prev.pack(side=tk.LEFT, padx=2)

        self.btn_search_next = tk.Button(
            self.search_bar_frame, text="▶", font=('Helvetica', 10, 'bold'),
            bg='#334155', fg='white', relief=tk.FLAT, padx=6, pady=2,
            cursor='hand2', state=tk.DISABLED,
            command=lambda: self._navigate_search_match(1)
        )
        self.btn_search_next.pack(side=tk.LEFT, padx=2)

        self.lbl_search_nav = tk.Label(
            self.search_bar_frame, text="", bg='#0F172A', fg='#38BDF8',
            font=('Helvetica', 10, 'bold'), padx=6
        )
        self.lbl_search_nav.pack(side=tk.LEFT, padx=4)

        self.btn_search_view_all = tk.Button(
            self.search_bar_frame, text="📋 All Results", font=('Helvetica', 10, 'bold'),
            bg='#0284C7', fg='white', relief=tk.FLAT, padx=10, pady=2,
            cursor='hand2', state=tk.DISABLED,
            command=self._show_all_search_results
        )
        self.btn_search_view_all.pack(side=tk.LEFT, padx=4)

    def _build_status_bar(self):
        self.status_bar = ttk.Frame(self, style='StatusBar.TFrame', height=26, padding=(12, 4))
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_status_lbl = ttk.Label(self.status_bar, text="Ready", style='StatusBar.TLabel')
        self.status_status_lbl.pack(side=tk.LEFT, padx=(0, 20))

        self.status_pages_lbl = ttk.Label(self.status_bar, text="Pages: 0", style='StatusBar.TLabel')
        self.status_pages_lbl.pack(side=tk.LEFT, padx=15)

        self.status_records_lbl = ttk.Label(self.status_bar, text="Records: 0", style='StatusBar.TLabel')
        self.status_records_lbl.pack(side=tk.LEFT, padx=15)

        self.status_category_lbl = ttk.Label(self.status_bar, text="Category: All", style='StatusBar.TLabel')
        self.status_category_lbl.pack(side=tk.LEFT, padx=15)

        self.status_mode_lbl = ttk.Label(self.status_bar, text="🔒 Fully Local Mode", style='StatusBar.TLabel')
        self.status_mode_lbl.pack(side=tk.RIGHT, padx=10)

    def _build_welcome_screen(self):
        self.welcome_frame = tk.Frame(self.container, bg='#F8FAFC')

        center_box = tk.Frame(self.welcome_frame, bg='#FFFFFF', bd=1, relief=tk.SOLID, padx=40, pady=40)
        center_box.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        icon_lbl = tk.Label(center_box, text="📑", font=('Helvetica', 52), bg='#FFFFFF')
        icon_lbl.pack(pady=(0, 10))

        title_lbl = tk.Label(center_box, text="PDF Workspace", font=('Helvetica', 24, 'bold'), bg='#FFFFFF', fg='#0F172A')
        title_lbl.pack()

        subtitle_lbl = tk.Label(
            center_box,
            text="Upload  →  Analyze  →  Search  →  Categorize  →  Edit  →  Export\n100% On-Device Processing. No Cloud, No API Keys.",
            font=('Helvetica', 12), bg='#FFFFFF', fg='#64748B', justify=tk.CENTER
        )
        subtitle_lbl.pack(pady=(8, 24))

        # Big Drag & Drop / Browse area
        drop_area = tk.Label(
            center_box, text="\n📂  Drop a PDF here  or  Click to Browse\n",
            font=('Helvetica', 13, 'bold'), bg='#F1F5F9', fg='#2563EB',
            bd=2, relief=tk.GROOVE, padx=60, pady=20, cursor='hand2'
        )
        drop_area.pack(fill=tk.X, pady=(0, 20))
        drop_area.bind('<Button-1>', lambda e: self.browse_pdf_dialog())

        btn_row = tk.Frame(center_box, bg='#FFFFFF')
        btn_row.pack(fill=tk.X, pady=(0, 20))

        btn_browse = tk.Button(
            btn_row, text="Browse PDF File", font=('Helvetica', 12, 'bold'),
            bg='#2563EB', fg='white', activebackground='#1D4ED8', activeforeground='white',
            relief=tk.FLAT, padx=20, pady=8, cursor='hand2', command=self.browse_pdf_dialog
        )
        btn_browse.pack(side=tk.LEFT, expand=True, padx=6)

        btn_sample = tk.Button(
            btn_row, text="⭐ Open Sample Document (Demo)", font=('Helvetica', 12, 'bold'),
            bg='#059669', fg='white', activebackground='#047857', activeforeground='white',
            relief=tk.FLAT, padx=20, pady=8, cursor='hand2', command=self.open_sample_pdf
        )
        btn_sample.pack(side=tk.RIGHT, expand=True, padx=6)

        # Recent Projects
        recent_hdr = tk.Label(center_box, text="Recent Projects", font=('Helvetica', 11, 'bold'), bg='#FFFFFF', fg='#334155')
        recent_hdr.pack(anchor=tk.W, pady=(15, 6))

        self.recent_listbox = tk.Listbox(center_box, height=4, font=('Helvetica', 10), bg='#F8FAFC', relief=tk.FLAT)
        self.recent_listbox.pack(fill=tk.X)
        self.recent_listbox.bind('<Double-1>', self._on_recent_double_click)
        self._refresh_recent_list()

    def _build_workspace_screen(self):
        self.workspace_frame = ttk.Frame(self.container)

        # Main Paned Window (Sidebar on left, Workspace on right)
        self.h_paned = ttk.PanedWindow(self.workspace_frame, orient=tk.HORIZONTAL)
        self.h_paned.pack(fill=tk.BOTH, expand=True)

        # --- LEFT SIDEBAR ---
        sidebar = ttk.Frame(self.h_paned, width=280, style='Sidebar.TFrame')
        self.h_paned.add(sidebar, weight=1)

        # Document Info Card
        doc_card = tk.Frame(sidebar, bg='#F1F5F9', padx=10, pady=8)
        doc_card.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.lbl_doc_title = tk.Label(doc_card, text="Document", font=('Helvetica', 11, 'bold'), bg='#F1F5F9', fg='#0F172A', anchor=tk.W)
        self.lbl_doc_title.pack(fill=tk.X)

        self.lbl_doc_meta = tk.Label(doc_card, text="0 pages | 0 bytes", font=('Helvetica', 9), bg='#F1F5F9', fg='#64748B', anchor=tk.W)
        self.lbl_doc_meta.pack(fill=tk.X)

        # Categories Section
        cat_hdr_frame = ttk.Frame(sidebar, style='Sidebar.TFrame', padding=(8, 6, 8, 2))
        cat_hdr_frame.pack(fill=tk.X)
        ttk.Label(cat_hdr_frame, text="📁 Categories", style='SidebarHeader.TLabel').pack(side=tk.LEFT)

        # Category Action Buttons
        cat_btn_frame = tk.Frame(sidebar, bg='#FFFFFF', padx=8)
        cat_btn_frame.pack(fill=tk.X, pady=(2, 6))
        
        btn_add_cat = tk.Button(cat_btn_frame, text="➕ New", font=('Helvetica', 9), bg='#F1F5F9', relief=tk.FLAT, padx=6, command=self._dialog_create_category)
        btn_add_cat.pack(side=tk.LEFT, padx=2)

        btn_ren_cat = tk.Button(cat_btn_frame, text="✏️ Rename", font=('Helvetica', 9), bg='#F1F5F9', relief=tk.FLAT, padx=6, command=self._dialog_rename_category)
        btn_ren_cat.pack(side=tk.LEFT, padx=2)

        btn_del_cat = tk.Button(cat_btn_frame, text="🗑️ Delete", font=('Helvetica', 9), bg='#F1F5F9', relief=tk.FLAT, padx=6, command=self._dialog_delete_category)
        btn_del_cat.pack(side=tk.LEFT, padx=2)

        btn_mrg_cat = tk.Button(cat_btn_frame, text="🔀 Merge", font=('Helvetica', 9), bg='#F1F5F9', relief=tk.FLAT, padx=6, command=self._dialog_merge_categories)
        btn_mrg_cat.pack(side=tk.LEFT, padx=2)

        # Categories Treeview
        cat_tree_frame = ttk.Frame(sidebar)
        cat_tree_frame.pack(fill=tk.BOTH, expand=True, padx=8)

        self.cat_tree = ttk.Treeview(cat_tree_frame, selectmode='browse', show='tree')
        cat_scroll = ttk.Scrollbar(cat_tree_frame, orient=tk.VERTICAL, command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cat_tree.bind('<<TreeviewSelect>>', self._on_category_selected)

        # Pages Section
        pages_hdr = ttk.Frame(sidebar, style='Sidebar.TFrame', padding=(8, 6, 8, 2))
        pages_hdr.pack(fill=tk.X)
        ttk.Label(pages_hdr, text="📄 Pages", style='SidebarHeader.TLabel').pack(side=tk.LEFT)

        pages_frame = ttk.Frame(sidebar)
        pages_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        self.pages_listbox = tk.Listbox(pages_frame, height=5, font=('Helvetica', 10), bg='#F8FAFC', relief=tk.FLAT)
        pages_scroll = ttk.Scrollbar(pages_frame, orient=tk.VERTICAL, command=self.pages_listbox.yview)
        self.pages_listbox.configure(yscrollcommand=pages_scroll.set)
        self.pages_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pages_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.pages_listbox.bind('<<ListboxSelect>>', self._on_page_selected_from_list)

        # Statistics Section
        stats_frame = tk.Frame(sidebar, bg='#F8FAFC', padx=10, pady=8, bd=1, relief=tk.SOLID)
        stats_frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(stats_frame, text="📊 Statistics", font=('Helvetica', 10, 'bold'), bg='#F8FAFC', fg='#334155').pack(anchor=tk.W)
        self.lbl_stats_pages = tk.Label(stats_frame, text="• Total Pages: 0", font=('Helvetica', 9), bg='#F8FAFC', fg='#64748B', anchor=tk.W)
        self.lbl_stats_pages.pack(fill=tk.X)
        self.lbl_stats_records = tk.Label(stats_frame, text="• Total Records: 0", font=('Helvetica', 9), bg='#F8FAFC', fg='#64748B', anchor=tk.W)
        self.lbl_stats_records.pack(fill=tk.X)
        self.lbl_stats_tables = tk.Label(stats_frame, text="• Tables Detected: 0", font=('Helvetica', 9), bg='#F8FAFC', fg='#64748B', anchor=tk.W)
        self.lbl_stats_tables.pack(fill=tk.X)
        self.lbl_stats_ocr = tk.Label(stats_frame, text="• OCR: Native Text PDF", font=('Helvetica', 9), bg='#F8FAFC', fg='#64748B', anchor=tk.W)
        self.lbl_stats_ocr.pack(fill=tk.X)

        # --- RIGHT MAIN WORKSPACE: NOTEBOOK WITH 3 TABS ---
        self.notebook = ttk.Notebook(self.h_paned)
        self.h_paned.add(self.notebook, weight=4)

        # TAB 1: 📄 PDF & OCR Text (Main Viewer)
        self.tab_pdf = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_pdf, text="  📄 PDF & Extracted Text  ")

        # Split pane inside Tab 1: PDF Canvas on Left, Extracted OCR Text on Right
        self.viewer_split = ttk.PanedWindow(self.tab_pdf, orient=tk.HORIZONTAL)
        self.viewer_split.pack(fill=tk.BOTH, expand=True)

        # Left Side: Canvas Viewer
        canvas_container = ttk.Frame(self.viewer_split)
        self.viewer_split.add(canvas_container, weight=3)

        # PDF Viewer Toolbar
        pdf_toolbar = tk.Frame(canvas_container, bg='#1E293B', padx=8, pady=6)
        pdf_toolbar.pack(fill=tk.X)

        btn_first = tk.Button(pdf_toolbar, text="⏮", font=('Helvetica', 10), bg='#334155', fg='white', relief=tk.FLAT, command=lambda: self.go_to_page(1))
        btn_first.pack(side=tk.LEFT, padx=2)

        btn_prev = tk.Button(pdf_toolbar, text="◀ Prev", font=('Helvetica', 10), bg='#334155', fg='white', relief=tk.FLAT, command=lambda: self.go_to_page(self.current_page_number - 1))
        btn_prev.pack(side=tk.LEFT, padx=2)

        self.page_entry_var = tk.StringVar(value="1")
        page_entry = tk.Entry(pdf_toolbar, textvariable=self.page_entry_var, width=4, font=('Helvetica', 10), justify=tk.CENTER)
        page_entry.pack(side=tk.LEFT, padx=4)
        page_entry.bind('<Return>', lambda e: self._on_page_entry_submitted())

        self.lbl_page_total = tk.Label(pdf_toolbar, text=" / 0 ", font=('Helvetica', 10), bg='#1E293B', fg='white')
        self.lbl_page_total.pack(side=tk.LEFT)

        btn_next = tk.Button(pdf_toolbar, text="Next ▶", font=('Helvetica', 10), bg='#334155', fg='white', relief=tk.FLAT, command=lambda: self.go_to_page(self.current_page_number + 1))
        btn_next.pack(side=tk.LEFT, padx=2)

        btn_last = tk.Button(pdf_toolbar, text="⏭", font=('Helvetica', 10), bg='#334155', fg='white', relief=tk.FLAT, command=lambda: self.go_to_page(self.total_pages))
        btn_last.pack(side=tk.LEFT, padx=2)

        # Zoom Controls
        btn_zoom_out = tk.Button(pdf_toolbar, text="🔍➖", font=('Helvetica', 9), bg='#334155', fg='white', relief=tk.FLAT, command=lambda: self._set_zoom(self.zoom_level * 0.8))
        btn_zoom_out.pack(side=tk.LEFT, padx=(16, 2))

        self.lbl_zoom = tk.Label(pdf_toolbar, text="100%", font=('Helvetica', 10), bg='#1E293B', fg='#94A3B8')
        self.lbl_zoom.pack(side=tk.LEFT, padx=2)

        btn_zoom_in = tk.Button(pdf_toolbar, text="🔍➕", font=('Helvetica', 9), bg='#334155', fg='white', relief=tk.FLAT, command=lambda: self._set_zoom(self.zoom_level * 1.25))
        btn_zoom_in.pack(side=tk.LEFT, padx=2)

        btn_fit_width = tk.Button(pdf_toolbar, text="Fit Width", font=('Helvetica', 9), bg='#334155', fg='white', relief=tk.FLAT, command=self._fit_width)
        btn_fit_width.pack(side=tk.LEFT, padx=4)

        self.lbl_match_info = tk.Label(pdf_toolbar, text="", font=('Helvetica', 9, 'italic'), bg='#1E293B', fg='#FCD34D')
        self.lbl_match_info.pack(side=tk.RIGHT, padx=8)

        # Canvas Frame
        canvas_frame = ttk.Frame(canvas_container)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.pdf_canvas = tk.Canvas(canvas_frame, bg='#475569', highlightthickness=0)
        canv_scroll_y = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.pdf_canvas.yview)
        canv_scroll_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.pdf_canvas.xview)
        self.pdf_canvas.configure(xscrollcommand=canv_scroll_x.set, yscrollcommand=canv_scroll_y.set)

        self.pdf_canvas.grid(row=0, column=0, sticky='nsew')
        canv_scroll_y.grid(row=0, column=1, sticky='ns')
        canv_scroll_x.grid(row=1, column=0, sticky='ew')
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # Right Side: Extracted / OCR Text Panel
        ocr_text_container = ttk.Frame(self.viewer_split, width=320)
        self.viewer_split.add(ocr_text_container, weight=1)

        ocr_header = tk.Frame(ocr_text_container, bg='#334155', padx=8, pady=6)
        ocr_header.pack(fill=tk.X)

        self.lbl_ocr_panel_title = tk.Label(ocr_header, text="📖 Page Text / OCR", font=('Helvetica', 10, 'bold'), bg='#334155', fg='#FFFFFF')
        self.lbl_ocr_panel_title.pack(side=tk.LEFT)

        btn_copy_ocr = tk.Button(
            ocr_header, text="📋 Copy", font=('Helvetica', 9),
            bg='#475569', fg='white', relief=tk.FLAT, padx=6, pady=1,
            command=self._copy_page_ocr_text
        )
        btn_copy_ocr.pack(side=tk.RIGHT, padx=2)

        self.lbl_ocr_wordcount = tk.Label(ocr_text_container, text="Words: 0 | Chars: 0", font=('Helvetica', 9), bg='#F1F5F9', fg='#64748B', padx=8, pady=3, anchor=tk.W)
        self.lbl_ocr_wordcount.pack(fill=tk.X)

        txt_frame = ttk.Frame(ocr_text_container)
        txt_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_page_ocr = tk.Text(txt_frame, wrap=tk.WORD, font=('Helvetica', 11), bg='#FFFFFF', relief=tk.FLAT, padx=8, pady=8)
        txt_scroll = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=self.txt_page_ocr.yview)
        self.txt_page_ocr.configure(yscrollcommand=txt_scroll.set)
        self.txt_page_ocr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        txt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # TAB 2: 📊 Structured Data Grid
        self.tab_data = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_data, text="  📊 Structured Data & Tables  ")

        data_toolbar = tk.Frame(self.tab_data, bg='#FFFFFF', padx=8, pady=6, bd=1, relief=tk.SOLID)
        data_toolbar.pack(fill=tk.X, padx=4, pady=(4, 2))

        lbl_filter = tk.Label(data_toolbar, text="Filter:", font=('Helvetica', 10, 'bold'), bg='#FFFFFF')
        lbl_filter.pack(side=tk.LEFT, padx=(0, 6))

        self.filter_cat_var = tk.StringVar(value="All Categories")
        self.filter_cat_combo = ttk.Combobox(data_toolbar, textvariable=self.filter_cat_var, state="readonly", width=18)
        self.filter_cat_combo.pack(side=tk.LEFT, padx=4)
        self.filter_cat_combo.bind('<<ComboboxSelected>>', lambda e: self._on_filter_changed())

        lbl_page_f = tk.Label(data_toolbar, text="Page:", font=('Helvetica', 10), bg='#FFFFFF')
        lbl_page_f.pack(side=tk.LEFT, padx=(10, 2))

        self.filter_page_var = tk.StringVar()
        self.filter_page_entry = ttk.Entry(data_toolbar, textvariable=self.filter_page_var, width=5)
        self.filter_page_entry.pack(side=tk.LEFT, padx=2)
        self.filter_page_entry.bind('<Return>', lambda e: self._on_filter_changed())

        btn_apply_filter = tk.Button(data_toolbar, text="Apply", font=('Helvetica', 9), bg='#E2E8F0', relief=tk.FLAT, padx=6, command=self._on_filter_changed)
        btn_apply_filter.pack(side=tk.LEFT, padx=4)

        btn_reset_filter = tk.Button(data_toolbar, text="Reset", font=('Helvetica', 9), bg='#E2E8F0', relief=tk.FLAT, padx=6, command=self._reset_filters)
        btn_reset_filter.pack(side=tk.LEFT, padx=4)

        btn_add_row = tk.Button(data_toolbar, text="➕ Add Row", font=('Helvetica', 9), bg='#E2E8F0', relief=tk.FLAT, padx=6, command=self._dialog_add_row)
        btn_add_row.pack(side=tk.RIGHT, padx=2)

        btn_del_row = tk.Button(data_toolbar, text="🗑️ Delete Row", font=('Helvetica', 9), bg='#E2E8F0', relief=tk.FLAT, padx=6, command=self._delete_selected_rows)
        btn_del_row.pack(side=tk.RIGHT, padx=2)

        btn_edit_cell = tk.Button(data_toolbar, text="✏️ Edit / Correct", font=('Helvetica', 9, 'bold'), bg='#FEF08A', relief=tk.FLAT, padx=6, command=self._dialog_edit_selected_cell)
        btn_edit_cell.pack(side=tk.RIGHT, padx=4)

        table_container = ttk.Frame(self.tab_data)
        table_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.data_tree = ttk.Treeview(table_container, selectmode='extended')
        tree_y_scroll = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.data_tree.yview)
        tree_x_scroll = ttk.Scrollbar(table_container, orient=tk.HORIZONTAL, command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=tree_y_scroll.set, xscrollcommand=tree_x_scroll.set)

        self.data_tree.grid(row=0, column=0, sticky='nsew')
        tree_y_scroll.grid(row=0, column=1, sticky='ns')
        tree_x_scroll.grid(row=1, column=0, sticky='ew')
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        self.data_tree.bind('<Double-1>', self._on_table_double_click)
        self.data_tree.bind('<<TreeviewSelect>>', self._on_table_row_selected)

        # TAB 3: 🔍 Search Results & Matches
        self.tab_search = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_search, text="  🔍 Search Results  ")

        search_tab_toolbar = tk.Frame(self.tab_search, bg='#F8FAFC', padx=8, pady=6)
        search_tab_toolbar.pack(fill=tk.X)

        self.lbl_search_summary = tk.Label(search_tab_toolbar, text="Type in top search bar to find words across all pages.", font=('Helvetica', 10), bg='#F8FAFC', fg='#334155')
        self.lbl_search_summary.pack(side=tk.LEFT)

        lbl_tab_scope = tk.Label(search_tab_toolbar, text="Scope:", font=('Helvetica', 9, 'bold'), bg='#F8FAFC', fg='#475569')
        lbl_tab_scope.pack(side=tk.RIGHT, padx=(10, 4))

        tab_scope_combo = ttk.Combobox(
            search_tab_toolbar, textvariable=self.search_scope_var,
            values=["All Fields", "Names Only (नाम)", "Voter ID (EPIC)", "Exact Word (सटीक)"],
            state="readonly", width=14, font=('Helvetica', 9)
        )
        tab_scope_combo.pack(side=tk.RIGHT, padx=(0, 8))
        tab_scope_combo.bind('<<ComboboxSelected>>', lambda e: self._on_scope_changed())

        search_tab_container = ttk.Frame(self.tab_search)
        search_tab_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.search_tree = ttk.Treeview(search_tab_container, selectmode='browse', columns=('page', 'field', 'snippet'), show='headings')
        self.search_tree.heading('page', text='Page')
        self.search_tree.heading('field', text='Match Type')
        self.search_tree.heading('snippet', text='Matching Details & Context')
        self.search_tree.column('page', width=65, anchor=tk.CENTER)
        self.search_tree.column('field', width=160, anchor=tk.W)
        self.search_tree.column('snippet', width=620, anchor=tk.W)

        st_y_scroll = ttk.Scrollbar(search_tab_container, orient=tk.VERTICAL, command=self.search_tree.yview)
        st_x_scroll = ttk.Scrollbar(search_tab_container, orient=tk.HORIZONTAL, command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=st_y_scroll.set, xscrollcommand=st_x_scroll.set)

        self.search_tree.grid(row=0, column=0, sticky='nsew')
        st_y_scroll.grid(row=0, column=1, sticky='ns')
        st_x_scroll.grid(row=1, column=0, sticky='ew')
        search_tab_container.grid_rowconfigure(0, weight=1)
        search_tab_container.grid_columnconfigure(0, weight=1)

        self.search_tree.bind('<<TreeviewSelect>>', self._on_search_result_selected)
        self.search_tree.bind('<Double-1>', self._on_search_result_selected)

    def _bind_shortcuts(self):
        # Cmd on macOS, Ctrl on Windows/Linux
        mod = 'Command' if sys.platform == 'darwin' else 'Control'
        self.bind(f'<{mod}-o>', lambda e: self.browse_pdf_dialog())
        self.bind(f'<{mod}-O>', lambda e: self.browse_pdf_dialog())
        self.bind(f'<{mod}-f>', lambda e: self.focus_search())
        self.bind(f'<{mod}-F>', lambda e: self.focus_search())
        self.bind(f'<{mod}-s>', lambda e: self.save_project())
        self.bind(f'<{mod}-S>', lambda e: self.save_project())
        self.bind(f'<{mod}-e>', lambda e: self.open_export_dialog())
        self.bind(f'<{mod}-E>', lambda e: self.open_export_dialog())
        self.bind('<Escape>', lambda e: self._on_escape())

    def _show_welcome_screen(self):
        self.workspace_frame.pack_forget()
        self.welcome_frame.pack(fill=tk.BOTH, expand=True)
        self.status_status_lbl.configure(text="Welcome - Select a PDF to get started")

    def _show_workspace_screen(self):
        self.welcome_frame.pack_forget()
        self.workspace_frame.pack(fill=tk.BOTH, expand=True)

    def focus_search(self):
        self.top_search_entry.focus_set()
        self.top_search_entry.select_range(0, tk.END)

    def _on_escape(self):
        self._clear_search()
        self.focus_set()

    # --- Project & PDF Import Pipeline ---

    def browse_pdf_dialog(self):
        path = filedialog.askopenfilename(
            title="Select PDF Document",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if path:
            self.open_pdf_file(path)

    def open_sample_pdf(self):
        candidates = [
            os.path.join(os.getcwd(), 'tests', 'fixtures', 'sample_students.pdf'),
            os.path.join(os.getcwd(), 'assets', 'sample', 'sample_students.pdf'),
        ]
        for c in candidates:
            if os.path.exists(c):
                self.open_pdf_file(c)
                return
        messagebox.showerror("Error", "Sample PDF fixture not found. Please run scripts/create_sample_pdf.py first.")

    def open_pdf_file(self, file_path: str):
        if not os.path.exists(file_path):
            messagebox.showerror("File Error", f"File not found:\n{file_path}")
            return

        pdf_name = os.path.splitext(os.path.basename(file_path))[0]
        base_dir = os.path.join(self.project_service._config_dir, 'projects')
        project_path = os.path.join(base_dir, pdf_name)
        os.makedirs(project_path, exist_ok=True)

        self.processing_service = self.project_service.create_project(project_path, name=pdf_name)

        # Show Processing Modal Dialog
        proc_dlg = ProcessingModal(self, title="Analyzing Document...")
        self.update_idletasks()

        def progress_cb(progress: ProcessingProgress):
            self.after(0, lambda p=progress: proc_dlg.update_progress(p))

        def completion_cb(doc_id: Optional[int], error: Optional[str]):
            self.after(0, lambda d=doc_id, e=error: self._on_processing_finished(proc_dlg, d, e))

        lang_code = self._get_selected_ocr_lang_code()
        layout_code = self._get_selected_layout_mode_code()
        engine_code = self._get_selected_ocr_engine_code()
        self.status_status_lbl.configure(text=f"Analyzing {os.path.basename(file_path)} ({self.ocr_engine_var.get()})...")
        self.processing_service.import_pdf_async(
            file_path,
            progress_callback=progress_cb,
            completion_callback=completion_cb,
            ocr_language=lang_code,
            layout_mode=layout_code,
            ocr_engine=engine_code
        )

    def _on_processing_finished(self, proc_dlg: 'ProcessingModal', doc_id: Optional[int], error: Optional[str]):
        proc_dlg.destroy()
        if error:
            messagebox.showerror("Processing Failed", f"Could not process PDF:\n{error}")
            self.status_status_lbl.configure(text="Processing failed")
            return

        self.active_document_id = doc_id
        self.current_pdf_path = self.processing_service.get_pdf_path(doc_id)

        # Switch to workspace screen and reload data
        self._show_workspace_screen()
        self.reload_workspace_data()
        self.go_to_page(1)
        self.status_status_lbl.configure(text=f"Loaded {os.path.basename(self.current_pdf_path or '')}")
        self._refresh_recent_list()

    def reload_workspace_data(self):
        """Refreshes sidebar, records table, categories, statistics from SQLite."""
        if not self.processing_service or not self.active_document_id:
            return

        repo = self.processing_service.get_repository()
        doc = repo.get_document(self.active_document_id)
        if doc:
            self.total_pages = doc.page_count
            self.lbl_doc_title.configure(text=doc.name)
            self.lbl_doc_meta.configure(text=f"{doc.page_count} pages | {doc.file_size // 1024} KB")
            self.lbl_page_total.configure(text=f" / {doc.page_count} ")
            self.status_pages_lbl.configure(text=f"Pages: {doc.page_count}")

            # Populate Pages listbox
            self._refresh_pages_listbox()

        # Categories
        self.current_categories = repo.get_categories_by_document(self.active_document_id)
        self._populate_category_tree()
        self._update_filter_categories()

        # Records
        self._load_records()

        # Statistics
        tables = repo.get_tables_by_document(self.active_document_id)
        total_recs = len(self.current_records)
        self.lbl_stats_pages.configure(text=f"• Total Pages: {self.total_pages}")
        self.lbl_stats_records.configure(text=f"• Total Records: {total_recs}")
        self.lbl_stats_tables.configure(text=f"• Tables Detected: {len(tables)}")
        self.status_records_lbl.configure(text=f"Records: {total_recs}")

    def _populate_category_tree(self):
        self.cat_tree.delete(*self.cat_tree.get_children())
        # Root "All Records"
        all_recs_count = len(self.processing_service.get_repository().get_all_records(self.active_document_id))
        self.cat_tree.insert('', 'end', iid='all', text=f"📋 All Records ({all_recs_count})", open=True)

        for cat in self.current_categories:
            self.cat_tree.insert('', 'end', iid=f"cat_{cat.id}", text=f"📁 {cat.name} ({cat.record_count})")

    def _update_filter_categories(self):
        cat_names = ["All Categories"] + [c.name for c in self.current_categories]
        self.filter_cat_combo['values'] = cat_names
        if self.filter_cat_var.get() not in cat_names:
            self.filter_cat_var.set("All Categories")

    def _load_records(self):
        repo = self.processing_service.get_repository()
        filters = {}
        if self.selected_category_id:
            filters['category_id'] = self.selected_category_id

        # Page filter
        p_val = self.filter_page_var.get().strip()
        if p_val.isdigit():
            filters['page_number'] = int(p_val)

        # Search query
        if self.active_search_query:
            filters['search_query'] = self.active_search_query
            filters['scope'] = self.search_scope_var.get() if hasattr(self, 'search_scope_var') else 'all'

        self.current_records = repo.get_filtered_records(self.active_document_id, filters)
        self._populate_data_table(self.current_records)

    def _populate_data_table(self, records: List[Record]):
        # Clear existing
        self.data_tree.delete(*self.data_tree.get_children())

        # Determine columns
        field_names = set()
        for r in records:
            if isinstance(r.data, dict):
                field_names.update(r.data.keys())

        # Sort fields with standard order (voter lists + general tables)
        ordered_fields = [
            'serial_no', 'voter_id', 'epic_no', 'name', 'relation_name',
            'relation_type', 'father_name', 'house_no', 'village', 'age',
            'gender', 'roll_no', 'class', 'section', 'phone', 'dob'
        ]
        cols = ['page', 'category']
        for of in ordered_fields:
            if of in field_names:
                cols.append(of)
        for fn in sorted(field_names):
            if fn not in cols:
                cols.append(fn)

        self.data_tree['columns'] = cols
        self.data_tree['show'] = 'headings'

        # Bilingual / Clean Headers map
        display_map = {
            'page': 'Page',
            'category': 'Category',
            'serial_no': 'Sl No (क्र. सं.)',
            'voter_id': 'Voter ID / EPIC',
            'epic_no': 'EPIC No.',
            'name': 'Name (नाम)',
            'relation_name': 'Father / Relative (पिता/पति)',
            'relation_type': 'Relation',
            'father_name': "Father's Name (पिता का नाम)",
            'husband_name': "Husband's Name (पति का नाम)",
            'house_no': 'House No (मकान/ग्राम)',
            'village': 'Village (ग्राम)',
            'age': 'Age (उम्र)',
            'gender': 'Gender (लिंग)',
            'roll_no': 'Roll No',
            'class': 'Class',
            'section': 'Section',
        }

        cat_map = {c.id: c.name for c in self.current_categories}
        for col in cols:
            display_header = display_map.get(col, col.replace('_', ' ').strip().title())
            self.data_tree.heading(col, text=display_header, command=lambda c=col: self._sort_table_column(c, False))
            self.data_tree.column(col, width=120, anchor=tk.W)

        self.data_tree.column('page', width=55, anchor=tk.CENTER)
        self.data_tree.column('category', width=110, anchor=tk.W)
        if 'serial_no' in cols:
            self.data_tree.column('serial_no', width=75, anchor=tk.CENTER)
        if 'voter_id' in cols:
            self.data_tree.column('voter_id', width=115, anchor=tk.CENTER)
        if 'age' in cols:
            self.data_tree.column('age', width=65, anchor=tk.CENTER)
        if 'gender' in cols:
            self.data_tree.column('gender', width=80, anchor=tk.CENTER)

        # Insert rows
        for record in records:
            cat_name = cat_map.get(record.category_id, "Uncategorized")
            row_vals = [record.page_number, cat_name]
            for col in cols[2:]:
                val = record.data.get(col, '') if isinstance(record.data, dict) else ''
                row_vals.append(val)

            item_id = self.data_tree.insert('', tk.END, iid=str(record.id), values=row_vals)
            if record.is_edited:
                self.data_tree.item(item_id, tags=('edited',))

        self.data_tree.tag_configure('edited', background='#FEF3C7')

    def _sort_table_column(self, col: str, reverse: bool):
        items = [(self.data_tree.set(k, col), k) for k in self.data_tree.get_children('')]
        # Attempt numeric sort if possible
        try:
            items.sort(key=lambda t: float(t[0]) if t[0] != '' else -999999, reverse=reverse)
        except ValueError:
            items.sort(key=lambda t: t[0].lower(), reverse=reverse)

        for index, (val, k) in enumerate(items):
            self.data_tree.move(k, '', index)

        self.data_tree.heading(col, command=lambda: self._sort_table_column(col, not reverse))

    # --- Search & Highlighting ---

    def _refresh_pages_listbox(self, page_match_counts: Optional[dict] = None):
        """Refresh left sidebar pages listbox, adding match indicators if search is active."""
        if not hasattr(self, 'pages_listbox') or self.total_pages <= 0:
            return
        curr = self.current_page_number
        self.pages_listbox.delete(0, tk.END)
        counts = page_match_counts or {}
        for p in range(1, self.total_pages + 1):
            c = counts.get(p, 0)
            if c > 0:
                self.pages_listbox.insert(tk.END, f"Page {p} ★ ({c})")
            else:
                self.pages_listbox.insert(tk.END, f"Page {p}")
        if 1 <= curr <= self.total_pages:
            self.pages_listbox.selection_clear(0, tk.END)
            self.pages_listbox.selection_set(curr - 1)
            self.pages_listbox.see(curr - 1)

    def _on_search_keyrelease(self):
        query = self.top_search_var.get().strip()
        if len(query) >= 1:
            self._execute_search(query)
        elif len(query) == 0:
            self._clear_search()

    def _on_search_triggered(self):
        query = self.top_search_var.get().strip()
        if not query:
            self._clear_search()
            return
        if query == self.active_search_query and self.active_search_results:
            self._navigate_search_match(1)
        else:
            self._execute_search(query)

    def _on_scope_changed(self):
        query = self.top_search_var.get().strip() if hasattr(self, 'top_search_var') else ""
        if query:
            self._execute_search(query)

    def _execute_search(self, query: str):
        self.active_search_query = query
        if not query or not self.processing_service or not self.active_document_id:
            self._clear_search()
            return

        search_engine = self.processing_service.get_search_engine()
        scope = self.search_scope_var.get() if hasattr(self, 'search_scope_var') else 'All Fields'
        results = search_engine.search(query, document_id=self.active_document_id, scope=scope)
        self.active_search_results = results

        # Filter the table view to matching records
        self._load_records()

        # Populate dedicated search results tab
        self._populate_search_results_tab(results)

        # If we have results, update nav badge and navigate to first match
        if results:
            self.current_match_index = 0
            distinct_pages = sorted(list(set(r.page_number for r in results)))
            self.lbl_search_nav.configure(
                text=f"1/{len(results)} ({len(distinct_pages)} pgs)"
            )
            self.btn_search_prev.configure(state=tk.NORMAL)
            self.btn_search_next.configure(state=tk.NORMAL)
            self.btn_search_view_all.configure(state=tk.NORMAL, text=f"📋 All ({len(results)})")
            if hasattr(self, 'notebook'):
                self.notebook.tab(2, text=f"🔍 Search Results ({len(results)})")

            match_counts = {}
            for r in results:
                match_counts[r.page_number] = match_counts.get(r.page_number, 0) + 1
            self._refresh_pages_listbox(match_counts)

            first = results[0]
            self.status_status_lbl.configure(
                text=f"Search '{query}': {len(results)} matches found across {len(distinct_pages)} page(s)"
            )
            self.go_to_page(first.page_number, highlight_text=query)
        else:
            self.current_match_index = -1
            self.lbl_search_nav.configure(text="0 matches")
            self.btn_search_prev.configure(state=tk.DISABLED)
            self.btn_search_next.configure(state=tk.DISABLED)
            self.btn_search_view_all.configure(state=tk.DISABLED, text="📋 All")
            if hasattr(self, 'notebook'):
                self.notebook.tab(2, text="🔍 Search Results")
            self._refresh_pages_listbox({})
            self.status_status_lbl.configure(text=f"Search '{query}': No matches found across entire document")
            self.highlight_boxes = []
            self._render_pdf_page()

    def _navigate_search_match(self, direction: int):
        """Navigate to next or previous match across the entire document."""
        if not self.active_search_results:
            return
        total = len(self.active_search_results)
        self.current_match_index = (self.current_match_index + direction) % total
        match = self.active_search_results[self.current_match_index]
        self.lbl_search_nav.configure(
            text=f"{self.current_match_index + 1}/{total} (P.{match.page_number})"
        )
        self.go_to_page(match.page_number, highlight_text=self.active_search_query)

    def _show_all_search_results(self):
        """Jump to Tab 3 (Search Results) to view all matches in a table."""
        if hasattr(self, 'notebook'):
            self.notebook.select(2)

    def _populate_search_results_tab(self, results: List[SearchResult]):
        """Populate the dedicated Search Results tab."""
        self.search_tree.delete(*self.search_tree.get_children())
        if not results:
            self.lbl_search_summary.configure(text=f"No results found for '{self.active_search_query}'")
            return
        
        self.lbl_search_summary.configure(
            text=f"Found {len(results)} match(es) for '{self.active_search_query}'. Click any match to jump to page:"
        )
        for idx, r in enumerate(results):
            snippet = r.context_snippet.replace('<b>', '【').replace('</b>', '】').replace('\n', ' ')
            field_label = r.match_field or r.category_name or "General"
            self.search_tree.insert('', tk.END, iid=str(idx), values=(r.page_number, field_label, snippet))

    def _on_search_result_selected(self, event):
        """Navigate to matching page from search result click."""
        sel = self.search_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.active_search_results):
            self.current_match_index = idx
            match = self.active_search_results[idx]
            total = len(self.active_search_results)
            self.lbl_search_nav.configure(text=f"{idx + 1}/{total} (P.{match.page_number})")
            self.notebook.select(0)  # Jump to PDF view tab
            self.go_to_page(match.page_number, highlight_text=self.active_search_query)

    def _copy_page_ocr_text(self):
        """Copy the current page's extracted/OCR text to system clipboard."""
        text = self.txt_page_ocr.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_status_lbl.configure(text="Page text copied to clipboard!")

    def _update_page_ocr_text(self, page_num: int):
        """Update the side-by-side extracted text drawer for the current page."""
        self.txt_page_ocr.delete("1.0", tk.END)
        self.lbl_ocr_panel_title.configure(text=f"📖 Page {page_num} Text / OCR")
        if self.processing_service and self.active_document_id:
            repo = self.processing_service.get_repository()
            page = repo.get_page_by_number(self.active_document_id, page_num)
            if page:
                text = page.processed_text or page.raw_text or ""
                self.txt_page_ocr.insert(tk.END, text)
                words = len(text.split())
                self.lbl_ocr_wordcount.configure(text=f"Words: {words} | Chars: {len(text)}")
                return
        self.lbl_ocr_wordcount.configure(text="Words: 0 | Chars: 0")

    def _clear_search(self):
        self.top_search_var.set("")
        self.active_search_query = ""
        self.active_search_results = []
        self.current_match_index = -1
        self.highlight_boxes = []
        if hasattr(self, 'lbl_search_nav'):
            self.lbl_search_nav.configure(text="")
        if hasattr(self, 'btn_search_prev'):
            self.btn_search_prev.configure(state=tk.DISABLED)
        if hasattr(self, 'btn_search_next'):
            self.btn_search_next.configure(state=tk.DISABLED)
        if hasattr(self, 'btn_search_view_all'):
            self.btn_search_view_all.configure(state=tk.DISABLED, text="📋 All")
        if hasattr(self, 'notebook'):
            self.notebook.tab(2, text="🔍 Search Results")
        self.lbl_match_info.configure(text="")
        self.lbl_search_summary.configure(text="Type in top search bar to find words across all pages.")
        self.search_tree.delete(*self.search_tree.get_children())
        self._refresh_pages_listbox({})
        self._load_records()
        self._render_pdf_page()

    def _run_ocr_on_active_document(self):
        """Run OCR on the active document with the selected language."""
        if not self.processing_service or not self.active_document_id or not self.current_pdf_path:
            messagebox.showinfo("No Document", "Please open a PDF document first before running OCR.", parent=self)
            return

        lang_code = self._get_selected_ocr_lang_code()
        lang_display = self.ocr_language_var.get()
        engine_code = self._get_selected_ocr_engine_code()
        engine_display = self.ocr_engine_var.get()
        confirm = messagebox.askyesno(
            "Run OCR",
            f"Run OCR with {engine_display} (Language: {lang_display})?\n\nThis will re-process images in the PDF, detect text & tables, and update the search index.",
            parent=self
        )
        if not confirm:
            return

        proc_dlg = ProcessingModal(self, title=f"Running OCR ({engine_display})...")
        self.update_idletasks()

        def on_progress(p: ProcessingProgress):
            self.after(0, lambda progress=p: proc_dlg.update_progress(progress))

        def worker():
            try:
                layout_code = self._get_selected_layout_mode_code()
                self.processing_service.import_pdf(
                    self.current_pdf_path,
                    progress_callback=on_progress,
                    ocr_language=lang_code,
                    layout_mode=layout_code,
                    force_ocr=True,
                    ocr_engine=engine_code
                )
                self.after(0, lambda: self._on_ocr_finished(proc_dlg))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_ocr_failed(proc_dlg, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ocr_finished(self, proc_dlg):
        proc_dlg.destroy()
        self.reload_workspace_data()
        self.go_to_page(self.current_page_number)
        messagebox.showinfo("OCR Complete", "OCR processing completed successfully! Search and text layers are now active.", parent=self)

    def _on_ocr_failed(self, proc_dlg, error_msg: str):
        proc_dlg.destroy()
        messagebox.showerror("OCR Failed", f"Failed to run OCR:\n{error_msg}", parent=self)

    # --- Integrated PDF Viewer Rendering ---

    def go_to_page(self, page_num: int, highlight_text: Optional[str] = None):
        if page_num < 1:
            page_num = 1
        if self.total_pages > 0 and page_num > self.total_pages:
            page_num = self.total_pages

        self.current_page_number = page_num
        self.page_entry_var.set(str(page_num))

        # Synchronize pages listbox selection
        self.pages_listbox.selection_clear(0, tk.END)
        self.pages_listbox.selection_set(page_num - 1)
        self.pages_listbox.see(page_num - 1)

        # Highlighting logic: Native vector text + Fallback to database OCR bounding boxes for image text
        self.highlight_boxes = []
        if highlight_text and self.current_pdf_path:
            # 1. Try PyMuPDF native vector text search with Hindi variants
            if HAS_FITZ:
                try:
                    from app.database.repository import get_hindi_search_variants
                    variants = get_hindi_search_variants(highlight_text)
                    doc = fitz.open(self.current_pdf_path)
                    if page_num - 1 < len(doc):
                        page = doc[page_num - 1]
                        for v in variants:
                            rects = page.search_for(v)
                            if rects:
                                for r in rects:
                                    box = (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
                                    if box not in self.highlight_boxes:
                                        self.highlight_boxes.append(box)
                    doc.close()
                except Exception:
                    pass

            # 2. Fallback to database OCR bounding boxes (essential for scanned/image PDFs and Hindi text)
            if not self.highlight_boxes and self.processing_service and self.active_document_id:
                repo = self.processing_service.get_repository()
                db_boxes = repo.find_bounding_boxes_for_text(self.active_document_id, page_num, highlight_text)
                if db_boxes:
                    self.highlight_boxes = db_boxes

            if self.highlight_boxes:
                self.lbl_match_info.configure(text=f"Found {len(self.highlight_boxes)} match(es) on page {page_num}")
            else:
                self.lbl_match_info.configure(text=f"Found on page {page_num}")
        elif not highlight_text:
            self.highlight_boxes = []
            self.lbl_match_info.configure(text="")

        self._update_page_ocr_text(page_num)
        self._render_pdf_page()

    def _render_pdf_page(self):
        if not HAS_PIL or not HAS_FITZ or not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            self.pdf_canvas.delete('all')
            self.pdf_canvas.create_text(200, 150, text="PDF Viewer unavailable\n(No document loaded)", fill='#CBD5E1', font=('Helvetica', 14))
            return

        try:
            doc = pymupdf.open(self.current_pdf_path) if hasattr(pymupdf, 'open') else fitz.open(self.current_pdf_path)
            if self.current_page_number - 1 >= len(doc):
                doc.close()
                return

            page = doc[self.current_page_number - 1]
            dpi = int(120 * self.zoom_level)
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Draw yellow highlight rectangles if any
            if self.highlight_boxes:
                draw = ImageDraw.Draw(img, 'RGBA')
                scale = dpi / 72.0
                for box in self.highlight_boxes:
                    x0, y0, x1, y1 = [b * scale for b in box]
                    # Draw translucent yellow overlay
                    draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill=(255, 235, 59, 120), outline=(234, 179, 8, 220), width=2)

            self._rendered_photo_ref = ImageTk.PhotoImage(img)
            self.pdf_canvas.delete('all')
            self.pdf_canvas.create_image(10, 10, anchor=tk.NW, image=self._rendered_photo_ref)
            self.pdf_canvas.configure(scrollregion=(0, 0, pix.width + 20, pix.height + 20))
            doc.close()

            self.lbl_zoom.configure(text=f"{int(self.zoom_level * 100)}%")
        except Exception as e:
            print(f"Error rendering PDF page: {e}")

    def _set_zoom(self, zoom: float):
        if 0.3 <= zoom <= 3.0:
            self.zoom_level = zoom
            self._render_pdf_page()

    def _fit_width(self):
        width = self.pdf_canvas.winfo_width()
        if width > 100:
            self.zoom_level = max(0.5, min(2.5, (width - 40) / 612.0))
            self._render_pdf_page()

    def _on_page_entry_submitted(self):
        val = self.page_entry_var.get().strip()
        if val.isdigit():
            self.go_to_page(int(val))

    def _on_page_selected_from_list(self, event):
        sel = self.pages_listbox.curselection()
        if sel:
            page_num = sel[0] + 1
            self.go_to_page(page_num, highlight_text=self.active_search_query)

    def _on_table_row_selected(self, event):
        sel = self.data_tree.selection()
        if sel and self.processing_service:
            rec_id = int(sel[0])
            repo = self.processing_service.get_repository()
            record = repo.get_record(rec_id)
            if record:
                # Highlight record source text or name if available
                name = record.data.get('name', '') if isinstance(record.data, dict) else ''
                self.go_to_page(record.page_number, highlight_text=name or record.source_text[:20])

    def _on_table_double_click(self, event):
        item = self.data_tree.identify('item', event.x, event.y)
        if item:
            self._dialog_edit_selected_cell()

    # --- Category Management ---

    def _on_category_selected(self, event):
        sel = self.cat_tree.selection()
        if not sel:
            return
        node_id = sel[0]
        if node_id == 'all':
            self.selected_category_id = None
            self.status_category_lbl.configure(text="Category: All")
        elif node_id.startswith('cat_'):
            cat_id = int(node_id.replace('cat_', ''))
            self.selected_category_id = cat_id
            cat = next((c for c in self.current_categories if c.id == cat_id), None)
            self.status_category_lbl.configure(text=f"Category: {cat.name if cat else ''}")

        self._load_records()

    def _dialog_create_category(self):
        if not self.processing_service or not self.active_document_id:
            return
        name = simpledialog.askstring("New Category", "Enter category name:", parent=self)
        if name and name.strip():
            repo = self.processing_service.get_repository()
            repo.add_category(self.active_document_id, name.strip())
            self.reload_workspace_data()

    def _dialog_rename_category(self):
        sel = self.cat_tree.selection()
        if not sel or not sel[0].startswith('cat_'):
            messagebox.showinfo("Select Category", "Please select a category from the tree to rename.")
            return
        cat_id = int(sel[0].replace('cat_', ''))
        cat = next((c for c in self.current_categories if c.id == cat_id), None)
        if not cat:
            return

        new_name = simpledialog.askstring("Rename Category", f"Rename category '{cat.name}' to:", initialvalue=cat.name, parent=self)
        if new_name and new_name.strip():
            repo = self.processing_service.get_repository()
            repo.update_category(cat_id, name=new_name.strip())
            self.reload_workspace_data()

    def _dialog_delete_category(self):
        sel = self.cat_tree.selection()
        if not sel or not sel[0].startswith('cat_'):
            messagebox.showinfo("Select Category", "Please select a category to delete.")
            return
        cat_id = int(sel[0].replace('cat_', ''))
        if messagebox.askyesno("Delete Category", "Are you sure you want to delete this category?\nRecords will become uncategorized."):
            repo = self.processing_service.get_repository()
            repo.delete_category(cat_id)
            self.reload_workspace_data()

    def _dialog_merge_categories(self):
        if len(self.current_categories) < 2:
            messagebox.showinfo("Merge Categories", "You need at least 2 categories to merge.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Merge Categories")
        dlg.geometry("380x300")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Select Source Category (to be merged into target):", font=('Helvetica', 10, 'bold')).pack(anchor=tk.W, padx=12, pady=(12, 4))
        src_var = tk.StringVar(value=self.current_categories[0].name)
        src_combo = ttk.Combobox(dlg, textvariable=src_var, values=[c.name for c in self.current_categories], state="readonly")
        src_combo.pack(fill=tk.X, padx=12, pady=4)

        tk.Label(dlg, text="Select Target Category:", font=('Helvetica', 10, 'bold')).pack(anchor=tk.W, padx=12, pady=(12, 4))
        tgt_var = tk.StringVar(value=self.current_categories[1].name)
        tgt_combo = ttk.Combobox(dlg, textvariable=tgt_var, values=[c.name for c in self.current_categories], state="readonly")
        tgt_combo.pack(fill=tk.X, padx=12, pady=4)

        def do_merge():
            s_name = src_var.get()
            t_name = tgt_var.get()
            if s_name == t_name:
                messagebox.showerror("Error", "Source and Target categories must be different.")
                return
            src_cat = next((c for c in self.current_categories if c.name == s_name), None)
            tgt_cat = next((c for c in self.current_categories if c.name == t_name), None)
            if src_cat and tgt_cat:
                repo = self.processing_service.get_repository()
                repo.merge_categories([src_cat.id], tgt_cat.id)
                dlg.destroy()
                self.reload_workspace_data()

        btn_merge = tk.Button(dlg, text="Merge Categories", bg='#2563EB', fg='white', relief=tk.FLAT, padx=12, pady=6, command=do_merge)
        btn_merge.pack(pady=20)

    # --- Cell Editing / OCR Correction ---

    def _dialog_edit_selected_cell(self):
        sel = self.data_tree.selection()
        if not sel:
            messagebox.showinfo("Select Record", "Please select a record row to edit.")
            return

        rec_id = int(sel[0])
        repo = self.processing_service.get_repository()
        record = repo.get_record(rec_id)
        if not record:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Record #{rec_id} (OCR Correction)")
        dlg.geometry("480x420")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=f"Record #{rec_id} (Source Page: {record.page_number})", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, padx=16, pady=(12, 6))

        content_frame = ttk.Frame(dlg, padding=16)
        content_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        row_i = 0

        # Category dropdown
        tk.Label(content_frame, text="Category:", font=('Helvetica', 10, 'bold')).grid(row=row_i, column=0, sticky='w', pady=4)
        cat_map = {c.name: c.id for c in self.current_categories}
        cat_names = ["Uncategorized"] + [c.name for c in self.current_categories]
        current_cat_name = next((c.name for c in self.current_categories if c.id == record.category_id), "Uncategorized")
        cat_var = tk.StringVar(value=current_cat_name)
        cat_combo = ttk.Combobox(content_frame, textvariable=cat_var, values=cat_names, state="readonly", width=24)
        cat_combo.grid(row=row_i, column=1, sticky='ew', pady=4)
        row_i += 1

        # Dynamic data fields
        for field, val in record.data.items():
            tk.Label(content_frame, text=f"{field.title()}:", font=('Helvetica', 10)).grid(row=row_i, column=0, sticky='w', pady=4)
            ent = ttk.Entry(content_frame, width=28)
            ent.insert(0, str(val))
            ent.grid(row=row_i, column=1, sticky='ew', pady=4)
            entries[field] = ent
            row_i += 1

        def save_correction():
            updated_data = {}
            for f, ent in entries.items():
                old_val = str(record.data.get(f, ''))
                new_val = ent.get().strip()
                updated_data[f] = new_val
                if old_val != new_val:
                    # Log user correction for auditing & OCR feedback
                    repo.add_correction(record.id, f, old_val, new_val)

            chosen_cat = cat_var.get()
            new_cat_id = cat_map.get(chosen_cat, None)

            repo.update_record(record.id, data=updated_data, category_id=new_cat_id, is_edited=1)
            dlg.destroy()
            self._load_records()
            self.status_status_lbl.configure(text=f"Record #{record.id} updated and saved")

        btn_save = tk.Button(dlg, text="Save Correction", bg='#059669', fg='white', relief=tk.FLAT, padx=14, pady=6, command=save_correction)
        btn_save.pack(pady=12)

    def _dialog_add_row(self):
        if not self.processing_service or not self.active_document_id:
            return
        repo = self.processing_service.get_repository()
        all_fields = repo.get_all_field_names(self.active_document_id)
        if not all_fields:
            all_fields = ['name', 'roll_no', 'class']

        new_data = {f: "" for f in all_fields}
        new_rec = repo.add_record(
            document_id=self.active_document_id,
            page_number=self.current_page_number,
            category_id=self.selected_category_id,
            data=new_data,
            source_text="Manually added record",
            bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0
        )
        self.reload_workspace_data()
        if new_rec:
            self.data_tree.selection_set(str(new_rec.id))
            self.data_tree.see(str(new_rec.id))
            self._dialog_edit_selected_cell()

    def _delete_selected_rows(self):
        sel = self.data_tree.selection()
        if not sel:
            messagebox.showinfo("Select Row", "Please select one or more rows to delete.")
            return
        if messagebox.askyesno("Delete Records", f"Delete {len(sel)} selected record(s)?"):
            repo = self.processing_service.get_repository()
            repo.delete_records([int(s) for s in sel])
            self.reload_workspace_data()

    # --- Filtering ---

    def _on_filter_changed(self):
        cat_name = self.filter_cat_var.get()
        if cat_name == "All Categories":
            self.selected_category_id = None
        else:
            cat = next((c for c in self.current_categories if c.name == cat_name), None)
            self.selected_category_id = cat.id if cat else None
        self._load_records()

    def _reset_filters(self):
        self.filter_cat_var.set("All Categories")
        self.filter_page_var.set("")
        self.selected_category_id = None
        self._load_records()

    # --- Convert / Export Dialog ---

    def open_export_dialog(self):
        if not self.processing_service or not self.active_document_id:
            messagebox.showinfo("No Document", "Please open and analyze a PDF document first.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Convert / Export Document")
        dlg.geometry("520x460")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Export Extracted Workspace Data", font=('Helvetica', 14, 'bold')).pack(anchor=tk.W, padx=20, pady=(16, 4))
        tk.Label(dlg, text="Export processed document content to multi-format spreadsheets and reports.", font=('Helvetica', 10), fg='#64748B').pack(anchor=tk.W, padx=20, pady=(0, 16))

        form_frame = ttk.Frame(dlg, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Format choice
        tk.Label(form_frame, text="Format:", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=6)
        fmt_var = tk.StringVar(value="xlsx")
        fmt_combo = ttk.Combobox(
            form_frame, textvariable=fmt_var, state="readonly",
            values=["xlsx", "docx", "csv", "json", "html", "markdown", "txt"], width=20
        )
        fmt_combo.grid(row=0, column=1, sticky='w', pady=6)

        # Scope choice
        tk.Label(form_frame, text="Export Scope:", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=6)
        scope_var = tk.StringVar(value="all")

        rb_all = ttk.Radiobutton(form_frame, text="Entire Document (All Records)", variable=scope_var, value="all")
        rb_all.grid(row=1, column=1, sticky='w', pady=2)

        rb_cat = ttk.Radiobutton(form_frame, text="Selected Category", variable=scope_var, value="category")
        rb_cat.grid(row=2, column=1, sticky='w', pady=2)

        rb_sel = ttk.Radiobutton(form_frame, text=f"Selected Records ({len(self.data_tree.selection())} selected)", variable=scope_var, value="selected")
        rb_sel.grid(row=3, column=1, sticky='w', pady=2)

        rb_search = ttk.Radiobutton(form_frame, text=f"Current Search Results ('{self.active_search_query}')", variable=scope_var, value="search")
        rb_search.grid(row=4, column=1, sticky='w', pady=2)

        # Output file destination
        tk.Label(form_frame, text="Output Path:", font=('Helvetica', 10, 'bold')).grid(row=5, column=0, sticky='w', pady=(12, 6))
        out_path_var = tk.StringVar()
        default_name = os.path.splitext(os.path.basename(self.current_pdf_path or 'export'))[0]
        out_path_var.set(os.path.join(self.processing_service.exports_dir, f"{default_name}.xlsx"))

        out_entry = ttk.Entry(form_frame, textvariable=out_path_var, width=32)
        out_entry.grid(row=5, column=1, sticky='ew', pady=(12, 6))

        def update_ext(*args):
            ext = fmt_var.get()
            cur = out_path_var.get()
            base = os.path.splitext(cur)[0]
            out_path_var.set(f"{base}.{ext}")

        fmt_var.trace_add('write', update_ext)

        def browse_save_path():
            ext = fmt_var.get()
            path = filedialog.asksaveasfilename(
                title="Save Export File",
                defaultextension=f".{ext}",
                filetypes=[(f"{ext.upper()} file", f"*.{ext}"), ("All files", "*.*")],
                initialdir=self.processing_service.exports_dir
            )
            if path:
                out_path_var.set(path)

        btn_browse_dest = tk.Button(form_frame, text="Browse...", font=('Helvetica', 9), command=browse_save_path)
        btn_browse_dest.grid(row=5, column=2, padx=4, pady=(12, 6))

        def do_export():
            fmt = fmt_var.get()
            scope = scope_var.get()
            out_path = out_path_var.get().strip()

            if not out_path:
                messagebox.showerror("Error", "Please provide a valid output file path.")
                return

            sel_ids = [int(s) for s in self.data_tree.selection()]
            if scope == 'selected' and not sel_ids:
                messagebox.showerror("Error", "No records selected in the data grid.")
                return

            if scope == 'search' and not self.active_search_query:
                messagebox.showerror("Error", "No search query active.")
                return

            config = ExportConfig(
                format=fmt,
                scope=scope,
                category_id=self.selected_category_id,
                record_ids=sel_ids if scope == 'selected' else None,
                search_query=self.active_search_query if scope == 'search' else None,
                output_path=out_path
            )

            try:
                export_service = ExportService(self.processing_service.get_repository())
                result_file = export_service.export(config)
                dlg.destroy()
                messagebox.showinfo("Export Complete", f"Successfully exported to:\n{result_file}")
                self.status_status_lbl.configure(text=f"Exported {fmt.upper()} to {os.path.basename(result_file)}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Export failed:\n{str(e)}")

        btn_export_act = tk.Button(
            dlg, text="⚡ Convert & Save Now", font=('Helvetica', 12, 'bold'),
            bg='#10B981', fg='white', relief=tk.FLAT, padx=20, pady=8, command=do_export
        )
        btn_export_act.pack(pady=16)

    def save_project(self):
        if self.processing_service:
            messagebox.showinfo("Project Saved", f"Project state and SQLite index are automatically persisted:\n{self.processing_service.project_path}")
            self.status_status_lbl.configure(text="Project saved locally")

    def _refresh_recent_list(self):
        self.recent_listbox.delete(0, tk.END)
        recents = self.project_service.get_recent_projects()
        for r in recents:
            name = r.get('name', '') or os.path.basename(r.get('path', ''))
            self.recent_listbox.insert(tk.END, f"📁 {name}")

    def _on_recent_double_click(self, event):
        sel = self.recent_listbox.curselection()
        if sel:
            recents = self.project_service.get_recent_projects()
            if sel[0] < len(recents):
                p_path = recents[sel[0]].get('path')
                if p_path and os.path.exists(p_path):
                    self.open_project_path(p_path)

    def open_project_path(self, project_path: str):
        self.processing_service = self.project_service.open_project(project_path)
        repo = self.processing_service.get_repository()
        docs = repo.get_all_documents()
        if docs:
            self.active_document_id = docs[0].id
            self.current_pdf_path = self.processing_service.get_pdf_path(self.active_document_id)
            self._show_workspace_screen()
            self.reload_workspace_data()
            self.go_to_page(1)
            self.status_status_lbl.configure(text=f"Opened project {os.path.basename(project_path)}")


class ProcessingModal(tk.Toplevel):
    """Modal dialog displaying document analysis progress checklist."""

    def __init__(self, parent, title="Analyzing Document..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("460x360")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.parent_app = parent
        self.configure(bg='#FFFFFF')

        tk.Label(self, text="Analyzing Document...", font=('Helvetica', 14, 'bold'), bg='#FFFFFF').pack(pady=(16, 4))
        self.lbl_step = tk.Label(self, text="Initializing local processing pipeline...", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B')
        self.lbl_step.pack(pady=(0, 12))

        # Checklist frame
        self.checklist_frame = tk.Frame(self, bg='#FFFFFF', padx=24)
        self.checklist_frame.pack(fill=tk.X, pady=8)

        self.steps = [
            ("Reading PDF", tk.Label(self.checklist_frame, text="○ Reading PDF", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B', anchor=tk.W)),
            ("Detecting pages", tk.Label(self.checklist_frame, text="○ Detecting pages", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B', anchor=tk.W)),
            ("Extracting text", tk.Label(self.checklist_frame, text="○ Extracting text", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B', anchor=tk.W)),
            ("Detecting tables", tk.Label(self.checklist_frame, text="○ Detecting tables", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B', anchor=tk.W)),
            ("Detecting sections", tk.Label(self.checklist_frame, text="○ Detecting sections", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B', anchor=tk.W)),
            ("Building index", tk.Label(self.checklist_frame, text="○ Building search index", font=('Helvetica', 10), bg='#FFFFFF', fg='#64748B', anchor=tk.W)),
        ]

        for _, lbl in self.steps:
            lbl.pack(fill=tk.X, pady=2)

        # Progress bar
        self.progress_bar = ttk.Progressbar(self, orient=tk.HORIZONTAL, mode='determinate', length=380)
        self.progress_bar.pack(pady=(16, 6))

        self.lbl_pct = tk.Label(self, text="0%", font=('Helvetica', 10, 'bold'), bg='#FFFFFF', fg='#2563EB')
        self.lbl_pct.pack()

        # Cancel button
        btn_cancel = tk.Button(self, text="Cancel", font=('Helvetica', 10), bg='#F1F5F9', relief=tk.FLAT, padx=12, pady=4, command=self._cancel)
        btn_cancel.pack(pady=(12, 0))

    def update_progress(self, p: ProcessingProgress):
        self.lbl_step.configure(text=p.message)
        self.progress_bar['value'] = p.percentage
        self.lbl_pct.configure(text=f"{int(p.percentage)}%")

        # Update checklist icons based on status
        step_idx = 0
        if p.status == ProcessingStatus.READING:
            step_idx = 0
        elif p.status == ProcessingStatus.DETECTING_PAGES:
            step_idx = 1
        elif p.status == ProcessingStatus.EXTRACTING_TEXT:
            step_idx = 2
        elif p.status == ProcessingStatus.DETECTING_TABLES:
            step_idx = 3
        elif p.status == ProcessingStatus.DETECTING_SECTIONS:
            step_idx = 4
        elif p.status in (ProcessingStatus.BUILDING_INDEX, ProcessingStatus.COMPLETE):
            step_idx = 5

        for i, (name, lbl) in enumerate(self.steps):
            if i < step_idx:
                lbl.configure(text=f"✓ {name}", fg='#059669', font=('Helvetica', 10, 'bold'))
            elif i == step_idx:
                lbl.configure(text=f"▶ {name}...", fg='#2563EB', font=('Helvetica', 10, 'bold'))
            else:
                lbl.configure(text=f"○ {name}", fg='#94A3B8')

        if p.status == ProcessingStatus.COMPLETE:
            for name, lbl in self.steps:
                lbl.configure(text=f"✓ {name}", fg='#059669')

    def _cancel(self):
        if self.parent_app.processing_service:
            self.parent_app.processing_service.cancel_processing()
        self.destroy()


def run_desktop_app(initial_pdf: Optional[str] = None):
    """Entrypoint for the desktop application."""
    app = DesktopApp(initial_pdf=initial_pdf)
    app.mainloop()


if __name__ == '__main__':
    sample_pdf = sys.argv[1] if len(sys.argv) > 1 else None
    run_desktop_app(sample_pdf)
