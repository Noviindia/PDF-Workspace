import os
from typing import List, Dict
from app.exporters.base_exporter import BaseExporter
from app.database.models import Record, Category

class HTMLExporter(BaseExporter):
    """HTML export."""
    
    def export_records(self, records: List[Record], output_path: str, document_name: str, categories: Dict[int, Category]):
        fields = self._get_field_names(records)
        headers = fields + ['Category', 'Source Page']
        
        category_records = {}
        for record in records:
            cat_id = record.category_id
            if cat_id not in category_records:
                category_records[cat_id] = []
            category_records[cat_id].append(record)
            
        html_parts = []
        html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{document_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1, h2 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f4f6f8; font-weight: 600; cursor: pointer; }}
        th:hover {{ background-color: #e2e6ea; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{ display: inline-block; margin-right: 15px; text-decoration: none; color: #007bff; }}
        .nav a:hover {{ text-decoration: underline; }}
        .search-box {{ width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
    </style>
    <script>
        function filterTable(inputId, tableClass) {{
            const input = document.getElementById(inputId);
            const filter = input.value.toUpperCase();
            const tables = document.getElementsByClassName(tableClass);
            for (let t = 0; t < tables.length; t++) {{
                const tr = tables[t].getElementsByTagName("tr");
                for (let i = 1; i < tr.length; i++) {{
                    let textValue = tr[i].textContent || tr[i].innerText;
                    if (textValue.toUpperCase().indexOf(filter) > -1) {{
                        tr[i].style.display = "";
                    }} else {{
                        tr[i].style.display = "none";
                    }}
                }}
            }}
        }}
        
        function sortTable(tableId, n) {{
            const table = document.getElementById(tableId);
            let rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
            switching = true;
            dir = "asc";
            while (switching) {{
                switching = false;
                rows = table.rows;
                for (i = 1; i < (rows.length - 1); i++) {{
                    shouldSwitch = false;
                    x = rows[i].getElementsByTagName("TD")[n];
                    y = rows[i + 1].getElementsByTagName("TD")[n];
                    let xVal = x.innerHTML.toLowerCase();
                    let yVal = y.innerHTML.toLowerCase();
                    if (!isNaN(parseFloat(xVal)) && isFinite(xVal)) xVal = parseFloat(xVal);
                    if (!isNaN(parseFloat(yVal)) && isFinite(yVal)) yVal = parseFloat(yVal);
                    
                    if (dir == "asc") {{
                        if (xVal > yVal) {{ shouldSwitch = true; break; }}
                    }} else if (dir == "desc") {{
                        if (xVal < yVal) {{ shouldSwitch = true; break; }}
                    }}
                }}
                if (shouldSwitch) {{
                    rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                    switching = true;
                    switchcount ++;
                }} else {{
                    if (switchcount == 0 && dir == "asc") {{
                        dir = "desc";
                        switching = true;
                    }}
                }}
            }}
        }}
    </script>
</head>
<body>
    <h1>{document_name}</h1>
    
    <div class="summary">
        <strong>Summary:</strong> Total Records: {len(records)} | Total Categories: {len(category_records)}
    </div>
    
    <input type="text" id="searchInput" class="search-box" onkeyup="filterTable('searchInput', 'data-table')" placeholder="Search in all tables...">
    
    <div class="nav">
""")
        for cat_id in category_records.keys():
            cat = categories.get(cat_id)
            cat_name = cat.name if cat else "Uncategorized"
            html_parts.append(f'<a href="#cat_{cat_id}">{cat_name}</a>')
            
        html_parts.append('</div>')
        
        for table_idx, (cat_id, cat_recs) in enumerate(category_records.items()):
            cat = categories.get(cat_id)
            cat_name = cat.name if cat else "Uncategorized"
            table_id = f"table_{table_idx}"
            
            html_parts.append(f'<h2 id="cat_{cat_id}">{cat_name} <small>({len(cat_recs)} records)</small></h2>')
            html_parts.append(f'<table id="{table_id}" class="data-table">')
            
            # Header
            html_parts.append('<tr>')
            for col_idx, header in enumerate(headers):
                html_parts.append(f'<th onclick="sortTable(\'{table_id}\', {col_idx})">{header} &#x21D5;</th>')
            html_parts.append('</tr>')
            
            # Rows
            for record in cat_recs:
                html_parts.append('<tr>')
                values = self._get_record_values(record, fields)
                values.append(cat_name)
                values.append(str(record.source_page) if record.source_page else "")
                
                for val in values:
                    html_parts.append(f'<td>{val}</td>')
                html_parts.append('</tr>')
                
            html_parts.append('</table>')
            
        html_parts.append("""
</body>
</html>
""")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("".join(html_parts))
