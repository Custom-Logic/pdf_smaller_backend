#!/usr/bin/env python3
"""
Test script to verify the compression service bug fix.
This script tests that jobs are properly marked as COMPLETED or FAILED,
not left stuck in PROCESSING status.
"""

import sys
import os
import uuid
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models import Job, JobStatus
from src.models.base import db
from src.services.compression_service import CompressionService
from src.services.service_registry import ServiceRegistry
from src.jobs import JobOperations
from src.config.config import Config
from src.app import create_app

def test_compression_success():
    """Test that successful compression updates job status to COMPLETED"""
    print("\n=== Testing Successful Compression ===")
    
    # Create a test job
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        task_type='compress',
        status=JobStatus.PENDING,
        input_data={
            'compression_settings': {
                'compression_level': 'medium',
                'image_quality': 80
            },
            'file_size': 1000,
            'original_filename': 'test.pdf'
        }
    )
    
    db.session.add(job)
    db.session.commit()
    
    print(f"Created job {job_id} with status: {job.status}")
    
    # Create a simple PDF content for testing
    simple_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n174\n%%EOF"
    
    try:
        # Test the compression service
        compression_service = ServiceRegistry.get_compression_service()
        
        # This should either succeed or fail, but not leave job stuck
        result = compression_service.process_file_data(
            file_data=simple_pdf,
            settings={
                'compression_level': 'medium',
                'image_quality': 80
            },
            original_filename='test.pdf',
            job_id=job_id
        )
        
        print(f"Compression completed with result: {result.get('success', False)}")
        
    except Exception as e:
        print(f"Compression failed with error: {str(e)}")
    
    # Check final job status
    updated_job = JobOperations.get_job(job_id)
    print(f"Final job status: {updated_job.status}")
    
    if updated_job.status == JobStatus.PROCESSING:
        print("❌ BUG: Job is still stuck in PROCESSING status!")
        return False
    elif updated_job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        print(f"✅ SUCCESS: Job properly transitioned to {updated_job.status}")
        return True
    else:
        print(f"❓ UNEXPECTED: Job has unexpected status {updated_job.status}")
        return False

def test_compression_failure():
    """Test that failed compression updates job status to FAILED"""
    print("\n=== Testing Failed Compression ===")
    
    # Create a test job
    job_id = str(uuid.uuid4())
    job = Job(
        job_id=job_id,
        task_type='compress',
        status=JobStatus.PENDING,
        input_data={
            'compression_settings': {
                'compression_level': 'medium',
                'image_quality': 80
            },
            'file_size': 1000,
            'original_filename': 'invalid.pdf'
        }
    )
    
    db.session.add(job)
    db.session.commit()
    
    print(f"Created job {job_id} with status: {job.status}")
    
    # Use invalid PDF data to trigger failure
    invalid_pdf = b"This is not a valid PDF file"
    
    try:
        # Test the compression service with invalid data
        compression_service = ServiceRegistry.get_compression_service()
        
        result = compression_service.process_file_data(
            file_data=invalid_pdf,
            settings={
                'compression_level': 'medium',
                'image_quality': 80
            },
            original_filename='invalid.pdf',
            job_id=job_id
        )
        
        print(f"Unexpected success: {result}")
        
    except Exception as e:
        print(f"Expected failure occurred: {str(e)}")
    
    # Check final job status
    updated_job = JobOperations.get_job(job_id)
    print(f"Final job status: {updated_job.status}")
    
    if updated_job.status == JobStatus.PROCESSING:
        print("❌ BUG: Job is still stuck in PROCESSING status!")
        return False
    elif updated_job.status == JobStatus.FAILED:
        print("✅ SUCCESS: Job properly marked as FAILED")
        return True
    else:
        print(f"❓ UNEXPECTED: Job has unexpected status {updated_job.status}")
        return False

def main():
    """Run the compression fix tests"""
    print("Starting Compression Service Bug Fix Tests")
    print("===========================================")
    
    # Initialize the Flask app context
    app = create_app()
    
    with app.app_context():
        # Test both success and failure scenarios
        success_test = test_compression_success()
        failure_test = test_compression_failure()
        
        print("\n=== Test Results ===")
        print(f"Success scenario: {'✅ PASS' if success_test else '❌ FAIL'}")
        print(f"Failure scenario: {'✅ PASS' if failure_test else '❌ FAIL'}")
        
        if success_test and failure_test:
            print("\n🎉 All tests passed! The bug fix is working correctly.")
            return 0
        else:
            print("\n💥 Some tests failed. The bug may still exist.")
            return 1

if __name__ == '__main__':
    sys.exit(main())