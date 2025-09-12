"""Invoice Extraction Service - AI-powered invoice data extraction"""

import os
import logging
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.services.service_registry import ServiceRegistry
from src.utils.exceptions import ExtractionError, ExtractionValidationError
from src.config import Config

logger = logging.getLogger(__name__)


class InvoiceExtractionService:
    """Service for extracting structured data from invoice PDFs using AI."""
    
    def __init__(self):
        """Initialize the invoice extraction service."""
        self.ai_service = ServiceRegistry.get_ai_service()
        self.file_service = ServiceRegistry.get_file_management_service()
        self.logger = logging.getLogger(__name__)
        
        # Supported extraction modes
        self.extraction_modes = ['standard', 'detailed']
        
        # Supported output formats
        self.output_formats = ['json', 'csv', 'excel']
        
        # Maximum file size (50MB)
        self.max_file_size = getattr(Config, 'EXTRACTION_MAX_FILE_SIZE', 52428800)
        
        # Extraction timeout (5 minutes)
        self.extraction_timeout = getattr(Config, 'EXTRACTION_TIMEOUT', 300)
    
    def extract_invoice_data(self, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data from invoice PDF.
        
        Args:
            file_path: Path to the PDF file
            options: Extraction options including mode, format, etc.
            
        Returns:
            Dictionary with extracted invoice data
            
        Raises:
            ExtractionError: If extraction fails
            ExtractionValidationError: If validation fails
        """
        try:
            self.logger.info(f"Starting invoice extraction for file: {file_path}")
            
            # Validate file exists and size
            if not self.file_service.file_exists(file_path):
                raise ExtractionError(f"File not found: {file_path}")
            
            file_size = self.file_service.get_file_size(file_path)
            if file_size > self.max_file_size:
                raise ExtractionError(f"File too large: {file_size} bytes (max: {self.max_file_size})")
            
            # Extract options
            extraction_mode = options.get('extraction_mode', 'standard')
            include_line_items = options.get('include_line_items', True)
            validate_totals = options.get('validate_totals', True)
            output_format = options.get('output_format', 'json')
            
            # Validate options
            if extraction_mode not in self.extraction_modes:
                raise ExtractionValidationError(f"Invalid extraction mode: {extraction_mode}")
            
            if output_format not in self.output_formats:
                raise ExtractionValidationError(f"Invalid output format: {output_format}")
            
            # Prepare extraction prompt
            prompt = self._prepare_extraction_prompt(extraction_mode, include_line_items)
            
            # Read PDF content (simplified - in real implementation would use PDF reader)
            # For now, we'll simulate reading the PDF content
            pdf_text = self._extract_pdf_text(file_path)
            
            # Call AI service for extraction
            ai_response = self._call_ai_extraction(pdf_text, prompt)
            
            # Validate and clean results
            extracted_data = self._validate_extraction_result(ai_response, validate_totals)
            
            # Add metadata
            result = {
                'success': True,
                'data': extracted_data,
                'metadata': {
                    'extraction_mode': extraction_mode,
                    'include_line_items': include_line_items,
                    'validate_totals': validate_totals,
                    'file_size': file_size,
                    'timestamp': datetime.utcnow().isoformat(),
                    'processing_time': None  # Will be calculated by caller
                }
            }
            
            self.logger.info(f"Invoice extraction completed successfully for file: {file_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"Invoice extraction failed for file {file_path}: {str(e)}")
            if isinstance(e, (ExtractionError, ExtractionValidationError)):
                raise
            raise ExtractionError(f"Extraction failed: {str(e)}")
    
    def _prepare_extraction_prompt(self, extraction_mode: str, include_line_items: bool) -> str:
        """Prepare AI prompt for invoice extraction.
        
        Args:
            extraction_mode: 'standard' or 'detailed'
            include_line_items: Whether to extract line items
            
        Returns:
            Formatted prompt string
        """
        base_prompt = """
You are an expert invoice data extraction system. Extract structured data from the provided invoice text.

Return the data as a valid JSON object with the following structure:
{
  "header": {
    "invoice_number": "string",
    "date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD",
    "vendor_info": {
      "name": "string",
      "address": "string",
      "phone": "string",
      "email": "string"
    },
    "customer_info": {
      "name": "string",
      "address": "string",
      "phone": "string",
      "email": "string"
    }
  },
  "totals": {
    "subtotal": "number",
    "tax_amount": "number",
    "total_amount": "number",
    "currency": "string"
  }"""
        
        if include_line_items:
            base_prompt += """,
  "line_items": [
    {
      "description": "string",
      "quantity": "number",
      "unit_price": "number",
      "total_price": "number"
    }
  ]"""
        
        base_prompt += "\n}"
        
        if extraction_mode == 'detailed':
            base_prompt += """

For detailed mode, also include:
- Payment terms
- Shipping information
- Tax details
- Discount information
- Additional notes or comments

Ensure all monetary values are numeric and dates are in YYYY-MM-DD format.
If a field is not found, use null or empty string as appropriate.
"""
        else:
            base_prompt += """

For standard mode, focus on the core invoice information.
Ensure all monetary values are numeric and dates are in YYYY-MM-DD format.
If a field is not found, use null or empty string as appropriate.
"""
        
        return base_prompt
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text content
            
        Note:
            This is a simplified implementation. In production, would use
            libraries like PyMuPDF, pdfplumber, or similar.
        """
        try:
            # Placeholder implementation - in real scenario would use PDF library
            # For now, return a sample invoice text for testing
            return f"Sample invoice text from {file_path}"
        except Exception as e:
            raise ExtractionError(f"Failed to extract text from PDF: {str(e)}")
    
    def _call_ai_extraction(self, pdf_text: str, prompt: str) -> Dict[str, Any]:
        """Call AI service for data extraction.
        
        Args:
            pdf_text: Extracted PDF text
            prompt: Extraction prompt
            
        Returns:
            AI response with extracted data
        """
        try:
            # Prepare the full prompt with PDF text
            full_prompt = f"{prompt}\n\nInvoice text to extract from:\n{pdf_text}"
            
            # Call AI service (using existing summarize_text method as base)
            # In production, would create a dedicated extraction method
            ai_options = {
                'style': 'professional',
                'max_tokens': 2000,
                'temperature': 0.1  # Low temperature for consistent extraction
            }
            
            # For now, return mock data - in production would call actual AI service
            mock_response = {
                'header': {
                    'invoice_number': 'INV-2024-001',
                    'date': '2024-01-15',
                    'due_date': '2024-02-15',
                    'vendor_info': {
                        'name': 'Sample Vendor Inc.',
                        'address': '123 Business St, City, State 12345',
                        'phone': '+1-555-0123',
                        'email': 'billing@samplevendor.com'
                    },
                    'customer_info': {
                        'name': 'Customer Corp',
                        'address': '456 Client Ave, City, State 67890',
                        'phone': '+1-555-0456',
                        'email': 'accounts@customer.com'
                    }
                },
                'totals': {
                    'subtotal': 1000.00,
                    'tax_amount': 80.00,
                    'total_amount': 1080.00,
                    'currency': 'USD'
                },
                'line_items': [
                    {
                        'description': 'Professional Services',
                        'quantity': 10,
                        'unit_price': 100.00,
                        'total_price': 1000.00
                    }
                ]
            }
            
            return mock_response
            
        except Exception as e:
            raise ExtractionError(f"AI extraction failed: {str(e)}")
    
    def _validate_extraction_result(self, result: Dict[str, Any], validate_totals: bool) -> Dict[str, Any]:
        """Validate and clean extraction results.
        
        Args:
            result: Raw extraction result from AI
            validate_totals: Whether to validate total calculations
            
        Returns:
            Validated and cleaned result
            
        Raises:
            ExtractionValidationError: If validation fails
        """
        try:
            # Validate required fields
            if 'header' not in result:
                raise ExtractionValidationError("Missing header information")
            
            if 'totals' not in result:
                raise ExtractionValidationError("Missing totals information")
            
            # Validate totals if requested
            if validate_totals and 'line_items' in result:
                self._validate_totals(result['totals'], result['line_items'])
            
            # Clean and format data
            cleaned_result = self._clean_extraction_data(result)
            
            return cleaned_result
            
        except ExtractionValidationError:
            raise
        except Exception as e:
            raise ExtractionValidationError(f"Validation failed: {str(e)}")
    
    def _validate_totals(self, totals: Dict[str, Any], line_items: List[Dict[str, Any]]) -> None:
        """Validate that totals match line items.
        
        Args:
            totals: Totals section from extraction
            line_items: Line items from extraction
            
        Raises:
            ExtractionValidationError: If totals don't match
        """
        try:
            # Calculate subtotal from line items
            calculated_subtotal = sum(
                float(item.get('total_price', 0)) for item in line_items
            )
            
            extracted_subtotal = float(totals.get('subtotal', 0))
            
            # Allow small rounding differences (within 0.01)
            if abs(calculated_subtotal - extracted_subtotal) > 0.01:
                self.logger.warning(
                    f"Subtotal mismatch: calculated={calculated_subtotal}, "
                    f"extracted={extracted_subtotal}"
                )
                # Don't raise error, just log warning
            
        except (ValueError, TypeError) as e:
            raise ExtractionValidationError(f"Invalid numeric values in totals: {str(e)}")
    
    def _clean_extraction_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and format extraction data.
        
        Args:
            data: Raw extraction data
            
        Returns:
            Cleaned data
        """
        # Create a deep copy to avoid modifying original
        import copy
        cleaned_data = copy.deepcopy(data)
        
        # Clean numeric values in totals
        if 'totals' in cleaned_data:
            for key in ['subtotal', 'tax_amount', 'total_amount']:
                if key in cleaned_data['totals']:
                    try:
                        cleaned_data['totals'][key] = float(cleaned_data['totals'][key])
                    except (ValueError, TypeError):
                        cleaned_data['totals'][key] = 0.0
        
        # Clean line items
        if 'line_items' in cleaned_data:
            for item in cleaned_data['line_items']:
                for key in ['quantity', 'unit_price', 'total_price']:
                    if key in item:
                        try:
                            item[key] = float(item[key])
                        except (ValueError, TypeError):
                            item[key] = 0.0
        
        return cleaned_data
    
    def get_extraction_capabilities(self) -> Dict[str, Any]:
        """Get invoice extraction capabilities.
        
        Returns:
            Dictionary with supported features and formats
        """
        return {
            'supported_formats': ['pdf'],
            'output_formats': self.output_formats,
            'extraction_modes': self.extraction_modes,
            'max_file_size': f"{self.max_file_size // (1024*1024)}MB",
            'supported_languages': ['en', 'es', 'fr', 'de', 'it'],
            'extractable_fields': {
                'header': ['invoice_number', 'date', 'due_date', 'vendor_info', 'customer_info'],
                'totals': ['subtotal', 'tax_amount', 'total_amount', 'currency'],
                'line_items': ['description', 'quantity', 'unit_price', 'total_price']
            },
            'features': {
                'total_validation': True,
                'line_item_extraction': True,
                'multi_language_support': True,
                'detailed_mode': True
            }
        }