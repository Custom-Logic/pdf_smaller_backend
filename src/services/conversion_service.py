"""
Conversion Service
Handles PDF to Word, Excel, Text, and HTML conversion
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json

# PDF processing libraries
try:
    import pdfplumber
    import fitz  # PyMuPDF
    PDF_LIBS_AVAILABLE = True
except ImportError:
    PDF_LIBS_AVAILABLE = False
    logging.warning("PDF processing libraries not available. Install pdfplumber and PyMuPDF for full functionality.")

# Document creation libraries
try:
    from docx import Document
    from docx.shared import Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx not available. Install for Word document creation.")

try:
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False
    logging.warning("openpyxl not available. Install for Excel document creation.")

logger = logging.getLogger(__name__)

class ConversionService:
    """Service for converting PDFs to various formats"""
    
    def __init__(self):
        self.supported_formats = ['docx', 'xlsx', 'txt', 'html']
        self.temp_dir = tempfile.mkdtemp(prefix='pdf_conversion_')
        
        # Check library availability
        if not PDF_LIBS_AVAILABLE:
            logger.error("PDF processing libraries not available. Conversion service will not work properly.")
        
        if not DOCX_AVAILABLE:
            logger.warning("Word document creation not available. Install python-docx.")
            
        if not XLSX_AVAILABLE:
            logger.warning("Excel document creation not available. Install openpyxl.")
    
    def convert_pdf(self, file, target_format: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Convert PDF to specified format
        
        Args:
            file: Uploaded file object
            target_format: Target format (docx, xlsx, txt, html)
            options: Conversion options
            
        Returns:
            Dictionary with conversion result
        """
        if not options:
            options = {}
            
        try:
            # Validate format
            if target_format not in self.supported_formats:
                raise ValueError(f"Unsupported format: {target_format}")
            
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Extract content from PDF
            pdf_content = self._extract_pdf_content(temp_file_path, options)
            
            # Convert to target format
            if target_format == 'docx':
                result = self._convert_to_docx(pdf_content, options)
            elif target_format == 'xlsx':
                result = self._convert_to_xlsx(pdf_content, options)
            elif target_format == 'txt':
                result = self._convert_to_txt(pdf_content, options)
            elif target_format == 'html':
                result = self._convert_to_html(pdf_content, options)
            else:
                raise ValueError(f"Unsupported format: {target_format}")
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return result
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise
    
    def get_conversion_preview(self, file, target_format: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get conversion preview and estimates
        
        Args:
            file: Uploaded file object
            target_format: Target format
            options: Conversion options
            
        Returns:
            Dictionary with preview information
        """
        if not options:
            options = {}
            
        try:
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Analyze PDF
            pdf_content = self._extract_pdf_content(temp_file_path, options)
            
            # Generate preview
            preview = {
                'originalSize': file.content_length or 0,
                'pageCount': pdf_content.get('page_count', 0),
                'estimatedSize': self._estimate_output_size(pdf_content, target_format),
                'estimatedTime': self._estimate_conversion_time(pdf_content, target_format),
                'complexity': self._assess_complexity(pdf_content, target_format),
                'recommendations': self._get_recommendations(pdf_content, target_format, options)
            }
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return preview
            
        except Exception as e:
            logger.error(f"Conversion preview failed: {str(e)}")
            raise
    
    def _save_uploaded_file(self, file) -> str:
        """Save uploaded file to temporary directory"""
        filename = secure_filename(file.filename)
        temp_path = os.path.join(self.temp_dir, filename)
        
        file.save(temp_path)
        return temp_path
    
    def _extract_pdf_content(self, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content from PDF file"""
        if not PDF_LIBS_AVAILABLE:
            raise RuntimeError("PDF processing libraries not available")
        
        try:
            content = {
                'pages': [],
                'tables': [],
                'images': [],
                'text': '',
                'page_count': 0,
                'metadata': {}
            }
            
            # Use PyMuPDF for better performance
            with fitz.open(file_path) as doc:
                content['page_count'] = len(doc)
                content['metadata'] = doc.metadata
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    
                    # Extract text
                    text = page.get_text()
                    content['text'] += text + '\n'
                    
                    # Extract tables (basic detection)
                    tables = self._extract_tables_from_page(page)
                    content['tables'].extend(tables)
                    
                    # Extract images
                    images = self._extract_images_from_page(page)
                    content['images'].extend(images)
                    
                    # Store page content
                    content['pages'].append({
                        'page_num': page_num + 1,
                        'text': text,
                        'tables': tables,
                        'images': images,
                        'width': page.rect.width,
                        'height': page.rect.height
                    })
            
            return content
            
        except Exception as e:
            logger.error(f"PDF content extraction failed: {str(e)}")
            raise
    
    def _extract_tables_from_page(self, page) -> list:
        """Extract tables from a PDF page"""
        tables = []
        try:
            # Basic table detection using text layout analysis
            # This is a simplified approach - in production you'd use more sophisticated table detection
            text_blocks = page.get_text("dict")
            
            for block in text_blocks.get("blocks", []):
                if "lines" in block:
                    # Check if this looks like a table structure
                    if self._looks_like_table(block):
                        table_data = self._extract_table_data(block)
                        if table_data:
                            tables.append(table_data)
            
        except Exception as e:
            logger.warning(f"Table extraction failed: {str(e)}")
        
        return tables
    
    def _looks_like_table(self, block) -> bool:
        """Check if a text block looks like a table"""
        # Simple heuristic: check for multiple lines with similar structure
        lines = block.get("lines", [])
        if len(lines) < 2:
            return False
        
        # Check if lines have similar number of spans (columns)
        span_counts = [len(line.get("spans", [])) for line in lines]
        return len(set(span_counts)) <= 2 and max(span_counts) > 1
    
    def _extract_table_data(self, block) -> list:
        """Extract table data from a block"""
        try:
            table_data = []
            lines = block.get("lines", [])
            
            for line in lines:
                row = []
                spans = line.get("spans", [])
                
                for span in spans:
                    text = span.get("text", "").strip()
                    if text:
                        row.append(text)
                
                if row:
                    table_data.append(row)
            
            return table_data if table_data else None
            
        except Exception as e:
            logger.warning(f"Table data extraction failed: {str(e)}")
            return None
    
    def _extract_images_from_page(self, page) -> list:
        """Extract images from a PDF page"""
        images = []
        try:
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                image_info = {
                    'index': img_index,
                    'xref': xref,
                    'width': img[2],
                    'height': img[3],
                    'colorspace': img[4],
                    'bpc': img[5]
                }
                images.append(image_info)
                
        except Exception as e:
            logger.warning(f"Image extraction failed: {str(e)}")
        
        return images
    
    def _convert_to_docx(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF content to Word document"""
        if not DOCX_AVAILABLE:
            raise RuntimeError("Word document creation not available. Install python-docx.")
        
        try:
            doc = Document()
            
            # Apply options
            preserve_formatting = options.get('preserveFormatting', True)
            include_headers = options.get('includeHeaders', True)
            include_footers = options.get('includeFooters', True)
            
            # Add title
            if pdf_content.get('metadata', {}).get('title'):
                title = doc.add_heading(pdf_content['metadata']['title'], 0)
                title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Process each page
            for page in pdf_content['pages']:
                # Add page break (except for first page)
                if page['page_num'] > 1:
                    doc.add_page_break()
                
                # Add page text
                if page['text'].strip():
                    # Split text into paragraphs
                    paragraphs = page['text'].split('\n\n')
                    for para_text in paragraphs:
                        if para_text.strip():
                            doc.add_paragraph(para_text.strip())
                
                # Add tables
                for table_data in page['tables']:
                    if table_data and len(table_data) > 0:
                        # Create table
                        table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
                        table.style = 'Table Grid'
                        
                        # Populate table
                        for row_idx, row_data in enumerate(table_data):
                            for col_idx, cell_data in enumerate(row_data):
                                if col_idx < len(table_data[row_idx]):
                                    table.cell(row_idx, col_idx).text = str(cell_data)
            
            # Save document
            output_filename = f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.docx"
            output_path = os.path.join(self.temp_dir, output_filename)
            doc.save(output_path)
            
            return {
                'file_path': output_path,
                'filename': output_filename,
                'mime_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'format': 'docx'
            }
            
        except Exception as e:
            logger.error(f"DOCX conversion failed: {str(e)}")
            raise
    
    def _convert_to_xlsx(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF content to Excel document"""
        if not XLSX_AVAILABLE:
            raise RuntimeError("Excel document creation not available. Install openpyxl.")
        
        try:
            wb = Workbook()
            
            # Apply options
            sheet_per_page = options.get('sheetPerPage', False)
            merge_tables = options.get('mergeTables', True)
            
            if sheet_per_page:
                # Create one sheet per page
                for page in pdf_content['pages']:
                    if page['page_num'] == 1:
                        ws = wb.active
                        ws.title = f"Page {page['page_num']}"
                    else:
                        ws = wb.create_sheet(f"Page {page['page_num']}")
                    
                    self._add_page_to_worksheet(ws, page)
            else:
                # Create one sheet with all content
                ws = wb.active
                ws.title = "PDF Content"
                
                # Add all pages
                for page in pdf_content['pages']:
                    self._add_page_to_worksheet(ws, page)
                    
                    # Add page break
                    if page['page_num'] < len(pdf_content['pages']):
                        ws.append([])  # Empty row as separator
            
            # Save workbook
            output_filename = f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.xlsx"
            output_path = os.path.join(self.temp_dir, output_filename)
            wb.save(output_path)
            
            return {
                'file_path': output_path,
                'filename': output_filename,
                'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'format': 'xlsx'
            }
            
        except Exception as e:
            logger.error(f"XLSX conversion failed: {str(e)}")
            raise
    
    def _add_page_to_worksheet(self, ws, page):
        """Add page content to worksheet"""
        # Add page header
        ws.append([f"Page {page['page_num']}"])
        ws.append([])  # Empty row
        
        # Add text content
        if page['text'].strip():
            paragraphs = page['text'].split('\n\n')
            for para_text in paragraphs:
                if para_text.strip():
                    ws.append([para_text.strip()])
            ws.append([])  # Empty row
        
        # Add tables
        for table_data in page['tables']:
            if table_data and len(table_data) > 0:
                for row_data in table_data:
                    ws.append(row_data)
                ws.append([])  # Empty row after table
    
    def _convert_to_txt(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF content to text file"""
        try:
            # Apply options
            preserve_paragraphs = options.get('preserveParagraphs', True)
            remove_extra_spaces = options.get('removeExtraSpaces', True)
            
            text_content = pdf_content['text']
            
            if remove_extra_spaces:
                # Clean up extra whitespace
                import re
                text_content = re.sub(r'\s+', ' ', text_content)
                text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            
            # Save text file
            output_filename = f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.txt"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            return {
                'file_path': output_path,
                'filename': output_filename,
                'mime_type': 'text/plain',
                'format': 'txt'
            }
            
        except Exception as e:
            logger.error(f"TXT conversion failed: {str(e)}")
            raise
    
    def _convert_to_html(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF content to HTML file"""
        try:
            # Apply options
            include_css = options.get('includeCSS', True)
            responsive_layout = options.get('responsiveLayout', True)
            
            # Generate HTML content
            html_content = self._generate_html_content(pdf_content, options)
            
            # Save HTML file
            output_filename = f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.html"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return {
                'file_path': output_path,
                'filename': output_filename,
                'mime_type': 'text/html',
                'format': 'html'
            }
            
        except Exception as e:
            logger.error(f"HTML conversion failed: {str(e)}")
            raise
    
    def _generate_html_content(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Generate HTML content from PDF content"""
        css_styles = ""
        if options.get('includeCSS', True):
            css_styles = """
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .page { page-break-after: always; margin-bottom: 30px; }
                .page:last-child { page-break-after: avoid; }
                .page-header { font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #333; }
                .text-content { line-height: 1.6; }
                table { border-collapse: collapse; width: 100%; margin: 15px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                @media print { .page { page-break-after: always; } }
            </style>
            """
        
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "<title>Converted PDF Document</title>",
            css_styles,
            "</head>",
            "<body>"
        ]
        
        # Add title
        if pdf_content.get('metadata', {}).get('title'):
            html_parts.append(f"<h1>{pdf_content['metadata']['title']}</h1>")
        
        # Process each page
        for page in pdf_content['pages']:
            html_parts.append(f'<div class="page">')
            html_parts.append(f'<div class="page-header">Page {page["page_num"]}</div>')
            
            # Add text content
            if page['text'].strip():
                html_parts.append('<div class="text-content">')
                paragraphs = page['text'].split('\n\n')
                for para_text in paragraphs:
                    if para_text.strip():
                        html_parts.append(f'<p>{para_text.strip()}</p>')
                html_parts.append('</div>')
            
            # Add tables
            for table_data in page['tables']:
                if table_data and len(table_data) > 0:
                    html_parts.append('<table>')
                    for row_idx, row_data in enumerate(table_data):
                        if row_idx == 0:
                            # Header row
                            html_parts.append('<thead><tr>')
                            for cell_data in row_data:
                                html_parts.append(f'<th>{cell_data}</th>')
                            html_parts.append('</tr></thead>')
                        else:
                            # Data row
                            html_parts.append('<tr>')
                            for cell_data in row_data:
                                html_parts.append(f'<td>{cell_data}</td>')
                            html_parts.append('</tr>')
                    html_parts.append('</table>')
            
            html_parts.append('</div>')
        
        html_parts.extend([
            "</body>",
            "</html>"
        ])
        
        return '\n'.join(html_parts)
    
    def _estimate_output_size(self, pdf_content: Dict[str, Any], target_format: str) -> int:
        """Estimate output file size"""
        base_size = len(pdf_content.get('text', ''))
        
        size_multipliers = {
            'docx': 1.2,    # Word files are typically larger due to formatting
            'xlsx': 0.8,    # Excel files are more compact
            'txt': 0.3,     # Text files are much smaller
            'html': 1.5     # HTML files include markup
        }
        
        multiplier = size_multipliers.get(target_format, 1.0)
        return int(base_size * multiplier)
    
    def _estimate_conversion_time(self, pdf_content: Dict[str, Any], target_format: str) -> int:
        """Estimate conversion time in seconds"""
        page_count = pdf_content.get('page_count', 1)
        
        # Base time per format
        base_times = {
            'docx': 2,   # 2 seconds per page
            'xlsx': 3,   # 3 seconds per page (table processing)
            'txt': 0.5,  # 0.5 seconds per page
            'html': 1    # 1 second per page
        }
        
        base_time = base_times.get(target_format, 1)
        return int(page_count * base_time)
    
    def _assess_complexity(self, pdf_content: Dict[str, Any], target_format: str) -> str:
        """Assess conversion complexity"""
        page_count = pdf_content.get('page_count', 1)
        table_count = len(pdf_content.get('tables', []))
        image_count = len(pdf_content.get('images', []))
        
        if page_count > 50 or table_count > 20 or image_count > 100:
            return 'high'
        elif page_count > 20 or table_count > 10 or image_count > 50:
            return 'medium'
        else:
            return 'low'
    
    def _get_recommendations(self, pdf_content: Dict[str, Any], target_format: str, options: Dict[str, Any]) -> list:
        """Get conversion recommendations"""
        recommendations = []
        
        page_count = pdf_content.get('page_count', 1)
        table_count = len(pdf_content.get('tables', []))
        image_count = len(pdf_content.get('images', []))
        
        if page_count > 100:
            recommendations.append("Large document detected. Consider splitting into smaller files for better performance.")
        
        if table_count > 0 and target_format == 'xlsx':
            recommendations.append("Document contains tables. Excel format will preserve table structure best.")
        
        if image_count > 0 and target_format == 'txt':
            recommendations.append("Document contains images. Text format will not preserve images.")
        
        if target_format == 'docx' and table_count > 10:
            recommendations.append("Document has many tables. Consider Excel format for better table handling.")
        
        return recommendations
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {str(e)}")

def secure_filename(filename):
    """Secure filename for safe file operations"""
    # This is a simplified version - in production use werkzeug.utils.secure_filename
    import re
    # Remove or replace unsafe characters
    filename = re.sub(r'[^\w\s-]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    return filename.strip('-')
