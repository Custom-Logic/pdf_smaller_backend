"""Unit tests for InvoiceExtractionService

Tests the invoice extraction service functionality including PDF text extraction,
AI-powered data extraction, validation, and export capabilities.
"""

import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest
from flask import Flask

from src.services.invoice_extraction_service import InvoiceExtractionService
from src.utils.exceptions import ExtractionError, ExtractionValidationError
from src.config.config import Config


class TestInvoiceExtractionService:
    """Test cases for InvoiceExtractionService."""
    
    @pytest.fixture
    def service(self, app):
        """Create InvoiceExtractionService instance for testing"""
        with app.app_context():
            return InvoiceExtractionService()
    
    @pytest.fixture
    def sample_pdf_content(self):
        """Sample PDF content for testing"""
        return b"%PDF-1.4\nSample invoice content\n%%EOF"
    
    @pytest.fixture
    def sample_invoice_text(self):
        """Sample extracted text from invoice PDF"""
        return """
        INVOICE
        
        Invoice Number: INV-2024-001
        Date: January 15, 2024
        Due Date: February 15, 2024
        
        Bill To:
        ABC Corporation
        456 Corporate Ave
        Business City, BC 67890
        
        From:
        Tech Solutions Inc.
        123 Business St
        Tech City, TC 12345
        Phone: +1-555-0123
        Email: billing@techsolutions.com
        
        Description                    Qty    Unit Price    Total
        Software Development Services   40      $125.00     $5,000.00
        Technical Consultation          8      $150.00     $1,200.00
        
        Subtotal:                                          $6,200.00
        Tax (8%):                                            $496.00
        Total:                                             $6,696.00
        
        Payment Terms: Net 30
        """
    
    @pytest.fixture
    def sample_extraction_result(self):
        """Sample AI extraction result"""
        with open('tests/ai/fixtures/invoices/sample_invoice_data.json', 'r') as f:
            data = json.load(f)
        return data['valid_invoice_extraction']
    
    @pytest.fixture
    def temp_pdf_file(self, sample_pdf_content):
        """Create temporary PDF file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(sample_pdf_content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    # ========================= INITIALIZATION TESTS =========================
    
    def test_service_initialization(self, service):
        """Test service initialization"""
        assert service.config is not None
        assert hasattr(service, 'ai_service')
        assert hasattr(service, 'file_service')
        assert service.service_name == 'InvoiceExtractionService'
    
    def test_service_initialization_with_custom_config(self, app):
        """Test service initialization with custom config"""
        custom_config = Config()
        custom_config.AI_MODEL = 'custom-model'
        
        with app.app_context():
            service = InvoiceExtractionService(config=custom_config)
            assert service.config.AI_MODEL == 'custom-model'
    
    # ========================= PDF TEXT EXTRACTION TESTS =========================
    
    @patch('src.services.invoice_extraction_service.extract_text_from_pdf')
    def test_extract_pdf_text_success(self, mock_extract, service, temp_pdf_file, sample_invoice_text):
        """Test successful PDF text extraction"""
        mock_extract.return_value = sample_invoice_text
        
        result = service._extract_pdf_text(temp_pdf_file)
        
        assert result == sample_invoice_text
        mock_extract.assert_called_once_with(temp_pdf_file)
    
    @patch('src.services.invoice_extraction_service.extract_text_from_pdf')
    def test_extract_pdf_text_failure(self, mock_extract, service, temp_pdf_file):
        """Test PDF text extraction failure"""
        mock_extract.side_effect = Exception("PDF extraction failed")
        
        with pytest.raises(ExtractionError, match="Failed to extract text from PDF"):
            service._extract_pdf_text(temp_pdf_file)
    
    def test_extract_pdf_text_nonexistent_file(self, service):
        """Test PDF text extraction with nonexistent file"""
        with pytest.raises(ExtractionError, match="PDF file not found"):
            service._extract_pdf_text('/nonexistent/file.pdf')
    
    # ========================= AI EXTRACTION TESTS =========================
    
    @patch.object(InvoiceExtractionService, '_call_ai_extraction')
    def test_call_ai_extraction_success(self, mock_ai_call, service, sample_invoice_text, sample_extraction_result):
        """Test successful AI extraction"""
        mock_ai_call.return_value = sample_extraction_result
        
        result = service._call_ai_extraction(sample_invoice_text)
        
        assert result == sample_extraction_result
        assert 'invoice_number' in result
        assert 'total_amount' in result
    
    @patch.object(InvoiceExtractionService, '_call_ai_extraction')
    def test_call_ai_extraction_failure(self, mock_ai_call, service, sample_invoice_text):
        """Test AI extraction failure"""
        mock_ai_call.side_effect = Exception("AI service unavailable")
        
        with pytest.raises(ExtractionError, match="AI extraction failed"):
            service._call_ai_extraction(sample_invoice_text)
    
    # ========================= VALIDATION TESTS =========================
    
    def test_validate_extraction_result_valid(self, service, sample_extraction_result):
        """Test validation of valid extraction result"""
        # Should not raise any exception
        service._validate_extraction_result(sample_extraction_result)
    
    def test_validate_extraction_result_missing_required_fields(self, service):
        """Test validation with missing required fields"""
        invalid_result = {
            'invoice_number': 'INV-001'
            # Missing other required fields
        }
        
        with pytest.raises(ExtractionValidationError, match="Missing required fields"):
            service._validate_extraction_result(invalid_result)
    
    def test_validate_extraction_result_invalid_data_types(self, service):
        """Test validation with invalid data types"""
        invalid_result = {
            'invoice_number': 'INV-001',
            'total_amount': 'invalid_amount',  # Should be numeric
            'date': '2024-01-15'
        }
        
        with pytest.raises(ExtractionValidationError, match="Invalid data types"):
            service._validate_extraction_result(invalid_result)
    
    def test_validate_extraction_result_empty_result(self, service):
        """Test validation with empty result"""
        with pytest.raises(ExtractionValidationError, match="Empty extraction result"):
            service._validate_extraction_result({})
    
    # ========================= MAIN EXTRACTION TESTS =========================
    
    @patch.object(InvoiceExtractionService, '_extract_pdf_text')
    @patch.object(InvoiceExtractionService, '_call_ai_extraction')
    @patch.object(InvoiceExtractionService, '_validate_extraction_result')
    def test_extract_statement_data_success(self, mock_validate, mock_ai_extract, mock_pdf_extract, 
                                          service, temp_pdf_file, sample_invoice_text, sample_extraction_result):
        """Test successful complete extraction process"""
        mock_pdf_extract.return_value = sample_invoice_text
        mock_ai_extract.return_value = sample_extraction_result
        mock_validate.return_value = None
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is True
        assert result['data'] == sample_extraction_result
        assert 'processing_time' in result
        assert 'confidence_score' in result
        
        mock_pdf_extract.assert_called_once_with(temp_pdf_file)
        mock_ai_extract.assert_called_once_with(sample_invoice_text)
        mock_validate.assert_called_once_with(sample_extraction_result)
    
    @patch.object(InvoiceExtractionService, '_extract_pdf_text')
    def test_extract_statement_data_pdf_extraction_failure(self, mock_pdf_extract, service, temp_pdf_file):
        """Test extraction failure during PDF text extraction"""
        mock_pdf_extract.side_effect = ExtractionError("PDF extraction failed")
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is False
        assert 'PDF extraction failed' in result['error']
        assert 'processing_time' in result
    
    @patch.object(InvoiceExtractionService, '_extract_pdf_text')
    @patch.object(InvoiceExtractionService, '_call_ai_extraction')
    def test_extract_statement_data_ai_extraction_failure(self, mock_ai_extract, mock_pdf_extract, 
                                                        service, temp_pdf_file, sample_invoice_text):
        """Test extraction failure during AI extraction"""
        mock_pdf_extract.return_value = sample_invoice_text
        mock_ai_extract.side_effect = ExtractionError("AI extraction failed")
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is False
        assert 'AI extraction failed' in result['error']
    
    @patch.object(InvoiceExtractionService, '_extract_pdf_text')
    @patch.object(InvoiceExtractionService, '_call_ai_extraction')
    @patch.object(InvoiceExtractionService, '_validate_extraction_result')
    def test_extract_statement_data_validation_failure(self, mock_validate, mock_ai_extract, mock_pdf_extract,
                                                     service, temp_pdf_file, sample_invoice_text, sample_extraction_result):
        """Test extraction failure during validation"""
        mock_pdf_extract.return_value = sample_invoice_text
        mock_ai_extract.return_value = sample_extraction_result
        mock_validate.side_effect = ExtractionValidationError("Validation failed")
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is False
        assert 'Validation failed' in result['error']
    
    # ========================= PROMPT PREPARATION TESTS =========================
    
    def test_prepare_extraction_prompt(self, service, sample_invoice_text):
        """Test extraction prompt preparation"""
        prompt = service._prepare_extraction_prompt(sample_invoice_text)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert 'invoice' in prompt.lower()
        assert sample_invoice_text in prompt
    
    def test_prepare_extraction_prompt_empty_text(self, service):
        """Test prompt preparation with empty text"""
        prompt = service._prepare_extraction_prompt('')
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert 'invoice' in prompt.lower()
    
    # ========================= CAPABILITIES TESTS =========================
    
    def test_get_extraction_capabilities(self, service):
        """Test getting extraction capabilities"""
        capabilities = service.get_extraction_capabilities()
        
        assert 'supported_formats' in capabilities
        assert 'max_file_size_mb' in capabilities
        assert 'features' in capabilities
        assert 'processing_time_estimate' in capabilities
        
        # Check specific capabilities
        assert 'pdf' in capabilities['supported_formats']
        assert isinstance(capabilities['max_file_size_mb'], (int, float))
        assert isinstance(capabilities['features'], list)
        assert len(capabilities['features']) > 0
    
    # ========================= ERROR HANDLING TESTS =========================
    
    def test_extract_statement_data_invalid_file_path(self, service):
        """Test extraction with invalid file path"""
        result = service.extract_statement_data('/invalid/path/file.pdf')
        
        assert result['success'] is False
        assert 'error' in result
        assert 'processing_time' in result
    
    def test_extract_statement_data_none_file_path(self, service):
        """Test extraction with None file path"""
        result = service.extract_statement_data(None)
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_extract_statement_data_empty_file_path(self, service):
        """Test extraction with empty file path"""
        result = service.extract_statement_data('')
        
        assert result['success'] is False
        assert 'error' in result
    
    # ========================= INTEGRATION TESTS =========================
    
    @patch('src.services.invoice_extraction_service.extract_text_from_pdf')
    @patch.object(InvoiceExtractionService, '_call_ai_extraction')
    def test_end_to_end_extraction_flow(self, mock_ai_extract, mock_pdf_extract, 
                                      service, temp_pdf_file, sample_invoice_text, sample_extraction_result):
        """Test complete end-to-end extraction flow"""
        mock_pdf_extract.return_value = sample_invoice_text
        mock_ai_extract.return_value = sample_extraction_result
        
        result = service.extract_statement_data(temp_pdf_file)
        
        # Verify successful extraction
        assert result['success'] is True
        assert result['data'] == sample_extraction_result
        
        # Verify all steps were called
        mock_pdf_extract.assert_called_once()
        mock_ai_extract.assert_called_once()
        
        # Verify result structure
        assert 'processing_time' in result
        assert 'confidence_score' in result
        assert isinstance(result['processing_time'], (int, float))
        assert isinstance(result['confidence_score'], (int, float))
    
    # ========================= UTILITY METHOD TESTS =========================
    
    def test_service_name_property(self, service):
        """Test service name property"""
        assert service.service_name == 'InvoiceExtractionService'
    
    def test_service_configuration_access(self, service):
        """Test access to service configuration"""
        assert hasattr(service, 'config')
        assert service.config is not None
        
        # Test configuration values
        assert hasattr(service.config, 'AI_MODEL')
        assert hasattr(service.config, 'MAX_FILE_SIZE_MB')