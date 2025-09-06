# PDF Smaller Backend API - TODO List

## Core Features Focus

This document outlines the tasks needed to streamline the backend API to focus only on core feature endpoints and backend processing. User authentication is not needed, and the backend will only communicate with a frontend running on another server.

## Summary of Changes

The PDF Smaller Backend API needs to be simplified to focus only on its core functionality:

1. **Remove Authentication**: All user authentication, JWT, and security middleware should be removed as the API will only communicate with a trusted frontend server.

2. **Remove Subscription Features**: Subscription tiers, payment processing, and rate limiting based on user tiers should be removed.

3. **Focus on Core Services**: Keep only the essential PDF processing services:
   - Compression (single and bulk)
   - Conversion
   - OCR processing
   - AI services (required)

4. **Simplify Database Models**: Remove User and Subscription models, simplify the job tracking system.

5. **Update Configuration**: Remove unnecessary settings and simplify the configuration.

6. **Verify Celery Queue**: Ensure the Celery task queue is properly configured and operational.

## High Priority Tasks

### Database Model Cleanup

- [x] Verify CompressionJob model doesn't have user dependencies:
  - [x] Check if `CompressionJob` model in `src/models/compression_job.py` has any user references
  - [x] Remove `user_id` reference in the `to_dict()` method of CompressionJob
  - [x] If needed, update job tracking mechanism to work without user association

- [x] Remove subscription model if present:
  - [x] Check for `Subscription` and `Plan` models in the codebase
  - [x] Update database schema to remove these tables if they exist
  - [x] Remove references to subscription in other models

- [x] Fix Job model discrepancy:
  - [x] Create a new `job.py` file in `src/models/` that defines the `Job` and `JobStatus` classes
  - [x] Ensure it's compatible with existing code that references it
  - [x] Add it to `models/__init__.py` exports

### Code Cleanup

- [x] Remove authentication-related code:
  - [x] Check for JWT implementation in `src/main/main.py` and remove if present
  - [x] Check for auth_bp blueprint registration in `register_blueprints()` and remove if present
  - [x] Remove auth-related middleware and security checks in all routes
  - [x] Remove `require_auth` and `optional_auth` decorators from all routes

- [x] Remove subscription-related code:
  - [x] Check for subscription_bp blueprint registration and remove if present
  - [x] Remove rate limiting based on subscription tiers

- [x] Remove admin-related code if present

- [x] Fix Task Queue Implementation:
  - [x] Create the missing `src/queues/task_queue.py` file or
  - [x] Update routes to use Celery's native task invocation methods (`celery_app.task.delay()` or `celery_app.task.apply_async()`)
  - [x] Update task implementations to use available models

### Celery Queue Verification

- [x] Verify Celery configuration:
  - [x] Ensure `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are properly configured
  - [x] Check that Redis or RabbitMQ is available for the broker
  - [x] Verify task routing is correctly set up for compression, cleanup, and default queues

- [x] Update task references:
  - [x] Ensure all task references in `celery_app.py` point to existing tasks
  - [x] Fix task imports in `tasks.py` to use available models
  - [ ] Check for admin_bp blueprint registration and remove if present
  - [ ] Remove admin privilege checks if present

- [ ] Clean up non-core feature routes:
  - [ ] Keep all AI-related endpoints in `extended_features_routes.py`
  - [ ] Keep core conversion, OCR, and compression features
  - [ ] Remove cloud integration service and related endpoints

### API Simplification

- [ ] Update CORS configuration to allow requests from the frontend server:
  - [ ] Modify CORS settings in all blueprint registrations
  - [ ] Update origins to include the frontend server URL

- [ ] Simplify request validation:
  - [ ] Remove authentication checks from all routes
  - [ ] Keep only file validation and parameter validation
  - [ ] Update error handlers to focus on core functionality errors

### Core Feature Optimization

- [ ] Ensure compression service works correctly without authentication:
  - [ ] Check `compression_routes.py` for auth requirements and remove if present
  - [ ] Check `enhanced_compression_routes.py` for auth requirements and remove if present
  - [ ] Test compression functionality end-to-end

- [ ] Ensure AI services work correctly:
  - [ ] Verify all AI endpoints in `extended_features_routes.py` function properly
  - [ ] Test AI summarization and translation features
  - [ ] Ensure AI service configuration is properly set up

- [ ] Update Celery configuration in `celery_app.py`:
  - [ ] Keep all AI-related task routes
  - [ ] Keep core compression, conversion, and OCR task routes
  - [ ] Ensure beat schedule uses correct task path for `cleanup_expired_jobs`
  - [ ] Review worker settings for optimal performance
  - [ ] Ensure all core tasks have proper error handling

- [ ] Ensure file cleanup processes work correctly:
  - [ ] Update `cleanup_expired_jobs` task to work without auth if needed
  - [ ] Test file cleanup functionality

### Configuration Updates

- [x] Update configuration in `config.py`:
  - [x] Check for JWT settings (JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRES, etc.) and remove if present
  - [x] Check for user tier rate limits (RATE_LIMITS dictionary) and simplify if present
  - [x] Check for Stripe payment settings (STRIPE_PUBLISHABLE_KEY, etc.) and remove if present
  - [x] Update CORS settings to allow requests from the frontend server
  - [x] Keep all AI service configuration settings (OPENROUTER_API_KEY, etc.)
  - [x] Ensure all necessary environment variables for AI services are documented
  - [x] Keep core settings for file handling and compression

- [x] Update environment variables:
  - [x] Remove unnecessary auth/subscription variables
  - [x] Update documentation for required environment variables

- [x] Update Docker configuration:
  - [x] Focus on core services only (compression, conversion, OCR)
  - [x] Remove unnecessary services and dependencies

## Medium Priority Tasks

- [ ] Optimize file storage and cleanup processes:
  - [ ] Review temporary file handling in all services
  - [ ] Ensure proper cleanup of temporary files

- [ ] Improve error handling:
  - [ ] Add better error messages for core operations
  - [ ] Implement consistent error response format
  - [ ] Add better logging for debugging core functionality

- [ ] Update API documentation:
  - [ ] Update API specification to reflect simplified API
  - [ ] Remove authentication and subscription documentation
  - [ ] Focus on core feature endpoints

## Low Priority Tasks

- [ ] Performance optimization for large file processing:
  - [ ] Review timeout settings for long-running tasks
  - [ ] Optimize memory usage during file processing

- [ ] Add additional file format support if needed
- [ ] Improve monitoring for core services