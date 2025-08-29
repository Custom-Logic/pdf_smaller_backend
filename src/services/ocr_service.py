"""
OCR Service
Handles Optical Character Recognition for scanned PDFs and images
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json
import base64

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
    """Service for performing OCR on PDFs and images"""
    
    def __init__(self):
        self.supported_formats = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp']
        self.supported_languages = [
            'eng', 'spa', 'fra', 'deu', 'ita', 'por', 'rus', 'jpn', 'kor', 'chi_sim', 'ara', 'hin'
        ]
        self.quality_levels = ['fast', 'balanced', 'accurate']
        self.output_formats = ['searchable_pdf', 'text', 'json']
        self.temp_dir = tempfile.mkdtemp(prefix='ocr_processing_')
        
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
            # Set Tesseract configuration
            pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
            
            # Test Tesseract availability
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
            
        except Exception as e:
            logger.warning(f"Tesseract configuration failed: {str(e)}")
            # Try alternative paths
            alternative_paths = [
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
    
    def process_ocr(self, file, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process OCR on uploaded file
        
        Args:
            file: Uploaded file object
            options: OCR options
            
        Returns:
            Dictionary with OCR result
        """
        if not options:
            options = {}
            
        try:
            # Validate file type
            file_extension = self._get_file_extension(file.filename)
            if file_extension not in self.supported_formats:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Process based on file type
            if file_extension == 'pdf':
                result = self._process_pdf_ocr(temp_file_path, options)
            else:
                result = self._process_image_ocr(temp_file_path, options)
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return result
            
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            raise
    
    def get_ocr_preview(self, file, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get OCR preview and estimates
        
        Args:
            file: Uploaded file object
            options: OCR options
            
        Returns:
            Dictionary with preview information
        """
        if not options:
            options = {}
            
        try:
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Analyze file
            analysis = self._analyze_file_for_ocr(temp_file_path)
            
            # Generate preview
            preview = {
                'originalSize': file.content_length or 0,
                'estimatedTime': self._estimate_ocr_time(analysis, options),
                'complexity': self._assess_ocr_complexity(analysis, options),
                'estimatedAccuracy': self._estimate_ocr_accuracy(analysis, options),
                'recommendations': self._get_ocr_recommendations(analysis, options)
            }
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return preview
            
        except Exception as e:
            logger.error(f"OCR preview failed: {str(e)}")
            raise
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return filename.lower().split('.')[-1] if '.' in filename else ''
    
    def _save_uploaded_file(self, file) -> str:
        """Save uploaded file to temporary directory"""
        filename = self._secure_filename(file.filename)
        temp_path = os.path.join(self.temp_dir, filename)
        
        file.save(temp_path)
        return temp_path
    
    def _secure_filename(self, filename: str) -> str:
        """Secure filename for safe file operations"""
        import re
        # Remove or replace unsafe characters
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename.strip('-')
    
    def _analyze_file_for_ocr(self, file_path: str) -> Dict[str, Any]:
        """Analyze file for OCR optimization"""
        try:
            file_extension = self._get_file_extension(file_path)
            file_size = os.path.getsize(file_path)
            
            analysis = {
                'fileType': file_extension,
                'fileSize': file_size,
                'pageCount': 1,
                'imageQuality': 'medium',
                'ocrPotential': 'medium'
            }
            
            if file_extension == 'pdf':
                # Analyze PDF
                pdf_analysis = self._analyze_pdf_for_ocr(file_path)
                analysis.update(pdf_analysis)
            else:
                # Analyze image
                image_analysis = self._analyze_image_for_ocr(file_path)
                analysis.update(image_analysis)
            
            return analysis
            
        except Exception as e:
            logger.warning(f"File analysis failed: {str(e)}")
            return {
                'fileType': file_extension,
                'fileSize': os.path.getsize(file_path),
                'pageCount': 1,
                'imageQuality': 'medium',
                'ocrPotential': 'medium'
            }
    
    def _analyze_pdf_for_ocr(self, file_path: str) -> Dict[str, Any]:
        """Analyze PDF for OCR optimization"""
        if not PDF_LIBS_AVAILABLE:
            return {'pageCount': 1, 'imageQuality': 'medium', 'ocrPotential': 'medium'}
        
        try:
            with fitz.open(file_path) as doc:
                page_count = len(doc)
                
                # Analyze first few pages to assess quality
                sample_pages = min(3, page_count)
                total_images = 0
                text_content = 0
                
                for page_num in range(sample_pages):
                    page = doc.load_page(page_num)
                    
                    # Count images
                    image_list = page.get_images()
                    total_images += len(image_list)
                    
                    # Check text content
                    text = page.get_text()
                    text_content += len(text.strip())
                
                # Assess quality
                image_quality = self._assess_image_quality(total_images, page_count)
                ocr_potential = self._assess_ocr_potential(text_content, total_images, page_count)
                
                return {
                    'pageCount': page_count,
                    'imageQuality': image_quality,
                    'ocrPotential': ocr_potential,
                    'totalImages': total_images,
                    'textContent': text_content
                }
                
        except Exception as e:
            logger.warning(f"PDF analysis failed: {str(e)}")
            return {'pageCount': 1, 'imageQuality': 'medium', 'ocrPotential': 'medium'}
    
    def _analyze_image_for_ocr(self, file_path: str) -> Dict[str, Any]:
        """Analyze image for OCR optimization"""
        if not OCR_LIBS_AVAILABLE:
            return {'imageQuality': 'medium', 'ocrPotential': 'medium'}
        
        try:
            with Image.open(file_path) as img:
                # Get image properties
                width, height = img.size
                file_size = os.path.getsize(file_path)
                
                # Assess quality based on resolution and file size
                image_quality = self._assess_image_quality_by_resolution(width, height, file_size)
                ocr_potential = self._assess_image_ocr_potential(img.format, file_size)
                
                return {
                    'imageQuality': image_quality,
                    'ocrPotential': ocr_potential,
                    'width': width,
                    'height': height,
                    'format': img.format
                }
                
        except Exception as e:
            logger.warning(f"Image analysis failed: {str(e)}")
            return {'imageQuality': 'medium', 'ocrPotential': 'medium'}
    
    def _assess_image_quality(self, image_count: int, page_count: int) -> str:
        """Assess image quality based on image count and page count"""
        if image_count == 0:
            return 'low'  # No images, likely text-based PDF
        elif image_count <= page_count * 2:
            return 'medium'  # Moderate number of images
        else:
            return 'high'  # Many images
    
    def _assess_image_quality_by_resolution(self, width: int, height: int, file_size: int) -> str:
        """Assess image quality based on resolution and file size"""
        # Calculate pixels per inch (assuming 300 DPI for print)
        ppi = min(width, height) / 300
        
        if ppi >= 2.0 and file_size > 1024 * 1024:  # 1MB
            return 'high'
        elif ppi >= 1.0 and file_size > 100 * 1024:  # 100KB
            return 'medium'
        else:
            return 'low'
    
    def _assess_ocr_potential(self, text_content: int, image_count: int, page_count: int) -> str:
        """Assess OCR potential based on content analysis"""
        if text_content > 1000:  # Significant text content
            return 'low'  # Already has text, OCR not needed
        elif image_count > page_count * 3:  # Many images
            return 'high'  # High OCR potential
        else:
            return 'medium'  # Moderate OCR potential
    
    def _assess_image_ocr_potential(self, image_format: str, file_size: int) -> str:
        """Assess OCR potential for image format"""
        # Some formats are better for OCR than others
        good_formats = ['PNG', 'TIFF', 'BMP']
        medium_formats = ['JPEG', 'JPG']
        
        if image_format.upper() in good_formats:
            return 'high'
        elif image_format.upper() in medium_formats:
            return 'medium'
        else:
            return 'low'
    
    def _process_pdf_ocr(self, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Process OCR on PDF file"""
        if not PDF_LIBS_AVAILABLE:
            raise RuntimeError("PDF processing libraries not available")
        
        try:
            # Extract options
            output_format = options.get('outputFormat', 'searchable_pdf')
            language = options.get('language', 'eng')
            quality = options.get('quality', 'balanced')
            
            # Open PDF
            with fitz.open(file_path) as doc:
                # Create output PDF
                output_doc = fitz.open()
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    
                    # Convert page to image for OCR
                    mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Save as temporary image
                    temp_image_path = os.path.join(self.temp_dir, f"page_{page_num}.png")
                    pix.save(temp_image_path)
                    
                    # Perform OCR on image
                    ocr_text = self._perform_image_ocr(temp_image_path, language, quality)
                    
                    # Create new page with OCR text
                    new_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
                    
                    # Add original page content
                    new_page.show_pdf_page(page.rect, doc, page_num)
                    
                    # Add OCR text as invisible layer
                    if ocr_text.strip():
                        text_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
                        new_page.insert_textbox(
                            text_rect,
                            ocr_text,
                            fontsize=1,  # Very small, invisible text
                            color=(0, 0, 0, 0)  # Transparent
                        )
                    
                    # Clean up temp image
                    os.unlink(temp_image_path)
                
                # Save output
                output_filename = f"ocr_{os.path.basename(file_path)}"
                output_path = os.path.join(self.temp_dir, output_filename)
                output_doc.save(output_path)
                output_doc.close()
                
                return {
                    'file_path': output_path,
                    'filename': output_filename,
                    'mime_type': 'application/pdf',
                    'outputFormat': 'searchable_pdf'
                }
                
        except Exception as e:
            logger.error(f"PDF OCR processing failed: {str(e)}")
            raise
    
    def _process_image_ocr(self, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Process OCR on image file"""
        if not OCR_LIBS_AVAILABLE:
            raise RuntimeError("OCR libraries not available")
        
        try:
            # Extract options
            output_format = options.get('outputFormat', 'text')
            language = options.get('language', 'eng')
            quality = options.get('quality', 'balanced')
            
            # Perform OCR
            ocr_text = self._perform_image_ocr(file_path, language, quality)
            
            # Process output based on format
            if output_format == 'text':
                return self._create_text_output(ocr_text, file_path)
            elif output_format == 'json':
                return self._create_json_output(ocr_text, file_path)
            else:
                return self._create_text_output(ocr_text, file_path)
                
        except Exception as e:
            logger.error(f"Image OCR processing failed: {str(e)}")
            raise
    
    def _perform_image_ocr(self, image_path: str, language: str, quality: str) -> str:
        """Perform OCR on image using Tesseract"""
        try:
            # Configure Tesseract based on quality
            config = self._get_tesseract_config(quality)
            
            # Perform OCR
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
            return '--oem 1 --psm 6'  # Fast OCR engine, uniform block of text
        elif quality == 'accurate':
            return '--oem 3 --psm 6'  # Best OCR engine, uniform block of text
        else:  # balanced
            return '--oem 2 --psm 6'  # Default OCR engine, uniform block of text
    
    def _create_text_output(self, ocr_text: str, original_file_path: str) -> Dict[str, Any]:
        """Create text output file"""
        output_filename = f"ocr_{os.path.basename(original_file_path)}.txt"
        output_path = os.path.join(self.temp_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ocr_text)
        
        return {
            'file_path': output_path,
            'filename': output_filename,
            'mime_type': 'text/plain',
            'outputFormat': 'text'
        }
    
    def _create_json_output(self, ocr_text: str, original_file_path: str) -> Dict[str, Any]:
        """Create JSON output file"""
        output_filename = f"ocr_{os.path.basename(original_file_path)}.json"
        output_path = os.path.join(self.temp_dir, output_filename)
        
        # Create structured output
        json_data = {
            'text': ocr_text,
            'word_count': len(ocr_text.split()),
            'character_count': len(ocr_text),
            'lines': ocr_text.split('\n'),
            'metadata': {
                'source_file': os.path.basename(original_file_path),
                'processing_timestamp': str(datetime.utcnow())
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return {
            'file_path': output_path,
            'filename': output_filename,
            'mime_type': 'application/json',
            'outputFormat': 'json'
        }
    
    def _estimate_ocr_time(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> int:
        """Estimate OCR processing time in seconds"""
        page_count = analysis.get('pageCount', 1)
        quality = options.get('quality', 'balanced')
        
        # Base time per page
        base_time_per_page = 5  # 5 seconds per page
        
        # Quality multipliers
        quality_multipliers = {
            'fast': 0.7,
            'balanced': 1.0,
            'accurate': 1.5
        }
        
        multiplier = quality_multipliers.get(quality, 1.0)
        estimated_time = page_count * base_time_per_page * multiplier
        
        return int(estimated_time)
    
    def _assess_ocr_complexity(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Assess OCR complexity"""
        page_count = analysis.get('pageCount', 1)
        image_quality = analysis.get('imageQuality', 'medium')
        quality = options.get('quality', 'balanced')
        
        complexity_score = 0
        
        # Page count factor
        if page_count > 50:
            complexity_score += 3
        elif page_count > 20:
            complexity_score += 2
        elif page_count > 10:
            complexity_score += 1
        
        # Image quality factor
        if image_quality == 'low':
            complexity_score += 2
        elif image_quality == 'high':
            complexity_score += 1
        
        # Quality setting factor
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
        image_quality = analysis.get('imageQuality', 'medium')
        quality = options.get('quality', 'balanced')
        
        base_accuracy = 0.8
        
        # Adjust based on image quality
        quality_adjustments = {
            'high': 0.1,
            'medium': 0.0,
            'low': -0.2
        }
        
        # Adjust based on quality setting
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
        
        image_quality = analysis.get('imageQuality', 'medium')
        quality = options.get('quality', 'balanced')
        page_count = analysis.get('pageCount', 1)
        
        if image_quality == 'low' and quality == 'fast':
            recommendations.append("Low image quality detected. Consider using 'accurate' quality setting for better results.")
        
        if page_count > 20 and quality == 'fast':
            recommendations.append("Large document detected. Consider using 'balanced' quality for better accuracy.")
        
        if analysis.get('ocrPotential') == 'low':
            recommendations.append("Document appears to already contain searchable text. OCR may not be necessary.")
        
        return recommendations
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {str(e)}")

# Import datetime for timestamp
from datetime import datetime
