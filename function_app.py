import logging
import azure.functions as func
import os
from azure.storage.blob import BlobServiceClient, ContentSettings
import uuid
from datetime import datetime

app = func.FunctionApp()

# Configuration - Utiliser les variables d'environnement
STORAGE_CONNECTION_STRING = os.environ.get('AzureWebJobsStorage')
CONTAINER_NAME = 'images'

def get_blob_service_client():
    """Crée et retourne un client Blob Storage"""
    return BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

def ensure_container_exists(blob_service_client):
    """Assure que le conteneur existe"""
    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        if not container_client.exists():
            container_client.create_container(public_access='blob')
            logging.info(f"Conteneur '{CONTAINER_NAME}' créé avec succès")
    except Exception as e:
        logging.error(f"Erreur lors de la création du conteneur: {str(e)}")

@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upload_image(req: func.HttpRequest) -> func.HttpResponse:
    """
    Fonction Azure #1: Téléverse une image vers Azure Blob Storage
    
    Cette fonction:
    1. Reçoit un fichier image via HTTP POST
    2. Génère un nom unique pour l'image
    3. Téléverse l'image dans le conteneur 'images'
    4. Retourne les informations du fichier téléversé
    """
    logging.info('Fonction upload_image appelée')
    
    try:
        # Récupérer le fichier depuis la requête
        file_data = req.files.get('file')
        
        if not file_data:
            return func.HttpResponse(
                '{"error": "Aucun fichier fourni"}',
                status_code=400,
                mimetype="application/json"
            )
        
        # Obtenir le nom et le contenu du fichier
        original_filename = file_data.filename
        file_content = file_data.stream.read()
        
        # Vérifier que c'est une image
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        file_extension = os.path.splitext(original_filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            return func.HttpResponse(
                '{"error": "Type de fichier non autorisé. Formats acceptés: JPG, PNG, GIF, WEBP, BMP"}',
                status_code=400,
                mimetype="application/json"
            )
        
        # Vérifier la taille du fichier (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            return func.HttpResponse(
                '{"error": "Fichier trop volumineux. Taille maximale: 10MB"}',
                status_code=400,
                mimetype="application/json"
            )
        
        # Générer un nom unique pour le fichier
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{unique_id}{file_extension}"
        
        # Déterminer le content type
        content_type_mapping = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        content_type = content_type_mapping.get(file_extension, 'application/octet-stream')
        
        # Créer le client Blob Storage
        blob_service_client = get_blob_service_client()
        ensure_container_exists(blob_service_client)
        
        # Obtenir le client blob pour le fichier
        blob_client = blob_service_client.get_blob_client(
            container=CONTAINER_NAME,
            blob=safe_filename
        )
        
        # Téléverser le fichier
        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type)
        )
        
        # Obtenir l'URL du blob
        blob_url = blob_client.url
        
        logging.info(f"Fichier téléversé avec succès: {safe_filename}")
        
        # Retourner la réponse
        response_data = {
            "success": True,
            "message": "Fichier téléversé avec succès",
            "filename": safe_filename,
            "original_filename": original_filename,
            "url": blob_url,
            "size": len(file_content),
            "timestamp": timestamp
        }
        
        return func.HttpResponse(
            func.HttpResponse.mimetype="application/json",
            body=str(response_data).replace("'", '"'),
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Erreur lors du téléversement: {str(e)}")
        return func.HttpResponse(
            f'{{"error": "Erreur lors du téléversement: {str(e)}"}}',
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="list-images", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_images(req: func.HttpRequest) -> func.HttpResponse:
    """
    Fonction Azure #2: Liste toutes les images et génère les URLs des miniatures
    
    Cette fonction:
    1. Récupère la liste de tous les blobs dans le conteneur
    2. Sépare les images originales des miniatures
    3. Génère les URLs pour affichage
    4. Retourne un JSON avec la liste complète
    """
    logging.info('Fonction list_images appelée')
    
    try:
        # Créer le client Blob Storage
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # Vérifier si le conteneur existe
        if not container_client.exists():
            return func.HttpResponse(
                '{"images": [], "count": 0}',
                status_code=200,
                mimetype="application/json"
            )
        
        # Lister tous les blobs
        blobs = container_client.list_blobs()
        
        images = []
        
        for blob in blobs:
            blob_name = blob.name
            
            # Ignorer les miniatures (on les associera aux originaux)
            if blob_name.startswith('thumbnails/'):
                continue
            
            # Générer les URLs
            blob_client = blob_service_client.get_blob_client(
                container=CONTAINER_NAME,
                blob=blob_name
            )
            original_url = blob_client.url
            
            # Chercher la miniature correspondante
            thumbnail_name = f"thumbnails/{blob_name}"
            thumbnail_blob_client = blob_service_client.get_blob_client(
                container=CONTAINER_NAME,
                blob=thumbnail_name
            )
            
            # Vérifier si la miniature existe
            try:
                thumbnail_blob_client.get_blob_properties()
                thumbnail_url = thumbnail_blob_client.url
            except:
                # Si la miniature n'existe pas encore, utiliser l'original
                thumbnail_url = original_url
            
            image_info = {
                "name": blob_name,
                "originalUrl": original_url,
                "thumbnailUrl": thumbnail_url,
                "size": blob.size,
                "lastModified": blob.last_modified.isoformat() if blob.last_modified else None
            }
            
            images.append(image_info)
        
        # Trier par date de modification (plus récent en premier)
        images.sort(key=lambda x: x['lastModified'] if x['lastModified'] else '', reverse=True)
        
        response_data = {
            "success": True,
            "images": images,
            "count": len(images)
        }
        
        logging.info(f"{len(images)} images trouvées")
        
        return func.HttpResponse(
            func.HttpResponse.mimetype="application/json",
            body=str(response_data).replace("'", '"').replace('None', 'null'),
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des images: {str(e)}")
        return func.HttpResponse(
            f'{{"error": "Erreur lors de la récupération des images: {str(e)}"}}',
            status_code=500,
            mimetype="application/json"
        )


@app.blob_trigger(arg_name="myblob", path="images/{name}",
                  connection="AzureWebJobsStorage")
def resize_image(myblob: func.InputStream):
    """
    Fonction Azure #3: Redimensionne automatiquement les images téléversées
    
    Cette fonction est déclenchée automatiquement lorsqu'une nouvelle image
    est ajoutée au conteneur 'images'. Elle:
    1. Télécharge l'image originale
    2. La redimensionne en 256x256 px
    3. Stocke la miniature dans un sous-dossier 'thumbnails/'
    
    Utilise PIL (Pillow) pour le redimensionnement
    """
    logging.info(f'Fonction resize_image déclenchée pour: {myblob.name}')
    
    try:
        from PIL import Image
        from io import BytesIO
        
        # Ignorer les fichiers qui sont déjà des miniatures
        if myblob.name.startswith('thumbnails/'):
            logging.info('Fichier ignoré: déjà une miniature')
            return
        
        # Lire l'image
        image_data = myblob.read()
        
        # Ouvrir l'image avec PIL
        img = Image.open(BytesIO(image_data))
        
        # Conserver le mode de couleur original ou convertir en RGB si nécessaire
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        # Redimensionner l'image (256x256 avec maintien du ratio)
        thumbnail_size = (256, 256)
        img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        
        # Créer une nouvelle image 256x256 avec fond blanc
        new_img = Image.new('RGB', thumbnail_size, (255, 255, 255))
        
        # Calculer la position pour centrer l'image redimensionnée
        x = (thumbnail_size[0] - img.size[0]) // 2
        y = (thumbnail_size[1] - img.size[1]) // 2
        
        # Coller l'image redimensionnée
        if img.mode == 'RGBA':
            new_img.paste(img, (x, y), img)
        else:
            new_img.paste(img, (x, y))
        
        # Sauvegarder la miniature en mémoire
        output = BytesIO()
        new_img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        # Créer le client Blob Storage
        blob_service_client = get_blob_service_client()
        
        # Nom de la miniature (dans un sous-dossier)
        thumbnail_name = f"thumbnails/{myblob.name}"
        
        # Téléverser la miniature
        thumbnail_blob_client = blob_service_client.get_blob_client(
            container=CONTAINER_NAME,
            blob=thumbnail_name
        )
        
        thumbnail_blob_client.upload_blob(
            output.getvalue(),
            overwrite=True,
            content_settings=ContentSettings(content_type='image/jpeg')
        )
        
        logging.info(f'Miniature créée avec succès: {thumbnail_name}')
        
    except ImportError:
        logging.error('Pillow (PIL) n\'est pas installé. Ajoutez "Pillow" à requirements.txt')
    except Exception as e:
        logging.error(f'Erreur lors du redimensionnement: {str(e)}')
        # Ne pas propager l'erreur pour éviter de bloquer le pipeline
