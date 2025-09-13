# Agent Framework Integration Guide

## Overview

This document describes the integration of the unified AgentPromptFramework across the PDF processing services. The framework provides a standardized approach for AI-driven tasks with consistent input/output schemas, reusable prompt templates, and role-based agent definitions.

## Architecture Changes

### Before (Ad-hoc Approach)
- Individual services managed their own prompts
- Inconsistent input validation
- Duplicate prompt construction logic
- Hard-coded AI model selections

### After (Agent Framework)
- Centralized agent definitions in `src/services/agent_prompt_framework.py`
- Standardized input/output schemas with validation
- Reusable prompt templates per agent role
- Consistent model selection and error handling

## Agent Roles

### 1. DocumentExtractor
- **Purpose**: Extract structured data from documents (invoices, forms, etc.)
- **Key Features**:
  - JSON schema validation
  - Field extraction with type checking
  - Multi-language support
  - Structured output format

### 2. Summarizer
- **Purpose**: Create concise summaries of text content
- **Key Features**:
  - Configurable summary styles (brief, detailed, bullet points)
  - Word count limits
  - Reading time estimation
  - Multi-language support

### 3. Translator
- **Purpose**: Translate text between languages
- **Key Features**:
  - Quality levels (basic, professional, native)
  - Context preservation
  - Language detection
  - Cultural adaptation hints

### 4. DataValidator
- **Purpose**: Validate and correct extracted data
- **Key Features**:
  - Schema validation
  - Data type checking
  - Business rule validation
  - Error correction suggestions

## Service Integration

### AIService Updates

#### New Methods Added
- `_process_with_agent()`: Core agent processing logic
- `_validate_agent_result()`: Result validation and enrichment

#### Updated Methods
- `summarize_text()`: Now uses agent framework
- `translate_text()`: Now uses agent framework
- `create_ai_job()`: Updated to recommend agent-based methods

#### Usage Example
```python
from src.services.ai_service import AIService

ai_service = AIService()

# Summarization with agent framework
result = ai_service.summarize_text(
    text="Your long document text here...",
    options={
        'style': 'detailed',
        'max_words': 500
    }
)
```

### InvoiceExtractionService Updates

#### New Architecture
- **Agent Role**: DocumentExtractor
- **Framework Integration**: AgentPromptFramework for consistent extraction
- **Enhanced Validation**: AI-powered validation and correction

#### Updated Methods
- `extract_invoice_data()`: Now uses agent-based extraction
- `_call_ai_extraction()`: Replaced static method with agent framework
- `get_extraction_capabilities()`: Added agent framework information

#### Usage Example
```python
from src.services.invoice_extraction_service import InvoiceExtractionService

service = InvoiceExtractionService()

# Extract invoice data with agent framework
result = service.extract_invoice_data(
    pdf_file_path="/path/to/invoice.pdf",
    extraction_mode="detailed",
    include_line_items=True,
    validate_totals=True
)
```

## Configuration

### Agent Framework Settings
The framework is initialized automatically when services are instantiated:

```python
# In AIService
self.agent_framework = AgentPromptFramework()

# In InvoiceExtractionService
self.agent_framework = AgentPromptFramework()
```

### Model Selection
Agents use intelligent model selection based on task requirements:
- **DocumentExtractor**: deepseek/deepseek-r1 (good for structured extraction)
- **Summarizer**: Model based on summary style and language
- **Translator**: Model optimized for translation quality
- **DataValidator**: Model focused on accuracy and validation

## Input/Output Schemas

### DocumentExtractor Schema
```json
{
  "text": "string",
  "extraction_type": "invoice|receipt|form",
  "extraction_mode": "standard|detailed|minimal",
  "include_line_items": "boolean",
  "validate_totals": "boolean",
  "output_format": "json"
}
```

### Summarizer Schema
```json
{
  "text": "string",
  "style": "brief|detailed|bullet_points|executive",
  "max_words": "number",
  "target_language": "string",
  "preserve_formatting": "boolean"
}
```

### Translator Schema
```json
{
  "text": "string",
  "target_language": "string",
  "source_language": "string",
  "quality": "basic|professional|native",
  "context": "string",
  "preserve_formatting": "boolean"
}
```

## Error Handling

### Agent Framework Errors
- **ValidationError**: Invalid input parameters
- **ExtractionError**: AI processing failures
- **SchemaValidationError**: Output format issues

### Error Response Format
```json
{
  "success": false,
  "error": "Error message",
  "error_type": "ValidationError|ExtractionError|SchemaValidationError"
}
```

## Migration Guide

### From Legacy Methods

#### Old AIService Usage
```python
# Deprecated approach
result = ai_service.create_ai_job(
    task_type="summarization",
    content="text to summarize",
    options={"style": "detailed"}
)
```

#### New Agent Framework Usage
```python
# Recommended approach
result = ai_service.summarize_text(
    text="text to summarize",
    options={"style": "detailed"}
)
```

### From Legacy Invoice Extraction

#### Old Approach
```python
# Direct extraction without agent framework
service = InvoiceExtractionService()
result = service.extract_invoice_data(
    pdf_file_path="invoice.pdf",
    extraction_mode="standard"
)
```

#### New Agent Framework Approach
```python
# Same API, but uses agent framework internally
service = InvoiceExtractionService()
result = service.extract_invoice_data(
    pdf_file_path="invoice.pdf",
    extraction_mode="standard"
)
# Now includes agent framework metadata in response
```

## Testing

### Unit Tests
- Agent role validation
- Schema validation
- Prompt template testing
- Error handling verification

### Integration Tests
- End-to-end service testing
- Cross-service compatibility
- Performance benchmarking

### Test Files
- `tests/test_agent_prompt_framework.py`
- `tests/test_ai_service.py`
- `tests/test_invoice_extraction_service.py`

## Performance Considerations

### Benefits
- **Consistency**: Uniform processing across all services
- **Maintainability**: Centralized prompt management
- **Scalability**: Easy to add new agent roles
- **Reliability**: Standardized error handling

### Overhead
- Minimal performance impact due to efficient agent initialization
- Caching of agent configurations
- Optimized model selection

## Future Enhancements

### Planned Features
- Additional agent roles (e.g., OCR Corrector, Data Enricher)
- Custom agent creation API
- Agent performance monitoring
- Dynamic prompt optimization

### Extension Points
- Custom validation rules
- Custom prompt templates
- Custom agent roles
- Integration with external AI services

## Support

For questions or issues with the agent framework:
1. Check the agent instructions in `prompts/agent_instructions.md`
2. Review service-specific documentation
3. Examine the agent framework source code
4. Check the test suite for usage examples