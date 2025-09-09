"""
Conversion Service - Job-Oriented Architecture
Handles PDF to Word, Text, HTML, and Images conversion
"""

import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

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

logger = logging.getLogger(__name__)

class ConversionService:
    """Service for converting PDFs to various formats - Job-Oriented"""
    
    def __init__(self, upload_folder: str = None):
        self.upload_folder = upload_folder or tempfile.mkdtemp(prefix='pdf_conversion_')
        self.supported_formats = ['docx', 'txt', 'html', 'images']
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
        
        # Check library availability
        if not PDF_LIBS_AVAILABLE:
            logger.error("PDF processing libraries not available. Conversion service will not work properly.")
        
        if not DOCX_AVAILABLE:
            logger.warning("Word document creation not available. Install python-docx.")
    
    def convert_pdf_data(self, file_data: bytes, target_format: str,
                             options: Dict[str, Any] = None, 
                             original_filename: str = None) -> Dict[str, Any]:
        """
        Convert PDF data to specified format
        
        Args:
            file_data: PDF file data as bytes
            target_format: Target format (docx, txt, html, images)
            options: Conversion options including quality
            original_filename: Original filename for naming
            
        Returns:
            Dictionary with conversion result
        """
        if not options:
            options = {}
            
        try:
            # Validate format against frontend supported formats
            if target_format not in self.supported_formats:
                raise ValueError(f"Unsupported format: {target_format}. Supported: {self.supported_formats}")
            
            # Create temporary file
            temp_file_path = self._save_file_data(file_data, original_filename)
            
            try:
                # Extract content from PDF
                pdf_content = self._extract_pdf_content(temp_file_path, options)
                
                # Convert to target format
                if target_format == 'docx':
                    result = self._convert_to_docx(pdf_content, options)
                elif target_format == 'txt':
                    result = self._convert_to_txt(pdf_content, options)
                elif target_format == 'html':
                    result = self._convert_to_html(pdf_content, options)
                elif target_format == 'images':
                    result = self._convert_to_images(pdf_content, options)
                else:
                    raise ValueError(f"Unsupported format: {target_format}")
                
                # Add metadata
                result.update({
                    'format': target_format,
                    'quality': options.get('quality', 'medium'),
                    'original_filename': original_filename,
                    'original_size': len(file_data)
                })
                
                return result
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise
    
    def get_conversion_preview(self, file_data: bytes, target_format: str, 
                                   options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get conversion preview and estimates
        
        Args:
            file_data: PDF file data as bytes
            target_format: Target format
            options: Conversion options
            
        Returns:
            Dictionary with preview information
        """
        if not options:
            options = {}
            
        try:
            # Create temporary file
            temp_file_path = self._save_file_data(file_data, "preview.pdf")
            
            try:
                # Analyze PDF
                pdf_content = self._extract_pdf_content(temp_file_path, options)
                
                # Generate preview
                preview = {
                    'success': True,
                    'original_size': len(file_data),
                    'page_count': pdf_content.get('page_count', 0),
                    'estimated_size': self._estimate_output_size(pdf_content, target_format),
                    'estimated_time': self._estimate_conversion_time(pdf_content, target_format),
                    'complexity': self._assess_complexity(pdf_content, target_format),
                    'recommendations': self._get_recommendations(pdf_content, target_format, options),
                    'supported_formats': self.supported_formats
                }
                
                return preview
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"Conversion preview failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'original_size': len(file_data)
            }
    
    def _save_file_data(self, file_data: bytes, filename: str = None) -> str:
        """Save file data to temporary directory"""
        filename = filename or f"temp_{uuid.uuid4().hex[:8]}.pdf"
        safe_filename = self._secure_filename(filename)
        temp_path = os.path.join(self.upload_folder, safe_filename)
        
        with open(temp_path, 'wb') as f:
            f.write(file_data)
        
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
                    
                    # Extract tables
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
            text_blocks = page.get_text("dict")
            
            for block in text_blocks.get("blocks", []):
                if "lines" in block:
                    if self._looks_like_table(block):
                        table_data = self._extract_table_data(block)
                        if table_data:
                            tables.append(table_data)
            
        except Exception as e:
            logger.warning(f"Table extraction failed: {str(e)}")
        
        return tables
    
    @staticmethod
    def _looks_like_table(block) -> bool:
        """Check if a text block looks like a table"""
        lines = block.get("lines", [])
        if len(lines) < 2:
            return False
        
        span_counts = [len(line.get("spans", [])) for line in lines]
        return len(set(span_counts)) <= 2 and max(span_counts) > 1
    
    @staticmethod
    def _extract_table_data(block) -> list| None:
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
    
    @staticmethod
    def _extract_images_from_page(page) -> list:
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
            
            # Apply quality settings
            quality = options.get('quality', 'medium')
            quality_settings = {
                'low': {'preserve_formatting': False, 'include_images': False},
                'medium': {'preserve_formatting': True, 'include_images': True},
                'high': {'preserve_formatting': True, 'include_images': True, 'high_quality': True}
            }
            quality_config = quality_settings.get(quality, quality_settings['medium'])
            
            # Add title
            if pdf_content.get('metadata', {}).get('title'):
                title = doc.add_heading(pdf_content['metadata']['title'], 0)
                title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Process each page
            for page in pdf_content['pages']:
                if page['page_num'] > 1:
                    doc.add_page_break()
                
                # Add page text
                if page['text'].strip():
                    paragraphs = page['text'].split('\n\n')
                    for para_text in paragraphs:
                        if para_text.strip():
                            doc.add_paragraph(para_text.strip())
                
                # Add tables
                for table_data in page['tables']:
                    if table_data and len(table_data) > 0:
                        table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
                        table.style = 'Table Grid'
                        
                        for row_idx, row_data in enumerate(table_data):
                            for col_idx, cell_data in enumerate(row_data):
                                if col_idx < len(table_data[row_idx]):
                                    table.cell(row_idx, col_idx).text = str(cell_data)
            
            # Save document
            output_filename = f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.docx"
            output_path = os.path.join(self.upload_folder, output_filename)
            doc.save(output_path)
            
            # Read the file data
            with open(output_path, 'rb') as f:
                file_data = f.read()
            
            return {
                'success': True,
                'file_data': file_data,
                'filename': output_filename,
                'mime_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'file_size': len(file_data)
            }
            
        except Exception as e:
            logger.error(f"DOCX conversion failed: {str(e)}")
            raise
    
    @staticmethod
    def _convert_to_txt(pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF content to text file"""
        try:
            # Apply quality settings
            quality = options.get('quality', 'medium')
            quality_settings = {
                'low': {'preserve_paragraphs': False, 'remove_extra_spaces': True},
                'medium': {'preserve_paragraphs': True, 'remove_extra_spaces': True},
                'high': {'preserve_paragraphs': True, 'remove_extra_spaces': False, 'preserve_layout': True}
            }
            quality_config = quality_settings.get(quality, quality_settings['medium'])
            
            text_content = pdf_content['text']
            
            if quality_config.get('remove_extra_spaces', True):
                import re
                text_content = re.sub(r'\s+', ' ', text_content)
                text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            
            # Convert to bytes
            file_data = text_content.encode('utf-8')
            
            return {
                'success': True,
                'file_data': file_data,
                'filename': f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.txt",
                'mime_type': 'text/plain',
                'file_size': len(file_data)
            }
            
        except Exception as e:
            logger.error(f"TXT conversion failed: {str(e)}")
            raise
    
    def _convert_to_html(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF content to HTML file"""
        try:
            # Apply quality settings
            quality = options.get('quality', 'medium')
            quality_settings = {
                'low': {'include_css': False, 'responsive_layout': False},
                'medium': {'include_css': True, 'responsive_layout': True},
                'high': {'include_css': True, 'responsive_layout': True, 'preserve_styles': True}
            }
            quality_config = quality_settings.get(quality, quality_settings['medium'])
            
            # Generate HTML content
            html_content = self._generate_html_content(pdf_content, quality_config)
            
            # Convert to bytes
            file_data = html_content.encode('utf-8')
            
            return {
                'success': True,
                'file_data': file_data,
                'filename': f"converted_{pdf_content.get('metadata', {}).get('title', 'document')}.html",
                'mime_type': 'text/html',
                'file_size': len(file_data)
            }
            
        except Exception as e:
            logger.error(f"HTML conversion failed: {str(e)}")
            raise
    
    @staticmethod
    def _convert_to_images(pdf_content: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF to images (one per page)"""
        try:
            # Apply quality settings
            quality = options.get('quality', 'medium')
            dpi_settings = {
                'low': 72,
                'medium': 150,
                'high': 300
            }
            dpi = dpi_settings.get(quality, 150)
            
            # This would be implemented using PyMuPDF to extract images from each page
            # For now, return a placeholder since image extraction is complex
            return {
                'success': False,
                'error': 'Image conversion not fully implemented',
                'format': 'images'
            }
            
        except Exception as e:
            logger.error(f"Image conversion failed: {str(e)}")
            raise
    
    def _generate_html_content(self, pdf_content: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Generate HTML content from PDF content"""
        css_styles = ""
        if options.get('include_css', True):
            css_styles = """
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .page { margin-bottom: 30px; }
                .page-header { font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #333; }
                .text-content { line-height: 1.6; }
                table { border-collapse: collapse; width: 100%; margin: 15px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
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
                            html_parts.append('<thead><tr>')
                            for cell_data in row_data:
                                html_parts.append(f'<th>{cell_data}</th>')
                            html_parts.append('</tr></thead>')
                        else:
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
    
    @staticmethod
    def _estimate_output_size(pdf_content: Dict[str, Any], target_format: str) -> int:
        """Estimate output file size"""
        base_size = len(pdf_content.get('text', ''))
        
        size_multipliers = {
            'docx': 1.2,
            'txt': 0.3,
            'html': 1.5,
            'images': 2.0  # Images are larger
        }
        
        multiplier = size_multipliers.get(target_format, 1.0)
        return int(base_size * multiplier)
    
    @staticmethod
    def _estimate_conversion_time(pdf_content: Dict[str, Any], target_format: str) -> int:
        """Estimate conversion time in seconds"""
        page_count = pdf_content.get('page_count', 1)
        
        base_times = {
            'docx': 2,
            'txt': 0.5,
            'html': 1,
            'images': 3  # Image conversion takes longer
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
    
    @staticmethod
    def _get_recommendations(pdf_content: Dict[str, Any], target_format: str, options: Dict[str, Any]) -> list:
        """Get conversion recommendations"""
        recommendations = []
        
        page_count = pdf_content.get('page_count', 1)
        table_count = len(pdf_content.get('tables', []))
        image_count = len(pdf_content.get('images', []))
        
        if page_count > 100:
            recommendations.append("Large document detected. Consider splitting into smaller files.")
        
        if table_count > 0 and target_format == 'txt':
            recommendations.append("Document contains tables. Consider DOCX format for better table preservation.")
        
        if image_count > 0 and target_format == 'txt':
            recommendations.append("Document contains images. Text format will not preserve images.")
        
        if target_format == 'html' and table_count > 10:
            recommendations.append("Document has many tables. HTML format will preserve table structure.")
        
        return recommendations
    
    @staticmethod
    def _secure_filename(filename: str) -> str:
        """Secure filename for safe file operations"""
        import re
        # Remove unsafe characters
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename.strip('-')
    
    def create_conversion_job(self, file_data: bytes, target_format: str,
                                  options: Dict[str, Any] = None,
                                  original_filename: str = None,
                                  client_job_id: str = None,
                                  client_session_id: str = None) -> Dict[str, Any]:
        """
        Create a conversion job for processing
        """
        try:
            # For processing, you'd typically:
            # 1. Create a job record in database
            # 2. Store file data in temporary storage
            # 3. Return job ID for tracking
            
            job_id = str(uuid.uuid4())
            
            # In a real implementation, you'd save this to a database
            job_info = {
                'job_id': job_id,
                'target_format': target_format,
                'options': options or {},
                'original_filename': original_filename,
                'client_job_id': client_job_id,
                'client_session_id': client_session_id,
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            # Store file data temporarily (in production, use proper storage)
            temp_file_path = self._save_file_data(file_data, f"{job_id}.pdf")
            job_info['temp_file_path'] = temp_file_path
            
            return {
                'success': True,
                'job_id': job_id,
                'status': 'pending',
                'message': 'Conversion job created successfully'
            }
            
        except Exception as e:
            logger.error(f"Error creating conversion job: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.upload_folder, ignore_errors=True)
            # Recreate directory
            Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {str(e)}")