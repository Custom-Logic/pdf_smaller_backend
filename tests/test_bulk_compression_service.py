"""
Unit tests for BulkCompressionService
"""
import pytest
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage
from io import BytesIO

from src.services.bulk_compression_service import BulkCompressionService
from src.models import CompressionJob, User, Plan, Subscription
from src.models.base import db


class TestBulkCompressionService:
    """Test cases for BulkCompressionService"""
    
    @pytest.fixture
    def temp_upload_dir(self):
        """Create temporary upload directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def bulk_service(self, temp_upload_dir):
        """Create BulkCompressionService instance"""
        with patch('src.services.bulk_compression_service.CompressionService') as mock_compression:
            service = BulkCompressionService(temp_upload_dir)
            service.compression_service = mock_compression.return_value
            return service
    
    @pytest.fixture
    def mock_pdf_file(self):
        """Create a mock PDF file"""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n'
        pdf_content += b'x' * 1000  # Add some content to make it non-empty
        
        file_storage = FileStorage(
            stream=BytesIO(pdf_content),
            filename='test.pdf',
            content_type='application/pdf'
        )
        return file_storage
    
    @pytest.fixture
    def premium_user(self, app):
        """Create a premium user with subscription"""
        with app.app_context():
            # Create user
            user = User(
                email='premium@example.com',
                password='TestPassword123',
                name='Premium User'
            )
            db.session.add(user)
            db.session.flush()
            
            # Get existing premium plan
            plan = Plan.query.filter_by(name='premium').first()
            if not plan:
                # Create premium plan if it doesn't exist
                plan = Plan(
                    name='premium',
                    display_name='Premium Plan',
                    description='Premium subscription',
                    price_monthly=9.99,
                    price_yearly=99.99,
                    daily_compression_limit=500,
                    max_file_size_mb=50,
                    bulk_processing=True,
                    priority_processing=False,
                    api_access=True
                )
                db.session.add(plan)
                db.session.flush()
            
            # Create subscription
            subscription = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                billing_cycle='monthly'
            )
            db.session.add(subscription)
            db.session.commit()
            
            yield user
    
    def test_validate_bulk_request_free_user_denied(self, app, bulk_service, test_user, mock_pdf_file):
        """Test that free users are denied bulk compression"""
        with app.app_context():
            files = [mock_pdf_file]
            
            with patch('src.services.bulk_compression_service.SubscriptionService.get_user_subscription') as mock_sub:
                mock_sub.return_value = None  # No subscription = free user
                
                result = bulk_service.validate_bulk_request(test_user.id, files)
                
                assert not result['valid']
                assert result['error_code'] == 'PREMIUM_REQUIRED'
                assert 'premium subscription' in result['error']
    
    def test_validate_bulk_request_too_many_files(self, app, bulk_service, premium_user, mock_pdf_file):
        """Test validation fails when too many files are uploaded"""
        with app.app_context():
            # Create more files than allowed for premium users
            files = [mock_pdf_file for _ in range(51)]  # Premium limit is 50
            
            with patch('src.services.bulk_compression_service.SubscriptionService.get_user_subscription') as mock_sub:
                # Mock premium subscription
                mock_subscription = Mock()
                mock_subscription.is_active.return_value = True
                mock_subscription.plan.name = 'premium'
                mock_sub.return_value = mock_subscription
                
                result = bulk_service.validate_bulk_request(premium_user.id, files)
                
                assert not result['valid']
                assert result['error_code'] == 'TOO_MANY_FILES'
                assert result['max_files'] == 50
    
    def test_validate_bulk_request_no_files(self, app, bulk_service, premium_user):
        """Test validation fails when no files are provided"""
        with app.app_context():
            files = []
            
            with patch('src.services.bulk_compression_service.SubscriptionService.get_user_subscription') as mock_sub:
                # Mock premium subscription
                mock_subscription = Mock()
                mock_subscription.is_active.return_value = True
                mock_subscription.plan.name = 'premium'
                mock_sub.return_value = mock_subscription
                
                result = bulk_service.validate_bulk_request(premium_user.id, files)
                
                assert not result['valid']
                assert result['error_code'] == 'NO_FILES'
    
    def test_validate_single_file_invalid_type(self, bulk_service):
        """Test validation of invalid file type"""
        # Create a non-PDF file
        txt_file = FileStorage(
            stream=BytesIO(b'This is not a PDF'),
            filename='test.txt',
            content_type='text/plain'
        )
        
        result = bulk_service._validate_single_file(txt_file, 0)
        
        assert not result['valid']
        assert result['error_code'] == 'INVALID_TYPE'
        assert 'PDF files are allowed' in result['error']
    
    def test_validate_single_file_too_large(self, bulk_service):
        """Test validation of oversized file"""
        # Create a large file (simulate by mocking file size)
        large_file = FileStorage(
            stream=BytesIO(b'%PDF-1.4\nLarge content'),
            filename='large.pdf',
            content_type='application/pdf'
        )
        
        # Mock the file size check
        with patch.object(large_file, 'tell', return_value=60 * 1024 * 1024):  # 60MB
            result = bulk_service._validate_single_file(large_file, 0)
            
            assert not result['valid']
            assert result['error_code'] == 'FILE_TOO_LARGE'
            assert '60.0MB' in result['error']
    
    def test_validate_single_file_empty_file(self, bulk_service):
        """Test validation of empty file"""
        empty_file = FileStorage(
            stream=BytesIO(b''),
            filename='empty.pdf',
            content_type='application/pdf'
        )
        
        result = bulk_service._validate_single_file(empty_file, 0)
        
        assert not result['valid']
        assert result['error_code'] == 'EMPTY_FILE'
    
    def test_validate_single_file_invalid_pdf_format(self, bulk_service):
        """Test validation of file with invalid PDF format"""
        invalid_pdf = FileStorage(
            stream=BytesIO(b'Not a PDF header'),
            filename='invalid.pdf',
            content_type='application/pdf'
        )
        
        result = bulk_service._validate_single_file(invalid_pdf, 0)
        
        assert not result['valid']
        assert result['error_code'] == 'INVALID_PDF'
    
    def test_validate_single_file_valid(self, bulk_service, mock_pdf_file):
        """Test validation of valid PDF file"""
        result = bulk_service._validate_single_file(mock_pdf_file, 0)
        
        assert result['valid']
        assert result['filename'] == 'test.pdf'
        assert result['size_mb'] > 0
        assert result['index'] == 0
    
    def test_validate_bulk_request_valid(self, app, bulk_service, premium_user, mock_pdf_file):
        """Test successful validation of bulk request"""
        with app.app_context():
            files = [mock_pdf_file]
            
            with patch('src.services.bulk_compression_service.SubscriptionService.get_user_subscription') as mock_sub, \
                 patch('src.services.bulk_compression_service.SubscriptionService.check_compression_permission') as mock_perm:
                
                # Mock premium subscription
                mock_subscription = Mock()
                mock_subscription.is_active.return_value = True
                mock_subscription.plan.name = 'premium'
                mock_sub.return_value = mock_subscription
                mock_perm.return_value = {'can_compress': True}
                
                result = bulk_service.validate_bulk_request(premium_user.id, files)
                
                assert result['valid']
                assert result['file_count'] == 1
                assert result['user_tier'] == 'premium'
                assert result['max_files'] == 50
    
    def test_create_bulk_job(self, app, bulk_service, premium_user, mock_pdf_file, temp_upload_dir):
        """Test creation of bulk compression job"""
        with app.app_context():
            files = [mock_pdf_file]
            settings = {
                'compression_level': 'medium',
                'image_quality': 80
            }
            
            job = bulk_service.create_bulk_job(premium_user.id, files, settings)
            
            assert job is not None
            assert job.user_id == premium_user.id
            assert job.job_type == 'bulk'
            assert job.file_count == 1
            assert job.status == 'pending'
            
            # Check that job directory was created
            job_settings = job.get_settings()
            job_dir = job_settings['job_directory']
            assert os.path.exists(job_dir)
            
            # Check that input files were saved
            input_files = job_settings['input_files']
            assert len(input_files) == 1
            assert os.path.exists(input_files[0]['path'])
    
    @patch('src.services.bulk_compression_service.BulkCompressionService._process_single_file_in_batch')
    @patch('src.services.bulk_compression_service.BulkCompressionService._create_result_archive')
    def test_process_bulk_job_sync_success(self, mock_archive, mock_process, app, bulk_service, premium_user, temp_upload_dir):
        """Test successful synchronous processing of bulk job"""
        with app.app_context():
            # Create a job
            job = CompressionJob(
                user_id=premium_user.id,
                job_type='bulk',
                original_filename='test_bulk',
                settings={
                    'job_directory': temp_upload_dir,
                    'input_files': [
                        {
                            'original_name': 'test.pdf',
                            'saved_name': 'input_001_test.pdf',
                            'path': os.path.join(temp_upload_dir, 'input_001_test.pdf'),
                            'size': 1000
                        }
                    ],
                    'compression_level': 'medium',
                    'image_quality': 80
                }
            )
            job.file_count = 1
            db.session.add(job)
            db.session.commit()
            
            # Create the input file
            input_file_path = os.path.join(temp_upload_dir, 'input_001_test.pdf')
            with open(input_file_path, 'wb') as f:
                f.write(b'%PDF-1.4\ntest content')
            
            # Mock the processing methods
            mock_process.return_value = {
                'original_name': 'test.pdf',
                'original_size': 1000,
                'compressed_size': 800,
                'compression_ratio': 20.0,
                'output_path': os.path.join(temp_upload_dir, 'compressed_001_test.pdf'),
                'output_filename': 'compressed_001_test.pdf'
            }
            
            archive_path = os.path.join(temp_upload_dir, 'result.zip')
            mock_archive.return_value = archive_path
            
            with patch('src.services.bulk_compression_service.SubscriptionService.increment_usage'):
                result = bulk_service.process_bulk_job_sync(job.id)
            
            assert result['success']
            assert result['processed_count'] == 1
            assert result['error_count'] == 0
            
            # Check job was updated
            updated_job = CompressionJob.query.get(job.id)
            assert updated_job.status == 'completed'
            assert updated_job.completed_count == 1
    
    def test_get_job_progress(self, app, bulk_service, premium_user):
        """Test getting job progress information"""
        with app.app_context():
            # Create a job
            job = CompressionJob(
                user_id=premium_user.id,
                job_type='bulk',
                original_filename='test_bulk'
            )
            job.file_count = 5
            job.completed_count = 3
            db.session.add(job)
            db.session.commit()
            
            progress = bulk_service.get_job_progress(job.id)
            
            assert progress['found']
            assert progress['job_id'] == job.id
            assert progress['status'] == 'pending'
            assert progress['file_count'] == 5
            assert progress['completed_count'] == 3
            assert progress['progress_percentage'] == 60.0
    
    def test_get_job_progress_not_found(self, bulk_service):
        """Test getting progress for non-existent job"""
        progress = bulk_service.get_job_progress(99999)
        
        assert not progress['found']
        assert 'not found' in progress['error']
    
    def test_get_result_file_path_success(self, app, bulk_service, premium_user, temp_upload_dir):
        """Test getting result file path for completed job"""
        with app.app_context():
            # Create result file
            result_path = os.path.join(temp_upload_dir, 'result.zip')
            with open(result_path, 'wb') as f:
                f.write(b'fake zip content')
            
            # Create completed job
            job = CompressionJob(
                user_id=premium_user.id,
                job_type='bulk',
                original_filename='test_bulk'
            )
            job.mark_as_completed()
            job.result_path = result_path
            db.session.add(job)
            db.session.commit()
            
            file_path = bulk_service.get_result_file_path(job.id, premium_user.id)
            
            assert file_path == result_path
    
    def test_get_result_file_path_unauthorized(self, app, bulk_service, premium_user, test_user):
        """Test getting result file path with wrong user"""
        with app.app_context():
            # Create job for premium_user
            job = CompressionJob(
                user_id=premium_user.id,
                job_type='bulk',
                original_filename='test_bulk'
            )
            job.mark_as_completed()
            db.session.add(job)
            db.session.commit()
            
            # Try to access with different user
            file_path = bulk_service.get_result_file_path(job.id, test_user.id)
            
            assert file_path is None
    
    def test_get_max_files_for_tier(self, bulk_service):
        """Test getting maximum files for different tiers"""
        assert bulk_service._get_max_files_for_tier('free') == 1
        assert bulk_service._get_max_files_for_tier('premium') == 50
        assert bulk_service._get_max_files_for_tier('pro') == 100
        assert bulk_service._get_max_files_for_tier('unknown') == 1  # Default to free
    
    def test_get_max_total_size_for_tier(self, bulk_service):
        """Test getting maximum total size for different tiers"""
        assert bulk_service._get_max_total_size_for_tier('free') == 10.0
        assert bulk_service._get_max_total_size_for_tier('premium') == 500.0
        assert bulk_service._get_max_total_size_for_tier('pro') == 1000.0
        assert bulk_service._get_max_total_size_for_tier('unknown') == 10.0  # Default to free
    
    def test_get_user_bulk_jobs(self, app, bulk_service, premium_user):
        """Test getting user's bulk jobs"""
        with app.app_context():
            # Create some bulk jobs
            for i in range(3):
                job = CompressionJob(
                    user_id=premium_user.id,
                    job_type='bulk',
                    original_filename=f'test_bulk_{i}'
                )
                db.session.add(job)
            
            # Create a single job (should not be included)
            single_job = CompressionJob(
                user_id=premium_user.id,
                job_type='single',
                original_filename='single_job'
            )
            db.session.add(single_job)
            db.session.commit()
            
            jobs = bulk_service.get_user_bulk_jobs(premium_user.id)
            
            assert len(jobs) == 3
            for job in jobs:
                assert job['job_type'] == 'bulk'
                assert job['user_id'] == premium_user.id
    
    def test_create_result_archive(self, bulk_service, temp_upload_dir):
        """Test creating result ZIP archive"""
        # Create some test files
        file1_path = os.path.join(temp_upload_dir, 'compressed_001_test1.pdf')
        file2_path = os.path.join(temp_upload_dir, 'compressed_002_test2.pdf')
        
        with open(file1_path, 'wb') as f:
            f.write(b'compressed pdf 1')
        with open(file2_path, 'wb') as f:
            f.write(b'compressed pdf 2')
        
        processed_files = [
            {
                'original_name': 'test1.pdf',
                'output_path': file1_path,
                'output_filename': 'compressed_001_test1.pdf'
            },
            {
                'original_name': 'test2.pdf',
                'output_path': file2_path,
                'output_filename': 'compressed_002_test2.pdf'
            }
        ]
        
        archive_path = bulk_service.create_result_archive(temp_upload_dir, processed_files, 123)
        
        assert os.path.exists(archive_path)
        assert archive_path.endswith('compressed_files_job_123.zip')
        
        # Verify archive contents
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            names = zipf.namelist()
            assert 'compressed_test1.pdf' in names
            assert 'compressed_test2.pdf' in names
    
    @patch('shutil.rmtree')
    def test_cleanup_job_files(self, mock_rmtree, app, bulk_service, premium_user, temp_upload_dir):
        """Test cleaning up job files"""
        with app.app_context():
            # Create job with directory
            job = CompressionJob(
                user_id=premium_user.id,
                job_type='bulk',
                original_filename='test_bulk',
                settings={'job_directory': temp_upload_dir}
            )
            db.session.add(job)
            db.session.commit()
            
            result = bulk_service.cleanup_job_files(job.id)
            
            assert result
            mock_rmtree.assert_called_once_with(temp_upload_dir)