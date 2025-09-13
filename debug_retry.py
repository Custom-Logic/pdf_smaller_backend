#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError
from src.utils.db_transaction import safe_db_operation, db_transaction
from src.models.job import Job, TaskType

def test_retry_mechanism():
    print("Testing retry mechanism...")
    
    # Create a mock that fails once, then succeeds
    mock_commit = MagicMock()
    mock_commit.side_effect = [
        OperationalError("Temporary error", None, None),
        None  # Success on second try
    ]
    
    def create_job_operation():
        print("Inside create_job_operation")
        with db_transaction("debug_test"):
            print("Inside db_transaction context")
            job = Job(
                job_id="debug-test",
                task_type=TaskType.COMPRESS.value
            )
            print(f"Created job: {job}")
            return job
    
    with patch('src.utils.db_transaction.db.session.commit', mock_commit):
        try:
            result = safe_db_operation(create_job_operation, "debug_test", max_retries=2)
            print(f"Result: {result}")
            print(f"Commit call count: {mock_commit.call_count}")
        except Exception as e:
            print(f"Exception: {e}")
            print(f"Exception type: {type(e)}")
            if hasattr(e, 'original_error'):
                print(f"Original error: {e.original_error}")
                print(f"Original error type: {type(e.original_error)}")
                if hasattr(e.original_error, 'original_error'):
                    print(f"Nested original error: {e.original_error.original_error}")
                    print(f"Nested original error type: {type(e.original_error.original_error)}")

if __name__ == "__main__":
    test_retry_mechanism()