"""Export Service - Handle data export to various formats (CSV, Excel, JSON)"""

import csv
import json
import logging
import os
from datetime import datetime, timezone
from mailbox import FormatError
from typing import Dict, Any, List, Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from src.utils.exceptions import ExportError
from src.config import Config

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting extracted data to various formats."""
    
    def __init__(self, file_service=None):
        """Initialize the export service.
        
        Args:
            file_service: Optional file management service instance
        """
        self.file_service = file_service
        self.logger = logging.getLogger(__name__)
        
        # Supported export formats
        self.supported_formats = ['json', 'csv', 'excel']
        
        # Export directory
        self.export_dir = os.path.join(Config.UPLOAD_FOLDER, 'exports')
        os.makedirs(self.export_dir, exist_ok=True)
        
        # Maximum export file size (100MB)
        self.max_export_size = 104857600
    
    def export_invoice_data(self, invoice_data: Dict[str, Any], export_format: str, 
                           filename: Optional[str] = None) -> Dict[str, Any]:
        """Export invoice data to specified format.
        
        Args:
            invoice_data: Extracted invoice data
            export_format: Export format ('json', 'csv', 'excel')
            filename: Optional custom filename
            
        Returns:
            Dictionary with export result and file path
            
        Raises:
            ExportError: If export fails
        """
        try:
            self.logger.info(f"Exporting invoice data to {export_format} format")
            
            # Validate format
            if export_format not in self.supported_formats:
                raise ExportError(f"Unsupported export format: {export_format}")
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"invoice_export_{timestamp}"
            
            # Export based on format
            if export_format == 'json':
                result = self._export_invoice_json(invoice_data, filename)
            elif export_format == 'csv':
                result = self._export_invoice_csv(invoice_data, filename)
            elif export_format == 'excel':
                result = self._export_invoice_excel(invoice_data, filename)
            else:
                raise FormatError('could not understand file format to export to')

            self.logger.info(f"Invoice data exported successfully to {result['output_path']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Invoice export failed: {str(e)}")
            if isinstance(e, ExportError):
                raise
            raise ExportError(f"Export failed: {str(e)}")
    
    def export_bank_statement_data(self, statement_data: Dict[str, Any], export_format: str,
                                  filename: Optional[str] = None) -> Dict[str, Any]:
        """Export bank statement data to specified format.
        
        Args:
            statement_data: Extracted bank statement data
            export_format: Export format ('json', 'csv', 'excel')
            filename: Optional custom filename
            
        Returns:
            Dictionary with export result and file path
            
        Raises:
            ExportError: If export fails
        """
        try:
            self.logger.info(f"Exporting bank statement data to {export_format} format")
            
            # Validate format
            if export_format not in self.supported_formats:
                raise ExportError(f"Unsupported export format: {export_format}")
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"bank_statement_export_{timestamp}"
            
            # Export based on format
            if export_format == 'json':
                result = self._export_statement_json(statement_data, filename)
            elif export_format == 'csv':
                result = self._export_statement_csv(statement_data, filename)
            elif export_format == 'excel':
                result = self._export_statement_excel(statement_data, filename)
            else:
                raise FormatError('could not understand file format to export to')

            self.logger.info(f"Bank statement data exported successfully to {result['output_path']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Bank statement export failed: {str(e)}")
            if isinstance(e, ExportError):
                raise
            raise ExportError(f"Export failed: {str(e)}")
    
    def _export_invoice_json(self, invoice_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Export invoice data to JSON format.
        
        Args:
            invoice_data: Invoice data to export
            filename: Base filename
            
        Returns:
            Export result with file path
        """
        try:
            output_path = os.path.join(self.export_dir, f"{filename}.json")
            
            # Prepare export data
            export_data = {
                'export_info': {
                    'type': 'invoice',
                    'format': 'json',
                    'exported_at': datetime.now(timezone.utc).isoformat(),
                    'version': '1.0'
                },
                'data': invoice_data
            }
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': os.path.basename(output_path),
                'format': 'json',
                'file_size': file_size,
                'mime_type': 'application/json'
            }
            
        except Exception as e:
            raise ExportError(f"JSON export failed: {str(e)}")
    
    def _export_invoice_csv(self, invoice_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Export invoice data to CSV format.
        
        Args:
            invoice_data: Invoice data to export
            filename: Base filename
            
        Returns:
            Export result with file path
        """
        try:
            output_path = os.path.join(self.export_dir, f"{filename}.csv")
            
            # Extract line items for CSV
            line_items = invoice_data.get('data', {}).get('line_items', [])
            
            if not line_items:
                # Create a summary CSV if no line items
                self._create_invoice_summary_csv(invoice_data, output_path)
            else:
                # Create detailed CSV with line items
                self._create_invoice_detailed_csv(invoice_data, output_path)
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': os.path.basename(output_path),
                'format': 'csv',
                'file_size': file_size,
                'mime_type': 'text/csv'
            }
            
        except Exception as e:
            raise ExportError(f"CSV export failed: {str(e)}")
    
    def _export_invoice_excel(self, invoice_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Export invoice data to Excel format.
        
        Args:
            invoice_data: Invoice data to export
            filename: Base filename
            
        Returns:
            Export result with file path
        """
        try:
            if not PANDAS_AVAILABLE:
                raise ExportError("Excel export requires pandas library")
            
            output_path = os.path.join(self.export_dir, f"{filename}.xlsx")
            
            # Create Excel writer
            # noinspection PyUnresolvedReferences
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Invoice summary sheet
                self._create_invoice_summary_sheet(invoice_data, writer)
                
                # Line items sheet
                line_items = invoice_data.get('data', {}).get('line_items', [])
                if line_items:
                    self._create_line_items_sheet(line_items, writer)
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': os.path.basename(output_path),
                'format': 'excel',
                'file_size': file_size,
                'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            
        except Exception as e:
            raise ExportError(f"Excel export failed: {str(e)}")
    
    def _export_statement_json(self, statement_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Export bank statement data to JSON format.
        
        Args:
            statement_data: Bank statement data to export
            filename: Base filename
            
        Returns:
            Export result with file path
        """
        try:
            output_path = os.path.join(self.export_dir, f"{filename}.json")
            
            # Prepare export data
            export_data = {
                'export_info': {
                    'type': 'bank_statement',
                    'format': 'json',
                    'exported_at': datetime.now(timezone.utc).isoformat(),
                    'version': '1.0'
                },
                'data': statement_data
            }
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': os.path.basename(output_path),
                'format': 'json',
                'file_size': file_size,
                'mime_type': 'application/json'
            }
            
        except Exception as e:
            raise ExportError(f"JSON export failed: {str(e)}")
    
    def _export_statement_csv(self, statement_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Export bank statement data to CSV format.
        
        Args:
            statement_data: Bank statement data to export
            filename: Base filename
            
        Returns:
            Export result with file path
        """
        try:
            output_path = os.path.join(self.export_dir, f"{filename}.csv")
            
            # Extract transactions for CSV
            transactions = statement_data.get('data', {}).get('transactions', [])
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                if transactions:
                    # Get all possible fieldnames from transactions
                    fieldnames = set()
                    for transaction in transactions:
                        fieldnames.update(transaction.keys())
                    fieldnames = sorted(list(fieldnames))
                    
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(transactions)
                else:
                    # Write empty CSV with headers
                    fieldnames = ['date', 'description', 'amount', 'balance', 'transaction_type']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': os.path.basename(output_path),
                'format': 'csv',
                'file_size': file_size,
                'mime_type': 'text/csv'
            }
            
        except Exception as e:
            raise ExportError(f"CSV export failed: {str(e)}")
    
    def _export_statement_excel(self, statement_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Export bank statement data to Excel format.
        
        Args:
            statement_data: Bank statement data to export
            filename: Base filename
            
        Returns:
            Export result with file path
        """
        try:
            if not PANDAS_AVAILABLE:
                raise ExportError("Excel export requires pandas library")
            
            output_path = os.path.join(self.export_dir, f"{filename}.xlsx")
            
            # Create Excel writer
            # noinspection PyUnresolvedReferences
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Account summary sheet
                self._create_statement_summary_sheet(statement_data, writer)
                
                # Transactions sheet
                transactions = statement_data.get('data', {}).get('transactions', [])
                if transactions:
                    self._create_transactions_sheet(transactions, writer)
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_path': output_path,
                'filename': os.path.basename(output_path),
                'format': 'excel',
                'file_size': file_size,
                'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
            
        except Exception as e:
            raise ExportError(f"Excel export failed: {str(e)}")
    
    @staticmethod
    def _create_invoice_summary_csv(invoice_data: Dict[str, Any], output_path: str) -> None:
        """Create invoice summary CSV file."""
        data = invoice_data.get('data', {})
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Field', 'Value'])
            
            # Write invoice details
            writer.writerow(['Invoice Number', data.get('invoice_number', '')])
            writer.writerow(['Date', data.get('date', '')])
            writer.writerow(['Due Date', data.get('due_date', '')])
            writer.writerow(['Total Amount', data.get('total_amount', '')])
            writer.writerow(['Currency', data.get('currency', '')])
            
            # Vendor info
            vendor = data.get('vendor', {})
            if vendor:
                writer.writerow(['Vendor Name', vendor.get('name', '')])
                writer.writerow(['Vendor Address', vendor.get('address', '')])
            
            # Customer info
            customer = data.get('customer', {})
            if customer:
                writer.writerow(['Customer Name', customer.get('name', '')])
                writer.writerow(['Customer Address', customer.get('address', '')])
    
    @staticmethod
    def _create_invoice_detailed_csv(invoice_data: Dict[str, Any], output_path: str) -> None:
        """Create detailed invoice CSV with line items."""
        line_items = invoice_data.get('data', {}).get('line_items', [])
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            if line_items:
                # Get all possible fieldnames from line items
                fieldnames = set()
                for item in line_items:
                    fieldnames.update(item.keys())
                fieldnames = sorted(list(fieldnames))
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(line_items)
    
    @staticmethod
    def _create_invoice_summary_sheet(invoice_data: Dict[str, Any], writer) -> None:
        """Create invoice summary Excel sheet."""
        data = invoice_data.get('data', {})
        
        # Prepare summary data
        summary_data = [
            ['Invoice Number', data.get('invoice_number', '')],
            ['Date', data.get('date', '')],
            ['Due Date', data.get('due_date', '')],
            ['Total Amount', data.get('total_amount', '')],
            ['Currency', data.get('currency', '')]
        ]
        
        # Add vendor info
        vendor = data.get('vendor', {})
        if vendor:
            summary_data.extend([
                ['Vendor Name', vendor.get('name', '')],
                ['Vendor Address', vendor.get('address', '')]
            ])
        
        # Add customer info
        customer = data.get('customer', {})
        if customer:
            summary_data.extend([
                ['Customer Name', customer.get('name', '')],
                ['Customer Address', customer.get('address', '')]
            ])
        
        # Create DataFrame and write to Excel
        # noinspection PyUnresolvedReferences
        df = pd.DataFrame(summary_data, columns=['Field', 'Value'])
        df.to_excel(writer, sheet_name='Invoice Summary', index=False)
    
    @staticmethod
    def _create_line_items_sheet(line_items: List[Dict[str, Any]], writer) -> None:
        """Create line items Excel sheet."""
        if line_items:
            # noinspection PyUnresolvedReferences
            df = pd.DataFrame(line_items)
            df.to_excel(writer, sheet_name='Line Items', index=False)
    
    @staticmethod
    def _create_statement_summary_sheet(statement_data: Dict[str, Any], writer) -> None:
        """Create bank statement summary Excel sheet."""
        data = statement_data.get('data', {})
        account_info = data.get('account_info', {})
        balances = data.get('balances', {})
        
        # Prepare summary data
        summary_data = [
            ['Account Number', account_info.get('account_number', '')],
            ['Account Holder', account_info.get('account_holder', '')],
            ['Bank Name', account_info.get('bank_name', '')],
            ['Statement Period Start', account_info.get('statement_period', {}).get('start_date', '')],
            ['Statement Period End', account_info.get('statement_period', {}).get('end_date', '')],
            ['Opening Balance', balances.get('opening_balance', '')],
            ['Closing Balance', balances.get('closing_balance', '')],
            ['Currency', balances.get('currency', '')]
        ]
        
        # Create DataFrame and write to Excel
        # noinspection PyUnresolvedReferences
        df = pd.DataFrame(summary_data, columns=['Field', 'Value'])
        df.to_excel(writer, sheet_name='Account Summary', index=False)
    
    @staticmethod
    def _create_transactions_sheet(transactions: List[Dict[str, Any]], writer) -> None:
        """Create transactions Excel sheet."""
        if transactions:
            # noinspection PyUnresolvedReferences
            df = pd.DataFrame(transactions)
            df.to_excel(writer, sheet_name='Transactions', index=False)
    
    def get_export_capabilities(self) -> Dict[str, Any]:
        """Get export service capabilities.
        
        Returns:
            Dictionary with supported formats and features
        """
        return {
            'supported_formats': self.supported_formats,
            'max_file_size': f"{self.max_export_size // (1024*1024)}MB",
            'features': {
                'json_export': True,
                'csv_export': True,
                'excel_export': PANDAS_AVAILABLE,
                'custom_filename': True,
                'multiple_sheets': PANDAS_AVAILABLE
            },
            'data_types': ['invoice', 'bank_statement'],
            'requirements': {
                'excel_export': 'pandas and openpyxl libraries required'
            }
        }
    
    def cleanup_old_exports(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """Clean up old export files.
        
        Args:
            max_age_hours: Maximum age of files to keep in hours
            
        Returns:
            Cleanup result summary
        """
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            deleted_files = []
            total_size_freed = 0
            
            for filename in os.listdir(self.export_dir):
                output_path = os.path.join(self.export_dir, filename)
                
                if os.path.isfile(output_path):
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(output_path))
                    
                    if file_mtime < cutoff_time:
                        file_size = os.path.getsize(output_path)
                        os.remove(output_path)
                        deleted_files.append(filename)
                        total_size_freed += file_size
            
            self.logger.info(f"Cleaned up {len(deleted_files)} old export files, freed {total_size_freed} bytes")
            
            return {
                'success': True,
                'deleted_files': len(deleted_files),
                'size_freed': total_size_freed,
                'files': deleted_files
            }
            
        except Exception as e:
            self.logger.error(f"Export cleanup failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }