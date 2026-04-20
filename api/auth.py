import os
import json
import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.config import settings

# Initialize Firebase Admin
if not firebase_admin._apps:
    firebase_service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if firebase_service_account_json:
        cred = credentials.Certificate(json.loads(firebase_service_account_json))
    else:
        cred = credentials.Certificate(settings.firebase_service_account_path_absolute)
    firebase_admin.initialize_app(cred)

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifies the Firebase ID token in the Authorization header.
    """
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
