import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from datetime import datetime
db = SQLAlchemy()


def generate_uuid():
    """Generate a UUID string"""
    return str(uuid.uuid4())


class BaseModel(db.Model):
    """Base model with common fields"""
    __abstract__ = True

    job_id = db.Column(db.String(255), primary_key=True, default=generate_uuid)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        # Ensure job_id is set during object creation
        if 'job_id' not in kwargs:
            kwargs['job_id'] = generate_uuid()
        super().__init__(**kwargs)


# Additional safety with event listener
@event.listens_for(BaseModel, 'before_insert')
def ensure_job_id_before_insert(mapper, connection, target):
    """Double-check that job_id is set before inserting"""
    if not target.job_id:
        target.job_id = generate_uuid()
