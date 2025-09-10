"""
OCR Service - Job-Oriented Architecture
Handles Optical Character Recognition for scanned PDFs and images
"""

import os
import tempfile
import logging
import uuid
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# OCR libraries
try:
    import pytesseract
    from PIL import Image
    OCR_LIBS_AVAILABLE = True
except ImportError:
    OCR_LIBS_AVAILABLE = False
    logging.warning("OCR libraries not available. Install pytesseract and Pillow for OCR functionality.")

# PDF processing libraries
try:
    import fitz  # PyMuPDF
    PDF_LIBS_AVAILABLE = True
except ImportError:
    PDF_LIBS_AVAILABLE = False
    logging.warning("PDF processing libraries not available. Install PyMuPDF for PDF OCR functionality.")

logger = logging.getLogger(__name__)

class OCRService:
    """Service for performing OCR on PDFs and images - Job-Oriented"""
    
    def __init__(self, upload_folder: str = None):
        self.upload_folder = upload_folder or tempfile.mkdtemp(prefix='ocr_processing_')
        self.supported_formats = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp']
        self.supported_languages = [
            'eng', 'spa', 'fra', 'deu', 'ita', 'por', 'rus', 'jpn', 'kor', 'chi_sim', 'ara', 'hin'
        ]
        self.quality_levels = ['fast', 'balanced', 'accurate']
        self.output_formats = ['searchable_pdf', 'text', 'json']
        
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
        
        # Check library availability
        if not OCR_LIBS_AVAILABLE:
            logger.error("OCR libraries not available. OCR service will not work properly.")
        
        if not PDF_LIBS_AVAILABLE:
            logger.warning("PDF processing libraries not available. PDF OCR will not work.")
        
        # Configure Tesseract if available
        if OCR_LIBS_AVAILABLE:
            self._configure_tesseract()
    
    def _configure_tesseract(self):
        """Configure Tesseract OCR settings"""
        try:
            # Try common Tesseract paths
            alternative_paths = [
                '/usr/bin/tesseract',
                '/usr/local/bin/tesseract',
                'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
                '/opt/homebrew/bin/tesseract'
            ]
            
            for path in alternative_paths:
                try:
                    pytesseract.pytesseract.tesseract_cmd = path
                    version = pytesseract.get_tesseract_version()
                    logger.info(f"Tesseract found at {path}, version: {version}")
                    break
                except Exception:
                    continue
            else:
                logger.error("Tesseract not found in any standard location")
                
        except Exception as e:
            logger.warning(f"Tesseract configuration failed: {str(e)}")
    
    async def process_ocr_data(self, file_data: bytes, options: Dict[str, Any] = None, 
                             original_filename: str = None) -> Dict[str, Any]:
        """
        Process OCR on file data
        
        Args:
            file_data: File data as bytes
            options: OCR options including outputFormat, language, quality
            original_filename: Original filename for naming
            
        Returns:
            Dictionary with OCR result including file_data
        """
        if not options:
            options = {}
            
        try:
            # Validate and get file extension
            file_extension = self._get_file_extension(original_filename) if original_filename else 'pdf'
            if file_extension not in self.supported_formats:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            # Save file data to temp directory
            temp_file_path = await self._save_file_data(file_data, original_filename)
            
            try:
                # Process based on file type
                if file_extension == 'pdf':
                    result = await self._process_pdf_ocr(temp_file_path, options)
                else:
                    result = await self._process_image_ocr(temp_file_path, options)
                
                # Read the result file data
                with open(result['file_path'], 'rb') as f:
                    result['file_data'] = f.read()
                
                # Add metadata
                result.update({
                    'original_filename': original_filename,
                    'original_size': len(file_data),
                    'options': options
                })
                
                return result
                
            finally:
                # Clean up temp files
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                if 'file_path' in locals() and os.path.exists(result['file_path']):
                    os.unlink(result['file_path'])
                    
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            raise
    
    async def get_ocr_preview(self, file_data: bytes, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get OCR preview and estimates
        
        Args:
            file_data: File data as bytes
            options: OCR options
            
        Returns:
            Dictionary with preview information
        """
        if not options:
            options = {}
            
        try:
            # Save file data to temp directory
            temp_file_path = await self._save_file_data(file_data, "preview.pdf")
            
            try:
                # Analyze file
                analysis = await self._analyze_file_for_ocr(temp_file_path)
                
                # Generate preview
                preview = {
                    'success': True,
                    'original_size': len(file_data),
                    'estimated_time': self._estimate_ocr_time(analysis, options),
                    'complexity': self._assess_ocr_complexity(analysis, options),
                    'estimated_accuracy': self._estimate_ocr_accuracy(analysis, options),
                    'recommendations': self._get_ocr_recommendations(analysis, options),
                    'supported_formats': self.output_formats,
                    'supported_languages': self.supported_languages
                }
                
                return preview
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"OCR preview failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'original_size': len(file_data)
            }
    
    async def _save_file_data(self, file_data: bytes, filename: str = None) -> str:
        """Save file data to temporary directory"""
        filename = filename or f"temp_{uuid.uuid4().hex[:8]}.pdf"
        safe_filename = self._secure_filename(filename)
        temp_path = os.path.join(self.upload_folder, safe_filename)
        
        with open(temp_path, 'wb') as f:
            f.write(file_data)
        
        return temp_path
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return filename.lower().split('.')[-1] if '.' in filename else ''
    
    def _secure_filename(self, filename: str) -> str:
        """Secure filename for safe file operations"""
        import re
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename.strip('-')
    
    async def _analyze_file_for_ocr(self, file_path: str) -> Dict[str, Any]:
        """Analyze file for OCR optimization"""
        try:
            file_extension = self._get_file_extension(file_path)
            file_size = os.path.getsize(file_path)
            
            analysis = {
                'file_type': file_extension,
                'file_size': file_size,
                'page_count': 1,
                'image_quality': 'medium',
                'ocr_potential': 'medium'
            }
            
            if file_extension == 'pdf':
                pdf_analysis = await self._analyze_pdf_for_ocr(file_path)
                analysis.update(pdf_analysis)
            else:
                image_analysis = await self._analyze_image_for_ocr(file_path)
                analysis.update(image_analysis)
            
            return analysis
            
        except Exception as e:
            logger.warning(f"File analysis failed: {str(e)}")
            return {
                'file_type': file_extension,
                'file_size': os.path.getsize(file_path),
                'page_count': 1,
                'image_quality': 'medium',
                'ocr_potential': 'medium'
            }
    
    async def _analyze_pdf_for_ocr(self, file_path: str) -> Dict[str, Any]:
        """Analyze PDF for OCR optimization"""
        if not PDF_LIBS_AVAILABLE:
            return {'page_count': 1, 'image_quality': 'medium', 'ocr_potential': 'medium'}
        
        try:
            with fitz.open(file_path) as doc:
                page_count = len(doc)
                
                sample_pages = min(3, page_count)
                total_images = 0
                text_content = 0
                
                for page_num in range(sample_pages):
                    page = doc.load_page(page_num)
                    image_list = page.get_images()
                    total_images += len(image_list)
                    
                    text = page.get_text()
                    text_content += len(text.strip())
                
                image_quality = self._assess_image_quality(total_images, page_count)
                ocr_potential = self._assess_ocr_potential(text_content, total_images, page_count)
                
                return {
                    'page_count': page_count,
                    'image_quality': image_quality,
                    'ocr_potential': ocr_potential,
                    'total_images': total_images,
                    'text_content': text_content
                }
                
        except Exception as e:
            logger.warning(f"PDF analysis failed: {str(e)}")
            return {'page_count': 1, 'image_quality': 'medium', 'ocr_potential': 'medium'}
    
    async def _analyze_image_for_ocr(self, file_path: str) -> Dict[str, Any]:
        """Analyze image for OCR optimization"""
        if not OCR_LIBS_AVAILABLE:
            return {'image_quality': 'medium', 'ocr_potential': 'medium'}
        
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                file_size = os.path.getsize(file_path)
                
                image_quality = self._assess_image_quality_by_resolution(width, height, file_size)
                ocr_potential = self._assess_image_ocr_potential(img.format, file_size)
                
                return {
                    'image_quality': image_quality,
                    'ocr_potential': ocr_potential,
                    'width': width,
                    'height': height,
                    'format': img.format
                }
                
        except Exception as e:
            logger.warning(f"Image analysis failed: {str(e)}")
            return {'image_quality': 'medium', 'ocr_potential': 'medium'}
    
    def _assess_image_quality(self, image_count: int, page_count: int) -> str:
        """Assess image quality based on image count and page count"""
        if image_count == 0:
            return 'low'
        elif image_count <= page_count * 2:
            return 'medium'
        else:
            return 'high'
    
    def _assess_image_quality_by_resolution(self, width: int, height: int, file_size: int) -> str:
        """Assess image quality based on resolution and file size"""
        ppi = min(width, height) / 300
        
        if ppi >= 2.0 and file_size > 1024 * 1024:
            return 'high'
        elif ppi >= 1.0 and file_size > 100 * 1024:
            return 'medium'
        else:
            return 'low'
    
    def _assess_ocr_potential(self, text_content: int, image_count: int, page_count: int) -> str:
        """Assess OCR potential based on content analysis"""
        if text_content > 1000:
            return 'low'
        elif image_count > page_count * 3:
            return 'high'
        else:
            return 'medium'
    
    def _assess_image_ocr_potential(self, image_format: str, file_size: int) -> str:
        """Assess OCR potential for image format"""
        good_formats = ['PNG', 'TIFF', 'BMP']
        medium_formats = ['JPEG', 'JPG']
        
        if image_format.upper() in good_formats:
            return 'high'
        elif image_format.upper() in medium_formats:
            return 'medium'
        else:
            return 'low'
    
    async def _process_pdf_ocr(self, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Process OCR on PDF file"""
        if not PDF_LIBS_AVAILABLE:
            raise RuntimeError("PDF processing libraries not available")
        
        try:
            output_format = options.get('outputFormat', 'searchable_pdf')
            language = options.get('language', 'eng')
            quality = options.get('quality', 'balanced')
            
            with fitz.open(file_path) as doc:
                output_doc = fitz.open()
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    mat = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=mat)
                    
                    temp_image_path = os.path.join(self.upload_folder, f"page_{page_num}.png")
                    pix.save(temp_image_path)
                    
                    ocr_text = await self._perform_image_ocr(temp_image_path, language, quality)
                    
                    new_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
                    new_page.show_pdf_page(page.rect, doc, page_num)
                    
                    if ocr_text.strip():
                        text_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
                        new_page.insert_textbox(
                            text_rect,
                            ocr_text,
                            fontsize=1,
                            color=(0, 0, 0, 0)
                        )
                    
                    os.unlink(temp_image_path)
                
                output_filename = f"ocr_{os.path.basename(file_path)}"
                output_path = os.path.join(self.upload_folder, output_filename)
                output_doc.save(output_path)
                output_doc.close()
                
                return {
                    'file_path': output_path,
                    'filename': output_filename,
                    'mime_type': 'application/pdf',
                    'output_format': 'searchable_pdf'
                }
                
        except Exception as e:
            logger.error(f"PDF OCR processing failed: {str(e)}")
            raise
    
    async def _process_image_ocr(self, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Process OCR on image file"""
        if not OCR_LIBS_AVAILABLE:
            raise RuntimeError("OCR libraries not available")
        
        try:
            output_format = options.get('outputFormat', 'text')
            language = options.get('language', 'eng')
            quality = options.get('quality', 'balanced')
            
            ocr_text = await self._perform_image_ocr(file_path, language, quality)
            
            if output_format == 'text':
                return await self._create_text_output(ocr_text, file_path)
            elif output_format == 'json':
                return await self._create_json_output(ocr_text, file_path)
            else:
                return await self._create_text_output(ocr_text, file_path)
                
        except Exception as e:
            logger.error(f"Image OCR processing failed: {str(e)}")
            raise
    
    async def _perform_image_ocr(self, image_path: str, language: str, quality: str) -> str:
        """Perform OCR on image using Tesseract"""
        try:
            config = self._get_tesseract_config(quality)
            
            ocr_text = pytesseract.image_to_string(
                Image.open(image_path),
                lang=language,
                config=config
            )
            
            return ocr_text
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {str(e)}")
            raise
    
    def _get_tesseract_config(self, quality: str) -> str:
        """Get Tesseract configuration based on quality setting"""
        if quality == 'fast':
            return '--oem 1 --psm 6'
        elif quality == 'accurate':
            return '--oem 3 --psm 6'
        else:
            return '--oem 2 --psm 6'
    
    async def _create_text_output(self, ocr_text: str, original_file_path: str) -> Dict[str, Any]:
        """Create text output file"""
        output_filename = f"ocr_{os.path.basename(original_file_path)}.txt"
        output_path = os.path.join(self.upload_folder, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ocr_text)
        
        return {
            'file_path': output_path,
            'filename': output_filename,
            'mime_type': 'text/plain',
            'output_format': 'text'
        }
    
    async def _create_json_output(self, ocr_text: str, original_file_path: str) -> Dict[str, Any]:
        """Create JSON output file"""
        output_filename = f"ocr_{os.path.basename(original_file_path)}.json"
        output_path = os.path.join(self.upload_folder, output_filename)
        
        json_data = {
            'text': ocr_text,
            'word_count': len(ocr_text.split()),
            'character_count': len(ocr_text),
            'lines': ocr_text.split('\n'),
            'metadata': {
                'source_file': os.path.basename(original_file_path),
                'processing_timestamp': datetime.utcnow().isoformat()
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return {
            'file_path': output_path,
            'filename': output_filename,
            'mime_type': 'application/json',
            'output_format': 'json'
        }
    
    def _estimate_ocr_time(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> int:
        """Estimate OCR processing time in seconds"""
        page_count = analysis.get('page_count', 1)
        quality = options.get('quality', 'balanced')
        
        base_time_per_page = 5
        quality_multipliers = {
            'fast': 0.7,
            'balanced': 1.0,
            'accurate': 1.5
        }
        
        multiplier = quality_multipliers.get(quality, 1.0)
        return int(page_count * base_time_per_page * multiplier)
    
    def _assess_ocr_complexity(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Assess OCR complexity"""
        page_count = analysis.get('page_count', 1)
        image_quality = analysis.get('image_quality', 'medium')
        quality = options.get('quality', 'balanced')
        
        complexity_score = 0
        
        if page_count > 50:
            complexity_score += 3
        elif page_count > 20:
            complexity_score += 2
        elif page_count > 10:
            complexity_score += 1
        
        if image_quality == 'low':
            complexity_score += 2
        elif image_quality == 'high':
            complexity_score += 1
        
        if quality == 'accurate':
            complexity_score += 1
        
        if complexity_score >= 4:
            return 'high'
        elif complexity_score >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _estimate_ocr_accuracy(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> float:
        """Estimate OCR accuracy (0.0 to 1.0)"""
        image_quality = analysis.get('image_quality', 'medium')
        quality = options.get('quality', 'balanced')
        
        base_accuracy = 0.8
        quality_adjustments = {
            'high': 0.1,
            'medium': 0.0,
            'low': -0.2
        }
        setting_adjustments = {
            'fast': -0.1,
            'balanced': 0.0,
            'accurate': 0.1
        }
        
        accuracy = base_accuracy
        accuracy += quality_adjustments.get(image_quality, 0.0)
        accuracy += setting_adjustments.get(quality, 0.0)
        
        return max(0.5, min(0.95, accuracy))
    
    def _get_ocr_recommendations(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> list:
        """Get OCR recommendations"""
        recommendations = []
        
        image_quality = analysis.get('image_quality', 'medium')
        quality = options.get('quality', 'balanced')
        page_count = analysis.get('page_count', 1)
        
        if image_quality == 'low' and quality == 'fast':
            recommendations.append("Low image quality detected. Consider using 'accurate' quality setting for better results.")
        
        if page_count > 20 and quality == 'fast':
            recommendations.append("Large document detected. Consider using 'balanced' quality for better accuracy.")
        
        if analysis.get('ocr_potential') == 'low':
            recommendations.append("Document appears to already contain searchable text. OCR may not be necessary.")
        
        return recommendations
    
    async def create_ocr_job(self, file_data: bytes,  job_id: str = None, options: Dict[str, Any] = None,
                           original_filename: str = None) -> Dict[str, Any]:
        """
        Create an OCR job for async processing
        """
        try:
            if job_id is None:
                job_id = str(uuid.uuid4())
            
            # In a real implementation, you'd save this to a database
            job_info = {
                'job_id': job_id,
                'options': options or {},
                'original_filename': original_filename,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Store file data temporarily
            temp_file_path = await self._save_file_data(file_data, f"{job_id}.pdf")
            job_info['temp_file_path'] = temp_file_path
            
            return {
                'success': True,
                'job_id': job_id,
                'status': 'pending',
                'message': 'OCR job created successfully'
            }
            
        except Exception as e:
            logger.error(f"Error creating OCR job: {str(e)}")
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