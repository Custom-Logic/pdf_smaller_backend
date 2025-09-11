# Agent Instructions - Invoice and Bank Statement Extraction Implementation

## Overview

This document provides comprehensive instructions for implementing the invoice and bank statement extraction features in the PDF Smaller backend. Follow these instructions carefully to ensure consistent, high-quality implementation that aligns with existing codebase patterns.

## Task Execution Protocol

### Task Completion System

**Marking Tasks:**
- Use `[ ]` for incomplete tasks
- Use `[x]` for completed tasks
- Update `implementation_tasks.md` after each task completion
- Never mark a task complete unless all completion criteria are met

**Task Dependencies:**
- Complete tasks in sequential order unless explicitly noted
- Verify previous task completion before starting next task
- If a task fails, resolve issues before proceeding
- Document any deviations from the planned approach

**Quality Gates:**
- Each task must pass its completion criteria
- Code must follow existing patterns and conventions
- Tests must pass before marking tasks complete
- Documentation must be updated as specified

## Code Quality Standards

### Following Existing Patterns

**Service Classes:**
- Follow patterns from `src/services/ai_service.py`
- Use consistent initialization with dependency injection
- Implement proper error handling with try/catch blocks
- Add comprehensive logging using existing logger patterns
- Use type hints and docstrings consistently

**Route Implementation:**
- Follow patterns from `src/routes/pdf_suite.py`
- Use `get_file_and_validate()` helper for file validation
- Use response helpers from `src/utils/response_helpers.py`
- Implement consistent error handling
- Add proper request validation

**Celery Tasks:**
- Follow patterns from existing tasks in `src/tasks/tasks.py`
- Use `@celery_app.task(bind=True, max_retries=3)` decorator
- Implement proper job status updates
- Add retry logic with exponential backoff
- Include comprehensive error handling and cleanup

**Database Models:**
- Follow patterns from `src/models/job.py`
- Use existing enum patterns for new values
- Maintain consistency with existing field naming
- Ensure proper serialization methods

### Error Handling Requirements

**Exception Usage:**
- Use custom exceptions from `src/utils/exceptions.py`
- Create new exceptions following existing patterns
- Provide meaningful error messages
- Log errors appropriately without exposing sensitive data

**Error Response Patterns:**
- Use `error_response()` helper for consistent API responses
- Include appropriate HTTP status codes
- Provide helpful error messages for debugging
- Never expose internal system details in error messages

**Logging Standards:**
- Use existing logger patterns from other services
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Include relevant context (job_id, file_name, etc.)
- Never log sensitive data (file contents, API keys, etc.)

## Testing Requirements

### Unit Testing Standards

**Test Structure:**
- Follow patterns from existing test files
- Use pytest fixtures for common setup
- Mock external dependencies (AI service, file operations)
- Test both success and failure scenarios

**Coverage Requirements:**
- Test all public methods in service classes
- Test all route endpoints with various inputs
- Test error handling and edge cases
- Achieve minimum 80% code coverage for new code

**Mock Requirements:**
- Mock AI service responses for predictable testing
- Mock file operations to avoid filesystem dependencies
- Mock Celery tasks for route testing
- Use realistic test data that matches expected formats

### Integration Testing Standards

**End-to-End Testing:**
- Test complete workflows from API request to job completion
- Test file upload, processing, and download flows
- Test job status polling and updates
- Test error scenarios and recovery

**Test Data Requirements:**
- Create sample PDF files for testing
- Include both valid and invalid test cases
- Test with various file sizes and formats
- Include edge cases and boundary conditions

## Documentation Update Requirements

### API Documentation Updates

**Required Updates to `docs/api_documentation.md`:**
- Add new endpoint sections following existing format
- Include complete request/response examples
- Document all parameters and their validation rules
- Add error response examples with status codes
- Update table of contents and navigation

**Documentation Standards:**
- Use consistent formatting with existing documentation
- Include curl examples for all endpoints
- Document authentication requirements (if any)
- Include rate limiting information
- Add troubleshooting sections for common issues

### Service Documentation Updates

**Required Updates to `docs/service_documentation.md`:**
- Document new service classes and their methods
- Include initialization requirements and dependencies
- Document configuration requirements
- Add usage examples and integration patterns
- Document error handling and recovery procedures

### Architecture Documentation Updates

**Required Updates to `docs/architecture_guide.md`:**
- Add new services to architecture overview
- Update component interaction diagrams
- Document new task types and job flows
- Add dependency information
- Update deployment considerations

## Implementation Guidelines

### Phase 1: Core Infrastructure (Tasks 1-3)

**Critical Requirements:**
- Extend existing enums without breaking changes
- Add exceptions following existing patterns
- Update configuration with proper defaults
- Test that existing functionality remains unaffected

**Validation Steps:**
- Verify existing job creation still works
- Test that new task types can be created
- Confirm configuration variables are accessible
- Check that imports work correctly

### Phase 2: Service Implementation (Tasks 4-6)

**Service Class Requirements:**
- Initialize with proper dependency injection
- Implement comprehensive error handling
- Add detailed logging for debugging
- Use type hints and docstrings
- Follow existing service patterns exactly

**AI Integration Requirements:**
- Use existing `AIService` class for OpenRouter integration
- Implement proper prompt engineering for extraction tasks
- Handle AI service errors gracefully
- Validate AI responses before processing
- Add timeout handling for long-running requests

**Export Functionality Requirements:**
- Support JSON, CSV, and Excel formats
- Use proper file naming conventions
- Integrate with existing file manager
- Handle export errors gracefully
- Add proper MIME type detection

### Phase 3: Celery Task Implementation (Tasks 7-8)

**Task Implementation Requirements:**
- Follow existing task patterns exactly
- Implement proper job status lifecycle management
- Add retry logic with exponential backoff
- Include comprehensive error handling
- Add proper resource cleanup

**Job Status Management:**
- Update status to PROCESSING when task starts
- Update to COMPLETED with results on success
- Update to FAILED with error message on failure
- Include progress updates for long-running tasks
- Handle task cancellation gracefully

### Phase 4: API Route Implementation (Tasks 9-11)

**Route Implementation Requirements:**
- Use existing blueprint patterns
- Implement proper file validation
- Add parameter validation and sanitization
- Use consistent response helpers
- Add comprehensive error handling

**Security Requirements:**
- Validate file types and sizes
- Sanitize all input parameters
- Implement proper rate limiting
- Add request logging for monitoring
- Prevent path traversal attacks

### Phase 5: Testing Implementation (Tasks 12-14)

**Test Implementation Requirements:**
- Create comprehensive unit tests
- Add integration tests for complete workflows
- Test error scenarios and edge cases
- Use realistic test data
- Achieve good test coverage

**Test Data Management:**
- Create sample PDF files for testing
- Include both valid and invalid test cases
- Mock external service responses
- Use fixtures for common test setup
- Clean up test data after tests

### Phase 6: Documentation Updates (Tasks 15-18)

**Documentation Requirements:**
- Update all specified documentation files
- Follow existing documentation patterns
- Include complete examples and use cases
- Add troubleshooting information
- Update navigation and cross-references

**Content Standards:**
- Use clear, concise language
- Include practical examples
- Document all configuration options
- Add deployment considerations
- Include performance recommendations

### Phase 7: Final Validation (Tasks 19-22)

**End-to-End Testing Requirements:**
- Test complete workflows with real data
- Verify performance under load
- Test error recovery scenarios
- Validate security measures
- Check resource usage and cleanup

**Deployment Readiness:**
- Verify all environment variables are documented
- Check database migration requirements
- Test with production-like configuration
- Validate monitoring and logging setup
- Confirm resource requirements

## Common Pitfalls to Avoid

### Code Implementation Pitfalls

1. **Inconsistent Patterns:**
   - Don't create new patterns when existing ones work
   - Follow existing naming conventions exactly
   - Use established error handling approaches

2. **Poor Error Handling:**
   - Don't ignore exceptions or fail silently
   - Always log errors with appropriate context
   - Provide meaningful error messages to users

3. **Security Issues:**
   - Don't trust user input without validation
   - Always sanitize file uploads
   - Never log sensitive information

4. **Performance Problems:**
   - Don't load large files into memory unnecessarily
   - Implement proper timeout handling
   - Clean up resources after processing

### Testing Pitfalls

1. **Insufficient Coverage:**
   - Don't skip error case testing
   - Test edge cases and boundary conditions
   - Include integration testing

2. **Poor Test Data:**
   - Don't use unrealistic test data
   - Include various file types and sizes
   - Test with malformed inputs

3. **Missing Mocks:**
   - Mock all external dependencies
   - Don't rely on external services in tests
   - Use predictable mock responses

### Documentation Pitfalls

1. **Incomplete Documentation:**
   - Don't skip any required documentation updates
   - Include all parameters and responses
   - Add troubleshooting information

2. **Inconsistent Formatting:**
   - Follow existing documentation patterns
   - Use consistent terminology
   - Maintain proper navigation structure

## Success Criteria

### Technical Success Criteria

- [ ] All 22 tasks completed and marked as [x]
- [ ] All tests passing with good coverage
- [ ] End-to-end workflows functional
- [ ] Performance within acceptable limits
- [ ] Security review completed
- [ ] Documentation updated and accurate

### Quality Success Criteria

- [ ] Code follows existing patterns consistently
- [ ] Error handling is comprehensive and appropriate
- [ ] Logging provides useful debugging information
- [ ] API responses are consistent with existing endpoints
- [ ] File handling is secure and efficient

### Documentation Success Criteria

- [ ] All specified documentation files updated
- [ ] API documentation includes complete examples
- [ ] Service documentation covers all new components
- [ ] Architecture documentation reflects new features
- [ ] Deployment guide includes new requirements

## Post-Implementation Checklist

### Code Review Checklist

- [ ] All new code follows existing patterns
- [ ] Error handling is comprehensive
- [ ] Logging is appropriate and secure
- [ ] Type hints and docstrings are complete
- [ ] No hardcoded values or magic numbers
- [ ] Resource cleanup is implemented

### Testing Checklist

- [ ] Unit tests cover all new functionality
- [ ] Integration tests verify complete workflows
- [ ] Error scenarios are tested
- [ ] Performance is acceptable
- [ ] Security measures are validated

### Documentation Checklist

- [ ] All required documentation is updated
- [ ] Examples are accurate and helpful
- [ ] Configuration is documented
- [ ] Troubleshooting information is included
- [ ] Navigation and cross-references work

### Deployment Checklist

- [ ] Environment variables are documented
- [ ] Dependencies are specified
- [ ] Resource requirements are documented
- [ ] Monitoring is configured
- [ ] Backup and recovery procedures are documented

## Support and Troubleshooting

### Common Issues and Solutions

**Task Failures:**
- Review completion criteria carefully
- Check for missing dependencies
- Verify existing patterns are followed
- Test incrementally during implementation

**Integration Problems:**
- Verify all imports work correctly
- Check configuration variables are set
- Test with existing functionality
- Review error logs for specific issues

**Performance Issues:**
- Profile memory usage during processing
- Check for resource leaks
- Optimize file handling operations
- Review AI service timeout settings

**Documentation Problems:**
- Follow existing documentation patterns exactly
- Verify all links and references work
- Check formatting and navigation
- Test examples for accuracy

### Getting Help

If you encounter issues during implementation:

1. Review the existing codebase for similar patterns
2. Check the completion criteria for the current task
3. Verify all dependencies are properly installed
4. Review error logs for specific error messages
5. Test with minimal examples to isolate issues

Remember: The goal is to create features that integrate seamlessly with the existing codebase while maintaining high quality and consistency standards.