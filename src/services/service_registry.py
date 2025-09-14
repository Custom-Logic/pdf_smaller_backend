"""Service Registry - Centralized service instantiation and configuration

This module provides a centralized registry for managing service instances
across the application, ensuring consistent instantiation patterns and
reducing code duplication.
"""
from typing import Dict, Any, Optional


class ServiceRegistry:
    """Centralized service management with singleton pattern for service instances"""
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def get_file_management_service(cls, upload_folder: Optional[str] = None):
        """Get FileManagementService instance
        
        Args:
            upload_folder: Optional custom upload folder path
            
        Returns:
            FileManagementService instance
        """
        if 'file_management' not in cls._instances:
            from src.services.file_management_service import FileManagementService
            cls._instances['file_management'] = FileManagementService(upload_folder=upload_folder)
        return cls._instances['file_management']
    
    @classmethod
    def get_compression_service(cls):
        """Get CompressionService instance
        
        Returns:
            CompressionService instance
        """
        if 'compression' not in cls._instances:
            from src.services.compression_service import CompressionService
            cls._instances['compression'] = CompressionService()
        return cls._instances['compression']
    
    @classmethod
    def get_ai_service(cls):
        """Get AIService instance
        
        Returns:
            AIService instance
        """
        if 'ai' not in cls._instances:
            from src.services.ai_service import AIService
            cls._instances['ai'] = AIService()
        return cls._instances['ai']
    
    @classmethod
    def get_conversion_service(cls):
        """Get ConversionService instance
        
        Returns:
            ConversionService instance
        """
        if 'conversion' not in cls._instances:
            from src.services.conversion_service import ConversionService
            cls._instances['conversion'] = ConversionService()
        return cls._instances['conversion']
    
    @classmethod
    def get_ocr_service(cls):
        """Get OCRService instance
        
        Returns:
            OCRService instance
        """
        if 'ocr' not in cls._instances:
            from src.services.ocr_service import OCRService
            cls._instances['ocr'] = OCRService()
        return cls._instances['ocr']
    
    @classmethod
    def get_export_service(cls):
        """Get ExportService instance
        
        Returns:
            ExportService instance
        """
        if 'export' not in cls._instances:
            from src.services.export_service import ExportService
            file_service = cls.get_file_management_service()
            cls._instances['export'] = ExportService(file_service=file_service)
        return cls._instances['export']
    
    @classmethod
    def get_invoice_extraction_service(cls):
        """Get InvoiceExtractionService instance
        
        Returns:
            InvoiceExtractionService instance
        """
        if 'invoice_extraction' not in cls._instances:
            from src.services.invoice_extraction_service import InvoiceExtractionService
            cls._instances['invoice_extraction'] = InvoiceExtractionService()
        return cls._instances['invoice_extraction']
    
    @classmethod
    def get_bank_statement_extraction_service(cls):
        """Get BankStatementExtractionService instance
        
        Returns:
            BankStatementExtractionService instance
        """
        if 'bank_statement_extraction' not in cls._instances:
            from src.services.bank_statement_extraction_service import BankStatementExtractionService
            cls._instances['bank_statement_extraction'] = BankStatementExtractionService()
        return cls._instances['bank_statement_extraction']

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

    @classmethod
    def clear_cache(cls):
        """Clear service cache (useful for testing)

        This method clears all cached service instances, forcing
        new instances to be created on next access.
        """
        cls._instances.clear()
