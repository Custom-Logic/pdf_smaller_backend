#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.db_transaction import db_transaction
from src.models.job import Job, TaskType
from src.main.main import create_app
from src.database.init_db import db

app = create_app()

with app.app_context():
    print("Testing context manager directly...")
    
    try:
        with db_transaction("test_direct", auto_commit=True, raise_on_error=True, max_retries=0) as session:
            print("Inside context manager")
            job = Job(
                job_id="direct-test",
                task_type=TaskType.COMPRESS.value
            )
            session.add(job)
            print(f"Created job: {job}")
            result = job
        
        print(f"Context manager completed successfully. Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()