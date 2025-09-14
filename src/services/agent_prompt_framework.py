"""
Agent Prompt Framework - Centralized AI Agent Management System

This module provides a comprehensive framework for managing AI agent interactions
across all services. It standardizes agent roles, prompts, input validation,
and output validation to ensure consistent AI behavior.

Key Features:
- Standardized agent roles and behaviors
- Structured input/output validation
- Reusable prompt templates
- Comprehensive error handling
- Agent capability reporting
"""

import json
import logging
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

from src.utils.exceptions import ValidationError


class AgentRole(Enum):
    """Defines the different types of AI agents available in the system."""
    DOCUMENT_EXTRACTOR = "document_extractor"
    SUMMARIZER = "summarizer"
    TRANSLATOR = "translator"
    DATA_VALIDATOR = "data_validator"


@dataclass
class InputSchema:
    """Defines the structure for agent input validation."""
    required_fields: List[str]
    optional_fields: List[str]
    field_types: Dict[str, str]
    constraints: Dict[str, Any]
    
    def validate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates input data against the schema."""
        errors = {}
        validated_data = {}
        
        # Check required fields
        for field in self.required_fields:
            if field not in input_data:
                errors.update(field=f"Missing required field: {field}")
            else:
                validated_data[field] = input_data[field]
        
        # Check optional fields
        for field in self.optional_fields:
            if field in input_data:
                validated_data[field] = input_data[field]
        
        # Validate field types
        for field, value in validated_data.items():
            expected_type = self.field_types.get(field)
            if expected_type:
                if expected_type == "string" and not isinstance(value, str):
                    errors.update(field=f"Field {field} must be a string")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.update(field=f"Field {field} must be an integer")
                elif expected_type == "list" and not isinstance(value, list):
                    errors.update(field=f"Field {field} must be a list")
                elif expected_type == "dict" and not isinstance(value, dict):
                    errors.update(field=f"Field {field} must be a dict")
        
        # Check constraints
        for field, value in validated_data.items():
            if field in self.constraints:
                constraint = self.constraints[field]
                if "min_length" in constraint and len(str(value)) < constraint["min_length"]:
                    errors.update(field=f"Field {field} must be at least {constraint['min_length']} characters")
                if "max_length" in constraint and len(str(value)) > constraint["max_length"]:
                    errors.update(field=f"Field {field} must be at most {constraint['max_length']} characters")
        
        if errors:
            raise ValidationError(message="Input validation failed", details=errors)
        
        return validated_data


@dataclass
class OutputSchema:
    """Defines the structure for agent output validation."""
    required_fields: List[str]
    optional_fields: List[str]
    field_types: Dict[str, str]
    nested_schemas: Dict[str, 'OutputSchema'] = None
    
    def validate(self, output_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates output data against the schema."""
        errors = {}
        validated_data = {}
        
        # Check required fields
        for field in self.required_fields:
            if field not in output_data:
                errors.update(field=f"Missing required field: {field}")
            else:
                validated_data[field] = output_data[field]
        
        # Check optional fields
        for field in self.optional_fields:
            if field in output_data:
                validated_data[field] = output_data[field]
        
        # Validate field types
        for field, value in validated_data.items():
            expected_type = self.field_types.get(field)
            if expected_type:
                if expected_type == "string" and not isinstance(value, str):
                    errors.update(field=f"Field {field} must be a string")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.update(field=f"Field {field} must be an integer")
                elif expected_type == "list" and not isinstance(value, list):
                    errors.update(field=f"Field {field} must be a list")
                elif expected_type == "dict" and not isinstance(value, dict):
                    errors.update(field=f"Field {field} must be a dict")
                elif expected_type == "float" and not isinstance(value, (int, float)):
                    errors.update(field=f"Field {field} must be a float")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.update(field=f"Field {field} must be a boolean")
        
        # Validate nested schemas
        if self.nested_schemas:
            for field, schema in self.nested_schemas.items():
                if field in validated_data:
                    try:
                        if isinstance(validated_data[field], list):
                            validated_data[field] = [
                                schema.validate(item) if isinstance(item, dict) else item
                                for item in validated_data[field]
                            ]
                        elif isinstance(validated_data[field], dict):
                            validated_data[field] = schema.validate(validated_data[field])
                    except ValidationError as e:
                        errors.update(e=e.details)
        
        if errors:
            raise ValidationError("Output validation failed", details=errors)
        
        return validated_data


class AgentPromptFramework:
    """Central framework for managing AI agent interactions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.schemas = self._initialize_schemas()
        self.prompts = self._initialize_prompts()
    
    def _initialize_schemas(self) -> Dict[AgentRole, Dict[str, Union[InputSchema, OutputSchema]]]:
        """Initialize schemas for all agent roles."""
        return {
            AgentRole.DOCUMENT_EXTRACTOR: {
                'input': InputSchema(
                    required_fields=['file_path', 'extraction_mode'],
                    optional_fields=['options', 'confidence_threshold'],
                    field_types={
                        'file_path': 'string',
                        'extraction_mode': 'string',
                        'options': 'dict',
                        'confidence_threshold': 'float'
                    },
                    constraints={
                        'file_path': {'min_length': 1},
                        'extraction_mode': {'min_length': 1}
                    }
                ),
                'output': OutputSchema(
                    required_fields=['success', 'data', 'confidence_score'],
                    optional_fields=['metadata', 'warnings', 'errors'],
                    field_types={
                        'success': 'boolean',
                        'data': 'dict',
                        'confidence_score': 'float',
                        'metadata': 'dict',
                        'warnings': 'list',
                        'errors': 'list'
                    }
                )
            },
            AgentRole.SUMMARIZER: {
                'input': InputSchema(
                    required_fields=['content', 'summary_type'],
                    optional_fields=['max_length', 'style', 'focus_areas'],
                    field_types={
                        'content': 'string',
                        'summary_type': 'string',
                        'max_length': 'integer',
                        'style': 'string',
                        'focus_areas': 'list'
                    },
                    constraints={
                        'content': {'min_length': 1},
                        'summary_type': {'min_length': 1}
                    }
                ),
                'output': OutputSchema(
                    required_fields=['success', 'summary', 'key_points'],
                    optional_fields=['metadata', 'confidence_score'],
                    field_types={
                        'success': 'boolean',
                        'summary': 'string',
                        'key_points': 'list',
                        'metadata': 'dict',
                        'confidence_score': 'float'
                    }
                )
            },
            AgentRole.TRANSLATOR: {
                'input': InputSchema(
                    required_fields=['content', 'target_language'],
                    optional_fields=['source_language', 'style', 'preserve_formatting'],
                    field_types={
                        'content': 'string',
                        'target_language': 'string',
                        'source_language': 'string',
                        'style': 'string',
                        'preserve_formatting': 'boolean'
                    },
                    constraints={
                        'content': {'min_length': 1},
                        'target_language': {'min_length': 2}
                    }
                ),
                'output': OutputSchema(
                    required_fields=['success', 'translated_text', 'source_language'],
                    optional_fields=['confidence_score', 'metadata'],
                    field_types={
                        'success': 'boolean',
                        'translated_text': 'string',
                        'source_language': 'string',
                        'confidence_score': 'float',
                        'metadata': 'dict'
                    }
                )
            },
            AgentRole.DATA_VALIDATOR: {
                'input': InputSchema(
                    required_fields=['data', 'validation_rules'],
                    optional_fields=['context', 'strict_mode'],
                    field_types={
                        'data': 'dict',
                        'validation_rules': 'dict',
                        'context': 'string',
                        'strict_mode': 'boolean'
                    },
                    constraints={
                        'data': {'min_length': 1},
                        'validation_rules': {'min_length': 1}
                    }
                ),
                'output': OutputSchema(
                    required_fields=['success', 'is_valid', 'issues'],
                    optional_fields=['suggestions', 'confidence_score'],
                    field_types={
                        'success': 'boolean',
                        'is_valid': 'boolean',
                        'issues': 'list',
                        'suggestions': 'list',
                        'confidence_score': 'float'
                    }
                )
            }
        }
    
    def _initialize_prompts(self) -> Dict[AgentRole, str]:
        """Initialize prompt templates for all agent roles."""
        return {
            AgentRole.DOCUMENT_EXTRACTOR: """
You are a professional document analysis expert specializing in extracting structured data from business documents. 
Your role is to accurately identify and extract relevant information while maintaining strict data integrity standards.

TASK: Extract structured data from the provided document.

INPUT SPECIFICATIONS:
- File Path: {file_path}
- Extraction Mode: {extraction_mode}
- Options: {options}

REQUIRED OUTPUT FORMAT:
Return a JSON object with the following structure:
{{
    "success": true/false,
    "data": {{
        // Extracted data based on document type
        "invoice_number": "string",
        "date": "string (YYYY-MM-DD)",
        "total_amount": "number",
        "line_items": [
            {{
                "description": "string",
                "quantity": "number",
                "unit_price": "number",
                "total": "number"
            }}
        ]
    }},
    "confidence_score": 0.0-1.0,
    "metadata": {{
        "extraction_timestamp": "ISO-8601 timestamp",
        "document_type": "string",
        "page_count": "number"
    }},
    "warnings": ["any warnings or uncertainties"],
    "errors": ["any extraction errors"]
}}

GUIDELINES:
- Always return valid JSON
- Use null for missing data, never omit fields
- Include confidence scores for each extracted field
- Flag any ambiguous or unclear data in warnings
- Handle edge cases gracefully with appropriate error messages
- Maintain data type consistency throughout

EXTRACTED DATA:
{input_data}
""",
            AgentRole.SUMMARIZER: """
You are an expert content analyst who creates clear, concise summaries while preserving key information and context.
Your role is to distill complex content into actionable insights without losing critical details.

TASK: Create a structured summary of the provided content.

INPUT SPECIFICATIONS:
- Content Type: {summary_type}
- Content Length: {content_length} characters
- Target Summary Length: {max_length} characters
- Focus Areas: {focus_areas}

REQUIRED OUTPUT FORMAT:
Return a JSON object with the following structure:
{{
    "success": true/false,
    "summary": "concise summary text",
    "key_points": [
        "key point 1",
        "key point 2",
        "key point 3"
    ],
    "metadata": {{
        "original_length": number,
        "summary_length": number,
        "compression_ratio": number,
        "processing_timestamp": "ISO-8601 timestamp"
    }},
    "confidence_score": 0.0-1.0
}}

GUIDELINES:
- Preserve essential context and meaning
- Use bullet points for key insights
- Maintain professional tone and clarity
- Include confidence score based on content clarity
- Handle technical content appropriately
- Flag any uncertainties in metadata

CONTENT TO SUMMARIZE:
{content}
""",
            AgentRole.TRANSLATOR: """
You are a professional translator with expertise in maintaining context, tone, and formatting across languages.
Your role is to provide accurate translations while preserving the original meaning and professional quality.

TASK: Translate the provided content to {target_language}.

INPUT SPECIFICATIONS:
- Source Language: {source_language}
- Target Language: {target_language}
- Content Length: {content_length} characters
- Style: {style}
- Preserve Formatting: {preserve_formatting}

REQUIRED OUTPUT FORMAT:
Return a JSON object with the following structure:
{{
    "success": true/false,
    "translated_text": "translated content",
    "source_language": "detected or provided source language",
    "confidence_score": 0.0-1.0,
    "metadata": {{
        "translation_timestamp": "ISO-8601 timestamp",
        "character_count": number,
        "style_applied": "string"
    }}
}}

GUIDELINES:
- Maintain professional tone and accuracy
- Preserve formatting and structure
- Handle technical terms appropriately
- Include confidence score based on translation quality
- Provide source language detection when not specified
- Handle edge cases gracefully

CONTENT TO TRANSLATE:
{content}
""",
            AgentRole.DATA_VALIDATOR: """
You are a data quality specialist who ensures extracted information meets business rules and validation criteria.
Your role is to validate data integrity and provide actionable feedback for improvement.

TASK: Validate the provided data against specified rules.

INPUT SPECIFICATIONS:
- Data Type: {data_type}
- Validation Rules: {validation_rules}
- Context: {context}
- Strict Mode: {strict_mode}

REQUIRED OUTPUT FORMAT:
Return a JSON object with the following structure:
{{
    "success": true/false,
    "is_valid": true/false,
    "issues": [
        {{
            "field": "field name",
            "issue": "description of the issue",
            "severity": "error/warning/info",
            "suggestion": "recommended fix"
        }}
    ],
    "suggestions": ["general improvement suggestions"],
    "confidence_score": 0.0-1.0
}}

GUIDELINES:
- Be specific about validation issues
- Provide actionable suggestions for fixes
- Use appropriate severity levels
- Include confidence scores for validation assessments
- Handle complex validation rules gracefully
- Provide clear guidance for data improvement

DATA TO VALIDATE:
{data}

VALIDATION RULES:
{validation_rules}
"""
        }
    
    def validate_agent_input(self, role: AgentRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates input data for a specific agent role."""
        if role not in self.schemas:
            raise ValidationError(f"Unknown agent role: {role}")
        
        schema = self.schemas[role]['input']
        return schema.validate(input_data)
    
    def validate_agent_output(self, role: AgentRole, output_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates output data for a specific agent role."""
        if role not in self.schemas:
            raise ValidationError(f"Unknown agent role: {role}")
        
        schema = self.schemas[role]['output']
        return schema.validate(output_data)
    
    def build_agent_prompt(self, role: AgentRole, task: str, input_data: Dict[str, Any]) -> str:
        """Builds a standardized prompt for a specific agent role."""
        if role not in self.prompts:
            raise ValidationError(f"Unknown agent role: {role}")
        
        # Validate input first
        validated_input = self.validate_agent_input(role, input_data)
        
        # Build prompt with role-specific template
        template = self.prompts[role]
        
        # Add common context
        context = {
            'input_data': json.dumps(validated_input, indent=2),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'role': role.value
        }
        
        # Add role-specific context
        role_context = self._get_role_context(role, validated_input)
        context.update(role_context)
        
        # Format the prompt
        try:
            prompt = template.format(**context)
            return prompt
        except KeyError as e:
            raise ValidationError(f"Missing required context for prompt: {e}")
    
    def _get_role_context(self, role: AgentRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gets role-specific context for prompt building."""
        context = {}
        
        if role == AgentRole.DOCUMENT_EXTRACTOR:
            context.update({
                'file_path': input_data.get('file_path', ''),
                'extraction_mode': input_data.get('extraction_mode', 'standard'),
                'options': json.dumps(input_data.get('options', {}))
            })
        elif role == AgentRole.SUMMARIZER:
            content = input_data.get('content', '')
            context.update({
                'content': content,
                'content_length': len(content),
                'summary_type': input_data.get('summary_type', 'general'),
                'max_length': input_data.get('max_length', 500),
                'focus_areas': ', '.join(input_data.get('focus_areas', []))
            })
        elif role == AgentRole.TRANSLATOR:
            content = input_data.get('content', '')
            context.update({
                'content': content,
                'content_length': len(content),
                'target_language': input_data.get('target_language', ''),
                'source_language': input_data.get('source_language', 'auto-detect'),
                'style': input_data.get('style', 'professional'),
                'preserve_formatting': input_data.get('preserve_formatting', True)
            })
        elif role == AgentRole.DATA_VALIDATOR:
            context.update({
                'data': json.dumps(input_data.get('data', {}), indent=2),
                'data_type': input_data.get('data_type', 'general'),
                'validation_rules': json.dumps(input_data.get('validation_rules', {}), indent=2),
                'context': input_data.get('context', ''),
                'strict_mode': input_data.get('strict_mode', False)
            })
        
        return context
    
    def get_agent_capabilities(self, role: AgentRole) -> Dict[str, Any]:
        """Returns capabilities and limitations for a specific agent role."""
        capabilities = {
            AgentRole.DOCUMENT_EXTRACTOR: {
                'supported_formats': ['pdf', 'image'],
                'extraction_types': ['invoice', 'receipt', 'bank_statement', 'contract'],
                'max_file_size': '10MB',
                'supported_languages': ['en', 'es', 'fr', 'de'],
                'confidence_threshold': 0.8
            },
            AgentRole.SUMMARIZER: {
                'max_content_length': 100000,
                'summary_types': ['executive', 'technical', 'bullet_points', 'detailed'],
                'languages': ['en', 'es', 'fr', 'de'],
                'max_summary_length': 2000
            },
            AgentRole.TRANSLATOR: {
                'supported_languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'zh', 'ja', 'ko'],
                'max_content_length': 50000,
                'translation_styles': ['formal', 'casual', 'technical', 'legal'],
                'format_preservation': True
            },
            AgentRole.DATA_VALIDATOR: {
                'validation_types': ['business_rules', 'format', 'completeness', 'consistency'],
                'max_data_size': '1MB',
                'supported_formats': ['json', 'csv', 'xml']
            }
        }
        
        return capabilities.get(role, {})


# Global framework instance
agent_framework = AgentPromptFramework()