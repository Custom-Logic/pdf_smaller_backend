"""Helper functions for standardized API responses"""
from typing import Dict, Any, Optional, List, Union
from flask import jsonify, request
from datetime import datetime
import uuid

def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> tuple:
    """Create a standardized success response
    
    Args:
        data: The data to include in the response
        message: A success message
        status_code: HTTP status code
        
    Returns:
        A tuple of (response, status_code)
    """
    response = {
        "status": "success",
        "message": message
    }
    
    if data is not None:
        response["data"] = data
        
    return jsonify(response), status_code

def generate_request_id() -> str:
    """Generate a unique request ID for error tracking."""
    return str(uuid.uuid4())[:8]


def error_response(message: str = "An error occurred", 
                  error_code: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None,
                  errors: Optional[Union[List[str], Dict[str, List[str]]]] = None, 
                  status_code: int = 400,
                  request_id: Optional[str] = None) -> tuple:
    """Create a standardized error response with enhanced structure.
    
    Args:
        message: The error message
        error_code: Error code for client-side error handling
        details: Additional error details
        errors: Detailed error information (list of errors or field-specific errors)
        status_code: HTTP status code
        request_id: Optional request ID for tracking
        
    Returns:
        A tuple of (response, status_code)
    """
    response = {
        "success": False,
        "error": {
            "code": error_code or "GENERIC_ERROR",
            "message": message,
            "details": details or {}
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request_id or generate_request_id()
    }
    
    # Add validation errors if present
    if errors is not None:
        response["error"]["validation_errors"] = errors
        
    return jsonify(response), status_code

def validation_error_response(errors: Dict[str, List[str]], 
                            message: str = "Validation failed", 
                            status_code: int = 422) -> tuple:
    """Create a standardized validation error response
    
    Args:
        errors: Dictionary mapping field names to lists of error messages
        message: The overall error message
        status_code: HTTP status code (default: 422 Unprocessable Entity)
        
    Returns:
        A tuple of (response, status_code)
    """
    return error_response(
        message=message,
        error_code="VALIDATION_ERROR",
        errors=errors,
        status_code=status_code
    )

def not_found_response(resource_type: str, resource_id: Optional[str] = None) -> tuple:
    """Create a standardized not found response
    
    Args:
        resource_type: The type of resource that wasn't found (e.g., "User", "File")
        resource_id: Optional identifier of the resource
        
    Returns:
        A tuple of (response, status_code)
    """
    message = f"{resource_type} not found"
    details = {"resource_type": resource_type}
    
    if resource_id:
        message = f"{resource_type} with ID {resource_id} not found"
        details["resource_id"] = resource_id
        
    return error_response(
        message=message,
        error_code="NOT_FOUND",
        details=details,
        status_code=404
    )

def server_error_response(message: str = "Internal server error", 
                        details: Optional[Dict[str, Any]] = None) -> tuple:
    """Create a standardized server error response
    
    Args:
        message: The error message
        details: Additional error details
        
    Returns:
        A tuple of (response, status_code)
    """
    return error_response(
        message=message,
        error_code="SERVER_ERROR",
        details=details,
        status_code=500
    )

def unauthorized_response(message: str = "Unauthorized access") -> tuple:
    """Create a standardized unauthorized response
    
    Args:
        message: The error message
        
    Returns:
        A tuple of (response, status_code)
    """
    return error_response(
        message=message,
        error_code="UNAUTHORIZED",
        status_code=401
    )

def forbidden_response(message: str = "Access forbidden") -> tuple:
    """Create a standardized forbidden response
    
    Args:
        message: The error message
        
    Returns:
        A tuple of (response, status_code)
    """
    return error_response(
        message=message,
        error_code="FORBIDDEN",
        status_code=403
    )