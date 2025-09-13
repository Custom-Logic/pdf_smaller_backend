I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

I've analyzed the current AI service architecture and found that while there are some structured approaches in place, there's no unified agent framework ensuring consistent behavior across all AI services. The current `ai_service.py` has good patterns for JSON output and model selection, but the extraction services (`invoice_extraction_service.py`, `bank_statement_extraction_service.py`) use ad-hoc prompt construction without a standardized agent framework.

The system needs a central agent prompt framework that can:
- Define agent roles and behaviors for different AI tasks
- Enforce structured input validation across all services
- Ensure consistent output schemas and validation
- Provide reusable prompt templates with agent instructions
- Handle error cases and fallback behaviors consistently

### Approach

The implementation will create a comprehensive agent-based framework for AI services to ensure structured input and output across all AI interactions. This involves creating a central `AgentPromptFramework` that standardizes how AI agents are instructed, validates inputs, and formats outputs. The framework will define agent roles, input schemas, output schemas, and validation rules for each AI task type.

The approach focuses on:
1. **Central Agent Framework**: Create a unified system for managing AI agent prompts and behaviors
2. **Structured Input/Output**: Enforce consistent schemas for all AI interactions
3. **Agent Role Definitions**: Define specific agent personas for different tasks (extraction, summarization, etc.)
4. **Validation Layer**: Add comprehensive input validation and output verification
5. **Service Integration**: Update all existing AI services to use the new agent framework

### Reasoning

I explored the repository structure to understand the current AI service implementation. I read the main AI service file to understand existing patterns for structured prompts and JSON output. I examined the extraction services to see how they currently handle AI interactions and prompt construction. I analyzed the service registry and configuration to understand how AI services are integrated. I also reviewed the existing prompt files to understand the current documentation and planning approach used in this project.

## Mermaid Diagram

sequenceDiagram
    participant Service as AI Service
    participant Framework as AgentPromptFramework
    participant Agent as AI Agent
    participant Validator as ResponseValidator
    participant Client as API Client

    Client->>Service: Request AI processing
    Service->>Framework: validate_agent_input(data, schema)
    Framework->>Service: Validated input
    
    Service->>Framework: build_agent_prompt(role, task, data)
    Framework->>Service: Structured agent prompt
    
    Service->>Agent: Send prompt with agent instructions
    Agent->>Service: AI response with structured output
    
    Service->>Framework: validate_agent_output(response, schema)
    Framework->>Validator: Check schema compliance
    Validator->>Framework: Validation result
    Framework->>Service: Validated response
    
    alt Validation Success
        Service->>Client: Structured result with metadata
    else Validation Failure
        Service->>Client: Error with validation details
    end
    
    Note over Framework: Ensures consistent agent behavior
    Note over Agent: Follows role-specific instructions
    Note over Validator: Enforces output schema compliance

## Proposed File Changes

### e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)

References: 

- e:\projects\pdf_smaller_backend\src\services\ai_service.py(MODIFY)
- e:\projects\pdf_smaller_backend\src\services\invoice_extraction_service.py(MODIFY)
- e:\projects\pdf_smaller_backend\src\services\bank_statement_extraction_service.py(MODIFY)

Create a comprehensive agent prompt framework that standardizes AI agent behavior across all services. The framework will include:

**Core Components:**
- `AgentRole` enum defining different agent types (DOCUMENT_EXTRACTOR, SUMMARIZER, TRANSLATOR, DATA_VALIDATOR)
- `InputSchema` and `OutputSchema` classes for structured data validation
- `AgentPromptBuilder` class for constructing standardized prompts with agent instructions
- `AgentResponseValidator` class for validating AI responses against expected schemas

**Agent Definitions:**
- Document Extraction Agent: Specialized for extracting structured data from PDFs with strict output formatting
- Summarization Agent: Focused on creating concise, structured summaries with key points
- Translation Agent: Professional translator with quality assurance and formatting preservation
- Data Validation Agent: Ensures extracted data meets business rules and validation criteria

**Prompt Templates:**
- Standardized agent instruction templates with role definitions, behavioral guidelines, and output requirements
- Input validation schemas with required fields, data types, and constraints
- Output schemas with strict JSON structures and validation rules
- Error handling instructions for agents when data is incomplete or ambiguous

**Integration Methods:**
- `build_agent_prompt()` method that combines agent role, input data, and task-specific instructions
- `validate_agent_input()` method for pre-processing input validation
- `validate_agent_output()` method for post-processing response validation
- `get_agent_capabilities()` method returning supported features for each agent type

The framework will ensure all AI interactions follow consistent patterns and produce reliable, structured outputs.

### e:\projects\pdf_smaller_backend\prompts\agent_instructions.md(NEW)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)

Create comprehensive agent instruction prompts that define how AI agents should behave for different tasks. This file will contain:

**Agent Role Definitions:**
- Document Extraction Agent: "You are a professional document analysis expert specializing in extracting structured data from business documents. You maintain strict accuracy standards and always return data in the specified JSON format."
- Summarization Agent: "You are an expert content analyst who creates clear, concise summaries while preserving key information and context."
- Translation Agent: "You are a professional translator with expertise in maintaining context, tone, and formatting across languages."
- Data Validation Agent: "You are a data quality specialist who ensures extracted information meets business rules and validation criteria."

**Behavioral Guidelines:**
- Consistency requirements: Always follow the exact output schema provided
- Error handling: When information is unclear or missing, use null values or specified defaults
- Quality standards: Maintain high accuracy and provide confidence scores when applicable
- Validation rules: Check data integrity and flag potential issues

**Output Format Requirements:**
- Strict JSON schema compliance with required fields
- Standardized error reporting format
- Confidence scoring for uncertain extractions
- Metadata inclusion for processing information

**Task-Specific Instructions:**
- Invoice extraction: Focus on financial accuracy, validate totals, extract all line items
- Bank statement extraction: Ensure transaction consistency, validate running balances
- Document summarization: Preserve key points, maintain original context
- Translation: Preserve formatting, maintain professional tone

The instructions will be referenced by the `AgentPromptFramework` to ensure consistent agent behavior across all AI services.

### e:\projects\pdf_smaller_backend\src\services\ai_service.py(MODIFY)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)
- e:\projects\pdf_smaller_backend\prompts\agent_instructions.md(NEW)

Update the AI service to use the new `AgentPromptFramework` for all AI interactions. Replace the current manual prompt construction with standardized agent-based prompts:

**Integration Changes:**
- Import `AgentPromptFramework`, `AgentRole` from `src.services.agent_prompt_framework`
- Initialize the framework in `__init__()` method
- Replace `_build_structured_summary_prompt()` with `framework.build_agent_prompt(AgentRole.SUMMARIZER, ...)`
- Replace `_build_translation_prompt()` with `framework.build_agent_prompt(AgentRole.TRANSLATOR, ...)`

**Method Updates:**
- Update `_prepare_summary_request()` to use agent framework for input validation and prompt building
- Update `_prepare_translation_request()` to use standardized agent prompts
- Modify `_call_openrouter_summarization()` and `_call_openrouter_translation()` to use agent response validation
- Add `_validate_agent_response()` method that uses the framework's output validation

**Enhanced Functionality:**
- Add input validation using `framework.validate_agent_input()` before processing
- Add output validation using `framework.validate_agent_output()` after AI response
- Include agent confidence scores in response metadata
- Add agent capability reporting through `get_agent_capabilities()` method

**Backward Compatibility:**
- Maintain existing method signatures and return formats
- Ensure all current API contracts continue to work
- Add new agent-specific metadata to responses without breaking existing clients

The updated service will demonstrate the agent framework pattern that other AI services should follow.

### e:\projects\pdf_smaller_backend\src\services\invoice_extraction_service.py(MODIFY)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)
- e:\projects\pdf_smaller_backend\prompts\agent_instructions.md(NEW)

Refactor the invoice extraction service to use the new `AgentPromptFramework` for structured AI interactions:

**Framework Integration:**
- Import `AgentPromptFramework`, `AgentRole` from `src.services.agent_prompt_framework`
- Initialize the framework in `__init__()` method
- Replace `_prepare_extraction_prompt()` with `framework.build_agent_prompt(AgentRole.DOCUMENT_EXTRACTOR, ...)`

**Structured Input/Output:**
- Update `extract_invoice_data()` to use `framework.validate_agent_input()` for input validation
- Replace manual prompt construction with agent-based prompts that include role definition and behavioral guidelines
- Update `_call_ai_extraction()` to use the framework's standardized AI calling pattern
- Replace `_validate_extraction_result()` with `framework.validate_agent_output()` for consistent validation

**Agent-Specific Enhancements:**
- Define invoice extraction input schema with required fields (file_path, extraction_mode, options)
- Define invoice extraction output schema with structured invoice data format
- Add agent confidence scoring for extracted fields
- Include data quality indicators in the response

**Improved Error Handling:**
- Use framework's standardized error reporting format
- Add agent-specific error codes for different failure types
- Include validation failure details with specific field-level errors
- Maintain backward compatibility with existing error handling patterns

**Enhanced Capabilities:**
- Add `get_agent_capabilities()` method that returns supported extraction features
- Include agent metadata in extraction results
- Add support for agent-driven validation rules and business logic

The service will serve as a reference implementation for document extraction agents using the new framework.

### e:\projects\pdf_smaller_backend\src\services\bank_statement_extraction_service.py(MODIFY)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)
- e:\projects\pdf_smaller_backend\prompts\agent_instructions.md(NEW)

Update the bank statement extraction service to use the `AgentPromptFramework` for consistent agent-based AI interactions:

**Framework Integration:**
- Import and initialize `AgentPromptFramework` with `AgentRole.DOCUMENT_EXTRACTOR` specialization
- Replace `_prepare_extraction_prompt()` with framework-based agent prompt construction
- Update the service to use standardized agent instructions from `prompts/agent_instructions.md`

**Structured Processing:**
- Implement input validation using `framework.validate_agent_input()` with bank statement specific schema
- Define structured output schema for bank statement data (account_info, balances, transactions)
- Replace manual AI calling with framework's standardized `call_agent()` method
- Update response validation to use `framework.validate_agent_output()`

**Agent Behavior Enhancements:**
- Add agent-specific instructions for bank statement processing (balance validation, transaction categorization)
- Include confidence scoring for extracted financial data
- Add data consistency validation through agent instructions
- Implement agent-driven transaction categorization with confidence levels

**Quality Assurance:**
- Use agent framework's validation rules for financial data accuracy
- Add agent-specific error handling for common bank statement extraction issues
- Include data quality metrics in extraction results
- Implement agent-driven balance reconciliation validation

**Backward Compatibility:**
- Maintain existing method signatures and return formats
- Preserve current functionality while adding agent framework benefits
- Ensure existing API contracts continue to work with enhanced agent capabilities

The updated service will demonstrate how financial document extraction can benefit from structured agent interactions.

### e:\projects\pdf_smaller_backend\src\services\ocr_service.py(MODIFY)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)
- e:\projects\pdf_smaller_backend\prompts\agent_instructions.md(NEW)

Update the OCR service to integrate with the `AgentPromptFramework` for AI-enhanced text recognition and validation:

**Agent Integration:**
- Import `AgentPromptFramework` and `AgentRole.DATA_VALIDATOR` for OCR result validation
- Add agent-based post-processing for OCR results to improve accuracy
- Implement agent-driven text validation and correction capabilities

**Structured OCR Enhancement:**
- Use agent framework to validate and enhance OCR results through AI
- Add agent-based confidence scoring for OCR accuracy
- Implement agent-driven text correction for common OCR errors
- Add structured output validation for OCR results

**Quality Improvement:**
- Use agents to identify and flag potential OCR errors
- Add agent-based text formatting and structure detection
- Implement agent-driven language detection and validation
- Include confidence metrics for OCR quality assessment

**Agent Capabilities:**
- Add `get_agent_capabilities()` method for OCR enhancement features
- Include agent metadata in OCR results
- Add support for agent-driven OCR result validation
- Implement agent-based text quality scoring

**Integration Points:**
- Maintain existing OCR functionality while adding agent enhancements
- Use agents as a post-processing layer for improved accuracy
- Add agent validation for critical text extraction scenarios
- Include agent feedback in OCR result metadata

The service will demonstrate how traditional OCR can be enhanced with agent-based AI validation and correction.

### e:\projects\pdf_smaller_backend\tests\test_agent_framework.py(NEW)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)
- e:\projects\pdf_smaller_backend\src\services\ai_service.py(MODIFY)
- e:\projects\pdf_smaller_backend\src\services\invoice_extraction_service.py(MODIFY)
- e:\projects\pdf_smaller_backend\src\services\bank_statement_extraction_service.py(MODIFY)

Create comprehensive tests for the agent prompt framework to ensure structured input/output behavior:

**Framework Testing:**
- Test `AgentPromptBuilder` for consistent prompt generation across different agent roles
- Test input validation with various data types and edge cases
- Test output validation with valid and invalid AI responses
- Test agent role definitions and behavioral consistency

**Agent Behavior Tests:**
- Test document extraction agent with sample invoice and bank statement data
- Test summarization agent with various text types and lengths
- Test translation agent with different languages and formatting requirements
- Test data validation agent with correct and incorrect data sets

**Input/Output Validation Tests:**
- Test schema validation with valid inputs and expected failures
- Test output format compliance across different agent types
- Test error handling and fallback behaviors
- Test confidence scoring and metadata inclusion

**Integration Tests:**
- Test framework integration with existing AI services
- Test backward compatibility with current API contracts
- Test performance impact of agent framework overhead
- Test concurrent agent operations and thread safety

**Mock AI Response Tests:**
- Create mock AI responses for testing validation logic
- Test edge cases like partial responses, malformed JSON, missing fields
- Test agent error handling and recovery scenarios
- Test validation failure reporting and error details

**Service Integration Tests:**
- Test updated AI service with agent framework
- Test invoice extraction service with agent prompts
- Test bank statement extraction with agent validation
- Test OCR service with agent enhancement features

The tests will ensure the agent framework provides reliable, structured AI interactions across all services.

### e:\projects\pdf_smaller_backend\docs\agent_framework_guide.md(NEW)

References: 

- e:\projects\pdf_smaller_backend\src\services\agent_prompt_framework.py(NEW)
- e:\projects\pdf_smaller_backend\prompts\agent_instructions.md(NEW)

Create comprehensive documentation for the agent prompt framework that explains how to ensure AI services use agents with structured input and output:

**Framework Overview:**
- Introduction to the agent-based AI architecture
- Benefits of structured agent interactions (consistency, reliability, validation)
- Overview of agent roles and their specific capabilities
- Integration patterns with existing AI services

**Agent Role Definitions:**
- Document Extraction Agent: Specialized for structured data extraction from PDFs
- Summarization Agent: Expert content analysis and summary generation
- Translation Agent: Professional translation with context preservation
- Data Validation Agent: Quality assurance and business rule validation

**Structured Input/Output Patterns:**
- Input schema definition and validation requirements
- Output schema enforcement and validation rules
- Error handling and fallback behavior specifications
- Confidence scoring and metadata inclusion standards

**Implementation Guide:**
- How to integrate the framework into new AI services
- Step-by-step guide for updating existing services
- Best practices for agent prompt construction
- Common patterns and anti-patterns to avoid

**Usage Examples:**
- Code examples for each agent type with input/output samples
- Integration examples showing before/after framework adoption
- Error handling examples and recovery scenarios
- Performance optimization tips and considerations

**Validation and Quality Assurance:**
- Input validation patterns and error reporting
- Output validation rules and compliance checking
- Quality metrics and confidence scoring
- Testing strategies for agent-based services

**Development Guidelines:**
- Standards for creating new agent types
- Prompt engineering best practices for agents
- Validation rule development and testing
- Performance monitoring and optimization

The guide will serve as the definitive reference for implementing structured agent-based AI interactions across the platform.