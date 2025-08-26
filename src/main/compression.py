import os
import subprocess
import tempfile
import logging
from pathlib import Path
from src.utils import secure_filename, cleanup_old_files

logger = logging.getLogger(__name__)


class CompressionService:
    GHOSTSCRIPT_BINARY = "/usr/bin/gs"  # Absolute path to Ghostscript

    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
        # Verify Ghostscript exists at startup
        if not os.path.exists(self.GHOSTSCRIPT_BINARY):
            raise EnvironmentError(f"Ghostscript binary not found at {self.GHOSTSCRIPT_BINARY}")

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
        filename = secure_filename(file.filename)
        input_path = os.path.join(self.upload_folder, f"input_{filename}")
        output_path = os.path.join(self.upload_folder, f"compressed_{filename}")

        try:
            file.save(input_path)
            self.compress_pdf(input_path, output_path, compression_level, image_quality)
            cleanup_old_files(self.upload_folder, max_age_hours=1)
            return output_path
        except Exception as e:
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.remove(path)
            logger.error(f"Compression service error: {str(e)}")
            raise
