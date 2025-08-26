import subprocess

from flask import Blueprint, request, send_file, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.main.compression import CompressionService

import os
import logging

from src.utils import validate_file
from flask_cors import CORS
logger = logging.getLogger(__name__)

compression_bp = Blueprint('compression', __name__)
CORS(compression_bp, resources={r"/compress": {"origins": ["https://www.pdfsmaller.site"]}})
# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

# Initialize compression service
compression_service = CompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))

@compression_bp.route('/compress', methods=['POST'])
@limiter.limit("10 per minute")
def compress_pdf():
    """Endpoint for PDF compression"""
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    validation_error = validate_file(file)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    # Get compression parameters
    compression_level = request.form.get('compressionLevel', 'medium')
    image_quality = int(request.form.get('imageQuality', 80))
    
    try:
        # Process the file
        output_path = compression_service.process_upload(
            file, compression_level, image_quality
        )
        
        # Return the compressed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"compressed_{file.filename}",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return jsonify({'error': f'Failed to compress PDF: {str(e)}'}), 500

@compression_bp.route('/info', methods=['POST'])
def get_pdf_info():
    """Get information about a PDF file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    validation_error = validate_file(file)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    try:
        # Save file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            file.save(tmp.name)
            
            # Use pdfinfo to get information
            result = subprocess.run(
                ['pdfinfo', tmp.name],
                capture_output=True, text=True
            )
            
            # Parse pdfinfo output
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            
            # Clean up
            os.unlink(tmp.name)
            
            return jsonify(info)
            
    except Exception as e:
        logger.error(f"Error getting PDF info: {str(e)}")
        return jsonify({'error': f'Failed to get PDF information: {str(e)}'}), 500
