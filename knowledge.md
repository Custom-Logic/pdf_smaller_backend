# PDF Smaller Backend Knowledge

## Project Overview
A Flask-based backend service for PDF compression and AI-powered document extraction (invoices, bank statements). Uses Celery for background task processing.

## Architecture
- **Flask**: Main web application framework
- **Celery**: Background task processing for file operations
- **SQLAlchemy**: Database ORM for job tracking
- **Redis/RabbitMQ**: Message broker for Celery
- **Gunicorn**: WSGI server for production

## Key Services
- `compression_service.py`: PDF compression logic
- `ai_service.py`: AI model integration for document extraction
- `file_management_service.py`: Unified file handling
- `invoice_extraction_service.py`: Invoice data extraction
- `bank_statement_extraction_service.py`: Bank statement processing

## Development Setup
- Main app: `app.py` (Flask application)
- Celery worker: `celery_worker.py`
- Celery beat: `celery_beat.py` (scheduler)
- Database management: `manage_db.py`

## File Structure
- `/src/routes/`: API endpoints
- `/src/services/`: Business logic services
- `/src/tasks/`: Celery task definitions
- `/src/utils/`: Helper utilities
- `/tests/`: Test suite
- `/uploads/`: File storage directory

## Important Notes
- Uses intelligent exception handling with specific error types
- File management is being standardized across services
- AI features support multiple models (DeepSeek, Moonshot) with cost-aware selection
- Background processes need Redis/message broker running
