"""
Integration tests for bulk compression API endpoints
"""
import os
import json
import tempfile
import zipfile
from io import BytesIO
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

from src.main import create_app
from src.models import User, Subscription, Plan, CompressionJob
from src.models.base import db
from src.services.auth_service import AuthService


class TestBulkCompressionAPI:
    """Test cases for bulk compression API endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['JWT_SECRET_KEY'] = 'test-secret-key'
        app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
        
        with app.app_context():
            db.create_all()
            self._create_test_plans()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def free_user_token(self, app):
        """Create a free user and return JWT token"""
        with app.app_context():
            user = User(
                email='free@test.com',
                password='Password123',
                name='Free User'
            )
            db.session.add(user)
            db.session.commit()
            
            # Create free subscription
            free_plan = Plan.query.filter_by(name='free').first()
            subscription = Subscription(
                user_id=user.id,
                plan_id=free_plan.id
            )
            db.session.add(subscription)
            db.session.commit()
            
            # Generate JWT token
            from flask_jwt_extended import create_access_token
            token = create_access_token(identity=str(user.id))
            return token
    
    @pytest.fixture
    def premium_user_token(self, app):
        """Create a premium user and return JWT token"""
        with app.app_context():
            user = User(
                email='premium@test.com',
                password='Password123',
                name='Premium User'
            )
            db.session.add(user)
            db.session.commit()
            
            # Create premium subscription
            premium_plan = Plan.query.filter_by(name='premium').first()
            subscription = Subscription(
                user_id=user.id,
                plan_id=premium_plan.id
            )
            db.session.add(subscription)
            db.session.commit()
            
            # Generate JWT token
            from flask_jwt_extended import create_access_token
            token = create_access_token(identity=str(user.id))
            return token
    
    def _create_test_plans(self):
        """Create test subscription plans if they don't exist"""
        from src.models.subscription import Plan
        
        # Check if plans already exist
        existing_plans = Plan.query.all()
        if existing_plans:
            return  # Plans already created by app initialization
        
        plans = [
            Plan(
                name='free', 
                display_name='Free', 
                price_monthly=0, 
                daily_compression_limit=10,
                max_file_size_mb=10,
                bulk_processing=False
            ),
            Plan(
                name='premium', 
                display_name='Premium', 
                price_monthly=9.99, 
                daily_compression_limit=500,
                max_file_size_mb=50,
                bulk_processing=True
            ),
            Plan(
                name='pro', 
                display_name='Pro', 
                price_monthly=19.99, 
                daily_compression_limit=-1,
                max_file_size_mb=100,
                bulk_processing=True,
                priority_processing=True,
                api_access=True
            )
        ]
        
        for plan in plans:
            db.session.add(plan)
        db.session.commit()
    
    def _create_test_pdf_file(self, filename='test.pdf', content=None):
        """Create a test PDF file"""
        if content is None:
            # Minimal PDF content
            content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000079 00000 n \n0000000173 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n253\n%%EOF'
        
        return FileStorage(
            stream=BytesIO(content),
            filename=filename,
            content_type='application/pdf'
        )
    
    def test_bulk_compress_no_auth(self, client):
        """Test bulk compression without authentication"""
        response = client.post('/api/bulk')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'msg' in data  # JWT error message
    
    def test_bulk_compress_free_user_denied(self, client, free_user_token):
        """Test bulk compression denied for free users"""
        files = [self._create_test_pdf_file('test1.pdf')]
        
        data = {
            'files': files,
            'compressionLevel': 'medium',
            'imageQuality': '80'
        }
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.validate_bulk_request') as mock_validate:
            mock_validate.return_value = {
                'valid': False,
                'error': 'Bulk compression requires a premium subscription',
                'error_code': 'PREMIUM_REQUIRED',
                'max_files': 1
            }
            
            response = client.post(
                '/api/bulk',
                data=data,
                content_type='multipart/form-data',
                headers={'Authorization': f'Bearer {free_user_token}'}
            )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'PREMIUM_REQUIRED'
        assert 'premium subscription' in response_data['error'].lower()
    
    def test_bulk_compress_no_files(self, client, premium_user_token):
        """Test bulk compression with no files provided"""
        data = {
            'compressionLevel': 'medium',
            'imageQuality': '80'
        }
        
        response = client.post(
            '/api/bulk',
            data=data,
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {premium_user_token}'}
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'NO_FILES'
    
    def test_bulk_compress_invalid_file_type(self, client, premium_user_token):
        """Test bulk compression with invalid file type"""
        # Create a non-PDF file
        invalid_file = FileStorage(
            stream=BytesIO(b'This is not a PDF file'),
            filename='test.txt',
            content_type='text/plain'
        )
        
        data = {
            'files': [invalid_file],
            'compressionLevel': 'medium',
            'imageQuality': '80'
        }
        
        response = client.post(
            '/api/bulk',
            data=data,
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {premium_user_token}'}
        )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'VALIDATION_FAILED'
        assert 'validation_errors' in response_data['details']
    
    @patch('src.services.bulk_compression_service.BulkCompressionService.process_bulk_job_async')
    @patch('src.services.bulk_compression_service.BulkCompressionService.create_bulk_job')
    def test_bulk_compress_success(self, mock_create_job, mock_process_async, client, premium_user_token):
        """Test successful bulk compression job creation"""
        # Mock job creation
        mock_job = MagicMock()
        mock_job.id = 123
        mock_create_job.return_value = mock_job
        mock_process_async.return_value = 'task-123'
        
        files = [
            self._create_test_pdf_file('test1.pdf'),
            self._create_test_pdf_file('test2.pdf')
        ]
        
        data = {
            'files': files,
            'compressionLevel': 'high',
            'imageQuality': '60'
        }
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.validate_bulk_request') as mock_validate:
            mock_validate.return_value = {
                'valid': True,
                'file_count': 2,
                'total_size_mb': 0.1,
                'user_tier': 'premium'
            }
            
            response = client.post(
                '/api/bulk',
                data=data,
                content_type='multipart/form-data',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 201
        response_data = json.loads(response.data)
        assert response_data['success'] is True
        assert response_data['job_id'] == 123
        assert response_data['task_id'] == 'task-123'
        assert response_data['file_count'] == 2
        assert response_data['status'] == 'queued'
    
    def test_get_bulk_job_status_no_auth(self, client):
        """Test getting job status without authentication"""
        response = client.get('/api/bulk/jobs/123/status')
        
        assert response.status_code == 401
    
    def test_get_bulk_job_status_not_found(self, client, premium_user_token):
        """Test getting status for non-existent job"""
        response = client.get(
            '/api/bulk/jobs/999/status',
            headers={'Authorization': f'Bearer {premium_user_token}'}
        )
        
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'ACCESS_DENIED'
    
    def test_get_bulk_job_status_success(self, client, premium_user_token, app):
        """Test successful job status retrieval"""
        with app.app_context():
            # Create a test job
            user = User.query.filter_by(email='premium@test.com').first()
            job = CompressionJob(
                user_id=user.id,
                job_type='bulk',
                original_filename='bulk_job_2_files',
                settings={'compression_level': 'medium'}
            )
            job.file_count = 2
            job.completed_count = 1
            job.status = 'processing'
            
            db.session.add(job)
            db.session.commit()
            job_id = job.id
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.get_job_progress') as mock_progress:
            mock_progress.return_value = {
                'found': True,
                'job_id': job_id,
                'status': 'processing',
                'job_type': 'bulk',
                'file_count': 2,
                'completed_count': 1,
                'progress_percentage': 50.0,
                'created_at': '2024-01-01T10:00:00',
                'started_at': '2024-01-01T10:01:00',
                'completed_at': None,
                'is_completed': False,
                'is_successful': False,
                'error_message': None
            }
            
            response = client.get(
                f'/api/bulk/jobs/{job_id}/status',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['job_id'] == job_id
        assert response_data['status'] == 'processing'
        assert response_data['progress_percentage'] == 50.0
        assert response_data['file_count'] == 2
        assert response_data['completed_count'] == 1
    
    def test_download_bulk_result_no_auth(self, client):
        """Test downloading result without authentication"""
        response = client.get('/api/bulk/jobs/123/download')
        
        assert response.status_code == 401
    
    def test_download_bulk_result_not_found(self, client, premium_user_token):
        """Test downloading result for non-existent job"""
        with patch('src.services.bulk_compression_service.BulkCompressionService.get_result_file_path') as mock_get_path:
            mock_get_path.return_value = None
            
            response = client.get(
                '/api/bulk/jobs/999/download',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'RESULT_NOT_AVAILABLE'
    
    def test_download_bulk_result_success(self, client, premium_user_token, app):
        """Test successful result download"""
        with app.app_context():
            # Create a test job
            user = User.query.filter_by(email='premium@test.com').first()
            job = CompressionJob(
                user_id=user.id,
                job_type='bulk',
                original_filename='bulk_job_2_files',
                settings={'compression_level': 'medium'}
            )
            job.file_count = 2
            job.status = 'completed'
            
            db.session.add(job)
            db.session.commit()
            job_id = job.id
        
        # Create a temporary ZIP file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w') as zf:
                zf.writestr('compressed_file1.pdf', b'fake compressed content 1')
                zf.writestr('compressed_file2.pdf', b'fake compressed content 2')
            
            temp_zip_path = temp_zip.name
        
        try:
            with patch('src.services.bulk_compression_service.BulkCompressionService.get_result_file_path') as mock_get_path:
                mock_get_path.return_value = temp_zip_path
                
                response = client.get(
                    f'/api/bulk/jobs/{job_id}/download',
                    headers={'Authorization': f'Bearer {premium_user_token}'}
                )
            
            assert response.status_code == 200
            assert response.content_type == 'application/zip'
            assert 'attachment' in response.headers.get('Content-Disposition', '')
            
            # Verify ZIP content
            zip_content = BytesIO(response.data)
            with zipfile.ZipFile(zip_content, 'r') as zf:
                files = zf.namelist()
                assert 'compressed_file1.pdf' in files
                assert 'compressed_file2.pdf' in files
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
    
    def test_get_bulk_jobs_no_auth(self, client):
        """Test getting bulk jobs without authentication"""
        response = client.get('/api/bulk/jobs')
        
        assert response.status_code == 401
    
    def test_get_bulk_jobs_success(self, client, premium_user_token):
        """Test successful bulk jobs retrieval"""
        with patch('src.services.bulk_compression_service.BulkCompressionService.get_user_bulk_jobs') as mock_get_jobs:
            mock_jobs = [
                {
                    'id': 1,
                    'job_type': 'bulk',
                    'status': 'completed',
                    'file_count': 3,
                    'created_at': '2024-01-01T10:00:00'
                },
                {
                    'id': 2,
                    'job_type': 'bulk',
                    'status': 'processing',
                    'file_count': 2,
                    'created_at': '2024-01-01T11:00:00'
                }
            ]
            mock_get_jobs.return_value = mock_jobs
            
            response = client.get(
                '/api/bulk/jobs?limit=20',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert response_data['total'] == 2
        assert len(response_data['jobs']) == 2
        assert response_data['jobs'][0]['id'] == 1
        assert response_data['jobs'][1]['id'] == 2
    
    def test_bulk_compress_too_many_files(self, client, premium_user_token):
        """Test bulk compression with too many files"""
        # Create more files than allowed for premium users (50+)
        files = [self._create_test_pdf_file(f'test{i}.pdf') for i in range(51)]
        
        data = {
            'files': files,
            'compressionLevel': 'medium',
            'imageQuality': '80'
        }
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.validate_bulk_request') as mock_validate:
            mock_validate.return_value = {
                'valid': False,
                'error': 'Too many files. Maximum allowed: 50',
                'error_code': 'TOO_MANY_FILES',
                'max_files': 50
            }
            
            response = client.post(
                '/api/bulk',
                data=data,
                content_type='multipart/form-data',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'TOO_MANY_FILES'
        assert response_data['details']['max_files'] == 50
    
    def test_bulk_compress_file_too_large(self, client, premium_user_token):
        """Test bulk compression with file too large"""
        # Create a large file (simulate by mocking validation)
        files = [self._create_test_pdf_file('large_file.pdf')]
        
        data = {
            'files': files,
            'compressionLevel': 'medium',
            'imageQuality': '80'
        }
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.validate_bulk_request') as mock_validate:
            mock_validate.return_value = {
                'valid': False,
                'error': 'File validation failed',
                'error_code': 'VALIDATION_FAILED',
                'validation_errors': [{
                    'valid': False,
                    'error': 'File 1: File too large (60.0MB). Maximum: 50MB',
                    'error_code': 'FILE_TOO_LARGE',
                    'filename': 'large_file.pdf',
                    'size_mb': 60.0,
                    'index': 0
                }]
            }
            
            response = client.post(
                '/api/bulk',
                data=data,
                content_type='multipart/form-data',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['error_code'] == 'VALIDATION_FAILED'
        assert 'validation_errors' in response_data['details']
        assert response_data['details']['validation_errors'][0]['error_code'] == 'FILE_TOO_LARGE'
    
    def test_bulk_compress_compression_settings(self, client, premium_user_token):
        """Test bulk compression with different compression settings"""
        files = [self._create_test_pdf_file('test.pdf')]
        
        # Test with custom settings
        data = {
            'files': files,
            'compressionLevel': 'high',
            'imageQuality': '50'
        }
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.validate_bulk_request') as mock_validate, \
             patch('src.services.bulk_compression_service.BulkCompressionService.create_bulk_job') as mock_create, \
             patch('src.services.bulk_compression_service.BulkCompressionService.process_bulk_job_async') as mock_process:
            
            mock_validate.return_value = {
                'valid': True,
                'file_count': 1,
                'total_size_mb': 0.1,
                'user_tier': 'premium'
            }
            
            mock_job = MagicMock()
            mock_job.id = 456
            mock_create.return_value = mock_job
            mock_process.return_value = 'task-456'
            
            response = client.post(
                '/api/bulk',
                data=data,
                content_type='multipart/form-data',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 201
        
        # Verify compression settings were passed correctly
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        compression_settings = call_args[0][2]  # Third argument
        assert compression_settings['compression_level'] == 'high'
        assert compression_settings['image_quality'] == 50
    
    def test_get_bulk_job_status_with_task_status(self, client, premium_user_token, app):
        """Test job status retrieval with Celery task status"""
        with app.app_context():
            # Create a test job with task ID
            user = User.query.filter_by(email='premium@test.com').first()
            job = CompressionJob(
                user_id=user.id,
                job_type='bulk',
                original_filename='bulk_job_2_files',
                settings={'compression_level': 'medium'}
            )
            job.file_count = 2
            job.completed_count = 1
            job.status = 'processing'
            job.task_id = 'celery-task-123'
            
            db.session.add(job)
            db.session.commit()
            job_id = job.id
        
        with patch('src.services.bulk_compression_service.BulkCompressionService.get_job_progress') as mock_progress, \
             patch('src.services.bulk_compression_service.BulkCompressionService.get_task_status') as mock_task_status:
            
            mock_progress.return_value = {
                'found': True,
                'job_id': job_id,
                'status': 'processing',
                'job_type': 'bulk',
                'file_count': 2,
                'completed_count': 1,
                'progress_percentage': 50.0,
                'created_at': '2024-01-01T10:00:00',
                'started_at': '2024-01-01T10:01:00',
                'completed_at': None,
                'is_completed': False,
                'is_successful': False,
                'error_message': None
            }
            
            mock_task_status.return_value = {
                'state': 'PROGRESS',
                'current': 1,
                'total': 2,
                'progress': 50,
                'status': 'Processing file 1 of 2'
            }
            
            response = client.get(
                f'/api/bulk/jobs/{job_id}/status',
                headers={'Authorization': f'Bearer {premium_user_token}'}
            )
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'task_status' in response_data
        assert response_data['task_status']['state'] == 'PROGRESS'
        assert response_data['task_status']['current'] == 1
        assert response_data['task_status']['total'] == 2


if __name__ == '__main__':
    pytest.main([__file__])
