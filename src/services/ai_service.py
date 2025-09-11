"""
AI Service - Job-Oriented Architecture with OpenRouter AI
Handles AI-powered features like summarization and translation
"""

import os
import logging
import json
import requests
import uuid
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class AIProvider(Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class SummaryStyle(Enum):
    CONCISE = "concise"
    DETAILED = "detailed"
    ACADEMIC = "academic"
    CASUAL = "casual"
    PROFESSIONAL = "professional"

class TranslationQuality(Enum):
    FAST = "fast"
    BALANCED = "balanced"
    HIGH_QUALITY = "high_quality"

class AIService:
    """Service for AI-powered features using OpenRouter AI - Job-Oriented"""
    
    def __init__(self):
        self.supported_languages = [
            'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi'
        ]
        
        # Load OpenRouter configuration
        self.config = self._load_config()
        self.api_clients = self._initialize_api_clients()
        
        # Supported models through OpenRouter
        self.supported_models = {
            # TODO - please use deepseek models, including free variants and moonshot models.
            AIProvider.OPENROUTER: [
                "openai/gpt-4-turbo",
                "openai/gpt-4",
                "openai/gpt-3.5-turbo",
                "anthropic/claude-3-opus",
                "anthropic/claude-3-sonnet",
                "anthropic/claude-3-haiku",
                "google/gemini-pro",
                "mistral/mistral-large",
                "meta/llama-3-70b"
            ]
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """Load AI service configuration with OpenRouter"""
        return {
            'openrouter': {
                'api_key': os.getenv('OPENROUTER_API_KEY', ''),
                'base_url': os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
                'default_model': os.getenv('OPENROUTER_DEFAULT_MODEL', 'openai/gpt-3.5-turbo'),
                'max_tokens': int(os.getenv('OPENROUTER_MAX_TOKENS', '4000')),
                'timeout': int(os.getenv('OPENROUTER_TIMEOUT', '30'))
            }
        }
    
    def _initialize_api_clients(self) -> Dict[str, Any]:
        """Initialize API clients"""
        clients = {}
        
        # OpenRouter client
        if self.config['openrouter']['api_key']:
            try:
                clients[AIProvider.OPENROUTER] = self._create_openrouter_client()
                logger.info("OpenRouter client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter client: {str(e)}")
        
        return clients
    
    def _create_openrouter_client(self):
        """Create OpenRouter API client"""
        return {
            'type': AIProvider.OPENROUTER,
            'config': self.config['openrouter'],
            'headers': {
                'Authorization': f"Bearer {self.config['openrouter']['api_key']}",
                'Content-Type': 'application/json',
                'HTTP-Referer': os.getenv('OPENROUTER_REFERER', 'https://www.pdfsmaller.site'),
                'X-Title': os.getenv('OPENROUTER_TITLE', 'PDF Smaller')
            }
        }
    
    def summarize_text(self, text: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Summarize text using AI with structured response
        
        Args:
            text: Text to summarize
            options: Summarization options
            
        Returns:
            Dictionary with structured summary result
        """
        if not options:
            options = {}
            
        try:
            # Validate text length
            if len(text) > 100000:
                raise ValueError("Text too long. Maximum length is 100KB.")
            
            # Prepare summarization request
            summary_request = self._prepare_summary_request(text, options)
            
            # Call AI provider
            result =  self._call_openrouter_summarization(summary_request)
            
            return {
                'success': True,
                'summary': result['summary'],
                'key_points': result['key_points'],
                'word_count': result['word_count'],
                'reading_time': result['reading_time'],
                'style': summary_request['style'],
                'model': summary_request['model'],
                'options': summary_request,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Text summarization failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def translate_text(self, text: str, target_language: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Translate text using AI with structured response
        
        Args:
            text: Text to translate
            target_language: Target language code
            options: Translation options
            
        Returns:
            Dictionary with structured translation result
        """
        if not options:
            options = {}
            
        try:
            # Validate text length
            if len(text) > 100000:
                raise ValueError("Text too long. Maximum length is 100KB.")
            
            # Validate target language
            if target_language not in self.supported_languages:
                raise ValueError(f"Unsupported target language: {target_language}")
            
            # Prepare translation request
            translation_request = self._prepare_translation_request(text, target_language, options)
            
            # Call AI provider
            result =  self._call_openrouter_translation(translation_request)
            
            return {
                'success': True,
                'translated_text': result['translated_text'],
                'original_language': result.get('original_language', 'auto'),
                'target_language': target_language,
                'word_count': result['word_count'],
                'confidence': result.get('confidence', 0.9),
                'model': translation_request['model'],
                'quality': translation_request['quality'],
                'options': translation_request,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Text translation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _prepare_summary_request(self, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare structured summarization request"""
        style = SummaryStyle(options.get('style', SummaryStyle.CONCISE.value))
        max_length = options.get('maxLength', 'medium')
        include_key_points = options.get('includeKeyPoints', True)
        language = options.get('language', 'en')
        model = options.get('model', self.config['openrouter']['default_model'])
        
        # Build structured prompt
        prompt = self._build_structured_summary_prompt(style, max_length, include_key_points, language)
        
        return {
            'text': text,
            'prompt': prompt,
            'style': style.value,
            'max_length': max_length,
            'include_key_points': include_key_points,
            'language': language,
            'model': model,
            'provider': AIProvider.OPENROUTER.value
        }
    
    def _prepare_translation_request(self, text: str, target_language: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare structured translation request"""
        quality = TranslationQuality(options.get('quality', TranslationQuality.BALANCED.value))
        preserve_formatting = options.get('preserveFormatting', True)
        model = options.get('model', self.config['openrouter']['default_model'])
        
        return {
            'text': text,
            'target_language': target_language,
            'quality': quality.value,
            'preserve_formatting': preserve_formatting,
            'model': model,
            'provider': AIProvider.OPENROUTER.value
        }
    
    def _build_structured_summary_prompt(self, style: SummaryStyle, max_length: str, 
                                       include_key_points: bool, language: str) -> str:
        """Build structured prompt for summarization"""
        prompt_template = """
        Please analyze the following text and provide a structured summary.

        REQUIREMENTS:
        - Style: {style}
        - Length: {length}
        - Language: {language}
        {key_points_requirement}

        OUTPUT FORMAT (JSON):
        {{
            "summary": "main summary text",
            "key_points": ["point 1", "point 2", "point 3"],
            "word_count": number,
            "reading_time_minutes": number
        }}

        TEXT TO SUMMARIZE:
        {text}
        """
        
        length_instructions = {
            'short': '2-3 sentences',
            'medium': '4-6 sentences',
            'long': '8-10 sentences'
        }
        
        key_points_req = "- Include key points as a bulleted list" if include_key_points else ""
        
        return prompt_template.format(
            style=style.value,
            length=length_instructions.get(max_length, '4-6 sentences'),
            language=language,
            key_points_requirement=key_points_req,
            text="{text}"  # Placeholder for text
        )
    
    def _call_openrouter_summarization(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenRouter API for structured summarization"""
        try:
            client = self.api_clients[AIProvider.OPENROUTER]
            config = client['config']
            
            # Prepare the prompt with actual text
            full_prompt = request['prompt'].replace('{text}', request['text'])
            
            # Prepare API request
            api_request = {
                'model': request['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert at analyzing and summarizing documents. Always respond with valid JSON.'
                    },
                    {
                        'role': 'user',
                        'content': full_prompt
                    }
                ],
                'max_tokens': config['max_tokens'],
                'temperature': 0.3,
                'response_format': { 'type': 'json_object' }
            }
            
            # Make API call
            response =  self._make_openrouter_request(api_request, client)
            
            # Parse and validate response
            result = self._parse_summary_response(response)
            
            return result
            
        except Exception as e:
            logger.error(f"OpenRouter summarization failed: {str(e)}")
            raise
    
    def _call_openrouter_translation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenRouter API for structured translation"""
        try:
            client = self.api_clients[AIProvider.OPENROUTER]
            config = client['config']
            
            # Build translation prompt
            prompt = self._build_translation_prompt(request)
            
            # Prepare API request
            api_request = {
                'model': request['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a professional translator. Always respond with valid JSON.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': config['max_tokens'],
                'temperature': 0.1,
                'response_format': { 'type': 'json_object' }
            }
            
            # Make API call
            response =  self._make_openrouter_request(api_request, client)
            
            # Parse and validate response
            result = self._parse_translation_response(response)
            
            return result
            
        except Exception as e:
            logger.error(f"OpenRouter translation failed: {str(e)}")
            raise
    
    def _build_translation_prompt(self, request: Dict[str, Any]) -> str:
        """Build structured translation prompt"""
        prompt_template = """
        Please translate the following text to {target_language}.

        REQUIREMENTS:
        - Quality: {quality}
        - Preserve formatting: {preserve_formatting}
        - Maintain context and meaning

        OUTPUT FORMAT (JSON):
        {{
            "translated_text": "translated text here",
            "word_count": number,
            "confidence": 0.0-1.0
        }}

        TEXT TO TRANSLATE:
        {text}
        """
        
        return prompt_template.format(
            target_language=request['target_language'],
            quality=request['quality'],
            preserve_formatting=str(request['preserve_formatting']).lower(),
            text=request['text']
        )
    
    def _make_openrouter_request(self, api_request: Dict[str, Any], client: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenRouter API"""
        try:
            response = requests.post(
                f"{client['config']['base_url']}/chat/completions",
                headers=client['headers'],
                json=api_request,
                timeout=client['config']['timeout']
            )
            
            if response.status_code != 200:
                error_msg = f"OpenRouter API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("OpenRouter API request timed out")
            raise Exception("API request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API request failed: {str(e)}")
            raise
    
    def _parse_summary_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate summary response"""
        try:
            content = response['choices'][0]['message']['content']
            result = json.loads(content)
            
            # Validate required fields
            required_fields = ['summary', 'key_points', 'word_count']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field in response: {field}")
            
            # Ensure key_points is a list
            if not isinstance(result['key_points'], list):
                result['key_points'] = [result['key_points']]
            
            # Calculate reading time if not provided
            if 'reading_time_minutes' not in result:
                result['reading_time_minutes'] = self._estimate_reading_time(result['summary'])
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            raise ValueError("Invalid JSON response from AI")
        except KeyError as e:
            logger.error(f"Missing key in response: {str(e)}")
            raise ValueError("Invalid response format from AI")
    
    def _parse_translation_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate translation response"""
        try:
            content = response['choices'][0]['message']['content']
            result = json.loads(content)
            
            # Validate required fields
            required_fields = ['translated_text', 'word_count']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field in response: {field}")
            
            # Set default confidence if not provided
            if 'confidence' not in result:
                result['confidence'] = 0.9
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            raise ValueError("Invalid JSON response from AI")
        except KeyError as e:
            logger.error(f"Missing key in response: {str(e)}")
            raise ValueError("Invalid response format from AI")
    
    def _estimate_reading_time(self, text: str) -> int:
        """Estimate reading time in minutes"""
        word_count = len(text.split())
        reading_time = word_count / 225  # 225 words per minute
        return max(1, round(reading_time))
    
    def create_ai_job(self, task_type: Literal["summarize", "translate"], 
                          text: str, options: Dict[str, Any] = None,
                          client_job_id: str = None) -> Dict[str, Any]:
        """
        Create an AI job for processing
        
        Args:
            task_type: Type of AI task (summarize/translate)
            text: Text to process
            options: Task-specific options
            client_job_id: Client-provided job ID
            
        Returns:
            Job information
        """
        try:
            job_id = str(uuid.uuid4())
            
            job_info = {
                'job_id': job_id,
                'task_type': task_type,
                'text_length': len(text),
                'options': options or {},
                'client_job_id': client_job_id,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
                'model': options.get('model', self.config['openrouter']['default_model']),
                'provider': AIProvider.OPENROUTER.value
            }
            
            # Store job metadata (in production, save to database)
            # For now, we'll return the job info
            
            return {
                'success': True,
                'job_id': job_id,
                'status': 'pending',
                'message': f'{task_type.capitalize()} job created successfully',
                'job_info': job_info
            }
            
        except Exception as e:
            logger.error(f"Error creating AI job: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_ai_job(self, job_id: str, task_type: str, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AI job
        
        Args:
            job_id: Job ID
            task_type: Type of AI task
            text: Text to process
            options: Task options
            
        Returns:
            Processing result
        """
        try:
            if task_type == "summarize":
                result =  self.summarize_text(text, options)
            elif task_type == "translate":
                target_language = options.get('target_language', 'en')
                result =  self.translate_text(text, target_language, options)
            else:
                raise ValueError(f"Unsupported task type: {task_type}")
            
            # Add job metadata to result
            result['job_id'] = job_id
            result['task_type'] = task_type
            
            return result
            
        except Exception as e:
            logger.error(f"AI job processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'job_id': job_id,
                'task_type': task_type
            }
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available AI models"""
        models = []
        
        for provider, model_list in self.supported_models.items():
            for model in model_list:
                models.append({
                    'id': model,
                    'provider': provider.value,
                    'name': model.split('/')[-1].replace('-', ' ').title(),
                    'capabilities': ['summarize', 'translate']
                })
        
        return models
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a specific model"""
        for provider, model_list in self.supported_models.items():
            if model_id in model_list:
                return {
                    'id': model_id,
                    'provider': provider.value,
                    'available': True,
                    'max_tokens': self.config['openrouter']['max_tokens'],
                    'supports_json': True
                }
        
        return {
            'id': model_id,
            'available': False,
            'error': 'Model not found'
        }
    
    def test_connectivity(self) -> Dict[str, Any]:
        """Test OpenRouter API connectivity"""
        try:
            if AIProvider.OPENROUTER not in self.api_clients:
                return {
                    'success': False,
                    'error': 'OpenRouter client not initialized',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            client = self.api_clients[AIProvider.OPENROUTER]
            
            # Simple test request
            test_request = {
                'model': 'openai/gpt-3.5-turbo',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Hello, are you working?'
                    }
                ],
                'max_tokens': 10
            }
            
            response = requests.post(
                f"{client['config']['base_url']}/chat/completions",
                headers=client['headers'],
                json=test_request,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'status': 'connected',
                    'response_time': response.elapsed.total_seconds(),
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': f"API error: {response.status_code}",
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }


    def extract_text_from_pdf_data(self, pdf_data: Any):
        """
            Use AI to Extrat Text from PDF Documenta
        """
        pass
