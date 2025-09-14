import logging
import os
import subprocess
import tempfile
import uuid
from typing import Dict, Any, Optional

from src.models.job import TaskType
from src.jobs import JobOperationsWrapper
from src.models import Job, JobStatus
from src.services.file_management_service import FileManagementService

logger = logging.getLogger(__name__)

class CompressionService:
    GHOSTSCRIPT_BINARY = "/usr/bin/gs"  # Absolute path to Ghostscript

    def __init__(self, file_service: Optional[FileManagementService] = None):
        self.file_service = file_service or FileManagementService()
        self._service_available = os.path.exists(self.GHOSTSCRIPT_BINARY)
        # Verify Ghostscript exists at startup

    def process_file_data(self, file_data: bytes, settings: Dict[str, Any], original_filename: str = None) -> Dict[str, Any]:
        """Process file data and save result to persistent location"""
        temp_input_path = None
        temp_output_path = None
        
        try:
            # Save input file using file service
            input_filename = original_filename or 'input.pdf'
            file_id, temp_input_path = self.file_service.save_file(file_data, input_filename)
            
            original_size = len(file_data)
            compression_level = settings.get('compression_level', 'medium')
            image_quality = settings.get('image_quality', 80)
            
            # Create temporary output file for compression
            job_id = str(uuid.uuid4())
            output_filename = f"compressed_{job_id}_{original_filename or 'file.pdf'}"
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_output:
                temp_output_path = tmp_output.name
            
            # Compress PDF
            self.compress_pdf(temp_input_path, temp_output_path, compression_level, image_quality)
            
            # Read compressed data and save through file service
            with open(temp_output_path, 'rb') as f:
                compressed_data = f.read()
            
            compressed_file_id, output_path = self.file_service.save_file(compressed_data, output_filename)
            compressed_size = self.file_service.get_file_size(output_path)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100
            
            return {
                'success': True,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'compression_level': compression_level,
                'image_quality': image_quality,
                'original_filename': original_filename,
                'output_path': output_path,  # Persistent path
                'mime_type': 'application/pdf'
            }
                
        except Exception as e:
            logger.error(f"Error processing file data: {str(e)}")
            raise
        finally:
            # Clean up temporary files
            if temp_input_path:
                self.file_service.delete_file(temp_input_path)
            if temp_output_path and os.path.exists(temp_output_path):
                os.unlink(temp_output_path)

    def compress_pdf(self, input_path: str, output_path: str, compression_level: str = 'medium', image_quality: int = 80) -> bool:
        """
        Compress PDF using Ghostscript with advanced options
        """
        compression_settings = {
            'low': '/prepress',
            'medium': '/default',
            'high': '/ebook',
            'maximum': '/screen'
        }
        if not self._service_available:
            raise EnvironmentError("Ghost Script not available")

        gs_setting = compression_settings.get(compression_level, '/default')

        try:
            command = [
                self.GHOSTSCRIPT_BINARY,
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.4',
                f'-dPDFSETTINGS={gs_setting}',
                f'-dColorImageDownsampleType=/Bicubic',
                f'-dColorImageResolution={image_quality}',
                f'-dGrayImageDownsampleType=/Bicubic',
                f'-dGrayImageResolution={image_quality}',
                f'-dMonoImageDownsampleType=/Bicubic',
                f'-dMonoImageResolution={image_quality}',
                '-dEmbedAllFonts=true',
                '-dSubsetFonts=true',
                '-dAutoRotatePages=/None',
                '-dColorConversionStrategy=/sRGB',
                '-dProcessColorModel=/DeviceRGB',
                '-dConvertCMYKImagesToRGB=true',
                '-dDetectDuplicateImages=true',
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dUseCIEColor=true',
                '-dNOPAUSE',
                '-dQUIET',
                '-dBATCH',
                f'-sOutputFile={output_path}',
                input_path
            ]

            logger.info(f"Executing Ghostscript command: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"Ghostscript error: {result.stderr}")
                raise Exception(f"Ghostscript failed: {result.stderr}")

            if not os.path.exists(output_path) or self.file_service.get_file_size(output_path) == 0:
                raise Exception("Compression failed: Output file is empty or doesn't exist")

            return True

        except subprocess.TimeoutExpired:
            logger.error("Ghostscript command timed out")
            raise Exception("Compression process timed out")
        except Exception as e:
            logger.error(f"Error during compression: {str(e)}")
            raise

    @staticmethod
    def create_compression_job(file_data: bytes, settings: Dict[str, Any],
                               original_filename: str = None, job_id: str = None) -> Job:
        """
        Create a compression job record for async processing using JobOperationsWrapper
        """
        try:
            job = JobOperationsWrapper.create_job_safely(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={
                    'settings': settings,
                    'file_size': len(file_data),
                    'original_filename': original_filename
                }
            )
            
            logger.info(f"Created compression job {job.job_id} (client_job_id: {job_id})")
            return job
            
        except Exception as e:
            logger.error(f"Error creating compression job: {str(e)}")
            raise

    def process_compression_job(self, job_id: str) -> Dict[str, Any]:
        """
        Process a compression job synchronously
        """
        try:
            job = Job.query().filter_by(job_id=job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            if not job.task_type_is_compression:
                raise ValueError(f"Job {job_id} is not a compression job")

            # Update job status using JobOperationsWrapper
            JobOperationsWrapper.update_job_status_safely(job_id=job_id, status=JobStatus.PROCESSING)

            # Get job data
            input_data = job.input_data
            settings = input_data.get('settings', {})
            file_size = input_data.get('file_size', 0)
            original_filename = input_data.get('original_filename')

            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # For demonstration - in real implementation, file_data would be passed
                # or retrieved from a temporary storage
                input_path = os.path.join(temp_dir, f"input_{job_id}.pdf")
                output_path = os.path.join(temp_dir, f"compressed_{job_id}.pdf")

                # Extract compression settings
                compression_level = settings.get('compression_level', 'medium')
                image_quality = settings.get('image_quality', 80)

                # Perform compression (in real implementation, use actual file_data)
                self.compress_pdf(input_path, output_path, compression_level, image_quality)

                # Get compressed size
                compressed_size = self.file_service.get_file_size(output_path)

                # Calculate compression ratio
                compression_ratio = ((file_size - compressed_size) / file_size) * 100
                result = {
                    'original_size': file_size,
                    'compressed_size': compressed_size,
                    'compression_ratio': compression_ratio,
                    'compression_level': compression_level,
                    'image_quality': image_quality,
                    'original_filename': original_filename,
                    'output_path': output_path
                }
                # Update job with results                
                JobOperationsWrapper.update_job_status_safely(job_id=job_id, status=JobStatus.COMPLETED, result=result)

                return job.result

        except Exception as e:
            if 'job' in locals():
                JobOperationsWrapper.update_job_status_safely(job_id, JobStatus.FAILED, error_message=str(e))

            logger.error(f"Error processing compression job {job_id}: {str(e)}")
            raise

    @staticmethod
    def get_compression_preview(file_data: bytes, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate compression preview without actual processing
        """
        try:
            # Analyze file for preview (simple size-based estimation)
            original_size = len(file_data)
            
            # Estimate compression based on settings
            compression_level = settings.get('compression_level', 'medium')
            image_quality = settings.get('image_quality', 80)
            
            # Simple estimation logic (can be enhanced with ML)
            compression_ratios = {
                'low': 0.2,    # 20% reduction
                'medium': 0.4, # 40% reduction
                'high': 0.6,   # 60% reduction
                'maximum': 0.8 # 80% reduction
            }
            
            ratio = compression_ratios.get(compression_level, 0.4)
            # Adjust based on image quality
            quality_factor = image_quality / 100.0
            ratio *= (1.0 - (1.0 - quality_factor) * 0.3)  # Adjust ratio based on quality
            
            estimated_size = int(original_size * (1 - ratio))
            
            return {
                'original_size': original_size,
                'estimated_size': estimated_size,
                'estimated_ratio': ratio * 100,
                'compression_level': compression_level,
                'image_quality': image_quality,
                'quality_adjustment': quality_factor
            }
            
        except Exception as e:
            logger.error(f"Error generating compression preview: {str(e)}")
            raise

    def analyze_pdf_content(self, file_data: bytes) -> Dict[str, Any]:
        """
        Analyze PDF content for compression potential
        :param file_data:
        :return:
        """
        try:
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name
            
            try:
                # Use pdfinfo to analyze PDF
                result = subprocess.run(
                    ['pdfinfo', tmp_path],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode != 0:
                    return {
                        'success': False,
                        'error': 'Failed to analyze PDF',
                        'analysis': {}
                    }
                
                # Parse pdfinfo output
                info = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                
                # Extract useful information
                page_count = int(info.get('Pages', 0))
                file_size = len(file_data)
                
                # Simple analysis (can be enhanced)
                analysis = {
                    'page_count': page_count,
                    'file_size': file_size,
                    'file_size_mb': file_size / (1024 * 1024),
                    'pages_per_mb': page_count / (file_size / (1024 * 1024)) if file_size > 0 else 0,
                    'compression_potential': self._estimate_compression_potential(info, file_data),
                    'document_type': self._classify_document_type(info),
                    'metadata': info
                }
                
                return {
                    'success': True,
                    'analysis': analysis
                }
                
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.error(f"Error analyzing PDF content: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'analysis': {}
            }

    @staticmethod
    def _estimate_compression_potential(pdfinfo: Dict[str, str], file_data: bytes) -> float:
        """
        Estimate compression potential based on PDF metadata
        """
        # Simple heuristic-based estimation
        potential = 0.3  # Base potential

        # Adjust based on file size (larger files have more potential)
        file_size_mb = len(file_data) / (1024 * 1024)
        if file_size_mb > 10:
            potential += 0.2
        elif file_size_mb > 5:
            potential += 0.1

        # Adjust based on page count (more pages = more potential)
        page_count = int(pdfinfo.get('Pages', 1))
        if page_count > 20:
            potential += 0.2
        elif page_count > 10:
            potential += 0.1

        # Cap at 0.8 (80% potential)
        return min(potential, 0.8)

    @staticmethod
    def _classify_document_type(pdfinfo: Dict[str, str]) -> str:
        """
        Classify document type based on PDF metadata
        """
        # Simple classification based on metadata
        title = pdfinfo.get('Title', '').lower()
        creator = pdfinfo.get('Creator', '').lower()
        
        if any(word in title + creator for word in ['scan', 'scanner', 'tiff', 'jpeg']):
            return 'scanned_document'
        elif any(word in creator for word in ['word', 'office', 'libreoffice']):
            return 'office_document'
        elif any(word in creator for word in ['latex', 'tex']):
            return 'academic_document'
        elif any(word in title for word in ['invoice', 'receipt', 'bill']):
            return 'business_document'
        else:
            return 'general_document'

    @staticmethod
    def cleanup_job_files(job: Job) -> bool:
        """
        Clean up files associated with a compression job
        """
        try:
            # Clean up result files
            if job.result and 'output_path' in job.result:
                output_path = job.result['output_path']
                if os.path.exists(output_path):
                    os.unlink(output_path)
                    logger.debug(f"Cleaned up output file: {output_path}")
            
            # Clean up any temporary files in input data
            if job.input_data and 'temp_files' in job.input_data:
                for temp_file in job.input_data['temp_files']:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                        logger.debug(f"Cleaned up temp file: {temp_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up job files for job {job.job_id}: {str(e)}")
            return False

    @staticmethod
    def get_recommended_settings(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get recommended compression settings based on analysis
        """
        doc_type = analysis.get('document_type', 'general_document')
        file_size_mb = analysis.get('file_size_mb', 0)
        compression_potential = analysis.get('compression_potential', 0.3)
        
        recommendations = {
            'scanned_document': {
                'compression_level': 'high',
                'image_quality': 75,
                'recommendation': 'High compression recommended for scanned documents'
            },
            'office_document': {
                'compression_level': 'medium',
                'image_quality': 85,
                'recommendation': 'Medium compression for Office documents'
            },
            'academic_document': {
                'compression_level': 'low',
                'image_quality': 90,
                'recommendation': 'Light compression to preserve academic content'
            },
            'business_document': {
                'compression_level': 'medium',
                'image_quality': 80,
                'recommendation': 'Medium compression for business documents'
            },
            'general_document': {
                'compression_level': 'medium',
                'image_quality': 85,
                'recommendation': 'Standard compression settings'
            }
        }
        
        base_settings = recommendations.get(doc_type, recommendations['general_document'])
        
        # Adjust based on file size
        if file_size_mb > 20:
            base_settings['compression_level'] = 'high'
            base_settings['image_quality'] = max(70, base_settings['image_quality'] - 10)
        elif file_size_mb < 1:
            base_settings['compression_level'] = 'low'
            base_settings['image_quality'] = min(95, base_settings['image_quality'] + 5)
        
        # Adjust based on compression potential
        if compression_potential > 0.6:
            base_settings['compression_level'] = 'high'
        elif compression_potential < 0.4:
            base_settings['compression_level'] = 'low'
        
        return base_settings