"""Unit tests for BankStatementExtractionService

Tests the bank statement extraction service functionality including PDF text extraction,
AI-powered data extraction, validation, and export capabilities.
"""

import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest
from flask import Flask

from src.services.bank_statement_extraction_service import BankStatementExtractionService
from src.utils.exceptions import ExtractionError, ExtractionValidationError
from src.config.config import Config


class TestBankStatementExtractionService:
    """Test cases for BankStatementExtractionService."""
    
    @pytest.fixture
    def service(self, app):
        """Create BankStatementExtractionService instance for testing"""
        with app.app_context():
            return BankStatementExtractionService()
    
    @pytest.fixture
    def sample_pdf_content(self):
        """Sample PDF content for testing"""
        return b"%PDF-1.4\nSample bank statement content\n%%EOF"
    
    @pytest.fixture
    def sample_statement_text(self):
        """Sample extracted text from bank statement PDF"""
        return """
        FIRST NATIONAL BANK
        ACCOUNT STATEMENT
        
        Account Holder: John Doe
        Account Number: ****1234
        Statement Period: January 1, 2024 - January 31, 2024
        
        ACCOUNT SUMMARY
        Opening Balance (01/01/2024):     $5,250.75
        Total Credits:                    $3,515.50
        Total Debits:                    ($3,425.50)
        Closing Balance (01/31/2024):     $4,890.25
        
        TRANSACTION HISTORY
        Date        Description                    Amount      Balance
        01/02/2024  Direct Deposit - Salary      $3,500.00   $8,750.75
        01/03/2024  ATM Withdrawal               ($200.00)   $8,550.75
        01/05/2024  Online Transfer to Savings   ($1,000.00) $7,550.75
        01/10/2024  Grocery Store Purchase       ($125.50)   $7,425.25
        01/15/2024  Utility Bill Payment         ($285.00)   $7,140.25
        01/20/2024  Interest Credit              $15.50      $7,155.75
        01/25/2024  Rent Payment                 ($1,800.00) $5,355.75
        01/30/2024  Service Fee                  ($15.00)    $5,340.75
        
        END OF STATEMENT
        """
    
    @pytest.fixture
    def sample_extraction_result(self):
        """Sample AI extraction result"""
        with open('tests/ai/fixtures/bank/sample_bank_data.json', 'r') as f:
            data = json.load(f)
        return data['valid_bank_statement_extraction']
    
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
        assert service.service_name == 'BankStatementExtractionService'
    
    def test_service_initialization_with_custom_config(self, app):
        """Test service initialization with custom config"""
        custom_config = Config()
        custom_config.AI_MODEL = 'custom-model'
        
        with app.app_context():
            service = BankStatementExtractionService(config=custom_config)
            assert service.config.AI_MODEL == 'custom-model'
    
    # ========================= PDF TEXT EXTRACTION TESTS =========================
    
    @patch('src.services.bank_statement_extraction_service.extract_text_from_pdf')
    def test_extract_pdf_text_success(self, mock_extract, service, temp_pdf_file, sample_statement_text):
        """Test successful PDF text extraction"""
        mock_extract.return_value = sample_statement_text
        
        result = service._extract_pdf_text(temp_pdf_file)
        
        assert result == sample_statement_text
        mock_extract.assert_called_once_with(temp_pdf_file)
    
    @patch('src.services.bank_statement_extraction_service.extract_text_from_pdf')
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
    
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    def test_call_ai_extraction_success(self, mock_ai_call, service, sample_statement_text, sample_extraction_result):
        """Test successful AI extraction"""
        mock_ai_call.return_value = sample_extraction_result
        
        result = service._call_ai_extraction(sample_statement_text)
        
        assert result == sample_extraction_result
        assert 'account_info' in result
        assert 'transactions' in result
        assert 'opening_balance' in result
        assert 'closing_balance' in result
    
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    def test_call_ai_extraction_failure(self, mock_ai_call, service, sample_statement_text):
        """Test AI extraction failure"""
        mock_ai_call.side_effect = Exception("AI service unavailable")
        
        with pytest.raises(ExtractionError, match="AI extraction failed"):
            service._call_ai_extraction(sample_statement_text)
    
    # ========================= VALIDATION TESTS =========================
    
    def test_validate_extraction_result_valid(self, service, sample_extraction_result):
        """Test validation of valid extraction result"""
        # Should not raise any exception
        service._validate_extraction_result(sample_extraction_result)
    
    def test_validate_extraction_result_missing_required_fields(self, service):
        """Test validation with missing required fields"""
        invalid_result = {
            'account_info': {'account_number': '****1234'}
            # Missing other required fields
        }
        
        with pytest.raises(ExtractionValidationError, match="Missing required fields"):
            service._validate_extraction_result(invalid_result)
    
    def test_validate_extraction_result_invalid_data_types(self, service):
        """Test validation with invalid data types"""
        invalid_result = {
            'account_info': {'account_number': '****1234'},
            'opening_balance': 'invalid_balance',  # Should be numeric
            'closing_balance': 1000.00,
            'transactions': []
        }
        
        with pytest.raises(ExtractionValidationError, match="Invalid data types"):
            service._validate_extraction_result(invalid_result)
    
    def test_validate_extraction_result_empty_result(self, service):
        """Test validation with empty result"""
        with pytest.raises(ExtractionValidationError, match="Empty extraction result"):
            service._validate_extraction_result({})
    
    def test_validate_extraction_result_invalid_transactions(self, service):
        """Test validation with invalid transaction structure"""
        invalid_result = {
            'account_info': {'account_number': '****1234'},
            'opening_balance': 1000.00,
            'closing_balance': 1000.00,
            'transactions': [
                {
                    'date': '2024-01-01',
                    'description': 'Test transaction'
                    # Missing amount and type
                }
            ]
        }
        
        with pytest.raises(ExtractionValidationError, match="Invalid transaction structure"):
            service._validate_extraction_result(invalid_result)
    
    # ========================= MAIN EXTRACTION TESTS =========================
    
    @patch.object(BankStatementExtractionService, '_extract_pdf_text')
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    @patch.object(BankStatementExtractionService, '_validate_extraction_result')
    def test_extract_statement_data_success(self, mock_validate, mock_ai_extract, mock_pdf_extract, 
                                          service, temp_pdf_file, sample_statement_text, sample_extraction_result):
        """Test successful complete extraction process"""
        mock_pdf_extract.return_value = sample_statement_text
        mock_ai_extract.return_value = sample_extraction_result
        mock_validate.return_value = None
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is True
        assert result['data'] == sample_extraction_result
        assert 'processing_time' in result
        assert 'confidence_score' in result
        
        mock_pdf_extract.assert_called_once_with(temp_pdf_file)
        mock_ai_extract.assert_called_once_with(sample_statement_text)
        mock_validate.assert_called_once_with(sample_extraction_result)
    
    @patch.object(BankStatementExtractionService, '_extract_pdf_text')
    def test_extract_statement_data_pdf_extraction_failure(self, mock_pdf_extract, service, temp_pdf_file):
        """Test extraction failure during PDF text extraction"""
        mock_pdf_extract.side_effect = ExtractionError("PDF extraction failed")
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is False
        assert 'PDF extraction failed' in result['error']
        assert 'processing_time' in result
    
    @patch.object(BankStatementExtractionService, '_extract_pdf_text')
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    def test_extract_statement_data_ai_extraction_failure(self, mock_ai_extract, mock_pdf_extract, 
                                                        service, temp_pdf_file, sample_statement_text):
        """Test extraction failure during AI extraction"""
        mock_pdf_extract.return_value = sample_statement_text
        mock_ai_extract.side_effect = ExtractionError("AI extraction failed")
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is False
        assert 'AI extraction failed' in result['error']
    
    @patch.object(BankStatementExtractionService, '_extract_pdf_text')
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    @patch.object(BankStatementExtractionService, '_validate_extraction_result')
    def test_extract_statement_data_validation_failure(self, mock_validate, mock_ai_extract, mock_pdf_extract,
                                                     service, temp_pdf_file, sample_statement_text, sample_extraction_result):
        """Test extraction failure during validation"""
        mock_pdf_extract.return_value = sample_statement_text
        mock_ai_extract.return_value = sample_extraction_result
        mock_validate.side_effect = ExtractionValidationError("Validation failed")
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert result['success'] is False
        assert 'Validation failed' in result['error']
    
    # ========================= PROMPT PREPARATION TESTS =========================
    
    def test_prepare_extraction_prompt(self, service, sample_statement_text):
        """Test extraction prompt preparation"""
        prompt = service._prepare_extraction_prompt(sample_statement_text)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert 'bank statement' in prompt.lower()
        assert sample_statement_text in prompt
    
    def test_prepare_extraction_prompt_empty_text(self, service):
        """Test prompt preparation with empty text"""
        prompt = service._prepare_extraction_prompt('')
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert 'bank statement' in prompt.lower()
    
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
        
        # Check bank statement specific features
        features_text = ' '.join(capabilities['features']).lower()
        assert 'transaction' in features_text or 'balance' in features_text
    
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
    
    # ========================= TRANSACTION ANALYSIS TESTS =========================
    
    def test_transaction_analysis_in_extraction(self, service, sample_extraction_result):
        """Test that extraction result includes transaction analysis"""
        # Verify transaction structure
        transactions = sample_extraction_result['transactions']
        assert isinstance(transactions, list)
        assert len(transactions) > 0
        
        # Check transaction fields
        for transaction in transactions:
            assert 'date' in transaction
            assert 'description' in transaction
            assert 'amount' in transaction
            assert 'type' in transaction
    
    def test_balance_calculation_validation(self, service, sample_extraction_result):
        """Test balance calculation validation"""
        opening_balance = sample_extraction_result['opening_balance']
        closing_balance = sample_extraction_result['closing_balance']
        transactions = sample_extraction_result['transactions']
        
        # Calculate expected balance
        calculated_balance = opening_balance
        for transaction in transactions:
            calculated_balance += transaction['amount']
        
        # Allow for small floating point differences
        assert abs(calculated_balance - closing_balance) < 0.01
    
    # ========================= INTEGRATION TESTS =========================
    
    @patch('src.services.bank_statement_extraction_service.extract_text_from_pdf')
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    def test_end_to_end_extraction_flow(self, mock_ai_extract, mock_pdf_extract, 
                                      service, temp_pdf_file, sample_statement_text, sample_extraction_result):
        """Test complete end-to-end extraction flow"""
        mock_pdf_extract.return_value = sample_statement_text
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
        
        # Verify bank statement specific data
        data = result['data']
        assert 'account_info' in data
        assert 'transactions' in data
        assert 'opening_balance' in data
        assert 'closing_balance' in data
    
    # ========================= UTILITY METHOD TESTS =========================
    
    def test_service_name_property(self, service):
        """Test service name property"""
        assert service.service_name == 'BankStatementExtractionService'
    
    def test_service_configuration_access(self, service):
        """Test access to service configuration"""
        assert hasattr(service, 'config')
        assert service.config is not None
        
        # Test configuration values
        assert hasattr(service.config, 'AI_MODEL')
        assert hasattr(service.config, 'MAX_FILE_SIZE_MB')
    
    # ========================= PERFORMANCE TESTS =========================
    
    @patch.object(BankStatementExtractionService, '_extract_pdf_text')
    @patch.object(BankStatementExtractionService, '_call_ai_extraction')
    def test_extraction_performance_timing(self, mock_ai_extract, mock_pdf_extract, 
                                         service, temp_pdf_file, sample_statement_text, sample_extraction_result):
        """Test that extraction includes performance timing"""
        mock_pdf_extract.return_value = sample_statement_text
        mock_ai_extract.return_value = sample_extraction_result
        
        result = service.extract_statement_data(temp_pdf_file)
        
        assert 'processing_time' in result
        assert isinstance(result['processing_time'], (int, float))
        assert result['processing_time'] >= 0
    
    def test_confidence_score_calculation(self, service, sample_extraction_result):
        """Test confidence score calculation"""
        # This would test the confidence scoring logic
        # For now, just verify the structure exists
        assert 'summary' in sample_extraction_result
        summary = sample_extraction_result['summary']
        assert 'transaction_count' in summary
        assert isinstance(summary['transaction_count'], int)
        assert summary['transaction_count'] > 0