import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """Configure application logging"""
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    log_file = os.environ.get('LOG_FILE', 'app.log')
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Set up rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1024 * 1024 * 10, backupCount=10
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(file_formatter)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
