# TODO.MD 

## Project Overview
This document outlines the refactoring plan for phasing out `cleanup_service.py` and `file_manager.py` from the pdfsmaller.site API project.

## Phase 1: Audit Current Usage (Before Removal)

### Tasks:
- [ ] Identify all imports of `cleanup_service.py` throughout the codebase
- [ ] Document all functions/methods being called from `cleanup_service.py`
- [ ] Create a mapping of `cleanup_service.py` functionality to replacement services
- [ ] Repeat the same audit process for `file_manager.py`

### Investigation Commands:
```bash
# Find all imports of cleanup_service
grep -r "import cleanup_service" .
grep -r "from cleanup_service" .

# Find all usages of cleanup_service functions
grep -r "cleanup_service\." .
```

## Phase 2: Replacement Implementation

### Tasks:
- [ ] Implement replacement functionality for each method in `cleanup_service.py`
- [ ] Update all calling code to use the new implementations instead
- [ ] Ensure all tests pass with the new implementations
- [ ] Verify no functionality regression occurs

## Phase 3: Verification and Testing

### Tasks:
- [ ] Create comprehensive tests for the replacement functionality
- [ ] Perform integration testing to ensure all components work together
- [ ] Conduct load testing to verify performance characteristics
- [ ] Validate that all file cleanup operations work as expected

## Phase 4: Removal Process

### Tasks:
- [ ] Remove all imports of `cleanup_service.py` from the codebase
- [ ] Delete the `cleanup_service.py` file from the repository
- [ ] Repeat the removal process for `file_manager.py`
- [ ] Update documentation to reflect the new architecture

## Phase 5: Post-Removal Validation

### Tasks:
- [ ] Run full test suite to ensure no regressions
- [ ] Verify all API endpoints function correctly
- [ ] Confirm file cleanup operations work as expected
- [ ] Monitor system for any issues in production

## Notes:
- Do not delete `cleanup_service.py` until all references have been removed
- Maintain backward compatibility during the transition period
- Keep the removal process atomic - remove all references at once rather than piecemeal

## Risk Mitigation:
- Create backups before making significant changes
- Have a rollback plan in case of issues
- Monitor system closely after changes are deployed

## Timeline:
- Phase 1: [Start Date] - [End Date]
- Phase 2: [Start Date] - [End Date]
- Phase 3: [Start Date] - [End Date]
- Phase 4: [Start Date] - [End Date]
- Phase 5: [Start Date] - [End Date]

## Responsible Team Members:
- [ ] Assign primary developer for this refactor
- [ ] Assign code reviewer for changes
- [ ] Assign QA tester for validation

---
*Last updated: [Date]*