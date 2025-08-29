"""
AI Service
Handles AI-powered features like summarization and translation
"""

import os
import tempfile
import logging
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

# PDF processing libraries
try:
    import fitz  # PyMuPDF
    PDF_LIBS_AVAILABLE = True
except ImportError:
    PDF_LIBS_AVAILABLE = False
    logging.warning("PDF processing libraries not available. Install PyMuPDF for PDF AI functionality.")

logger = logging.getLogger(__name__)

class AIService:
    """Service for AI-powered PDF features"""
    
    def __init__(self):
        self.supported_languages = [
            'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi'
        ]
        self.summary_styles = ['concise', 'detailed', 'academic', 'casual', 'professional']
        self.translation_providers = ['openai', 'deepl', 'google', 'azure']
        self.temp_dir = tempfile.mkdtemp(prefix='ai_processing_')
        
        # Check library availability
        if not PDF_LIBS_AVAILABLE:
            logger.error("PDF processing libraries not available. AI service will not work properly.")
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize API clients
        self.api_clients = self._initialize_api_clients()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load AI service configuration"""
        config = {
            'openai': {
                'api_key': os.getenv('OPENAI_API_KEY', ''),
                'base_url': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                'model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
                'max_tokens': int(os.getenv('OPENAI_MAX_TOKENS', '2000'))
            },
            'deepl': {
                'api_key': os.getenv('DEEPL_API_KEY', ''),
                'base_url': os.getenv('DEEPL_BASE_URL', 'https://api-free.deepl.com/v2')
            },
            'google': {
                'api_key': os.getenv('GOOGLE_TRANSLATE_API_KEY', ''),
                'base_url': 'https://translation.googleapis.com/language/translate/v2'
            },
            'azure': {
                'api_key': os.getenv('AZURE_TRANSLATOR_API_KEY', ''),
                'base_url': os.getenv('AZURE_TRANSLATOR_BASE_URL', 'https://api.cognitive.microsofttranslator.com'),
                'region': os.getenv('AZURE_TRANSLATOR_REGION', '')
            }
        }
        
        return config
    
    def _initialize_api_clients(self) -> Dict[str, Any]:
        """Initialize API clients for different providers"""
        clients = {}
        
        # OpenAI client
        if self.config['openai']['api_key']:
            try:
                clients['openai'] = self._create_openai_client()
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {str(e)}")
        
        # DeepL client
        if self.config['deepl']['api_key']:
            try:
                clients['deepl'] = self._create_deepl_client()
            except Exception as e:
                logger.warning(f"Failed to initialize DeepL client: {str(e)}")
        
        # Google client
        if self.config['google']['api_key']:
            try:
                clients['google'] = self._create_google_client()
            except Exception as e:
                logger.warning(f"Failed to initialize Google client: {str(e)}")
        
        # Azure client
        if self.config['azure']['api_key']:
            try:
                clients['azure'] = self._create_azure_client()
            except Exception as e:
                logger.warning(f"Failed to initialize Azure client: {str(e)}")
        
        return clients
    
    def _create_openai_client(self):
        """Create OpenAI API client"""
        return {
            'type': 'openai',
            'config': self.config['openai']
        }
    
    def _create_deepl_client(self):
        """Create DeepL API client"""
        return {
            'type': 'deepl',
            'config': self.config['deepl']
        }
    
    def _create_google_client(self):
        """Create Google Translate API client"""
        return {
            'type': 'google',
            'config': self.config['google']
        }
    
    def _create_azure_client(self):
        """Create Azure Translator API client"""
        return {
            'type': 'azure',
            'config': self.config['azure']
        }
    
    def summarize_text(self, text: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Summarize text using AI
        
        Args:
            text: Text to summarize
            options: Summarization options
            
        Returns:
            Dictionary with summary result
        """
        if not options:
            options = {}
            
        try:
            # Validate text length
            if len(text) > 100000:  # 100KB limit
                raise ValueError("Text too long. Maximum length is 100KB.")
            
            # Get provider
            provider = options.get('provider', 'openai')
            if provider not in self.api_clients:
                raise ValueError(f"Provider {provider} not available")
            
            # Prepare summarization request
            summary_request = self._prepare_summary_request(text, options)
            
            # Call AI provider
            if provider == 'openai':
                result = self._call_openai_summarization(summary_request)
            else:
                # For now, fall back to OpenAI for summarization
                result = self._call_openai_summarization(summary_request)
            
            return result
            
        except Exception as e:
            logger.error(f"Text summarization failed: {str(e)}")
            raise
    
    def translate_text(self, text: str, target_language: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Translate text using AI
        
        Args:
            text: Text to translate
            target_language: Target language code
            options: Translation options
            
        Returns:
            Dictionary with translation result
        """
        if not options:
            options = {}
            
        try:
            # Validate text length
            if len(text) > 100000:  # 100KB limit
                raise ValueError("Text too long. Maximum length is 100KB.")
            
            # Validate target language
            if target_language not in self.supported_languages:
                raise ValueError(f"Unsupported target language: {target_language}")
            
            # Get provider
            provider = options.get('provider', 'openai')
            if provider not in self.api_clients:
                raise ValueError(f"Provider {provider} not available")
            
            # Prepare translation request
            translation_request = self._prepare_translation_request(text, target_language, options)
            
            # Call AI provider
            if provider == 'openai':
                result = self._call_openai_translation(translation_request)
            elif provider == 'deepl':
                result = self._call_deepl_translation(translation_request)
            elif provider == 'google':
                result = self._call_google_translation(translation_request)
            elif provider == 'azure':
                result = self._call_azure_translation(translation_request)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            return result
            
        except Exception as e:
            logger.error(f"Text translation failed: {str(e)}")
            raise
    
    def extract_text_from_pdf(self, file) -> str:
        """
        Extract text content from PDF file
        
        Args:
            file: Uploaded PDF file
            
        Returns:
            Extracted text content
        """
        if not PDF_LIBS_AVAILABLE:
            raise RuntimeError("PDF processing libraries not available")
        
        try:
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Extract text from PDF
            text_content = self._extract_pdf_text(temp_file_path)
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return text_content
            
        except Exception as e:
            logger.error(f"PDF text extraction failed: {str(e)}")
            raise
    
    def _prepare_summary_request(self, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare summarization request"""
        style = options.get('style', 'concise')
        max_length = options.get('maxLength', 'medium')
        include_key_points = options.get('includeKeyPoints', True)
        include_quotes = options.get('includeQuotes', False)
        focus_areas = options.get('focusAreas', [])
        language = options.get('language', 'en')
        
        # Build prompt based on style and options
        prompt = self._build_summary_prompt(style, max_length, include_key_points, include_quotes, focus_areas, language)
        
        return {
            'text': text,
            'prompt': prompt,
            'style': style,
            'max_length': max_length,
            'include_key_points': include_key_points,
            'include_quotes': include_quotes,
            'focus_areas': focus_areas,
            'language': language
        }
    
    def _prepare_translation_request(self, text: str, target_language: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare translation request"""
        provider = options.get('provider', 'openai')
        preserve_formatting = options.get('preserveFormatting', True)
        translate_tables = options.get('translateTables', True)
        translate_images = options.get('translateImages', False)
        quality = options.get('quality', 'high')
        preserve_context = options.get('preserveContext', True)
        
        return {
            'text': text,
            'target_language': target_language,
            'provider': provider,
            'preserve_formatting': preserve_formatting,
            'translate_tables': translate_tables,
            'translate_images': translate_images,
            'quality': quality,
            'preserve_context': preserve_context
        }
    
    def _build_summary_prompt(self, style: str, max_length: str, include_key_points: bool, 
                             include_quotes: bool, focus_areas: List[str], language: str) -> str:
        """Build summarization prompt based on options"""
        prompt_parts = []
        
        # Style instructions
        style_instructions = {
            'concise': 'Provide a concise summary focusing on the main points.',
            'detailed': 'Provide a comprehensive summary covering all important aspects.',
            'academic': 'Provide an academic-style summary with formal language and structure.',
            'casual': 'Provide a casual, easy-to-understand summary.',
            'professional': 'Provide a professional summary suitable for business contexts.'
        }
        
        prompt_parts.append(style_instructions.get(style, 'Provide a summary.'))
        
        # Length instructions
        length_instructions = {
            'short': 'Keep the summary brief (2-3 sentences).',
            'medium': 'Provide a medium-length summary (4-6 sentences).',
            'long': 'Provide a detailed summary (8-10 sentences).'
        }
        
        prompt_parts.append(length_instructions.get(max_length, 'Provide a medium-length summary.'))
        
        # Additional requirements
        if include_key_points:
            prompt_parts.append('Include key points as bullet points.')
        
        if include_quotes:
            prompt_parts.append('Include relevant quotes from the text.')
        
        if focus_areas:
            prompt_parts.append(f'Focus on these areas: {", ".join(focus_areas)}.')
        
        # Language instruction
        if language != 'en':
            prompt_parts.append(f'Provide the summary in {language}.')
        
        prompt_parts.append('Text to summarize:')
        
        return ' '.join(prompt_parts)
    
    def _call_openai_summarization(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI API for summarization"""
        try:
            config = self.api_clients['openai']['config']
            
            # Prepare API request
            api_request = {
                'model': config['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a helpful assistant that summarizes text documents.'
                    },
                    {
                        'role': 'user',
                        'content': f"{request['prompt']}\n\n{request['text']}"
                    }
                ],
                'max_tokens': config['max_tokens'],
                'temperature': 0.3
            }
            
            # Make API call
            response = requests.post(
                f"{config['base_url']}/chat/completions",
                headers={
                    'Authorization': f"Bearer {config['api_key']}",
                    'Content-Type': 'application/json'
                },
                json=api_request,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            summary = result['choices'][0]['message']['content']
            
            # Extract key points if requested
            key_points = []
            if request['include_key_points']:
                key_points = self._extract_key_points_from_summary(summary)
            
            return {
                'success': True,
                'summary': summary,
                'key_points': key_points,
                'word_count': len(summary.split()),
                'reading_time': self._estimate_reading_time(summary),
                'style': request['style'],
                'options': request
            }
            
        except Exception as e:
            logger.error(f"OpenAI summarization failed: {str(e)}")
            raise
    
    def _call_openai_translation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI API for translation"""
        try:
            config = self.api_clients['openai']['config']
            
            # Build translation prompt
            prompt = f"Translate the following text to {request['target_language']}. "
            if request['preserve_formatting']:
                prompt += "Preserve the original formatting and structure. "
            if request['preserve_context']:
                prompt += "Maintain the context and meaning of the original text. "
            prompt += "Text to translate:"
            
            # Prepare API request
            api_request = {
                'model': config['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a professional translator.'
                    },
                    {
                        'role': 'user',
                        'content': f"{prompt}\n\n{request['text']}"
                    }
                ],
                'max_tokens': config['max_tokens'],
                'temperature': 0.1  # Lower temperature for more consistent translation
            }
            
            # Make API call
            response = requests.post(
                f"{config['base_url']}/chat/completions",
                headers={
                    'Authorization': f"Bearer {config['api_key']}",
                    'Content-Type': 'application/json'
                },
                json=api_request,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
            
            result = response.json()
            translated_text = result['choices'][0]['message']['content']
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_language': 'auto',  # OpenAI doesn't detect source language
                'target_language': request['target_language'],
                'word_count': len(translated_text.split()),
                'confidence': 0.9,  # OpenAI doesn't provide confidence scores
                'provider': 'openai',
                'options': request
            }
            
        except Exception as e:
            logger.error(f"OpenAI translation failed: {str(e)}")
            raise
    
    def _call_deepl_translation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call DeepL API for translation"""
        try:
            config = self.api_clients['deepl']['config']
            
            # Prepare API request
            api_request = {
                'text': [request['text']],
                'target_lang': request['target_language'].upper(),
                'preserve_formatting': '1' if request['preserve_formatting'] else '0'
            }
            
            # Make API call
            response = requests.post(
                f"{config['base_url']}/translate",
                headers={
                    'Authorization': f"DeepL-Auth-Key {config['api_key']}",
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data=api_request,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"DeepL API error: {response.status_code} - {response.text}")
            
            result = response.json()
            translated_text = result['translations'][0]['text']
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_language': result['translations'][0].get('detected_source_language', 'auto'),
                'target_language': request['target_language'],
                'word_count': len(translated_text.split()),
                'confidence': 0.95,  # DeepL typically has high confidence
                'provider': 'deepl',
                'options': request
            }
            
        except Exception as e:
            logger.error(f"DeepL translation failed: {str(e)}")
            raise
    
    def _call_google_translation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call Google Translate API for translation"""
        try:
            config = self.api_clients['google']['config']
            
            # Prepare API request
            api_request = {
                'q': request['text'],
                'target': request['target_language'],
                'format': 'text'
            }
            
            # Make API call
            response = requests.post(
                f"{config['base_url']}",
                params={'key': config['api_key']},
                json=api_request,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Google Translate API error: {response.status_code} - {response.text}")
            
            result = response.json()
            translated_text = result['data']['translations'][0]['translatedText']
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_language': result['data']['translations'][0].get('detectedSourceLanguage', 'auto'),
                'target_language': request['target_language'],
                'word_count': len(translated_text.split()),
                'confidence': 0.85,  # Google Translate confidence
                'provider': 'google',
                'options': request
            }
            
        except Exception as e:
            logger.error(f"Google translation failed: {str(e)}")
            raise
    
    def _call_azure_translation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call Azure Translator API for translation"""
        try:
            config = self.api_clients['azure']['config']
            
            # Prepare API request
            api_request = [{'text': request['text']}]
            
            # Make API call
            response = requests.post(
                f"{config['base_url']}/translate",
                params={
                    'api-version': '3.0',
                    'to': request['target_language']
                },
                headers={
                    'Ocp-Apim-Subscription-Key': config['api_key'],
                    'Ocp-Apim-Subscription-Region': config['region'],
                    'Content-Type': 'application/json'
                },
                json=api_request,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Azure Translator API error: {response.status_code} - {response.text}")
            
            result = response.json()
            translated_text = result[0]['translations'][0]['text']
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_language': 'auto',  # Azure doesn't detect source language
                'target_language': request['target_language'],
                'word_count': len(translated_text.split()),
                'confidence': 0.9,  # Azure Translator confidence
                'provider': 'azure',
                'options': request
            }
            
        except Exception as e:
            logger.error(f"Azure translation failed: {str(e)}")
            raise
    
    def _save_uploaded_file(self, file) -> str:
        """Save uploaded file to temporary directory"""
        filename = self._secure_filename(file.filename)
        temp_path = os.path.join(self.temp_dir, filename)
        
        file.save(temp_path)
        return temp_path
    
    def _secure_filename(self, filename: str) -> str:
        """Secure filename for safe file operations"""
        import re
        # Remove or replace unsafe characters
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename.strip('-')
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text content from PDF file"""
        try:
            text_content = ""
            
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    text_content += text + "\n"
            
            return text_content.strip()
            
        except Exception as e:
            logger.error(f"PDF text extraction failed: {str(e)}")
            raise
    
    def _extract_key_points_from_summary(self, summary: str) -> List[str]:
        """Extract key points from summary text"""
        try:
            # Simple extraction: look for bullet points or numbered lists
            lines = summary.split('\n')
            key_points = []
            
            for line in lines:
                line = line.strip()
                if line.startswith(('•', '-', '*', '1.', '2.', '3.')):
                    # Remove bullet/number and clean up
                    clean_line = line.lstrip('•-*1234567890.').strip()
                    if clean_line:
                        key_points.append(clean_line)
            
            return key_points
            
        except Exception as e:
            logger.warning(f"Key points extraction failed: {str(e)}")
            return []
    
    def _estimate_reading_time(self, text: str) -> int:
        """Estimate reading time in minutes"""
        # Average reading speed: 200-250 words per minute
        word_count = len(text.split())
        reading_time = word_count / 225  # 225 words per minute
        return max(1, round(reading_time))
    
    def get_available_providers(self) -> List[str]:
        """Get list of available AI providers"""
        return list(self.api_clients.keys())
    
    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """Get status of specific AI provider"""
        if provider not in self.api_clients:
            return {'available': False, 'error': 'Provider not found'}
        
        try:
            # Test provider connectivity
            if provider == 'openai':
                return self._test_openai_connectivity()
            elif provider == 'deepl':
                return self._test_deepl_connectivity()
            elif provider == 'google':
                return self._test_google_connectivity()
            elif provider == 'azure':
                return self._test_azure_connectivity()
            else:
                return {'available': False, 'error': 'Unknown provider'}
                
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def _test_openai_connectivity(self) -> Dict[str, Any]:
        """Test OpenAI API connectivity"""
        try:
            config = self.api_clients['openai']['config']
            
            response = requests.get(
                f"{config['base_url']}/models",
                headers={'Authorization': f"Bearer {config['api_key']}"},
                timeout=10
            )
            
            if response.status_code == 200:
                return {'available': True, 'status': 'connected'}
            else:
                return {'available': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def _test_deepl_connectivity(self) -> Dict[str, Any]:
        """Test DeepL API connectivity"""
        try:
            config = self.api_clients['deepl']['config']
            
            response = requests.get(
                f"{config['base_url']}/usage",
                headers={'Authorization': f"DeepL-Auth-Key {config['api_key']}"},
                timeout=10
            )
            
            if response.status_code == 200:
                return {'available': True, 'status': 'connected'}
            else:
                return {'available': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def _test_google_connectivity(self) -> Dict[str, Any]:
        """Test Google Translate API connectivity"""
        try:
            config = self.api_clients['google']['config']
            
            # Test with a simple translation
            test_request = {
                'q': 'Hello',
                'target': 'es',
                'key': config['api_key']
            }
            
            response = requests.post(
                config['base_url'],
                json=test_request,
                timeout=10
            )
            
            if response.status_code == 200:
                return {'available': True, 'status': 'connected'}
            else:
                return {'available': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def _test_azure_connectivity(self) -> Dict[str, Any]:
        """Test Azure Translator API connectivity"""
        try:
            config = self.api_clients['azure']['config']
            
            # Test with a simple translation
            test_request = [{'text': 'Hello'}]
            
            response = requests.post(
                f"{config['base_url']}/translate",
                params={
                    'api-version': '3.0',
                    'to': 'es'
                },
                headers={
                    'Ocp-Apim-Subscription-Key': config['api_key'],
                    'Ocp-Apim-Subscription-Region': config['region'],
                    'Content-Type': 'application/json'
                },
                json=test_request,
                timeout=10
            )
            
            if response.status_code == 200:
                return {'available': True, 'status': 'connected'}
            else:
                return {'available': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {str(e)}")
