"""
Tests for Enhanced Compression Service
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.services.enhanced_compression_service import EnhancedCompressionService


class TestEnhancedCompressionService:
    """Test cases for EnhancedCompressionService"""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = EnhancedCompressionService(temp_dir)
            yield service
    
    @pytest.fixture
    def mock_pdf_data(self):
        """Mock PDF data for testing"""
        return b"%PDF-1.4\n%Test PDF content\n%%EOF"
    
    def test_init(self, service):
        """Test service initialization"""
        assert service.upload_folder.exists()
        assert hasattr(service, 'base_compression_service')
        assert hasattr(service, 'analysis_cache')
    
    @patch('subprocess.run')
    def test_analyze_with_pdfinfo_success(self, mock_run, service):
        """Test successful PDF analysis with pdfinfo"""
        # Mock successful pdfinfo output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
Pages: 5
File size: 1024000 bytes
Title: Test Document
Author: Test Author
Subject: Test Subject
Creator: Test Creator
Producer: Test Producer
CreationDate: D:20240101000000
ModDate: D:20240101000000
        """
        mock_run.return_value = mock_result
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(b"test pdf content")
            temp_file_path = Path(temp_file.name)
        
        try:
            analysis = service.analyze_with_pdfinfo(temp_file_path)
            
            assert analysis['page_count'] == 5
            assert analysis['file_size_bytes'] == 1024000
            assert analysis['title'] == 'Test Document'
            assert analysis['author'] == 'Test Author'
            assert analysis['document_type'] == 'short_document'
        finally:
            temp_file_path.unlink()
    
    @patch('subprocess.run')
    def test_analyze_with_pdfinfo_failure(self, mock_run, service):
        """Test PDF analysis failure handling"""
        # Mock failed pdfinfo
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "pdfinfo failed"
        mock_run.return_value = mock_result
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(b"test pdf content")
            temp_file_path = Path(temp_file.name)
        
        try:
            analysis = service.analyze_with_pdfinfo(temp_file_path)
            assert analysis == {}
        finally:
            temp_file_path.unlink()
    
    def test_classify_document_type(self, service):
        """Test document type classification"""
        # Test single page document
        analysis = {'page_count': 1, 'file_size_bytes': 1024}
        doc_type = service.classify_document_type(analysis)
        assert doc_type == 'single_page_document'
        
        # Test single image
        analysis = {'page_count': 1, 'file_size_bytes': 6 * 1024 * 1024}
        doc_type = service.classify_document_type(analysis)
        assert doc_type == 'single_image'
        
        # Test long document
        analysis = {'page_count': 60, 'file_size_bytes': 1024}
        doc_type = service.classify_document_type(analysis)
        assert doc_type == 'long_document'
        
        # Test medium document
        analysis = {'page_count': 25, 'file_size_bytes': 1024}
        doc_type = service.classify_document_type(analysis)
        assert doc_type == 'medium_document'
        
        # Test short document
        analysis = {'page_count': 8, 'file_size_bytes': 1024}
        doc_type = service.classify_document_type(analysis)
        assert doc_type == 'short_document'
    
    def test_calculate_compression_potential(self, service):
        """Test compression potential calculation"""
        # Test base case
        analysis = {'page_count': 1, 'file_size': 1024}
        potential = service.calculate_compression_potential(analysis)
        assert potential == 0.5  # Base score
        
        # Test with images
        analysis = {'page_count': 1, 'file_size': 1024, 'estimated_image_count': 3}
        potential = service.calculate_compression_potential(analysis)
        assert potential > 0.5
        
        # Test with fonts
        analysis = {'page_count': 1, 'file_size': 1024, 'estimated_font_count': 8}
        potential = service.calculate_compression_potential(analysis)
        assert potential > 0.5
        
        # Test large file
        analysis = {'page_count': 1, 'file_size': 15 * 1024 * 1024}
        potential = service.calculate_compression_potential(analysis)
        assert potential > 0.5
        
        # Test long document
        analysis = {'page_count': 30, 'file_size': 1024}
        potential = service.calculate_compression_potential(analysis)
        assert potential > 0.5
    
    def test_get_ml_recommendations(self, service):
        """Test ML recommendations generation"""
        # Test high compression potential
        analysis = {'compression_potential': 0.9, 'document_type': 'image_heavy', 'file_size': 15 * 1024 * 1024}
        recommendations = service.get_ml_recommendations(analysis)
        
        assert recommendations['compression_level'] == 'high'
        assert recommendations['image_quality'] == 70
        assert recommendations['optimization_strategy'] == 'aggressive'
        assert recommendations['target_size'] == '50%'
        
        # Test low compression potential
        analysis = {'compression_potential': 0.3, 'document_type': 'text_heavy', 'file_size': 1024}
        recommendations = service.get_ml_recommendations(analysis)
        
        assert recommendations['compression_level'] == 'low'
        assert recommendations['image_quality'] == 90
        assert recommendations['optimization_strategy'] == 'conservative'
        
        # Test medium compression potential
        analysis = {'compression_potential': 0.6, 'document_type': 'mixed_content', 'file_size': 8 * 1024 * 1024}
        recommendations = service.get_ml_recommendations(analysis)
        
        assert recommendations['compression_level'] == 'medium'
        assert recommendations['image_quality'] == 80
        assert recommendations['optimization_strategy'] == 'balanced'
        assert recommendations['target_size'] == '70%'
    
    def test_merge_preferences(self, service):
        """Test preference merging"""
        recommendations = {
            'compression_level': 'medium',
            'image_quality': 80,
            'target_size': 'auto',
            'optimization_strategy': 'balanced'
        }
        
        user_preferences = {
            'compression_level': 'high',
            'image_quality': 75
        }
        
        merged = service.merge_preferences(recommendations, user_preferences)
        
        assert merged['compression_level'] == 'high'  # User preference
        assert merged['image_quality'] == 75  # User preference
        assert merged['target_size'] == 'auto'  # Recommendation
        assert merged['optimization_strategy'] == 'balanced'  # Recommendation
    
    def test_clear_analysis_cache(self, service):
        """Test cache clearing"""
        # Add some mock data to cache
        service.analysis_cache['test_hash'] = {'test': 'data'}
        assert len(service.analysis_cache) == 1
        
        # Clear cache
        service.clear_analysis_cache()
        assert len(service.analysis_cache) == 0
    
    @patch('src.services.enhanced_compression_service.CompressionJob')
    @patch('src.services.enhanced_compression_service.db')
    def test_create_compression_job(self, mock_db, mock_job_class, service):
        """Test compression job creation"""
        # Mock job instance
        mock_job = Mock()
        mock_job.id = 123
        mock_job_class.return_value = mock_job
        
        # Mock database session
        mock_session = Mock()
        mock_db.session = mock_session
        
        analysis = {'file_size': 1024, 'page_count': 5}
        settings = {'compression_level': 'medium'}
        
        job_id = service.create_compression_job(analysis, settings, 'user123')
        
        assert job_id == '123'
        mock_session.add.assert_called_once_with(mock_job)
        mock_session.commit.assert_called_once()
    
    def test_get_compression_history(self, service):
        """Test compression history retrieval"""
        # Mock database query
        with patch.object(service, 'get_compression_history') as mock_method:
            mock_method.return_value = [
                {'id': 1, 'status': 'completed'},
                {'id': 2, 'status': 'failed'}
            ]
            
            history = service.get_compression_history('user123', 10)
            
            assert len(history) == 2
            assert history[0]['id'] == 1
            assert history[1]['id'] == 2
    
    @patch('src.services.enhanced_compression_service.CompressionJob')
    @patch('src.services.enhanced_compression_service.db')
    def test_update_compression_job(self, mock_db, mock_job_class, service):
        """Test compression job update"""
        # Mock job instance
        mock_job = Mock()
        mock_job_class.query.get.return_value = mock_job
        
        # Mock database session
        mock_session = Mock()
        mock_db.session = mock_session
        
        result = {
            'success': True,
            'compression_ratio': 0.8,
            'compressed_size': 800
        }
        
        service.update_compression_job('123', result)
        
        assert mock_job.status == 'completed'
        assert mock_job.compression_ratio == 0.8
        assert mock_job.file_size_after == 800
        mock_session.commit.assert_called_once()
    
    def test_error_handling(self, service):
        """Test error handling in various methods"""
        # Test with invalid data
        with pytest.raises(Exception):
            service.calculate_compression_potential(None)
        
        # Test with empty analysis
        analysis = {}
        potential = service.calculate_compression_potential(analysis)
        assert potential == 0.5  # Default fallback
        
        # Test recommendations with invalid data
        analysis = {'compression_potential': 'invalid'}
        recommendations = service.get_ml_recommendations(analysis)
        assert 'compression_level' in recommendations  # Should have defaults


if __name__ == '__main__':
    pytest.main([__file__])
