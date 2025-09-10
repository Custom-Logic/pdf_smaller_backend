"""
Enhanced Compression Routes
Provides intelligent compression and batch processing endpoints
"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
from datetime import datetime
from flask_cors import CORS
from src.services.enhanced_compression_service import EnhancedCompressionService

# DEPRECATED ROUTE PLEASE IGNORE

logger = logging.getLogger(__name__)

enhanced_compression_bp = Blueprint('enhanced_compression', __name__)
# CORS(enhanced_compression_bp, resources={r"/api/enhanced": {"origins": ["https://www.pdfsmaller.site"]}})
# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

# Initialize enhanced compression service
enhanced_compression_service = EnhancedCompressionService(
    os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads')
)


@enhanced_compression_bp.route('/compress/intelligent', methods=['POST'])
async def intelligent_compression():
    """Intelligent compression with AI recommendations"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Get user preferences
        user_preferences = {}
        if request.form.get('compressionLevel'):
            user_preferences['compression_level'] = request.form.get('compressionLevel')
        if request.form.get('imageQuality'):
            user_preferences['image_quality'] = int(request.form.get('imageQuality'))
        if request.form.get('targetSize'):
            user_preferences['target_size'] = request.form.get('targetSize')
        if request.form.get('optimizationStrategy'):
            user_preferences['optimization_strategy'] = request.form.get('optimizationStrategy')
        
        # Get current user
        current_user = get_current_user()
        user_id = str(current_user.id) if current_user else None
        
        # Read file data
        file_data = file.read()
        
        # Process with intelligent compression
        result = await enhanced_compression_service.compress_with_intelligence(
            file_data, user_preferences, user_id
        )
        
        # Return compressed file
        if result.get('success'):
            # For now, return the result data
            # In production, you'd return the actual compressed file
            return jsonify({
                'success': True,
                'job_id': result['job_id'],
                'compression_ratio': result['compression_ratio'],
                'original_size': result['original_size'],
                'compressed_size': result['compressed_size'],
                'settings_used': result['settings_used'],
                'analysis': result['analysis'],
                'recommendations': result['recommendations']
            })
        else:
            return jsonify({'error': 'Compression failed'}), 500
        
    except Exception as e:
        logger.error(f"Intelligent compression failed: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/analyze', methods=['POST'])
async def analyze_pdf():
    """Analyze PDF for compression potential"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Read file data
        file_data = file.read()
        
        # Analyze file
        analysis = await enhanced_compression_service.analyze_content(file_data)
        recommendations = enhanced_compression_service.get_ml_recommendations(analysis)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'recommendations': recommendations
        })
        
    except Exception as e:
        logger.error(f"PDF analysis failed: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/batch', methods=['POST'])
async def create_batch_job():
    """Create batch compression job"""
    try:
        # Check if files were uploaded
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        # Validate files
        valid_files = []
        for file in files:
            validation_error = validate_file(file)
            if validation_error:
                logger.warning(f"File validation failed for {file.filename}: {validation_error}")
                continue
            valid_files.append(file)
        
        if not valid_files:
            return jsonify({'error': 'No valid files provided'}), 400
        
        # Get compression settings
        settings = {}
        if request.form.get('compressionLevel'):
            settings['compression_level'] = request.form.get('compressionLevel')
        if request.form.get('imageQuality'):
            settings['image_quality'] = int(request.form.get('imageQuality'))
        if request.form.get('targetSize'):
            settings['target_size'] = request.form.get('targetSize')
        if request.form.get('optimizationStrategy'):
            settings['optimization_strategy'] = request.form.get('optimizationStrategy')
        
        # Get current user
        current_user = get_current_user()
        user_id = str(current_user.id) if current_user else None
        
        # Read file data
        file_data_list = []
        for file in valid_files:
            file_data_list.append(file.read())
        
        # Process batch compression
        result = await enhanced_compression_service.batch_compress(
            file_data_list, settings, user_id
        )
        
        return jsonify({
            'success': True,
            'batch_id': result['batch_id'],
            'total_files': result['total_files'],
            'successful_files': result['successful_files'],
            'failed_files': result['failed_files'],
            'status': 'completed'
        })
        
    except Exception as e:
        logger.error(f"Batch compression failed: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/batch/<batch_id>/status', methods=['GET'])
async def get_batch_status(batch_id):
    """Get batch job status"""
    try:
        # In a real implementation, you'd query the database for batch job status
        # For now, return a mock response
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'status': 'completed',
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'created_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get batch status: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/history', methods=['GET'])
async def get_compression_history():
    """Get user's compression history"""
    try:
        # Get current user
        current_user = get_current_user()
        user_id = str(current_user.id) if current_user else None
        
        # Get limit parameter
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Cap at 100
        
        # Get compression history
        history = enhanced_compression_service.get_compression_history(user_id, limit)
        
        return jsonify({
            'success': True,
            'history': history,
            'total': len(history)
        })
        
    except Exception as e:
        logger.error(f"Failed to get compression history: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/preview', methods=['POST'])
async def get_compression_preview():
    """Get compression preview with estimated results"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Get compression settings
        settings = {}
        if request.form.get('compressionLevel'):
            settings['compression_level'] = request.form.get('compressionLevel')
        if request.form.get('imageQuality'):
            settings['image_quality'] = int(request.form.get('imageQuality'))
        if request.form.get('targetSize'):
            settings['target_size'] = request.form.get('targetSize')
        if request.form.get('optimizationStrategy'):
            settings['optimization_strategy'] = request.form.get('optimizationStrategy')
        
        # Read file data
        file_data = file.read()
        
        # Analyze file for preview
        analysis = await enhanced_compression_service.analyze_content(file_data)
        recommendations = enhanced_compression_service.get_ml_recommendations(analysis)
        
        # Merge settings
        final_settings = enhanced_compression_service.merge_preferences(recommendations, settings)
        
        # Estimate compression results
        estimated_ratio = enhanced_compression_service.calculate_compression_potential(analysis)
        estimated_size = int(len(file_data) * estimated_ratio)
        
        return jsonify({
            'success': True,
            'original_size': len(file_data),
            'estimated_size': estimated_size,
            'estimated_ratio': estimated_ratio,
            'compression_potential': analysis.get('compression_potential', 0.5),
            'recommended_settings': recommendations,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Compression preview failed: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/optimize', methods=['POST'])
async def optimize_compression_settings():
    """Get optimized compression settings for a file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Get user preferences
        user_preferences = {}
        if request.form.get('compressionLevel'):
            user_preferences['compression_level'] = request.form.get('compressionLevel')
        if request.form.get('imageQuality'):
            user_preferences['image_quality'] = int(request.form.get('imageQuality'))
        if request.form.get('targetSize'):
            user_preferences['target_size'] = request.form.get('targetSize')
        if request.form.get('optimizationStrategy'):
            user_preferences['optimization_strategy'] = request.form.get('optimizationStrategy')
        
        # Read file data
        file_data = file.read()
        
        # Analyze file
        analysis = await enhanced_compression_service.analyze_content(file_data)
        recommendations = enhanced_compression_service.get_ml_recommendations(analysis)
        
        # Merge preferences
        optimized_settings = enhanced_compression_service.merge_preferences(recommendations, user_preferences)
        
        return jsonify({
            'success': True,
            'original_settings': user_preferences,
            'ai_recommendations': recommendations,
            'optimized_settings': optimized_settings,
            'analysis': analysis,
            'explanation': {
                'compression_potential': f"{analysis.get('compression_potential', 0.5) * 100:.1f}%",
                'document_type': analysis.get('document_type', 'unknown'),
                'page_count': analysis.get('page_count', 0),
                'estimated_fonts': analysis.get('estimated_font_count', 0),
                'estimated_images': analysis.get('estimated_image_count', 0)
            }
        })
        
    except Exception as e:
        logger.error(f"Settings optimization failed: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/compare', methods=['POST'])
async def compare_compression_settings():
    """Compare different compression settings for a file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Get comparison settings
        comparison_settings = request.form.get('comparisonSettings')
        if not comparison_settings:
            return jsonify({'error': 'No comparison settings provided'}), 400
        
        try:
            comparison_settings = json.loads(comparison_settings)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid comparison settings format'}), 400
        
        # Read file data
        file_data = file.read()
        
        # Analyze file
        analysis = await enhanced_compression_service.analyze_content(file_data)
        
        # Compare different settings
        comparisons = []
        for setting_name, settings in comparison_settings.items():
            try:
                recommendations = enhanced_compression_service.get_ml_recommendations(analysis)
                final_settings = enhanced_compression_service.merge_preferences(recommendations, settings)
                
                # Estimate compression ratio
                estimated_ratio = enhanced_compression_service.calculate_compression_potential(analysis)
                estimated_size = int(len(file_data) * estimated_ratio)
                
                comparisons.append({
                    'setting_name': setting_name,
                    'settings': final_settings,
                    'estimated_size': estimated_size,
                    'estimated_ratio': estimated_ratio,
                    'compression_potential': analysis.get('compression_potential', 0.5)
                })
            except Exception as e:
                logger.warning(f"Failed to compare setting {setting_name}: {str(e)}")
                comparisons.append({
                    'setting_name': setting_name,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'comparisons': comparisons
        })
        
    except Exception as e:
        logger.error(f"Settings comparison failed: {str(e)}")
        return handle_api_error(e)


@enhanced_compression_bp.route('/compress/health', methods=['GET'])
async def compression_health_check():
    """Health check for compression service"""
    try:
        # Check if required tools are available
        import subprocess
        
        # Check pdfinfo
        try:
            subprocess.run(['pdfinfo', '--version'], capture_output=True, timeout=5)
            pdfinfo_available = True
        except:
            pdfinfo_available = False
        
        # Check Ghostscript
        try:
            subprocess.run(['gs', '--version'], capture_output=True, timeout=5)
            ghostscript_available = True
        except:
            ghostscript_available = False
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'services': {
                'pdfinfo': pdfinfo_available,
                'ghostscript': ghostscript_available,
                'enhanced_compression': True
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
