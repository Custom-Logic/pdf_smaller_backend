**Task Prompt: Code Consistency Fix - Remove All session_id References**

**Objective:** 
Eliminate all code references to `session_id` that are causing the SQL operational error. The database schema has already been modified - now align the application code to match the current schema.

**Problem Statement:**
The application code is attempting to query a `session_id` column that no longer exists in the database, causing SQL errors. Fix this by removing all `session_id` references throughout the codebase.

**Scope Boundaries:**
- ONLY remove `session_id` references from application code
- NO database schema changes (already completed)
- NO new features or refactoring
- NO modifications to unrelated functionality

**Specific Files to Modify:**

1. **SQLAlchemy Model (`src/models/job.py`):**
   - Remove `session_id` column definition
   - Remove from `__repr__` method
   - Remove from any query filters or conditions

2. **Route Handlers all route handlers:**
   - Remove `session_id` from request parameters
   - Remove from response serialization
   - Update any session-based filtering logic

3. **Task Handlers (`src/tasks/tasks.py`):**
   - Remove `session_id` from task signatures
   - Remove from task invocation parameters
   - Update job retrieval queries to exclude session_id

4. **Service Utilities (`src/utils/` any relevant files):**
   - Remove session_id from job tracking
   - Update any session-based utility functions
   - Remove any session_id references from job status tracking

5. **Query Patterns (search entire codebase):**
   - Remove `.filter_by(session_id=...)` patterns
   - Remove `Job.session_id` references in queries
   - Update any JOIN conditions involving session_id

**Required Changes:**

1. **In Job model:** Delete the line: `session_id = db.Column(db.String(36), nullable=True)`

2. **In routes:** Remove any `session_id` parameter processing or filtering

3. **In tasks:** Update all task functions to remove `session_id` parameters

4. **In queries:** Change `Job.query.filter_by(session_id=xyz)` to `Job.query.filter_by(job_id=xyz)`

**Validation Requirements:**
- All existing endpoints must work
- Task processing must complete without SQL errors
- Job status retrieval must function correctly
- No regression in error handling capabilities

**Error Handling:**
- Ensure no try-catch blocks are hiding session_id errors
- Verify all SQL queries work with current schema
- Test both individual and bulk compression operations


**Deliverables:**
1. Cleaned Job model without session_id references
2. Updated route handlers with proper filtering
3. Modified task signatures and calls
4. Verified operational functionality

**Success Criteria:**
- SQL operational error eliminated
- All compression tasks process successfully
- Job status queries return correct results
- System operates without database schema conflicts

Execute ONLY these targeted changes. Do not modify database schema, add features, or refactor unrelated code. The fix must be minimal and focused solely on removing session_id code references.