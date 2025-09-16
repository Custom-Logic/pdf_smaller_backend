#!/usr/bin/env python3
"""
Test script to verify conversion job status fix
Per project rules (Rule 2) and debug-phase restrictions, this test uses existing
modules and methods to validate the conversion service job status handling.
"""

import sys
import os
import uuid
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up Flask app context
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from src.app import create_app
from src.models.base import db
from src.models import Job, JobStatus
from src.services.conversion_service import ConversionService
from src.jobs import JobOperationsController

def test_conversion_job_status():
    """Test conversion job status transitions"""
    app = create_app()
    
    with app.app_context():
        # Initialize database
        db.create_all()
        
        # Create test PDF data (minimal valid PDF)
        test_pdf_data = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000079 00000 n \n0000000173 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n253\n%%EOF"
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        print(f"Testing conversion job status handling for job {job_id}")
        
        # Create job using JobOperationsController
        job = JobOperationsController.create_job_safely(
            job_id=job_id,
            task_type='convert',
            input_data={
                'target_format': 'txt',
                'options': {},
                'file_size': len(test_pdf_data),
                'original_filename': 'test.pdf'
            }
        )
        
        if not job:
            print("❌ FAILED: Could not create job")
            return False
            
        print(f"✅ Job created with status: {job.status}")
        
        # Test the conversion service process_conversion_job method
        try:
            service = ConversionService()
            result = service.process_conversion_job(
                job_id=job_id,
                file_data=test_pdf_data,
                target_format='txt',
                options={}
            )
            
            print(f"✅ Conversion completed: {result.get('success', False)}")
            
        except Exception as e:
            print(f"❌ Conversion failed: {str(e)}")
            return False
        
        # Check final job status
        updated_job = Job.query.filter_by(job_id=job_id).first()
        print(f"Final job status: {updated_job.status}")
        
        if updated_job.status == JobStatus.PROCESSING:
            print("❌ BUG: Job is still stuck in PROCESSING status!")
            return False
        elif updated_job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            print("✅ SUCCESS: Job properly transitioned from PROCESSING")
            return True
        else:
            print(f"❓ UNEXPECTED: Job has unexpected status {updated_job.status}")
            return False

if __name__ == '__main__':
    print("Testing conversion job status fix...")
    success = test_conversion_job_status()
    
    if success:
        print("\n🎉 CONVERSION JOB STATUS FIX VERIFIED!")
        print("The conversion service now properly manages job status transitions.")
    else:
        print("\n❌ CONVERSION JOB STATUS ISSUE PERSISTS")
        print("Further investigation needed.")
    
    sys.exit(0 if success else 1)