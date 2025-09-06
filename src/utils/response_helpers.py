"""Helper functions for standardized API responses"""
from typing import Dict, Any, Optional, List, Union
from flask import jsonify

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

def error_response(message: str = "An error occurred", 
                  errors: Optional[Union[List[str], Dict[str, List[str]]]] = None, 
                  status_code: int = 400,
                  error_code: Optional[str] = None) -> tuple:
    """Create a standardized error response
    
    Args:
        message: The error message
        errors: Detailed error information (list of errors or field-specific errors)
        status_code: HTTP status code
        error_code: Optional error code for client-side error handling
        
    Returns:
        A tuple of (response, status_code)
    """
    response = {
        "status": "error",
        "message": message
    }
    
    if errors is not None:
        response["errors"] = errors
        
    if error_code is not None:
        response["error_code"] = error_code
        
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
        errors=errors,
        status_code=status_code,
        error_code="VALIDATION_ERROR"
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
    if resource_id:
        message = f"{resource_type} with ID {resource_id} not found"
        
    return error_response(
        message=message,
        status_code=404,
        error_code="NOT_FOUND"
    )

def server_error_response(message: str = "Internal server error") -> tuple:
    """Create a standardized server error response
    
    Args:
        message: The error message
        
    Returns:
        A tuple of (response, status_code)
    """
    return error_response(
        message=message,
        status_code=500,
        error_code="SERVER_ERROR"
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
        status_code=401,
        error_code="UNAUTHORIZED"
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
        status_code=403,
        error_code="FORBIDDEN"
    )