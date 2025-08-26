import os
import subprocess
import tempfile
import logging
from pathlib import Path
from src.utils import secure_filename, cleanup_old_files

logger = logging.getLogger(__name__)

class CompressionService:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
    
    def compress_pdf(self, input_path, output_path, compression_level='medium', image_quality=80):
        """
        Compress PDF using Ghostscript with advanced options
        """
        compression_settings = {
            'low': '/prepress',
            'medium': '/default', 
            'high': '/ebook',
            'maximum': '/screen'
        }
        
        gs_setting = compression_settings.get(compression_level, '/default')
        
        try:
            # Advanced Ghostscript command with more optimization options
            command = [
                'gs',
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
            
            # Execute the command with timeout
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Ghostscript error: {result.stderr}")
                raise Exception(f"Ghostscript failed: {result.stderr}")
            
            # Verify output file exists and is valid
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception("Compression failed: Output file is empty or doesn't exist")
                
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Ghostscript command timed out")
            raise Exception("Compression process timed out")
        except Exception as e:
            logger.error(f"Error during compression: {str(e)}")
            raise
    
    def process_upload(self, file, compression_level='medium', image_quality=80):
        """
        Process an uploaded file and return the path to the compressed version
        """
        # Secure filename and create paths
        filename = secure_filename(file.filename)
        input_path = os.path.join(self.upload_folder, f"input_{filename}")
        output_path = os.path.join(self.upload_folder, f"compressed_{filename}")
        
        try:
            # Save uploaded file
            file.save(input_path)
            
            # Compress the PDF
            self.compress_pdf(input_path, output_path, compression_level, image_quality)
            
            # Clean up old files
            cleanup_old_files(self.upload_folder, max_age_hours=1)
            
            return output_path
            
        except Exception as e:
            # Clean up on error
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise
