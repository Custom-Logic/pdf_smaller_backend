import logging
import os
import subprocess
import tempfile
from typing import Dict, Any, Optional

from src.models import TaskType, JobStatus, Job
from src.jobs import job_operations_wrapper, job_operations
from src.services.file_management_service import FileManagementService

logger = logging.getLogger(__name__)


class CompressionService:
    GHOSTSCRIPT_BINARY = "/usr/bin/gs"

    def __init__(self, file_service: Optional[FileManagementService] = None):
        self.file_service = file_service or FileManagementService()
        self._service_available = os.path.exists(self.GHOSTSCRIPT_BINARY)
        if not self._service_available:
            logger.warning(f"Ghostscript not found at {self.GHOSTSCRIPT_BINARY}")

    # Fix for compression_service.py - remove job retrieval check

    def process_file_data(self, file_data: bytes, settings: Dict[str, Any],
                          original_filename: str = None, job_id: str = None) -> Dict[str, Any]:
        """Process file data through compression pipeline with proper job management"""
        temp_input_path = None
        temp_output_path = None

        try:
            # Job should already exist and be managed by the caller
            # No need to retrieve or validate job existence here

            if job_id:
                logger.debug(f"Processing compression for job {job_id}")

            # Save input file using file service
            file_id, input_file_path = self.file_service.save_file(
                file_data, original_filename or 'input.pdf'
            )
            logger.debug(f"Saved input file: {input_file_path}")

            original_size = len(file_data)
            compression_level = settings.get('compression_level', 'medium')
            image_quality = settings.get('image_quality', 80)
            output_filename = f"compressed_{file_id}.pdf"
            output_path = self.file_service.create_output_path(output_filename)
            logger.debug(f"Output path: {output_path}")

            # Perform compression
            self._execute_compression(
                input_path=input_file_path,
                output_path=output_path,
                compression_level=compression_level,
                image_quality=image_quality
            )
            logger.debug("Compression completed")

            compressed_size = self.file_service.get_file_size(output_path)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100

            result = {
                'success': True,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'compression_level': compression_level,
                'image_quality': image_quality,
                'original_filename': original_filename,
                'output_path': output_path,
                'mime_type': 'application/pdf',
                'input_file_id': file_id,
                'output_file_id': file_id
            }
            logger.debug(f"Compression result: {result}")

            return result

        except Exception as e:
            # Let the caller handle job status updates
            logger.error(f"Error processing file data: {str(e)}")
            raise
        finally:
            pass

    def _execute_compression(self, input_path: str, output_path: str,
                             compression_level: str, image_quality: int) -> None:
        """Execute Ghostscript compression with proper error handling"""
        compression_settings = {
            'low': '/prepress',
            'medium': '/default',
            'high': '/ebook',
            'maximum': '/screen'
        }

        if not self._service_available:
            raise EnvironmentError("Ghostscript not available")

        # Verify input file exists
        if not self.file_service.file_exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        gs_setting = compression_settings.get(compression_level, '/default')

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

        logger.info(f"Executing Ghostscript compression with level {compression_level}")
        # Running Compression
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            logger.error(f"Ghostscript error: {result.stderr}")
            raise Exception(f"Ghostscript failed: {result.stderr}")

        # Verify output file
        if not self.file_service.file_exists(output_path) or self.file_service.get_file_size(output_path) == 0:
            raise Exception("Compression failed: Output file is empty or doesn't exist")

    def process_compression_job(self, job_id: str, file_data: bytes) -> Dict[str, Any]:
        """
        Process a compression job with provided file data
        """
        try:
            # Get job information
            job_info = job_operations_wrapper.get_job_with_progress(job_id)
            if not job_info:
                raise ValueError(f"Job {job_id} not found")

            # Update job status to processing
            job_operations_wrapper.update_job_status_safely(
                job_id=job_id,
                status=JobStatus.PROCESSING
            )

            # Get full job details through job_operations_wrapper
            # Since we need input_data, we'll use a direct approach for now
            # In production, you'd extend job_operations_wrapper to include input_data
            job = job_operations.get_job(job_id=job_id)
            if not isinstance(job, Job):
                raise ValueError(f"Job {job_id} not found")

            input_data = job.input_data or {}
            settings = input_data.get('settings', {})
            original_filename = input_data.get('original_filename')

            # Process the file data
            result = self.process_file_data(
                file_data=file_data,
                settings=settings,
                original_filename=original_filename,
                job_id=job_id
            )

            return result

        except Exception as e:
            job_operations_wrapper.update_job_status_safely(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=str(e)
            )
            logger.error(f"Error processing compression job {job_id}: {str(e)}")
            raise

    def create_compression_job(self, file_data: bytes, settings: Dict[str, Any],
                               original_filename: str = None, job_id: str = None) -> str:
        """
        Create a compression job and return job ID
        """
        try:
            job = job_operations_wrapper.create_job_safely(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={
                    'settings': settings,
                    'file_size': len(file_data),
                    'original_filename': original_filename,
                    'file_data_present': False  # Data will be provided separately
                }
            )

            if not isinstance(job, Job):
                raise Exception("Failed to create compression job")

            logger.info(f"Created compression job {job.job_id}")
            return job.job_id

        except Exception as e:
            logger.error(f"Error creating compression job: {str(e)}")
            raise

    @staticmethod
    def get_compression_preview(file_data: bytes, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate compression preview without actual processing
        """
        try:
            original_size = len(file_data)
            compression_level = settings.get('compression_level', 'medium')
            image_quality = settings.get('image_quality', 80)

            compression_ratios = {
                'low': 0.2,  # 20% reduction
                'medium': 0.4,  # 40% reduction
                'high': 0.6,  # 60% reduction
                'maximum': 0.8  # 80% reduction
            }

            ratio = compression_ratios.get(compression_level, 0.4)
            quality_factor = image_quality / 100.0
            ratio *= (1.0 - (1.0 - quality_factor) * 0.3)

            estimated_size = int(original_size * (1 - ratio))

            return {
                'original_size': original_size,
                'estimated_size': estimated_size,
                'estimated_ratio': ratio * 100,
                'compression_level': compression_level,
                'image_quality': image_quality
            }

        except Exception as e:
            logger.error(f"Error generating compression preview: {str(e)}")
            raise

    def analyze_pdf_content(self, file_data: bytes) -> Dict[str, Any]:
        """
        Analyze PDF content for compression potential using FileManagementService
        """
        temp_file_path = None

        try:
            # Create temporary file using FileManagementService
            file_id, temp_file_path = self.file_service.save_file(file_data, "analysis_temp.pdf")

            # Use pdfinfo to analyze PDF
            result = subprocess.run(
                ['pdfinfo', temp_file_path],
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

        except Exception as e:
            logger.error(f"Error analyzing PDF content: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'analysis': {}
            }
        finally:
            # Clean up temporary file
            if temp_file_path and self.file_service.file_exists(temp_file_path):
                self.file_service.delete_file(temp_file_path)

    @staticmethod
    def _estimate_compression_potential(pdfinfo: Dict[str, str], file_data: bytes) -> float:
        """Estimate compression potential based on PDF metadata"""
        potential = 0.3
        file_size_mb = len(file_data) / (1024 * 1024)

        if file_size_mb > 10:
            potential += 0.2
        elif file_size_mb > 5:
            potential += 0.1

        page_count = int(pdfinfo.get('Pages', 1))
        if page_count > 20:
            potential += 0.2
        elif page_count > 10:
            potential += 0.1

        return min(potential, 0.8)

    @staticmethod
    def _classify_document_type(pdfinfo: Dict[str, str]) -> str:
        """Classify document type based on PDF metadata"""
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

    def cleanup_job_files(self, job_id: str) -> bool:
        """
        Clean up files associated with a compression job using FileManagementService
        """
        try:
            # Get job information
            job_info = job_operations_wrapper.get_job_with_progress(job_id)
            if not job_info:
                logger.warning(f"Job {job_id} not found for cleanup")
                return False

            # Get full job details for file paths
            from src.models.job import Job
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                return False

            files_cleaned = 0

            # Clean up result files
            if job.result and isinstance(job.result, dict):
                for path_key in ['output_path', 'result_path', 'file_path']:
                    if path_key in job.result and job.result[path_key]:
                        file_path = job.result[path_key]
                        if self.file_service.delete_file(file_path):
                            files_cleaned += 1
                            logger.debug(f"Cleaned up {path_key}: {file_path}")

            logger.info(f"Cleaned up {files_cleaned} files for job {job_id}")
            return files_cleaned > 0

        except Exception as e:
            logger.error(f"Error cleaning up job files for job {job_id}: {str(e)}")
            return False