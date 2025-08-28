"""Admin routes for system management and cleanup operations"""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.services.cleanup_service import CleanupService
from src.utils.scheduler import scheduler
from src.models import User

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


def require_admin():
    """Decorator to require admin privileges"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            # For now, check if user email contains 'admin' - in production, use proper role system
            if not user or 'admin' not in user.email.lower():
                return jsonify({'error': 'Admin privileges required'}), 403
            
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


@admin_bp.route('/cleanup/stats', methods=['GET'])
@jwt_required()
@require_admin()
def get_cleanup_stats():
    """Get cleanup statistics"""
    try:
        stats = CleanupService.get_cleanup_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting cleanup stats: {str(e)}")
        return jsonify({'error': 'Failed to get cleanup statistics'}), 500


@admin_bp.route('/cleanup/run', methods=['POST'])
@jwt_required()
@require_admin()
def run_cleanup():
    """Manually trigger cleanup operations"""
    try:
        cleanup_type = request.json.get('type', 'all') if request.json else 'all'
        
        results = {}
        
        if cleanup_type in ['all', 'jobs']:
            results['jobs'] = CleanupService.cleanup_expired_jobs()
        
        if cleanup_type in ['all', 'temp']:
            upload_folder = request.json.get('upload_folder', '/tmp/pdf_uploads') if request.json else '/tmp/pdf_uploads'
            results['temp_files'] = CleanupService.cleanup_temp_files(upload_folder)
        
        return jsonify({
            'message': 'Cleanup completed',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error running cleanup: {str(e)}")
        return jsonify({'error': 'Failed to run cleanup'}), 500


@admin_bp.route('/cleanup/user/<int:user_id>', methods=['DELETE'])
@jwt_required()
@require_admin()
def cleanup_user_data(user_id):
    """Force cleanup of all data for a specific user"""
    try:
        result = CleanupService.force_cleanup_user_jobs(user_id)
        
        return jsonify({
            'message': f'User {user_id} data cleanup completed',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up user {user_id} data: {str(e)}")
        return jsonify({'error': 'Failed to cleanup user data'}), 500


@admin_bp.route('/scheduler/status', methods=['GET'])
@jwt_required()
@require_admin()
def get_scheduler_status():
    """Get status of the background scheduler"""
    try:
        status = scheduler.get_task_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return jsonify({'error': 'Failed to get scheduler status'}), 500


@admin_bp.route('/system/health', methods=['GET'])
@jwt_required()
@require_admin()
def system_health():
    """Get comprehensive system health information"""
    try:
        from src.models.base import db
        from src.models import CompressionJob, User, Subscription
        
        # Database health
        try:
            db.session.execute('SELECT 1')
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        # Get counts
        user_count = User.query.count()
        job_count = CompressionJob.query.count()
        subscription_count = Subscription.query.count()
        
        # Get recent activity
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_jobs = CompressionJob.query.filter(CompressionJob.created_at >= recent_cutoff).count()
        
        # Cleanup stats
        cleanup_stats = CleanupService.get_cleanup_statistics()
        
        return jsonify({
            'database': db_status,
            'counts': {
                'users': user_count,
                'jobs': job_count,
                'subscriptions': subscription_count,
                'recent_jobs_24h': recent_jobs
            },
            'cleanup': cleanup_stats,
            'scheduler': scheduler.get_task_status(),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return jsonify({'error': 'Failed to get system health'}), 500