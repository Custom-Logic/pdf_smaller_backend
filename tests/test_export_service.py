"""Unit tests for ExportService

Tests the export service functionality including JSON, CSV, and Excel export
capabilities for invoice and bank statement data.
"""

import os
import json
import tempfile
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import pytest
from flask import Flask

from src.services.export_service import ExportService
from src.utils.exceptions import ExportError
from src.config.config import Config


class TestExportService:
    """Test cases for ExportService."""
    
    @pytest.fixture
    def service(self, app):
        """Create ExportService instance for testing"""
        with app.app_context():
            return ExportService()
    
    @pytest.fixture
    def sample_invoice_data(self):
        """Sample invoice data for export testing"""
        with open('tests/ai/fixtures/invoices/sample_invoice_data.json', 'r') as f:
            data = json.load(f)
        return data['valid_invoice_extraction']
    
    @pytest.fixture
    def sample_bank_data(self):
        """Sample bank statement data for export testing"""
        with open('tests/ai/fixtures/bank/sample_bank_data.json', 'r') as f:
            data = json.load(f)
        return data['valid_bank_statement_extraction']
    
    @pytest.fixture
    def temp_export_dir(self):
        """Create temporary directory for export testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    # ========================= INITIALIZATION TESTS =========================
    
    def test_service_initialization(self, service):
        """Test service initialization"""
        assert service.config is not None
        assert hasattr(service, 'file_service')
        assert service.service_name == 'ExportService'
    
    def test_service_initialization_with_custom_config(self, app):
        """Test service initialization with custom config"""
        custom_config = Config()
        custom_config.EXPORT_MAX_RECORDS = 5000
        
        with app.app_context():
            service = ExportService(config=custom_config)
            assert service.config.EXPORT_MAX_RECORDS == 5000
    
    # ========================= JSON EXPORT TESTS =========================
    
    def test_export_invoice_to_json_success(self, service, sample_invoice_data, temp_export_dir):
        """Test successful invoice JSON export"""
        output_path = os.path.join(temp_export_dir, 'invoice_export.json')
        
        result = service.export_invoice_to_json(sample_invoice_data, output_path)
        
        assert result['success'] is True
        assert result['file_path'] == output_path
        assert os.path.exists(output_path)
        
        # Verify exported content
        with open(output_path, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data == sample_invoice_data
        assert 'invoice_number' in exported_data
        assert 'total_amount' in exported_data
    
    def test_export_bank_statement_to_json_success(self, service, sample_bank_data, temp_export_dir):
        """Test successful bank statement JSON export"""
        output_path = os.path.join(temp_export_dir, 'bank_export.json')
        
        result = service.export_bank_statement_to_json(sample_bank_data, output_path)
        
        assert result['success'] is True
        assert result['file_path'] == output_path
        assert os.path.exists(output_path)
        
        # Verify exported content
        with open(output_path, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data == sample_bank_data
        assert 'account_info' in exported_data
        assert 'transactions' in exported_data
    
    def test_export_to_json_invalid_path(self, service, sample_invoice_data):
        """Test JSON export with invalid output path"""
        invalid_path = '/invalid/directory/export.json'
        
        result = service.export_invoice_to_json(sample_invoice_data, invalid_path)
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_export_to_json_empty_data(self, service, temp_export_dir):
        """Test JSON export with empty data"""
        output_path = os.path.join(temp_export_dir, 'empty_export.json')
        
        result = service.export_invoice_to_json({}, output_path)
        
        assert result['success'] is True
        assert os.path.exists(output_path)
        
        with open(output_path, 'r') as f:
            exported_data = json.load(f)
        assert exported_data == {}
    
    # ========================= CSV EXPORT TESTS =========================
    
    def test_export_invoice_to_csv_success(self, service, sample_invoice_data, temp_export_dir):
        """Test successful invoice CSV export"""
        output_path = os.path.join(temp_export_dir, 'invoice_export.csv')
        
        result = service.export_invoice_to_csv(sample_invoice_data, output_path)
        
        assert result['success'] is True
        assert result['file_path'] == output_path
        assert os.path.exists(output_path)
        
        # Verify CSV content
        df = pd.read_csv(output_path)
        assert len(df) > 0
        
        # Check for expected columns
        expected_columns = ['invoice_number', 'date', 'vendor_name', 'total_amount']
        for col in expected_columns:
            assert col in df.columns
    
    def test_export_bank_statement_to_csv_success(self, service, sample_bank_data, temp_export_dir):
        """Test successful bank statement CSV export"""
        output_path = os.path.join(temp_export_dir, 'bank_export.csv')
        
        result = service.export_bank_statement_to_csv(sample_bank_data, output_path)
        
        assert result['success'] is True
        assert result['file_path'] == output_path
        assert os.path.exists(output_path)
        
        # Verify CSV content
        df = pd.read_csv(output_path)
        assert len(df) > 0
        
        # Check for expected columns
        expected_columns = ['date', 'description', 'amount', 'type', 'balance']
        for col in expected_columns:
            assert col in df.columns
        
        # Verify transaction count matches
        assert len(df) == len(sample_bank_data['transactions'])
    
    def test_export_invoice_items_to_csv(self, service, sample_invoice_data, temp_export_dir):
        """Test CSV export of invoice line items"""
        output_path = os.path.join(temp_export_dir, 'invoice_items.csv')
        
        result = service.export_invoice_to_csv(sample_invoice_data, output_path)
        
        assert result['success'] is True
        
        # Check if items are properly exported
        df = pd.read_csv(output_path)
        if 'items' in sample_invoice_data and sample_invoice_data['items']:
            # Should have item-related columns or separate items export
            assert len(df) >= len(sample_invoice_data['items'])
    
    # ========================= EXCEL EXPORT TESTS =========================
    
    def test_export_invoice_to_excel_success(self, service, sample_invoice_data, temp_export_dir):
        """Test successful invoice Excel export"""
        output_path = os.path.join(temp_export_dir, 'invoice_export.xlsx')
        
        result = service.export_invoice_to_excel(sample_invoice_data, output_path)
        
        assert result['success'] is True
        assert result['file_path'] == output_path
        assert os.path.exists(output_path)
        
        # Verify Excel content
        df = pd.read_excel(output_path)
        assert len(df) > 0
        
        # Check for expected columns
        expected_columns = ['invoice_number', 'date', 'vendor_name', 'total_amount']
        for col in expected_columns:
            assert col in df.columns
    
    def test_export_bank_statement_to_excel_success(self, service, sample_bank_data, temp_export_dir):
        """Test successful bank statement Excel export"""
        output_path = os.path.join(temp_export_dir, 'bank_export.xlsx')
        
        result = service.export_bank_statement_to_excel(sample_bank_data, output_path)
        
        assert result['success'] is True
        assert result['file_path'] == output_path
        assert os.path.exists(output_path)
        
        # Verify Excel content
        df = pd.read_excel(output_path)
        assert len(df) > 0
        
        # Check for expected columns
        expected_columns = ['date', 'description', 'amount', 'type']
        for col in expected_columns:
            assert col in df.columns
    
    def test_export_to_excel_multiple_sheets(self, service, sample_invoice_data, temp_export_dir):
        """Test Excel export with multiple sheets"""
        output_path = os.path.join(temp_export_dir, 'multi_sheet_export.xlsx')
        
        result = service.export_invoice_to_excel(sample_invoice_data, output_path)
        
        assert result['success'] is True
        
        # Check if multiple sheets are created (summary + items)
        excel_file = pd.ExcelFile(output_path)
        sheet_names = excel_file.sheet_names
        
        # Should have at least one sheet
        assert len(sheet_names) >= 1
        
        # If items exist, should have items sheet
        if 'items' in sample_invoice_data and sample_invoice_data['items']:
            assert any('item' in sheet.lower() for sheet in sheet_names)
    
    # ========================= DATA TRANSFORMATION TESTS =========================
    
    def test_flatten_invoice_data(self, service, sample_invoice_data):
        """Test invoice data flattening for tabular export"""
        # This tests internal data transformation logic
        flattened = service._flatten_invoice_data(sample_invoice_data)
        
        assert isinstance(flattened, dict)
        assert 'invoice_number' in flattened
        assert 'vendor_name' in flattened
        assert 'customer_name' in flattened
        assert 'total_amount' in flattened
    
    def test_flatten_bank_statement_data(self, service, sample_bank_data):
        """Test bank statement data flattening for tabular export"""
        # This tests internal data transformation logic
        transactions_list = service._flatten_bank_statement_data(sample_bank_data)
        
        assert isinstance(transactions_list, list)
        assert len(transactions_list) == len(sample_bank_data['transactions'])
        
        # Check first transaction structure
        if transactions_list:
            transaction = transactions_list[0]
            assert 'date' in transaction
            assert 'description' in transaction
            assert 'amount' in transaction
            assert 'account_number' in transaction
    
    # ========================= FORMAT VALIDATION TESTS =========================
    
    def test_validate_export_format_valid(self, service):
        """Test validation of valid export formats"""
        valid_formats = ['json', 'csv', 'excel', 'xlsx']
        
        for format_type in valid_formats:
            assert service._validate_export_format(format_type) is True
    
    def test_validate_export_format_invalid(self, service):
        """Test validation of invalid export formats"""
        invalid_formats = ['pdf', 'xml', 'txt', 'doc']
        
        for format_type in invalid_formats:
            assert service._validate_export_format(format_type) is False
    
    # ========================= FILE MANAGEMENT TESTS =========================
    
    def test_cleanup_export_files(self, service, temp_export_dir):
        """Test cleanup of export files"""
        # Create some test export files
        test_files = [
            os.path.join(temp_export_dir, 'export1.json'),
            os.path.join(temp_export_dir, 'export2.csv'),
            os.path.join(temp_export_dir, 'export3.xlsx')
        ]
        
        for file_path in test_files:
            with open(file_path, 'w') as f:
                f.write('test content')
        
        # Verify files exist
        for file_path in test_files:
            assert os.path.exists(file_path)
        
        # Test cleanup
        result = service.cleanup_export_files(test_files)
        
        assert result['success'] is True
        assert result['files_cleaned'] == len(test_files)
        
        # Verify files are deleted
        for file_path in test_files:
            assert not os.path.exists(file_path)
    
    def test_cleanup_nonexistent_files(self, service):
        """Test cleanup of nonexistent files"""
        nonexistent_files = ['/path/to/nonexistent1.json', '/path/to/nonexistent2.csv']
        
        result = service.cleanup_export_files(nonexistent_files)
        
        assert result['success'] is True
        assert result['files_cleaned'] == 0
        assert len(result['errors']) == len(nonexistent_files)
    
    # ========================= CAPABILITIES TESTS =========================
    
    def test_get_export_capabilities(self, service):
        """Test getting export capabilities"""
        capabilities = service.get_export_capabilities()
        
        assert 'supported_formats' in capabilities
        assert 'max_records' in capabilities
        assert 'features' in capabilities
        
        # Check supported formats
        supported_formats = capabilities['supported_formats']
        assert 'json' in supported_formats
        assert 'csv' in supported_formats
        assert 'excel' in supported_formats
        
        # Check features
        features = capabilities['features']
        assert isinstance(features, list)
        assert len(features) > 0
    
    def test_get_format_specific_capabilities(self, service):
        """Test getting format-specific capabilities"""
        json_caps = service.get_format_capabilities('json')
        csv_caps = service.get_format_capabilities('csv')
        excel_caps = service.get_format_capabilities('excel')
        
        # JSON capabilities
        assert json_caps['preserves_structure'] is True
        assert json_caps['human_readable'] is True
        
        # CSV capabilities
        assert csv_caps['tabular_format'] is True
        assert csv_caps['excel_compatible'] is True
        
        # Excel capabilities
        assert excel_caps['multiple_sheets'] is True
        assert excel_caps['formatting_support'] is True
    
    # ========================= ERROR HANDLING TESTS =========================
    
    def test_export_with_permission_error(self, service, sample_invoice_data):
        """Test export with file permission errors"""
        # Try to write to a read-only location (simulated)
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            result = service.export_invoice_to_json(sample_invoice_data, '/readonly/path.json')
            
            assert result['success'] is False
            assert 'Permission denied' in result['error']
    
    def test_export_with_disk_full_error(self, service, sample_invoice_data):
        """Test export with disk full errors"""
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            result = service.export_invoice_to_json(sample_invoice_data, '/tmp/export.json')
            
            assert result['success'] is False
            assert 'No space left on device' in result['error']
    
    def test_export_with_invalid_data_structure(self, service, temp_export_dir):
        """Test export with invalid data structure"""
        invalid_data = "not a dictionary"
        output_path = os.path.join(temp_export_dir, 'invalid_export.json')
        
        result = service.export_invoice_to_json(invalid_data, output_path)
        
        assert result['success'] is False
        assert 'error' in result
    
    # ========================= INTEGRATION TESTS =========================
    
    def test_full_export_workflow_invoice(self, service, sample_invoice_data, temp_export_dir):
        """Test complete export workflow for invoice data"""
        # Test all formats
        formats = {
            'json': 'invoice_export.json',
            'csv': 'invoice_export.csv',
            'excel': 'invoice_export.xlsx'
        }
        
        export_files = []
        
        for format_type, filename in formats.items():
            output_path = os.path.join(temp_export_dir, filename)
            
            if format_type == 'json':
                result = service.export_invoice_to_json(sample_invoice_data, output_path)
            elif format_type == 'csv':
                result = service.export_invoice_to_csv(sample_invoice_data, output_path)
            elif format_type == 'excel':
                result = service.export_invoice_to_excel(sample_invoice_data, output_path)
            
            assert result['success'] is True
            assert os.path.exists(output_path)
            export_files.append(output_path)
        
        # Test cleanup
        cleanup_result = service.cleanup_export_files(export_files)
        assert cleanup_result['success'] is True
        assert cleanup_result['files_cleaned'] == len(export_files)
    
    def test_full_export_workflow_bank_statement(self, service, sample_bank_data, temp_export_dir):
        """Test complete export workflow for bank statement data"""
        # Test all formats
        formats = {
            'json': 'bank_export.json',
            'csv': 'bank_export.csv',
            'excel': 'bank_export.xlsx'
        }
        
        export_files = []
        
        for format_type, filename in formats.items():
            output_path = os.path.join(temp_export_dir, filename)
            
            if format_type == 'json':
                result = service.export_bank_statement_to_json(sample_bank_data, output_path)
            elif format_type == 'csv':
                result = service.export_bank_statement_to_csv(sample_bank_data, output_path)
            elif format_type == 'excel':
                result = service.export_bank_statement_to_excel(sample_bank_data, output_path)
            
            assert result['success'] is True
            assert os.path.exists(output_path)
            export_files.append(output_path)
        
        # Test cleanup
        cleanup_result = service.cleanup_export_files(export_files)
        assert cleanup_result['success'] is True
        assert cleanup_result['files_cleaned'] == len(export_files)
    
    # ========================= UTILITY METHOD TESTS =========================
    
    def test_service_name_property(self, service):
        """Test service name property"""
        assert service.service_name == 'ExportService'
    
    def test_service_configuration_access(self, service):
        """Test access to service configuration"""
        assert hasattr(service, 'config')
        assert service.config is not None
        
        # Test configuration values
        assert hasattr(service.config, 'EXPORT_MAX_RECORDS')
        assert hasattr(service.config, 'EXPORT_FORMATS')
    
    def test_get_supported_formats(self, service):
        """Test getting list of supported export formats"""
        formats = service.get_supported_formats()
        
        assert isinstance(formats, list)
        assert 'json' in formats
        assert 'csv' in formats
        assert 'excel' in formats
        assert len(formats) >= 3