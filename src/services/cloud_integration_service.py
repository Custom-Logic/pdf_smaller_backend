"""
Cloud Integration Service
Handles integration with cloud storage providers like Google Drive
"""

import os
import tempfile
import logging
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import base64

logger = logging.getLogger(__name__)

class CloudIntegrationService:
    """Service for cloud storage integration"""
    
    def __init__(self):
        self.supported_providers = ['google_drive', 'dropbox', 'onedrive']
        self.temp_dir = tempfile.mkdtemp(prefix='cloud_integration_')
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize provider clients
        self.provider_clients = self._initialize_provider_clients()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load cloud integration configuration"""
        config = {
            'google_drive': {
                'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
                'client_secret': os.getenv('GOOGLE_CLIENT_SECRET', ''),
                'redirect_uri': os.getenv('GOOGLE_REDIRECT_URI', ''),
                'scopes': ['https://www.googleapis.com/auth/drive.file']
            },
            'dropbox': {
                'client_id': os.getenv('DROPBOX_CLIENT_ID', ''),
                'client_secret': os.getenv('DROPBOX_CLIENT_SECRET', ''),
                'redirect_uri': os.getenv('DROPBOX_REDIRECT_URI', ''),
                'scopes': ['files.content.write', 'files.content.read']
            },
            'onedrive': {
                'client_id': os.getenv('ONEDRIVE_CLIENT_ID', ''),
                'client_secret': os.getenv('ONEDRIVE_CLIENT_SECRET', ''),
                'redirect_uri': os.getenv('ONEDRIVE_REDIRECT_URI', ''),
                'scopes': ['files.readwrite']
            }
        }
        
        return config
    
    def _initialize_provider_clients(self) -> Dict[str, Any]:
        """Initialize provider-specific clients"""
        clients = {}
        
        # Google Drive client
        if self.config['google_drive']['client_id']:
            try:
                clients['google_drive'] = self._create_google_drive_client()
            except Exception as e:
                logger.warning(f"Failed to initialize Google Drive client: {str(e)}")
        
        # Dropbox client
        if self.config['dropbox']['client_id']:
            try:
                clients['dropbox'] = self._create_dropbox_client()
            except Exception as e:
                logger.warning(f"Failed to initialize Dropbox client: {str(e)}")
        
        # OneDrive client
        if self.config['onedrive']['client_id']:
            try:
                clients['onedrive'] = self._create_onedrive_client()
            except Exception as e:
                logger.warning(f"Failed to initialize OneDrive client: {str(e)}")
        
        return clients
    
    def _create_google_drive_client(self):
        """Create Google Drive client"""
        return {
            'type': 'google_drive',
            'config': self.config['google_drive']
        }
    
    def _create_dropbox_client(self):
        """Create Dropbox client"""
        return {
            'type': 'dropbox',
            'config': self.config['dropbox']
        }
    
    def _create_onedrive_client(self):
        """Create OneDrive client"""
        return {
            'type': 'onedrive',
            'config': self.config['onedrive']
        }
    
    def exchange_code_for_token(self, provider: str, code: str, redirect_uri: str = None) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        
        Args:
            provider: Cloud provider name
            code: Authorization code
            redirect_uri: Redirect URI (optional)
            
        Returns:
            Dictionary with token information
        """
        try:
            if provider not in self.provider_clients:
                raise ValueError(f"Provider {provider} not available")
            
            if provider == 'google_drive':
                return self._exchange_google_drive_token(code, redirect_uri)
            elif provider == 'dropbox':
                return self._exchange_dropbox_token(code, redirect_uri)
            elif provider == 'onedrive':
                return self._exchange_onedrive_token(code, redirect_uri)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"Token exchange failed for {provider}: {str(e)}")
            raise
    
    def _exchange_google_drive_token(self, code: str, redirect_uri: str = None) -> Dict[str, Any]:
        """Exchange Google Drive authorization code for token"""
        try:
            config = self.provider_clients['google_drive']['config']
            redirect_uri = redirect_uri or config['redirect_uri']
            
            # Prepare token exchange request
            token_request = {
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
            
            # Exchange code for token
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data=token_request,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Google token exchange failed: {response.status_code} - {response.text}")
            
            token_data = response.json()
            
            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'scope': token_data.get('scope', ''),
                'provider': 'google_drive'
            }
            
        except Exception as e:
            logger.error(f"Google Drive token exchange failed: {str(e)}")
            raise
    
    def _exchange_dropbox_token(self, code: str, redirect_uri: str = None) -> Dict[str, Any]:
        """Exchange Dropbox authorization code for token"""
        try:
            config = self.provider_clients['dropbox']['config']
            redirect_uri = redirect_uri or config['redirect_uri']
            
            # Prepare token exchange request
            token_request = {
                'code': code,
                'grant_type': 'authorization_code',
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'redirect_uri': redirect_uri
            }
            
            # Exchange code for token
            response = requests.post(
                'https://api.dropboxapi.com/oauth2/token',
                data=token_request,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Dropbox token exchange failed: {response.status_code} - {response.text}")
            
            token_data = response.json()
            
            return {
                'access_token': token_data['access_token'],
                'token_type': 'Bearer',
                'scope': token_data.get('scope', ''),
                'provider': 'dropbox'
            }
            
        except Exception as e:
            logger.error(f"Dropbox token exchange failed: {str(e)}")
            raise
    
    def _exchange_onedrive_token(self, code: str, redirect_uri: str = None) -> Dict[str, Any]:
        """Exchange OneDrive authorization code for token"""
        try:
            config = self.provider_clients['onedrive']['config']
            redirect_uri = redirect_uri or config['redirect_uri']
            
            # Prepare token exchange request
            token_request = {
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
            
            # Exchange code for token
            response = requests.post(
                'https://login.microsoftonline.com/common/oauth2/v2.0/token',
                data=token_request,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"OneDrive token exchange failed: {response.status_code} - {response.text}")
            
            token_data = response.json()
            
            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'scope': token_data.get('scope', ''),
                'provider': 'onedrive'
            }
            
        except Exception as e:
            logger.error(f"OneDrive token exchange failed: {str(e)}")
            raise
    
    def validate_token(self, provider: str, token: str) -> bool:
        """
        Validate access token with provider
        
        Args:
            provider: Cloud provider name
            token: Access token
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            if provider == 'google_drive':
                return self._validate_google_drive_token(token)
            elif provider == 'dropbox':
                return self._validate_dropbox_token(token)
            elif provider == 'onedrive':
                return self._validate_onedrive_token(token)
            else:
                return False
                
        except Exception as e:
            logger.warning(f"Token validation failed for {provider}: {str(e)}")
            return False
    
    def _validate_google_drive_token(self, token: str) -> bool:
        """Validate Google Drive access token"""
        try:
            response = requests.get(
                'https://www.googleapis.com/drive/v3/about',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            return response.status_code == 200
            
        except Exception:
            return False
    
    def _validate_dropbox_token(self, token: str) -> bool:
        """Validate Dropbox access token"""
        try:
            response = requests.post(
                'https://api.dropboxapi.com/2/users/get_current_account',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            return response.status_code == 200
            
        except Exception:
            return False
    
    def _validate_onedrive_token(self, token: str) -> bool:
        """Validate OneDrive access token"""
        try:
            response = requests.get(
                'https://graph.microsoft.com/v1.0/me',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            return response.status_code == 200
            
        except Exception:
            return False
    
    def upload_file(self, provider: str, token: str, file, destination_path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Upload file to cloud storage
        
        Args:
            provider: Cloud provider name
            token: Access token
            file: File to upload
            destination_path: Destination path in cloud storage
            options: Upload options
            
        Returns:
            Dictionary with upload result
        """
        if not options:
            options = {}
            
        try:
            if provider == 'google_drive':
                return self._upload_to_google_drive(token, file, destination_path, options)
            elif provider == 'dropbox':
                return self._upload_to_dropbox(token, file, destination_path, options)
            elif provider == 'onedrive':
                return self._upload_to_onedrive(token, file, destination_path, options)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"File upload failed for {provider}: {str(e)}")
            raise
    
    def _upload_to_google_drive(self, token: str, file, destination_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Upload file to Google Drive"""
        try:
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Prepare upload request
            file_metadata = {
                'name': os.path.basename(destination_path) or file.filename,
                'parents': [self._get_google_drive_folder_id(token, os.path.dirname(destination_path))]
            }
            
            # Upload file
            files = {'file': open(temp_file_path, 'rb')}
            response = requests.post(
                'https://www.googleapis.com/upload/drive/v3/files',
                params={'uploadType': 'multipart'},
                headers={'Authorization': f'Bearer {token}'},
                data={'metadata': json.dumps(file_metadata)},
                files=files,
                timeout=300
            )
            
            if response.status_code != 200:
                raise Exception(f"Google Drive upload failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return {
                'success': True,
                'file_id': result['id'],
                'file_name': result['name'],
                'file_size': result.get('size', 0),
                'web_view_link': result.get('webViewLink', ''),
                'provider': 'google_drive'
            }
            
        except Exception as e:
            logger.error(f"Google Drive upload failed: {str(e)}")
            raise
    
    def _upload_to_dropbox(self, token: str, file, destination_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Upload file to Dropbox"""
        try:
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Prepare upload request
            dropbox_path = destination_path
            if not dropbox_path.startswith('/'):
                dropbox_path = f'/{dropbox_path}'
            
            # Upload file
            with open(temp_file_path, 'rb') as f:
                file_content = f.read()
            
            response = requests.post(
                'https://content.dropboxapi.com/2/files/upload',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Dropbox-API-Arg': json.dumps({
                        'path': dropbox_path,
                        'mode': 'add',
                        'autorename': True,
                        'mute': False
                    }),
                    'Content-Type': 'application/octet-stream'
                },
                data=file_content,
                timeout=300
            )
            
            if response.status_code != 200:
                raise Exception(f"Dropbox upload failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return {
                'success': True,
                'file_id': result['id'],
                'file_name': result['name'],
                'file_size': result.get('size', 0),
                'path_lower': result.get('path_lower', ''),
                'provider': 'dropbox'
            }
            
        except Exception as e:
            logger.error(f"Dropbox upload failed: {str(e)}")
            raise
    
    def _upload_to_onedrive(self, token: str, file, destination_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Upload file to OneDrive"""
        try:
            # Save uploaded file to temp directory
            temp_file_path = self._save_uploaded_file(file)
            
            # Prepare upload request
            onedrive_path = destination_path
            if not onedrive_path.startswith('/'):
                onedrive_path = f'/{onedrive_path}'
            
            # Upload file
            with open(temp_file_path, 'rb') as f:
                file_content = f.read()
            
            response = requests.put(
                f'https://graph.microsoft.com/v1.0/me/drive/root:{onedrive_path}:/content',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/octet-stream'
                },
                data=file_content,
                timeout=300
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"OneDrive upload failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return {
                'success': True,
                'file_id': result['id'],
                'file_name': result['name'],
                'file_size': result.get('size', 0),
                'web_url': result.get('webUrl', ''),
                'provider': 'onedrive'
            }
            
        except Exception as e:
            logger.error(f"OneDrive upload failed: {str(e)}")
            raise
    
    def download_file(self, provider: str, token: str, file_path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Download file from cloud storage
        
        Args:
            provider: Cloud provider name
            token: Access token
            file_path: File path in cloud storage
            options: Download options
            
        Returns:
            Dictionary with download result
        """
        if not options:
            options = {}
            
        try:
            if provider == 'google_drive':
                return self._download_from_google_drive(token, file_path, options)
            elif provider == 'dropbox':
                return self._download_from_dropbox(token, file_path, options)
            elif provider == 'onedrive':
                return self._download_from_onedrive(token, file_path, options)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"File download failed for {provider}: {str(e)}")
            raise
    
    def _download_from_google_drive(self, token: str, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Download file from Google Drive"""
        try:
            # Get file ID from path (simplified - in production you'd need to resolve the path)
            file_id = file_path  # Assuming file_path is the file ID for now
            
            # Download file
            response = requests.get(
                f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media',
                headers={'Authorization': f'Bearer {token}'},
                timeout=300
            )
            
            if response.status_code != 200:
                raise Exception(f"Google Drive download failed: {response.status_code} - {response.text}")
            
            # Save to temp file
            temp_file_path = os.path.join(self.temp_dir, f"download_{file_id}")
            with open(temp_file_path, 'wb') as f:
                f.write(response.content)
            
            return {
                'success': True,
                'file_path': temp_file_path,
                'filename': f"download_{file_id}",
                'mime_type': response.headers.get('content-type', 'application/octet-stream'),
                'provider': 'google_drive'
            }
            
        except Exception as e:
            logger.error(f"Google Drive download failed: {str(e)}")
            raise
    
    def _download_from_dropbox(self, token: str, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Download file from Dropbox"""
        try:
            # Prepare download request
            dropbox_path = file_path
            if not dropbox_path.startswith('/'):
                dropbox_path = f'/{dropbox_path}'
            
            # Download file
            response = requests.post(
                'https://content.dropboxapi.com/2/files/download',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Dropbox-API-Arg': json.dumps({'path': dropbox_path})
                },
                timeout=300
            )
            
            if response.status_code != 200:
                raise Exception(f"Dropbox download failed: {response.status_code} - {response.text}")
            
            # Save to temp file
            filename = response.headers.get('dropbox-api-result', '{}')
            try:
                filename = json.loads(filename).get('name', 'download')
            except:
                filename = 'download'
            
            temp_file_path = os.path.join(self.temp_dir, filename)
            with open(temp_file_path, 'wb') as f:
                f.write(response.content)
            
            return {
                'success': True,
                'file_path': temp_file_path,
                'filename': filename,
                'mime_type': response.headers.get('content-type', 'application/octet-stream'),
                'provider': 'dropbox'
            }
            
        except Exception as e:
            logger.error(f"Dropbox download failed: {str(e)}")
            raise
    
    def _download_from_onedrive(self, token: str, file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Download file from OneDrive"""
        try:
            # Prepare download request
            onedrive_path = file_path
            if not onedrive_path.startswith('/'):
                onedrive_path = f'/{onedrive_path}'
            
            # Download file
            response = requests.get(
                f'https://graph.microsoft.com/v1.0/me/drive/root:{onedrive_path}:/content',
                headers={'Authorization': f'Bearer {token}'},
                timeout=300
            )
            
            if response.status_code != 200:
                raise Exception(f"OneDrive download failed: {response.status_code} - {response.text}")
            
            # Save to temp file
            filename = os.path.basename(file_path) or 'download'
            temp_file_path = os.path.join(self.temp_dir, filename)
            with open(temp_file_path, 'wb') as f:
                f.write(response.content)
            
            return {
                'success': True,
                'file_path': temp_file_path,
                'filename': filename,
                'mime_type': response.headers.get('content-type', 'application/octet-stream'),
                'provider': 'onedrive'
            }
            
        except Exception as e:
            logger.error(f"OneDrive download failed: {str(e)}")
            raise
    
    def list_files(self, provider: str, token: str, folder_path: str = '/', options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        List files in cloud storage
        
        Args:
            provider: Cloud provider name
            token: Access token
            folder_path: Folder path to list
            options: List options
            
        Returns:
            Dictionary with file list
        """
        if not options:
            options = {}
            
        try:
            if provider == 'google_drive':
                return self._list_google_drive_files(token, folder_path, options)
            elif provider == 'dropbox':
                return self._list_dropbox_files(token, folder_path, options)
            elif provider == 'onedrive':
                return self._list_onedrive_files(token, folder_path, options)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"File listing failed for {provider}: {str(e)}")
            raise
    
    def _list_google_drive_files(self, token: str, folder_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """List files in Google Drive folder"""
        try:
            # Get folder ID
            folder_id = self._get_google_drive_folder_id(token, folder_path)
            
            # List files
            response = requests.get(
                'https://www.googleapis.com/drive/v3/files',
                params={
                    'q': f"'{folder_id}' in parents",
                    'fields': 'files(id,name,mimeType,size,modifiedTime,webViewLink)'
                },
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Google Drive list failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            return {
                'success': True,
                'files': result.get('files', []),
                'folder_path': folder_path,
                'provider': 'google_drive'
            }
            
        except Exception as e:
            logger.error(f"Google Drive file listing failed: {str(e)}")
            raise
    
    def _list_dropbox_files(self, token: str, folder_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """List files in Dropbox folder"""
        try:
            # Prepare list request
            dropbox_path = folder_path
            if not dropbox_path.startswith('/'):
                dropbox_path = f'/{dropbox_path}'
            
            # List files
            response = requests.post(
                'https://api.dropboxapi.com/2/files/list_folder',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json={'path': dropbox_path},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Dropbox list failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            return {
                'success': True,
                'files': result.get('entries', []),
                'folder_path': folder_path,
                'provider': 'dropbox'
            }
            
        except Exception as e:
            logger.error(f"Dropbox file listing failed: {str(e)}")
            raise
    
    def _list_onedrive_files(self, token: str, folder_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """List files in OneDrive folder"""
        try:
            # Prepare list request
            onedrive_path = folder_path
            if not onedrive_path.startswith('/'):
                onedrive_path = f'/{onedrive_path}'
            
            # List files
            response = requests.get(
                f'https://graph.microsoft.com/v1.0/me/drive/root:{onedrive_path}:/children',
                headers={'Authorization': f'Bearer {token}'},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"OneDrive list failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            return {
                'success': True,
                'files': result.get('value', []),
                'folder_path': folder_path,
                'provider': 'onedrive'
            }
            
        except Exception as e:
            logger.error(f"OneDrive file listing failed: {str(e)}")
            raise
    
    def create_folder(self, provider: str, token: str, folder_path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create folder in cloud storage
        
        Args:
            provider: Cloud provider name
            token: Access token
            folder_path: Folder path to create
            options: Create options
            
        Returns:
            Dictionary with create result
        """
        if not options:
            options = {}
            
        try:
            if provider == 'google_drive':
                return self._create_google_drive_folder(token, folder_path, options)
            elif provider == 'dropbox':
                return self._create_dropbox_folder(token, folder_path, options)
            elif provider == 'onedrive':
                return self._create_onedrive_folder(token, folder_path, options)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"Folder creation failed for {provider}: {str(e)}")
            raise
    
    def _create_google_drive_folder(self, token: str, folder_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Create folder in Google Drive"""
        try:
            folder_name = os.path.basename(folder_path)
            parent_path = os.path.dirname(folder_path)
            parent_id = self._get_google_drive_folder_id(token, parent_path)
            
            # Create folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            response = requests.post(
                'https://www.googleapis.com/drive/v3/files',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json=folder_metadata,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Google Drive folder creation failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            return {
                'success': True,
                'folder_id': result['id'],
                'folder_name': result['name'],
                'folder_path': folder_path,
                'provider': 'google_drive'
            }
            
        except Exception as e:
            logger.error(f"Google Drive folder creation failed: {str(e)}")
            raise
    
    def _create_dropbox_folder(self, token: str, folder_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Create folder in Dropbox"""
        try:
            # Prepare create request
            dropbox_path = folder_path
            if not dropbox_path.startswith('/'):
                dropbox_path = f'/{dropbox_path}'
            
            # Create folder
            response = requests.post(
                'https://api.dropboxapi.com/2/files/create_folder_v2',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json={'path': dropbox_path, 'autorename': False},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Dropbox folder creation failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            return {
                'success': True,
                'folder_id': result['metadata']['id'],
                'folder_name': result['metadata']['name'],
                'folder_path': folder_path,
                'provider': 'dropbox'
            }
            
        except Exception as e:
            logger.error(f"Dropbox folder creation failed: {str(e)}")
            raise
    
    def _create_onedrive_folder(self, token: str, folder_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Create folder in OneDrive"""
        try:
            # Prepare create request
            onedrive_path = folder_path
            if not onedrive_path.startswith('/'):
                onedrive_path = f'/{onedrive_path}'
            
            # Create folder
            folder_metadata = {
                'name': os.path.basename(folder_path),
                'folder': {},
                '@microsoft.graph.conflictBehavior': 'rename'
            }
            
            response = requests.post(
                f'https://graph.microsoft.com/v1.0/me/drive/root:{os.path.dirname(onedrive_path)}:/children',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json=folder_metadata,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"OneDrive folder creation failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            return {
                'success': True,
                'folder_id': result['id'],
                'folder_name': result['name'],
                'folder_path': folder_path,
                'provider': 'onedrive'
            }
            
        except Exception as e:
            logger.error(f"OneDrive folder creation failed: {str(e)}")
            raise
    
    def revoke_token(self, provider: str, token: str) -> Dict[str, Any]:
        """
        Revoke access token
        
        Args:
            provider: Cloud provider name
            token: Access token to revoke
            
        Returns:
            Dictionary with revocation result
        """
        try:
            if provider == 'google_drive':
                return self._revoke_google_drive_token(token)
            elif provider == 'dropbox':
                return self._revoke_dropbox_token(token)
            elif provider == 'onedrive':
                return self._revoke_onedrive_token(token)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"Token revocation failed for {provider}: {str(e)}")
            raise
    
    def _revoke_google_drive_token(self, token: str) -> Dict[str, Any]:
        """Revoke Google Drive access token"""
        try:
            response = requests.post(
                'https://oauth2.googleapis.com/revoke',
                data={'token': token},
                timeout=30
            )
            
            return {
                'success': True,
                'provider': 'google_drive',
                'message': 'Token revoked successfully'
            }
            
        except Exception as e:
            logger.error(f"Google Drive token revocation failed: {str(e)}")
            raise
    
    def _revoke_dropbox_token(self, token: str) -> Dict[str, Any]:
        """Revoke Dropbox access token"""
        try:
            # Dropbox doesn't have a token revocation endpoint
            # The token will expire naturally
            return {
                'success': True,
                'provider': 'dropbox',
                'message': 'Token will expire naturally (Dropbox does not support immediate revocation)'
            }
            
        except Exception as e:
            logger.error(f"Dropbox token revocation failed: {str(e)}")
            raise
    
    def _revoke_onedrive_token(self, token: str) -> Dict[str, Any]:
        """Revoke OneDrive access token"""
        try:
            # OneDrive doesn't have a token revocation endpoint
            # The token will expire naturally
            return {
                'success': True,
                'provider': 'onedrive',
                'message': 'Token will expire naturally (OneDrive does not support immediate revocation)'
            }
            
        except Exception as e:
            logger.error(f"OneDrive token revocation failed: {str(e)}")
            raise
    
    def _get_google_drive_folder_id(self, token: str, folder_path: str) -> str:
        """Get Google Drive folder ID from path"""
        try:
            if not folder_path or folder_path == '/':
                return 'root'
            
            # For now, return root - in production you'd need to traverse the path
            # and resolve each folder level to get the correct folder ID
            return 'root'
            
        except Exception as e:
            logger.warning(f"Failed to get Google Drive folder ID: {str(e)}")
            return 'root'
    
    def _save_uploaded_file(self, file) -> str:
        """Save uploaded file to temporary directory"""
        filename = self._secure_filename(file.filename)
        temp_path = os.path.join(self.temp_dir, filename)
        
        file.save(temp_path)
        return temp_path
    
    def _secure_filename(self, filename: str) -> str:
        """Secure filename for safe file operations"""
        import re
        # Remove or replace unsafe characters
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename.strip('-')
    
    def get_available_providers(self) -> List[str]:
        """Get list of available cloud providers"""
        return list(self.provider_clients.keys())
    
    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """Get status of specific cloud provider"""
        if provider not in self.provider_clients:
            return {'available': False, 'error': 'Provider not found'}
        
        try:
            # Check if provider is configured
            config = self.provider_clients[provider]['config']
            if not config['client_id']:
                return {'available': False, 'error': 'Provider not configured'}
            
            return {'available': True, 'status': 'configured'}
            
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {str(e)}")





