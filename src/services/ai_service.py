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
from datetime import datetime, timezone
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
from enum import Enum

class AIProvider(Enum):
    OPENROUTER = "openrouter"

class TaskType(Enum):
    SUMMARIZATION = "summarization"
    PDF_EXTRACTION = "pdf_text_extraction"
    BANK_STATEMENT_EXTRACTION = "bank_statement_extraction"
    INVOICE_EXTRACTION = "invoice_extraction"

class ModelConfig:
    def __init__(self):
        # Supported models focused on cost-effectiveness and capability
        self.supported_models = {
            AIProvider.OPENROUTER: [
                # DeepSeek models (generally more cost-effective)
                "deepseek/deepseek-v3",
                "deepseek/deepseek-chat",
                "deepseek/deepseek-r1",
                "deepseek/deepseek-r1-distill-llama-70b",
                "deepseek/deepseek-r1-distill-qwen-32b",
                "deepseek/deepseek-r1-distill-qwen-14b",
                
                # Moonshot models (good balance of cost and capability)
                "moonshot/moonshot-k2-premium",  # Better than free version
                "moonshot/moonshot-v1-32k",      # Good context window
                "moonshot/moonshot-v1-128k",     # Best for long documents
                
                # OpenAI's more affordable options (compared to GPT-4 Turbo)
                "openai/gpt-3.5-turbo",          # Most affordable OpenAI option
                
                # Anthropic's cost-effective option
                "anthropic/claude-3-haiku",      # Fastest and most affordable Claude
                
                # Other capable and relatively affordable models
                "google/gemini-pro",             # Good multimodal capabilities
                "meta/llama-3-70b"              # Strong open-weight option
            ]
        }
        
        # Task-specific model preferences with cost considerations
        # Ordered by recommendation priority (considering capability and cost)
        self.task_preferences = {
            TaskType.SUMMARIZATION: [
                "deepseek/deepseek-v3",          # Strong summarization at lower cost
                "moonshot/moonshot-v1-128k",     # Long context for document summarization
                "anthropic/claude-3-haiku",      # Fast and affordable
                "openai/gpt-3.5-turbo",          # Cost-effective
                "google/gemini-pro"              # Good alternative
            ],
            TaskType.PDF_EXTRACTION: [
                "google/gemini-pro",             # Native multimodal support
                "moonshot/moonshot-v1-128k",     # Long context for full PDF processing
                "deepseek/deepseek-r1",          # Strong reasoning for complex extraction
                "anthropic/claude-3-haiku",      # Affordable with decent capabilities
                "openai/gpt-3.5-turbo"           # Budget option (may need OCR preprocessing)
            ],
            TaskType.BANK_STATEMENT_EXTRACTION: [
                "deepseek/deepseek-r1",          # Strong reasoning for structured data
                "google/gemini-pro",             # Good with financial documents
                "moonshot/moonshot-v1-128k",     # Long context for detailed statements
                "anthropic/claude-3-haiku",      # Affordable option
                "openai/gpt-3.5-turbo"           # Most budget-friendly
            ],
            TaskType.INVOICE_EXTRACTION: [
                "google/gemini-pro",             # Specifically tested for invoice extraction
                "deepseek/deepseek-r1",          # Strong reasoning for field extraction
                "moonshot/moonshot-v1-32k",      # Good for standard invoices
                "anthropic/claude-3-haiku",      # Affordable alternative
                "openai/gpt-3.5-turbo"           # Budget option
            ]
        }
        
        # Cost efficiency tiers (for general guidance)
        self.cost_tiers = {
            "high_cost": ["openai/gpt-4-turbo", "openai/gpt-4", "anthropic/claude-3-opus"],
            "medium_cost": ["anthropic/claude-3-sonnet", "google/gemini-pro", "mistral/mistral-large"],
            "low_cost": [
                "openai/gpt-3.5-turbo", 
                "anthropic/claude-3-haiku",
                "deepseek/deepseek-v3",
                "deepseek/deepseek-chat",
                "moonshot/moonshot-k2-premium",
                "moonshot/moonshot-v1-32k",
                "meta/llama-3-70b"
            ]
        }
    
    def get_recommended_models(self, task_type, consider_cost=True):
        """
        Get recommended models for a specific task type
        consider_cost: If True, prioritizes cost-effective options
        """
        if not consider_cost:
            return self.task_preferences.get(task_type, [])
        
        # Return cost-aware recommendations (already built into task_preferences)
        return self.task_preferences.get(task_type, [])
    
    def get_cost_efficient_models(self, task_type=None):
        """
        Get the most cost-efficient models overall or for a specific task
        """
        if task_type:
            # Return the first two recommendations (most cost-effective capable)
            return self.task_preferences.get(task_type, [])[:2]
        else:
            # Return generally cost-effective models across all tasks
            return [
                "deepseek/deepseek-v3",
                "openai/gpt-3.5-turbo", 
                "anthropic/claude-3-haiku",
                "moonshot/moonshot-v1-32k",
                "google/gemini-pro"
            ]
    
    def get_all_supported_models(self, provider):
        """Get all supported models for a provider"""
        return self.supported_models.get(provider, [])
    
    def is_model_supported(self, provider, model_name):
        """Check if a model is supported for a provider"""
        return model_name in self.supported_models.get(provider, [])
    
    def estimate_cost_considerations(self):
        """
        Provide general cost guidance based on model capabilities
        """
        return {
            "most_cost_effective": [
                "openai/gpt-3.5-turbo",
                "anthropic/claude-3-haiku", 
                "deepseek/deepseek-v3"
            ],
            "best_value": [
                "google/gemini-pro",  # Good capabilities at reasonable cost
                "moonshot/moonshot-v1-128k",  # Long context good for documents
                "deepseek/deepseek-r1"  # Strong reasoning for complex tasks
            ],
            "premium_capability": [
                "openai/gpt-4-turbo",
                "anthropic/claude-3-opus",
                "anthropic/claude-3-sonnet"
            ]
        }


class AIService:
    """Service for AI-powered features using OpenRouter AI - Job-Oriented"""
    
    def __init__(self):
        self.supported_languages = [
            'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi'
        ]
        
        # Initialize ModelConfig for intelligent model selection
        self.model_config = ModelConfig()
        
        # Load OpenRouter configuration
        self.config = self._load_config()
        self.api_clients = self._initialize_api_clients()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load AI service configuration with OpenRouter"""
        return {
            'openrouter': {
                'api_key': os.getenv('OPENROUTER_API_KEY', ''),
                'base_url': os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
                'default_model': os.getenv('OPENROUTER_DEFAULT_MODEL', 'deepseek/deepseek-v3-free'),
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
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Text summarization failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
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
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Text translation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _prepare_summary_request(self, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare structured summarization request using ModelConfig"""
        style = SummaryStyle(options.get('style', SummaryStyle.CONCISE.value))
        max_length = options.get('maxLength', 'medium')
        include_key_points = options.get('includeKeyPoints', True)
        language = options.get('language', 'en')
        
        # Use ModelConfig to get recommended model for summarization
        model = options.get('model')
        if not model:
            recommended_models = self.model_config.get_recommended_models(TaskType.SUMMARIZATION)
            model = recommended_models[0] if recommended_models else self.config['openrouter']['default_model']
        
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
        """Prepare structured translation request using ModelConfig"""
        quality = TranslationQuality(options.get('quality', TranslationQuality.BALANCED.value))
        preserve_formatting = options.get('preserveFormatting', True)
        
        # Use ModelConfig to get recommended model for translation (using summarization as proxy)
        model = options.get('model')
        if not model:
            recommended_models = self.model_config.get_recommended_models(TaskType.SUMMARIZATION)
            model = recommended_models[0] if recommended_models else self.config['openrouter']['default_model']
        
        return {
            'text': text,
            'target_language': target_language,
            'quality': quality.value,
            'preserve_formatting': preserve_formatting,
            'model': model,
            'provider': AIProvider.OPENROUTER.value
        }
    
    @staticmethod
    def _build_structured_summary_prompt(style: SummaryStyle, max_length: str,
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
        [DEPRECATED] Create an AI job for processing
        
        This method is deprecated. Use JobOperations.create_job_safely instead.
        
        Args:
            task_type: Type of AI task (summarize/translate)
            text: Text to process
            options: Task-specific options
            client_job_id: Client-provided job ID
            
        Returns:
            Job information (stubbed for backward compatibility)
        """
        # Deprecated: Use JobOperations.create_job_safely instead
        # This method is kept for backward compatibility but should not be used
        logger.warning("create_ai_job is deprecated. Use JobOperations.create_job_safely instead.")
        
        return {
            'success': False,
            'error': 'Method deprecated. Use JobOperations.create_job_safely instead.',
            'deprecated': True
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
        """Get list of available AI models using ModelConfig"""
        models = []
        
        # Get all supported models from ModelConfig
        model_list = self.model_config.get_all_supported_models(AIProvider.OPENROUTER)
        
        for model in model_list:
            models.append({
                'id': model,
                'provider': AIProvider.OPENROUTER.value,
                'name': model.split('/')[-1].replace('-', ' ').title(),
                'capabilities': ['summarize', 'translate']
            })
        
        return models
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a specific model using ModelConfig"""
        if self.model_config.is_model_supported(AIProvider.OPENROUTER, model_id):
            return {
                'id': model_id,
                'provider': AIProvider.OPENROUTER.value,
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
                    'timestamp': datetime.now(timezone.utc).isoformat()
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
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': f"API error: {response.status_code}",
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }


    def get_recommended_models_for_task(self, task_type: str, consider_cost: bool = True) -> List[str]:
        """Get recommended models for a specific task type using ModelConfig"""
        try:
            # Map string task types to TaskType enum
            task_mapping = {
                'summarization': TaskType.SUMMARIZATION,
                'summarize': TaskType.SUMMARIZATION,
                'pdf_extraction': TaskType.PDF_EXTRACTION,
                'bank_statement_extraction': TaskType.BANK_STATEMENT_EXTRACTION,
                'invoice_extraction': TaskType.INVOICE_EXTRACTION
            }
            
            task_enum = task_mapping.get(task_type.lower())
            if not task_enum:
                return self.model_config.get_cost_efficient_models()
            
            return self.model_config.get_recommended_models(task_enum, consider_cost)
        except Exception as e:
            logger.warning(f"Error getting recommended models: {str(e)}")
            return [self.config['openrouter']['default_model']]
    
    def get_cost_efficient_models(self, task_type: str = None) -> List[str]:
        """Get cost-efficient models using ModelConfig"""
        try:
            if task_type:
                task_mapping = {
                    'summarization': TaskType.SUMMARIZATION,
                    'summarize': TaskType.SUMMARIZATION,
                    'pdf_extraction': TaskType.PDF_EXTRACTION,
                    'bank_statement_extraction': TaskType.BANK_STATEMENT_EXTRACTION,
                    'invoice_extraction': TaskType.INVOICE_EXTRACTION
                }
                task_enum = task_mapping.get(task_type.lower())
                return self.model_config.get_cost_efficient_models(task_enum)
            else:
                return self.model_config.get_cost_efficient_models()
        except Exception as e:
            logger.warning(f"Error getting cost-efficient models: {str(e)}")
            return [self.config['openrouter']['default_model']]
    
    def extract_text_from_pdf_data(self, pdf_data: Any):
        """
            Use AI to Extract Text from PDF Documents
        """
        pass
