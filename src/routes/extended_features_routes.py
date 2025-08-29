"""
Extended Features Routes
Handles conversion, OCR, AI, and cloud integration endpoints
"""

from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import tempfile
import json
from datetime import datetime
import logging

# Import services
from ..services.conversion_service import ConversionService
from ..services.ocr_service import OCRService
from ..services.ai_service import AIService
from ..services.cloud_integration_service import CloudIntegrationService

# Import utilities
from ..utils.file_validator import validate_file_type, validate_file_size
from ..utils.response_helpers import success_response, error_response
from ..utils.auth_decorators import require_auth, optional_auth

# Initialize blueprint
extended_features_bp = Blueprint('extended_features', __name__, url_prefix='/api/v1')

# Initialize services
conversion_service = ConversionService()
ocr_service = OCRService()
ai_service = AIService()
cloud_service = CloudIntegrationService()

# Configure logging
logger = logging.getLogger(__name__)

# File upload configuration
ALLOWED_EXTENSIONS = {
    'conversion': {'pdf'},
    'ocr': {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'},
    'ai': {'pdf'}
}

MAX_FILE_SIZES = {
    'conversion': 100 * 1024 * 1024,  # 100MB
    'ocr': 50 * 1024 * 1024,          # 50MB
    'ai': 25 * 1024 * 1024            # 25MB
}

def allowed_file(filename, feature_type):
    """Check if file extension is allowed for the feature"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(feature_type, set())

# ============================================================================
# CONVERSION ROUTES
# ============================================================================

@extended_features_bp.route('/convert/pdf-to-<format>', methods=['POST'])
@optional_auth
def convert_pdf(format):
    """Convert PDF to specified format"""
    try:
        # Validate format
        supported_formats = ['docx', 'xlsx', 'txt', 'html']
        if format not in supported_formats:
            return error_response(f"Unsupported format: {format}", 400)
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("No file selected", 400)
        
        # Validate file
        if not allowed_file(file.filename, 'conversion'):
            return error_response("Invalid file type. Only PDF files are supported.", 400)
        
        if file.content_length and file.content_length > MAX_FILE_SIZES['conversion']:
            return error_response("File too large. Maximum size is 100MB.", 400)
        
        # Get conversion options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Process conversion
        result = conversion_service.convert_pdf(file, format, options)
        
        # Return converted file
        return send_file(
            result['file_path'],
            as_attachment=True,
            download_name=result['filename'],
            mimetype=result['mime_type']
        )
        
    except Exception as e:
        logger.error(f"PDF conversion failed: {str(e)}")
        return error_response(f"Conversion failed: {str(e)}", 500)

@extended_features_bp.route('/convert/preview', methods=['POST'])
@optional_auth
def get_conversion_preview():
    """Get conversion preview and estimates"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        format = request.form.get('format', 'docx')
        options = {}
        
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Get preview
        preview = conversion_service.get_conversion_preview(file, format, options)
        return success_response("Preview generated successfully", preview)
        
    except Exception as e:
        logger.error(f"Conversion preview failed: {str(e)}")
        return error_response(f"Preview generation failed: {str(e)}", 500)

# ============================================================================
# OCR ROUTES
# ============================================================================

@extended_features_bp.route('/ocr/process', methods=['POST'])
@optional_auth
def process_ocr():
    """Process OCR on uploaded file"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("No file selected", 400)
        
        # Validate file
        if not allowed_file(file.filename, 'ocr'):
            return error_response("Invalid file type for OCR processing.", 400)
        
        if file.content_length and file.content_length > MAX_FILE_SIZES['ocr']:
            return error_response("File too large. Maximum size is 50MB.", 400)
        
        # Get OCR options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Process OCR
        result = ocr_service.process_ocr(file, options)
        
        # Return processed file
        return send_file(
            result['file_path'],
            as_attachment=True,
            download_name=result['filename'],
            mimetype=result['mime_type']
        )
        
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        return error_response(f"OCR processing failed: {str(e)}", 500)

@extended_features_bp.route('/ocr/preview', methods=['POST'])
@optional_auth
def get_ocr_preview():
    """Get OCR preview and estimates"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        options = {}
        
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Get preview
        preview = ocr_service.get_ocr_preview(file, options)
        return success_response("OCR preview generated successfully", preview)
        
    except Exception as e:
        logger.error(f"OCR preview failed: {str(e)}")
        return error_response(f"OCR preview generation failed: {str(e)}", 500)

# ============================================================================
# AI ROUTES
# ============================================================================

@extended_features_bp.route('/ai/summarize', methods=['POST'])
@optional_auth
def summarize_pdf():
    """Summarize PDF content using AI"""
    try:
        # Get text content from request
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response("No text content provided", 400)
        
        text = data['text']
        options = data.get('options', {})
        
        # Validate text length
        if len(text) > 100000:  # 100KB limit
            return error_response("Text too long. Maximum length is 100KB.", 400)
        
        # Process summarization
        result = ai_service.summarize_text(text, options)
        return success_response("Summarization completed successfully", result)
        
    except Exception as e:
        logger.error(f"AI summarization failed: {str(e)}")
        return error_response(f"Summarization failed: {str(e)}", 500)

@extended_features_bp.route('/ai/translate', methods=['POST'])
@optional_auth
def translate_text():
    """Translate text using AI"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response("No text content provided", 400)
        
        text = data['text']
        target_language = data.get('target_language', 'en')
        options = data.get('options', {})
        
        # Validate text length
        if len(text) > 100000:  # 100KB limit
            return error_response("Text too long. Maximum length is 100KB.", 400)
        
        # Process translation
        result = ai_service.translate_text(text, target_language, options)
        return success_response("Translation completed successfully", result)
        
    except Exception as e:
        logger.error(f"AI translation failed: {str(e)}")
        return error_response(f"Translation failed: {str(e)}", 500)

# ============================================================================
# CLOUD INTEGRATION ROUTES
# ============================================================================

@extended_features_bp.route('/cloud/<provider>/token', methods=['POST'])
@require_auth
def exchange_cloud_token(provider):
    """Exchange authorization code for access token"""
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return error_response("No authorization code provided", 400)
        
        code = data['code']
        redirect_uri = data.get('redirect_uri')
        
        # Exchange code for token
        result = cloud_service.exchange_code_for_token(provider, code, redirect_uri)
        return success_response("Token exchange successful", result)
        
    except Exception as e:
        logger.error(f"Cloud token exchange failed: {str(e)}")
        return error_response(f"Token exchange failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/validate', methods=['GET'])
@require_auth
def validate_cloud_token(provider):
    """Validate cloud provider access token"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Validate token
        is_valid = cloud_service.validate_token(provider, token)
        
        if is_valid:
            return success_response("Token is valid", {'valid': True})
        else:
            return error_response("Token is invalid", 401)
            
    except Exception as e:
        logger.error(f"Cloud token validation failed: {str(e)}")
        return error_response(f"Token validation failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/upload', methods=['POST'])
@require_auth
def upload_to_cloud(provider):
    """Upload file to cloud storage"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        destination_path = request.form.get('destination_path', '/')
        options = {}
        
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Upload to cloud
        result = cloud_service.upload_file(provider, token, file, destination_path, options)
        return success_response("File uploaded successfully", result)
        
    except Exception as e:
        logger.error(f"Cloud upload failed: {str(e)}")
        return error_response(f"Upload failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/download', methods=['GET'])
@require_auth
def download_from_cloud(provider):
    """Download file from cloud storage"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Get parameters
        file_path = request.args.get('file_path')
        if not file_path:
            return error_response("No file path provided", 400)
        
        options = {}
        if 'options' in request.args:
            try:
                options = json.loads(request.args['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Download from cloud
        result = cloud_service.download_file(provider, token, file_path, options)
        
        # Return file
        return send_file(
            result['file_path'],
            as_attachment=True,
            download_name=result['filename'],
            mimetype=result['mime_type']
        )
        
    except Exception as e:
        logger.error(f"Cloud download failed: {str(e)}")
        return error_response(f"Download failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/list', methods=['GET'])
@require_auth
def list_cloud_files(provider):
    """List files in cloud storage"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Get parameters
        folder_path = request.args.get('folder_path', '/')
        options = {}
        
        if 'options' in request.args:
            try:
                options = json.loads(request.args['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # List files
        result = cloud_service.list_files(provider, token, folder_path, options)
        return success_response("Files listed successfully", result)
        
    except Exception as e:
        logger.error(f"Cloud file listing failed: {str(e)}")
        return error_response(f"File listing failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/folder', methods=['POST'])
@require_auth
def create_cloud_folder(provider):
    """Create folder in cloud storage"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Get parameters
        data = request.get_json()
        if not data or 'folder_path' not in data:
            return error_response("No folder path provided", 400)
        
        folder_path = data['folder_path']
        options = data.get('options', {})
        
        # Create folder
        result = cloud_service.create_folder(provider, token, folder_path, options)
        return success_response("Folder created successfully", result)
        
    except Exception as e:
        logger.error(f"Cloud folder creation failed: {str(e)}")
        return error_response(f"Folder creation failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/revoke', methods=['POST'])
@require_auth
def revoke_cloud_token(provider):
    """Revoke cloud provider access token"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Revoke token
        result = cloud_service.revoke_token(provider, token)
        return success_response("Token revoked successfully", result)
        
    except Exception as e:
        logger.error(f"Cloud token revocation failed: {str(e)}")
        return error_response(f"Token revocation failed: {str(e)}", 500)

# ============================================================================
# TEXT EXTRACTION ROUTES
# ============================================================================

@extended_features_bp.route('/extract/text', methods=['POST'])
@optional_auth
def extract_text():
    """Extract text content from PDF"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("No file selected", 400)
        
        # Validate file
        if not allowed_file(file.filename, 'ai'):
            return error_response("Invalid file type. Only PDF files are supported.", 400)
        
        if file.content_length and file.content_length > MAX_FILE_SIZES['ai']:
            return error_response("File too large. Maximum size is 25MB.", 400)
        
        # Extract text
        text_content = ai_service.extract_text_from_pdf(file)
        
        return success_response("Text extracted successfully", {
            'text': text_content,
            'length': len(text_content)
        })
        
    except Exception as e:
        logger.error(f"Text extraction failed: {str(e)}")
        return error_response(f"Text extraction failed: {str(e)}", 500)

# ============================================================================
# HEALTH CHECK AND STATUS ROUTES
# ============================================================================

@extended_features_bp.route('/extended-features/status', methods=['GET'])
def get_extended_features_status():
    """Get status of all extended features"""
    try:
        status = {
            'conversion': {
                'available': True,
                'supported_formats': ['docx', 'xlsx', 'txt', 'html'],
                'max_file_size': '100MB'
            },
            'ocr': {
                'available': True,
                'supported_formats': ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'],
                'max_file_size': '50MB'
            },
            'ai': {
                'available': True,
                'supported_formats': ['pdf'],
                'max_file_size': '25MB'
            },
            'cloud': {
                'available': True,
                'supported_providers': ['google_drive', 'dropbox', 'onedrive']
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return success_response("Extended features status retrieved successfully", status)
        
    except Exception as e:
        logger.error(f"Status retrieval failed: {str(e)}")
        return error_response(f"Status retrieval failed: {str(e)}", 500)

@extended_features_bp.route('/extended-features/capabilities', methods=['GET'])
def get_extended_features_capabilities():
    """Get detailed capabilities of all extended features"""
    try:
        capabilities = {
            'conversion': {
                'name': 'PDF Conversion',
                'description': 'Convert PDFs to Word, Excel, Text, and HTML formats',
                'features': ['format_conversion', 'layout_preservation', 'table_extraction', 'batch_processing'],
                'options': {
                    'preserveLayout': 'boolean',
                    'extractTables': 'boolean',
                    'extractImages': 'boolean',
                    'quality': 'string (low|medium|high)'
                }
            },
            'ocr': {
                'name': 'Optical Character Recognition',
                'description': 'Extract text from scanned PDFs and images',
                'features': ['text_extraction', 'searchable_pdf', 'language_support', 'quality_options'],
                'options': {
                    'language': 'string',
                    'quality': 'string (fast|balanced|accurate)',
                    'outputFormat': 'string (searchable_pdf|text|json)'
                }
            },
            'ai': {
                'name': 'AI-Powered Features',
                'description': 'Summarize and translate PDF content using AI',
                'features': ['summarization', 'translation', 'multiple_languages', 'style_options'],
                'options': {
                    'style': 'string (concise|detailed|academic|casual|professional)',
                    'maxLength': 'string (short|medium|long)',
                    'targetLanguage': 'string (language code)'
                }
            },
            'cloud': {
                'name': 'Cloud Integration',
                'description': 'Save and load files from cloud storage providers',
                'features': ['file_upload', 'file_download', 'folder_management', 'oauth_authentication'],
                'providers': ['google_drive', 'dropbox', 'onedrive']
            }
        }
        
        return success_response("Extended features capabilities retrieved successfully", capabilities)
        
    except Exception as e:
        logger.error(f"Capabilities retrieval failed: {str(e)}")
        return error_response(f"Capabilities retrieval failed: {str(e)}", 500)
