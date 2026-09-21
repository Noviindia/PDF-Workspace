import os
import io
import json
import tempfile
import fitz
from typing import Optional, Dict, Any, List
from flask import Flask, request, jsonify, render_template, send_file, Response

from app.services.project_service import ProjectService
from app.services.processing_service import ProcessingService
from app.core.ocr_engine import OCREngine
from app.core.search_engine import SearchResult
from app.database.models import ExportConfig
from app.exporters.xlsx_exporter import XLSXExporter
from app.exporters.csv_exporter import CSVExporter
from app.exporters.docx_exporter import DOCXExporter
from app.exporters.json_exporter import JSONExporter
from app.exporters.html_exporter import HTMLExporter
from app.exporters.txt_exporter import TXTExporter


EXPORTERS = {
    'xlsx': XLSXExporter,
    'csv': CSVExporter,
    'docx': DOCXExporter,
    'json': JSONExporter,
    'html': HTMLExporter,
    'txt': TXTExporter,
}


def create_app(data_dir: Optional[str] = None) -> Flask:
    """Create and configure the PDF Workspace Flask web application."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(app_dir, 'templates')
    static_dir = os.path.join(app_dir, 'static')
    os.makedirs(templates_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)

    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=static_dir
    )
    app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250 MB max upload

    if not data_dir:
        base_dir = os.path.dirname(os.path.dirname(app_dir))
        data_dir = os.path.join(base_dir, 'data', 'web_projects')
    os.makedirs(data_dir, exist_ok=True)
    os.environ['PDFWORKSPACE_DIR'] = data_dir

    project_service = ProjectService()
    ocr_engine = OCREngine()

    # Active session state
    state: Dict[str, Any] = {
        'active_project_path': None,
        'active_processing_service': None,
        'active_document_id': None,
        'active_pdf_path': None,
    }

    def get_service() -> Optional[ProcessingService]:
        return state.get('active_processing_service')

    # --- HTML View Route ---
    @app.route('/')
    def index():
        return render_template('index.html')

    # --- API Status & Environment ---
    @app.route('/api/status')
    def api_status():
        ps = get_service()
        doc_id = state.get('active_document_id')
        doc_name = None
        total_pages = 0
        total_records = 0

        if ps and doc_id:
            repo = ps.get_repository()
            doc = repo.get_document(doc_id)
            if doc:
                doc_name = doc.name
                total_pages = doc.page_count
                total_records = repo.get_record_count(doc_id)

        return jsonify({
            'status': 'online',
            'lens_available': ocr_engine._check_lens(),
            'tesseract_available': ocr_engine._backend in ('fitz', 'pytesseract'),
            'default_engine': 'lens' if ocr_engine._check_lens() else 'tesseract',
            'active_doc_id': doc_id,
            'active_doc_name': doc_name,
            'total_pages': total_pages,
            'total_records': total_records
        })

    # --- Document Upload & Processing ---
    @app.route('/api/upload', methods=['POST'])
    def api_upload():
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in request'}), 400

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'error': 'No selected file'}), 400

        filename = file.filename
        if not filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400

        ocr_engine_choice = request.form.get('ocr_engine', 'lens').lower().strip()
        ocr_language = request.form.get('ocr_language', 'eng+hin').strip()
        layout_mode = request.form.get('layout_mode', 'auto').strip()
        force_ocr = request.form.get('force_ocr', 'true').lower() in ('true', '1', 'yes')

        # Save uploaded PDF to a temporary directory preserving original filename
        temp_dir = tempfile.mkdtemp()
        temp_pdf_path = os.path.join(temp_dir, filename)
        try:
            file.save(temp_pdf_path)

            doc_name = os.path.splitext(filename)[0]
            project_dir = os.path.join(data_dir, 'projects', doc_name)
            os.makedirs(project_dir, exist_ok=True)

            # Create or open project
            ps = project_service.create_project(project_dir, name=doc_name)
            doc_id = ps.import_pdf(
                temp_pdf_path,
                ocr_language=ocr_language,
                layout_mode=layout_mode,
                force_ocr=force_ocr,
                ocr_engine=ocr_engine_choice
            )

            # Update active state
            state['active_project_path'] = project_dir
            state['active_processing_service'] = ps
            state['active_document_id'] = doc_id
            state['active_pdf_path'] = ps.get_pdf_path(doc_id)

            repo = ps.get_repository()
            doc = repo.get_document(doc_id)
            total_records = repo.get_record_count(doc_id)

            return jsonify({
                'success': True,
                'doc_id': doc_id,
                'doc_name': filename,
                'total_pages': doc.page_count if doc else 0,
                'total_records': total_records,
                'ocr_engine': ocr_engine_choice,
                'ocr_language': ocr_language
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

    # --- Document Metadata ---
    @app.route('/api/documents/<int:doc_id>')
    def api_get_document(doc_id: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        repo = ps.get_repository()
        doc = repo.get_document(doc_id)
        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        pages = repo.get_pages_by_document(doc_id)
        categories = repo.get_categories()
        total_records = repo.get_record_count(doc_id)

        return jsonify({
            'id': doc.id,
            'filename': doc.name,
            'total_pages': doc.page_count,
            'total_records': total_records,
            'page_type': doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type),
            'categories': [{'id': c.id, 'name': c.name, 'count': c.record_count} for c in categories],
            'pages': [{'page_number': p.page_number, 'has_text': bool(p.raw_text and len(p.raw_text.strip()) > 0)} for p in pages]
        })

    # --- Page Image Rendering ---
    @app.route('/api/documents/<int:doc_id>/pages/<int:page_num>/image')
    def api_page_image(doc_id: int, page_num: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        pdf_path = ps.get_pdf_path(doc_id)
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({'error': 'PDF file not found'}), 404

        try:
            dpi = int(request.args.get('dpi', 150))
            dpi = max(72, min(dpi, 300))

            doc = fitz.open(pdf_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                return jsonify({'error': 'Page number out of bounds'}), 404

            page = doc.load_page(page_num - 1)
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            doc.close()

            return Response(img_bytes, mimetype='image/png', headers={
                'Cache-Control': 'public, max-age=3600'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # --- Page Raw/Processed Text ---
    @app.route('/api/documents/<int:doc_id>/pages/<int:page_num>/text')
    def api_page_text(doc_id: int, page_num: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        repo = ps.get_repository()
        page = repo.get_page_by_number(doc_id, page_num)
        if not page:
            return jsonify({'error': 'Page not found'}), 404

        return jsonify({
            'page_number': page_num,
            'raw_text': page.raw_text or '',
            'processed_text': page.processed_text or ''
        })

    # --- Search with Devanagari Normalization ---
    @app.route('/api/documents/<int:doc_id>/search')
    def api_search(doc_id: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        query = request.args.get('q', '').strip()
        scope = request.args.get('scope', 'all').strip().lower()

        if not query:
            return jsonify({'query': '', 'total_matches': 0, 'page_counts': {}, 'results': []})

        search_engine = ps.get_search_engine()
        results: List[SearchResult] = search_engine.search(query, document_id=doc_id, limit=500, scope=scope)

        page_counts: Dict[str, int] = {}
        out_results = []
        for idx, r in enumerate(results):
            p_str = str(r.page_number)
            page_counts[p_str] = page_counts.get(p_str, 0) + 1
            out_results.append({
                'id': idx + 1,
                'page_number': r.page_number,
                'field_name': getattr(r, 'match_field', '') or getattr(r, 'category_name', '') or 'Text',
                'snippet': getattr(r, 'context_snippet', '') or getattr(r, 'text', '') or '',
                'record_id': getattr(r, 'record_id', None)
            })

        return jsonify({
            'query': query,
            'scope': scope,
            'total_matches': len(results),
            'page_counts': page_counts,
            'results': out_results
        })

    # --- Page Bounding Box Highlights ---
    @app.route('/api/documents/<int:doc_id>/pages/<int:page_num>/highlights')
    def api_page_highlights(doc_id: int, page_num: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'boxes': [], 'page_width': 0, 'page_height': 0})

        repo = ps.get_repository()
        boxes = repo.find_bounding_boxes_for_text(doc_id, page_num, query)

        # Get actual page dimensions in PDF points
        pdf_path = ps.get_pdf_path(doc_id)
        page_width, page_height = 0.0, 0.0
        if pdf_path and os.path.exists(pdf_path):
            try:
                doc = fitz.open(pdf_path)
                if 1 <= page_num <= len(doc):
                    page = doc.load_page(page_num - 1)
                    page_width = float(page.rect.width)
                    page_height = float(page.rect.height)
                doc.close()
            except Exception:
                pass

        return jsonify({
            'page_number': page_num,
            'boxes': [[float(b[0]), float(b[1]), float(b[2]), float(b[3])] for b in boxes],
            'page_width': page_width,
            'page_height': page_height
        })

    # --- Structured Records Grid ---
    @app.route('/api/documents/<int:doc_id>/records')
    def api_get_records(doc_id: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        repo = ps.get_repository()
        category_id = request.args.get('category_id')
        if category_id:
            try:
                category_id = int(category_id)
                records = repo.get_records_by_category(category_id)
            except ValueError:
                records = repo.get_all_records()
        else:
            records = repo.get_all_records()

        # Collect ordered keys
        standard_cols = ['serial_no', 'voter_id', 'name', 'relation_name', 'house_no', 'age', 'gender']
        extra_keys = set()
        for r in records:
            if isinstance(r.data, dict):
                for k in r.data.keys():
                    if k not in standard_cols and not k.startswith('_'):
                        extra_keys.add(k)

        all_cols = standard_cols + sorted(list(extra_keys))

        rows = []
        for r in records:
            data = r.data if isinstance(r.data, dict) else {}
            row_dict = {
                'id': r.id,
                'page_number': r.page_number,
                'category_id': r.category_id,
                'is_edited': r.is_edited
            }
            for col in all_cols:
                row_dict[col] = data.get(col, '')
            rows.append(row_dict)

        return jsonify({
            'columns': all_cols,
            'total_records': len(rows),
            'records': rows
        })

    # --- Update Record ---
    @app.route('/api/records/<int:record_id>', methods=['POST'])
    def api_update_record(record_id: int):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        payload = request.get_json() or {}
        repo = ps.get_repository()
        record = repo.get_record(record_id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404

        curr_data = dict(record.data) if isinstance(record.data, dict) else {}
        for k, v in payload.items():
            if k not in ('id', 'page_number', 'category_id', 'is_edited'):
                curr_data[k] = v

        repo.update_record(record_id, data=curr_data)
        return jsonify({'success': True, 'record_id': record_id})

    # --- Export Document ---
    @app.route('/api/documents/<int:doc_id>/export/<format_name>')
    def api_export(doc_id: int, format_name: str):
        ps = get_service()
        if not ps:
            return jsonify({'error': 'No active project'}), 404

        fmt = format_name.lower().strip()
        if fmt not in EXPORTERS:
            return jsonify({'error': f'Unsupported export format: {fmt}'}), 400

        repo = ps.get_repository()
        doc = repo.get_document(doc_id)
        base_name = os.path.splitext(doc.name)[0] if doc else f"document_{doc_id}"

        temp_fd, out_path = tempfile.mkstemp(suffix=f".{fmt}")
        os.close(temp_fd)

        try:
            exporter_cls = EXPORTERS[fmt]
            exporter = exporter_cls(repo)
            config = ExportConfig(
                format=fmt,
                scope='all',
                output_path=out_path
            )
            exporter.export(config)

            download_name = f"{base_name}.{fmt}"
            return send_file(
                out_path,
                as_attachment=True,
                download_name=download_name
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)
