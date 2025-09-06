"""
Enhanced Compression Service
Provides intelligent PDF compression with analysis and ML recommendations
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import subprocess
import json
from datetime import datetime
import hashlib

from src.services.compression_service import CompressionService
from src.utils.file_utils import secure_filename, cleanup_old_files
from src.models.compression_job import CompressionJob
from src.models.base import db

logger = logging.getLogger(__name__)


class EnhancedCompressionService:
    """Enhanced compression service with intelligent analysis and recommendations"""
    
    def __init__(self, upload_folder: str):
        self.upload_folder = Path(upload_folder)
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.base_compression_service = CompressionService(upload_folder)
        self.analysis_cache = {}
        
    async def compress_with_intelligence(self, file_data: bytes, user_preferences: Dict[str, Any], 
                                       user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Compress PDF with intelligent analysis and ML recommendations
        """
        try:
            # Analyze file content
            analysis = await self.analyze_content(file_data)
            
            # Get AI recommendations
            recommendations = self.get_ml_recommendations(analysis)
            
            # Merge user preferences with recommendations
            settings = self.merge_preferences(recommendations, user_preferences)
            
            # Create compression job record
            job_id = await self.create_compression_job(analysis, settings, user_id)
            
            # Compress with optimal settings
            result = await self.compress_file(file_data, settings, job_id)
            
            # Update job with results
            await self.update_compression_job(job_id, result)
            
            # Log for analytics
            await self.log_compression_analytics(analysis, settings, result, user_id)
            
            return {
                'success': True,
                'job_id': job_id,
                'compression_ratio': result.get('compression_ratio', 1.0),
                'original_size': result.get('original_size', 0),
                'compressed_size': result.get('compressed_size', 0),
                'settings_used': settings,
                'analysis': analysis,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Intelligent compression failed: {str(e)}")
            raise Exception(f"Intelligent compression failed: {str(e)}")
    
    async def analyze_content(self, file_data: bytes) -> Dict[str, Any]:
        """
        Analyze PDF content for compression optimization
        """
        try:
            # Generate file hash for caching
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Check cache first
            if file_hash in self.analysis_cache:
                return self.analysis_cache[file_hash]
            
            # Save file temporarily for analysis
            temp_file = self.upload_folder / f"temp_analysis_{file_hash[:8]}.pdf"
            with open(temp_file, 'wb') as f:
                f.write(file_data)
            
            try:
                # Analyze with pdfinfo
                analysis = await self.analyze_with_pdfinfo(temp_file)
                
                # Analyze with Ghostscript for additional insights
                gs_analysis = await self.analyze_with_ghostscript(temp_file)
                
                # Combine analysis results
                combined_analysis = {
                    'file_size': len(file_data),
                    'file_hash': file_hash,
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    **analysis,
                    **gs_analysis
                }
                
                # Calculate compression potential
                combined_analysis['compression_potential'] = self.calculate_compression_potential(combined_analysis)
                
                # Cache the result
                self.analysis_cache[file_hash] = combined_analysis
                
                return combined_analysis
                
            finally:
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
                    
        except Exception as e:
            logger.error(f"Content analysis failed: {str(e)}")
            # Return basic analysis if detailed analysis fails
            return {
                'file_size': len(file_data),
                'page_count': 0,
                'compression_potential': 0.5,
                'document_type': 'unknown',
                'error': str(e)
            }
    
    async def analyze_with_pdfinfo(self, file_path: Path) -> Dict[str, Any]:
        """Analyze PDF using pdfinfo command"""
        try:
            result = subprocess.run(
                ['pdfinfo', str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.warning(f"pdfinfo failed: {result.stderr}")
                return {}
            
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            
            # Extract key metrics
            analysis = {
                'page_count': int(info.get('Pages', '0')),
                'file_size_bytes': int(info.get('File size', '0').split()[0]),
                'title': info.get('Title', ''),
                'author': info.get('Author', ''),
                'subject': info.get('Subject', ''),
                'creator': info.get('Creator', ''),
                'producer': info.get('Producer', ''),
                'creation_date': info.get('CreationDate', ''),
                'mod_date': info.get('ModDate', '')
            }
            
            # Determine document type
            analysis['document_type'] = self.classify_document_type(analysis)
            
            return analysis
            
        except Exception as e:
            logger.warning(f"pdfinfo analysis failed: {str(e)}")
            return {}
    
    async def analyze_with_ghostscript(self, file_path: Path) -> Dict[str, Any]:
        """Analyze PDF using Ghostscript for additional insights"""
        try:
            # Use Ghostscript to analyze PDF structure
            result = subprocess.run([
                'gs', '-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=nullpage',
                '-sOutputFile=/dev/null', str(file_path)
            ], capture_output=True, text=True, timeout=60)
            
            analysis = {}
            
            # Parse Ghostscript output for insights
            if result.stderr:
                # Look for font and image information
                stderr_lines = result.stderr.split('\n')
                font_count = 0
                image_count = 0
                
                for line in stderr_lines:
                    if 'Font' in line and 'loaded' in line:
                        font_count += 1
                    elif 'image' in line.lower():
                        image_count += 1
                
                analysis['estimated_font_count'] = font_count
                analysis['estimated_image_count'] = image_count
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Ghostscript analysis failed: {str(e)}")
            return {}
    
    def classify_document_type(self, analysis: Dict[str, Any]) -> str:
        """Classify document type based on analysis"""
        page_count = analysis.get('page_count', 0)
        file_size = analysis.get('file_size_bytes', 0)
        
        if page_count == 1:
            if file_size > 5 * 1024 * 1024:  # > 5MB
                return 'single_image'
            else:
                return 'single_page_document'
        elif page_count > 50:
            return 'long_document'
        elif page_count > 10:
            return 'medium_document'
        else:
            return 'short_document'
    
    def calculate_compression_potential(self, analysis: Dict[str, Any]) -> float:
        """Calculate compression potential score (0.0 to 1.0)"""
        try:
            score = 0.5  # Base score
            
            # Page count factor
            page_count = analysis.get('page_count', 1)
            if page_count > 20:
                score += 0.1  # Long documents have more redundancy
            
            # File size factor
            file_size = analysis.get('file_size', 0)
            if file_size > 10 * 1024 * 1024:  # > 10MB
                score += 0.2  # Large files have more compression opportunity
            
            # Document type factor
            doc_type = analysis.get('document_type', 'unknown')
            if doc_type == 'single_image':
                score += 0.3  # Images compress well
            elif doc_type == 'long_document':
                score += 0.2  # Long documents have redundancy
            
            # Font count factor
            font_count = analysis.get('estimated_font_count', 0)
            if font_count > 5:
                score += 0.1  # Many fonts can be optimized
            
            # Image count factor
            image_count = analysis.get('estimated_image_count', 0)
            if image_count > 0:
                score += 0.2  # Images provide compression opportunity
            
            return min(score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logger.warning(f"Compression potential calculation failed: {str(e)}")
            return 0.5
    
    def get_ml_recommendations(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get ML-based compression recommendations"""
        try:
            compression_potential = analysis.get('compression_potential', 0.5)
            document_type = analysis.get('document_type', 'unknown')
            file_size = analysis.get('file_size', 0)
            
            recommendations = {
                'compression_level': 'medium',
                'image_quality': 80,
                'target_size': 'auto',
                'optimization_strategy': 'balanced'
            }
            
            # Adjust compression level based on potential
            if compression_potential > 0.8:
                recommendations['compression_level'] = 'high'
                recommendations['image_quality'] = 70
                recommendations['optimization_strategy'] = 'aggressive'
            elif compression_potential > 0.6:
                recommendations['compression_level'] = 'medium'
                recommendations['image_quality'] = 80
                recommendations['optimization_strategy'] = 'balanced'
            else:
                recommendations['compression_level'] = 'low'
                recommendations['image_quality'] = 90
                recommendations['optimization_strategy'] = 'conservative'
            
            # Adjust based on document type
            if document_type == 'single_image':
                recommendations['image_quality'] = 75
                recommendations['optimization_strategy'] = 'image_optimized'
            elif document_type == 'long_document':
                recommendations['compression_level'] = 'medium'
                recommendations['optimization_strategy'] = 'batch_optimized'
            
            # Adjust based on file size
            if file_size > 20 * 1024 * 1024:  # > 20MB
                recommendations['compression_level'] = 'high'
                recommendations['target_size'] = '50%'
            elif file_size > 10 * 1024 * 1024:  # > 10MB
                recommendations['compression_level'] = 'medium'
                recommendations['target_size'] = '70%'
            
            return recommendations
            
        except Exception as e:
            logger.warning(f"ML recommendations failed: {str(e)}")
            return {
                'compression_level': 'medium',
                'image_quality': 80,
                'target_size': 'auto',
                'optimization_strategy': 'balanced'
            }
    
    def merge_preferences(self, recommendations: Dict[str, Any], 
                         user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Merge AI recommendations with user preferences"""
        merged = recommendations.copy()
        
        # User preferences override recommendations
        for key, value in user_preferences.items():
            if value is not None and value != '':
                merged[key] = value
        
        return merged
    
    async def compress_file(self, file_data: bytes, settings: Dict[str, Any], 
                           job_id: str) -> Dict[str, Any]:
        """Compress file with given settings"""
        try:
            # Save file temporarily
            temp_file = self.upload_folder / f"temp_compress_{job_id}.pdf"
            with open(temp_file, 'wb') as f:
                f.write(file_data)
            
            try:
                # Use base compression service
                output_path = self.upload_folder / f"compressed_{job_id}.pdf"
                
                compression_level = settings.get('compression_level', 'medium')
                image_quality = settings.get('image_quality', 80)
                
                success = self.base_compression_service.compress_pdf(
                    str(temp_file),
                    str(output_path),
                    compression_level,
                    image_quality
                )
                
                if success and output_path.exists():
                    compressed_size = output_path.stat().st_size
                    compression_ratio = compressed_size / len(file_data)
                    
                    return {
                        'success': True,
                        'compressed_size': compressed_size,
                        'compression_ratio': compression_ratio,
                        'output_path': str(output_path),
                        'settings_used': settings
                    }
                else:
                    raise Exception("Compression failed")
                    
            finally:
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
                    
        except Exception as e:
            logger.error(f"File compression failed: {str(e)}")
            raise Exception(f"File compression failed: {str(e)}")
    
    async def create_compression_job(self, analysis: Dict[str, Any], 
                                   settings: Dict[str, Any], 
                                   user_id: Optional[str] = None) -> str:
        """Create compression job record"""
        try:
            job = CompressionJob(
                user_id=user_id,
                status='processing',
                file_size=analysis.get('file_size', 0),
                page_count=analysis.get('page_count', 0),
                compression_settings=json.dumps(settings),
                analysis_data=json.dumps(analysis),
                created_at=datetime.utcnow()
            )
            
            db.session.add(job)
            db.session.commit()
            
            return str(job.id)
            
        except Exception as e:
            logger.error(f"Failed to create compression job: {str(e)}")
            raise Exception(f"Failed to create compression job: {str(e)}")
    
    async def update_compression_job(self, job_id: str, result: Dict[str, Any]):
        """Update compression job with results"""
        try:
            job = CompressionJob.query.get(job_id)
            if job:
                job.status = 'completed' if result.get('success') else 'failed'
                job.compression_ratio = result.get('compression_ratio', 1.0)
                job.processing_time_ms = result.get('processing_time_ms', 0)
                job.file_size_before = result.get('original_size', 0)
                job.file_size_after = result.get('compressed_size', 0)
                job.completed_at = datetime.utcnow()
                
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update compression job {job_id}: {str(e)}")
    
    async def log_compression_analytics(self, analysis: Dict[str, Any], 
                                      settings: Dict[str, Any], 
                                      result: Dict[str, Any], 
                                      user_id: Optional[str] = None):
        """Log compression analytics for ML improvement"""
        try:
            # In a production system, this would send data to analytics service
            # For now, just log the information
            analytics_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': user_id,
                'analysis': analysis,
                'settings': settings,
                'result': result
            }
            
            logger.info(f"Compression analytics: {json.dumps(analytics_data, default=str)}")
            
        except Exception as e:
            logger.warning(f"Analytics logging failed: {str(e)}")
    
    async def batch_compress(self, files: List[bytes], settings: Dict[str, Any], 
                           user_id: Optional[str] = None) -> Dict[str, Any]:
        """Compress multiple files in batch"""
        try:
            batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hash(str(files)) % 10000}"
            results = []
            
            for i, file_data in enumerate(files):
                try:
                    result = await self.compress_with_intelligence(file_data, settings, user_id)
                    results.append({
                        'file_index': i,
                        'success': True,
                        'result': result
                    })
                except Exception as e:
                    results.append({
                        'file_index': i,
                        'success': False,
                        'error': str(e)
                    })
            
            successful = len([r for r in results if r['success']])
            failed = len(results) - successful
            
            return {
                'batch_id': batch_id,
                'total_files': len(files),
                'successful_files': successful,
                'failed_files': failed,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Batch compression failed: {str(e)}")
            raise Exception(f"Batch compression failed: {str(e)}")
    
    def get_compression_history(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get compression history for user"""
        try:
            query = CompressionJob.query
            
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            jobs = query.order_by(CompressionJob.created_at.desc()).limit(limit).all()
            
            return [{
                'id': job.id,
                'status': job.status,
                'file_size': job.file_size,
                'compression_ratio': job.compression_ratio,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None
            } for job in jobs]
            
        except Exception as e:
            logger.error(f"Failed to get compression history: {str(e)}")
            return []
    
    def clear_analysis_cache(self):
        """Clear the analysis cache"""
        self.analysis_cache.clear()
        logger.info("Analysis cache cleared")
