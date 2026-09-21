#!/usr/bin/env python3
"""
PDF Workspace - Development Launcher
Run the app on desktop for development/testing.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set development environment
os.environ['KIVY_LOG_LEVEL'] = 'debug'

if __name__ == '__main__':
    print("=" * 50)
    print("  PDF Workspace - Development Mode")
    print("=" * 50)
    print()
    
    # Check dependencies
    missing = []
    
    try:
        import kivy
        print(f"  ✓ Kivy {kivy.__version__}")
    except ImportError:
        missing.append('kivy')
        print("  ✗ Kivy not found")
    
    try:
        import kivymd
        print(f"  ✓ KivyMD")
    except ImportError:
        missing.append('kivymd')
        print("  ✗ KivyMD not found")
    
    try:
        import pypdf
        print(f"  ✓ pypdf")
    except ImportError:
        missing.append('pypdf')
        print("  ✗ pypdf not found")
    
    try:
        import fitz
        print(f"  ✓ PyMuPDF {fitz.version[0]} (enhanced PDF rendering)")
    except ImportError:
        print("  ⚠ PyMuPDF not installed (using pypdf for text extraction)")
    
    try:
        import docx
        print(f"  ✓ python-docx")
    except ImportError:
        missing.append('python-docx')
        print("  ✗ python-docx not found")
    
    try:
        import openpyxl
        print(f"  ✓ openpyxl")
    except ImportError:
        missing.append('openpyxl')
        print("  ✗ openpyxl not found")
    
    try:
        import PIL
        print(f"  ✓ Pillow")
    except ImportError:
        missing.append('Pillow')
        print("  ✗ Pillow not found")
    
    # Check OCR
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        print(f"  ✓ Tesseract OCR available")
    except Exception:
        print("  ⚠ Tesseract OCR not available (OCR disabled)")
    
    print()
    
    if missing:
        print(f"  Missing dependencies: {', '.join(missing)}")
        print(f"  Install with: pip install {' '.join(missing)}")
        print()
        sys.exit(1)
    
    # Check for sample PDF
    sample_path = os.path.join(project_root, 'assets', 'sample', 'sample_students.pdf')
    if os.path.exists(sample_path):
        print(f"  ✓ Sample PDF found")
    else:
        print(f"  ⚠ Sample PDF not found. Generate with:")
        print(f"    python scripts/create_sample_pdf.py")
    
    print()
    print("  Starting application...")
    print("=" * 50)
    print()
    
    # Import and run
    from main import main
    main()
