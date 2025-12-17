import logging
import json
import azure.functions as func
import os
from azure.storage.blob import BlobServiceClient, ContentSettings
import uuid
from datetime import datetime

# Configuration
STORAGE_CONNECTION_STRING = os.environ.get('AzureWebJobsStorage')
CONTAINER_NAME = 'images'

def get_blob_service_client():
    """Crée et retourne un client Blob Storage"""
    return BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Fonction principale qui route vers upload ou list-images selon le path
    """
    logging.info('HTTP trigger function processed a request.')
    
    # Récupérer le path de la route
    route = req.route_params.get('route')
    
    if route == 'upload':
        return upload_image(req)
    elif route == 'list-images':
        return list_images(req)
    else:
        return func.HttpResponse(
            json.dumps({'error': 'Route non trouvée'}),
            status_code=404,
            mimetype="application/json"
        )

def upload_image(req: func.HttpRequest) -> func.HttpResponse:
    """Upload d'une image"""
    logging.info('Upload function called')
    
    try:
        # Récupérer le fichier
        file_data = req.files.get('file')
        
        if not file_data:
            return func.HttpResponse(
                json.dumps({'error': 'Aucun fichier fourni'}),
                status_code=400,
                mimetype="application/json"
            )
        
        original_filename = file_data.filename
        file_content = file_data.stream.read()
        
        # Générer nom unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        file_extension = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{timestamp}_{unique_id}{file_extension}"
        
        # Content type
        content_type_mapping = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        content_type = content_type_mapping.get(file_extension, 'image/jpeg')
        
        # Upload
        blob_service_client = get_blob_service_client()
        blob_client = blob_service_client.get_blob_client(
            container=CONTAINER_NAME,
            blob=safe_filename
        )
        
        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type)
        )
        
        response_data = {
            'success': True,
            'message': 'Image téléversée avec succès',
            'filename': safe_filename,
            'url': blob_client.url
        }
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Erreur: {str(e)}")
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype="application/json"
        )

def list_images(req: func.HttpRequest) -> func.HttpResponse:
    """Liste des images"""
    logging.info('List images function called')
    
    try:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        if not container_client.exists():
            return func.HttpResponse(
                json.dumps({'images': [], 'count': 0}),
                status_code=200,
                mimetype="application/json"
            )
        
        blobs = container_client.list_blobs()
        images = []
        
        for blob in blobs:
            if blob.name.startswith('thumbnails/'):
                continue
            
            blob_client = blob_service_client.get_blob_client(
                container=CONTAINER_NAME,
                blob=blob.name
            )
            
            image_info = {
                'name': blob.name,
                'url': blob_client.url,
                'size': blob.size,
                'lastModified': blob.last_modified.isoformat() if blob.last_modified else None
            }
            images.append(image_info)
        
        images.sort(key=lambda x: x['lastModified'] if x['lastModified'] else '', reverse=True)
        
        return func.HttpResponse(
            json.dumps({'success': True, 'images': images, 'count': len(images)}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Erreur: {str(e)}")
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype="application/json"
        )
        
        
            
        
        
    
    
             
               
   



   
        
          
