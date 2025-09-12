"""Service Registry - Centralized service instantiation and configuration

This module provides a centralized registry for managing service instances
across the application, ensuring consistent instantiation patterns and
reducing code duplication.
"""
from typing import Dict, Any, Optional
from src.config.config import Config
from src.services.file_management_service import FileManagementService
from src.services.compression_service import CompressionService
from src.services.ai_service import AIService
from src.services.conversion_service import ConversionService
from src.services.ocr_service import OCRService
from src.services.export_service import ExportService
from src.services.invoice_extraction_service import InvoiceExtractionService
from src.services.bank_statement_extraction_service import BankStatementExtractionService


class ServiceRegistry:
    """Centralized service management with singleton pattern for service instances"""
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def get_file_management_service(cls, upload_folder: Optional[str] = None) -> FileManagementService:
        """Get FileManagementService instance
        
        Args:
            upload_folder: Optional custom upload folder path
            
        Returns:
            FileManagementService instance
        """
        key = f"file_management_{upload_folder or 'default'}"
        if key not in cls._instances:
            cls._instances[key] = FileManagementService(upload_folder)
        return cls._instances[key]
    
    @classmethod
    def get_compression_service(cls) -> CompressionService:
        """Get CompressionService instance
        
        Returns:
            CompressionService instance
        """
        if 'compression' not in cls._instances:
            cls._instances['compression'] = CompressionService()
        return cls._instances['compression']
    
    @classmethod
    def get_ai_service(cls) -> AIService:
        """Get AIService instance
        
        Returns:
            AIService instance
        """
        if 'ai' not in cls._instances:
            cls._instances['ai'] = AIService()
        return cls._instances['ai']
    
    @classmethod
    def get_conversion_service(cls) -> ConversionService:
        """Get ConversionService instance
        
        Returns:
            ConversionService instance
        """
        if 'conversion' not in cls._instances:
            cls._instances['conversion'] = ConversionService()
        return cls._instances['conversion']
    
    @classmethod
    def get_ocr_service(cls) -> OCRService:
        """Get OCRService instance
        
        Returns:
            OCRService instance
        """
        if 'ocr' not in cls._instances:
            cls._instances['ocr'] = OCRService()
        return cls._instances['ocr']
    
    @classmethod
    def get_export_service(cls) -> ExportService:
        """Get ExportService instance
        
        Returns:
            ExportService instance
        """
        if 'export' not in cls._instances:
            cls._instances['export'] = ExportService()
        return cls._instances['export']
    
    @classmethod
    def get_invoice_extraction_service(cls) -> InvoiceExtractionService:
        """Get InvoiceExtractionService instance
        
        Returns:
            InvoiceExtractionService instance
        """
        if 'invoice_extraction' not in cls._instances:
            cls._instances['invoice_extraction'] = InvoiceExtractionService()
        return cls._instances['invoice_extraction']
    
    @classmethod
    def get_bank_statement_extraction_service(cls) -> BankStatementExtractionService:
        """Get BankStatementExtractionService instance
        
        Returns:
            BankStatementExtractionService instance
        """
        if 'bank_statement_extraction' not in cls._instances:
            cls._instances['bank_statement_extraction'] = BankStatementExtractionService()
        return cls._instances['bank_statement_extraction']
    
    @classmethod
    def clear_cache(cls):
        """Clear service cache (useful for testing)
        
        This method clears all cached service instances, forcing
        new instances to be created on next access.
        """
        cls._instances.clear()
    
    @classmethod
    def get_service_count(cls) -> int:
        """Get count of cached service instances
        
        Returns:
            Number of cached service instances
        """
        return len(cls._instances)
    
    @classmethod
    def list_cached_services(cls) -> list:
        """List all cached service keys
        
        Returns:
            List of cached service keys
        """
        return list(cls._instances.keys())