# virtual-concierge-app/reservation-api-service/src/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Import CORS middleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
import os
import json

# Initialize FastAPI app
app = FastAPI(
    title="Cafe Reservation API",
    description="API for managing cafe reservations with Firestore backend.",
    version="1.0.0"
)

# --- CORS Configuration ---
# This is crucial for allowing your frontend (running on localhost:80)
# to make requests to your backend (running on localhost:8000).
# In a production environment, replace "*" with your frontend's actual domain(s).
origins = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:8000", # If your frontend is served from here during dev
    # Add your production frontend URL(s) here when deploying
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (GET, POST, DELETE, etc.)
    allow_headers=["*"], # Allow all headers
)

# --- Firebase Initialization ---
# This section handles the secure initialization of Firebase Admin SDK.
# For local Docker deployment, it expects a service account key file mounted into the container.
# In production, consider using environment variables or Kubernetes secrets for credentials.
db = None # Initialize db as None
try:
    # Get the path to the Firebase service account key JSON file from environment variable
    # This environment variable will be set in docker-compose.yml
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

    if not service_account_path:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_PATH environment variable not set.")

    # Load credentials from the specified path
    # Ensure this path is accessible inside the Docker container
    cred = credentials.Certificate(service_account_path)

    # Initialize Firebase app if it hasn't been initialized already
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    else:
        print("Firebase app already initialized.")

    db = firestore.client()
    print("Firebase Firestore client initialized successfully.")

except ValueError as e:
    print(f"Configuration Error: {e}. Firebase Admin SDK not initialized.")
    # In a production app, you might want to exit or log more severely
except FirebaseError as e:
    print(f"Firebase Initialization Error: {e}. Check your service account key.")
except Exception as e:
    print(f"An unexpected error occurred during Firebase initialization: {e}")

# Get APP_ID from environment variable, used for Firestore collection paths
# This should match your Firebase Project ID or a custom app ID you define for security rules.
APP_ID = os.getenv("APP_ID", "default-app-id")

# For this blueprint, we'll use a fixed user ID for all reservations
# In a real application, this would come from an authentication system (e.g., Firebase Auth)
# and would be passed securely from the frontend or derived from an auth token.
# This ensures data is stored under a specific user's context as per Firestore security rules.
DEMO_USER_ID = "demo_cafe_user" # This is a placeholder. IMPORTANT for security rules.

# Pydantic model for request body validation
class ReservationCreate(BaseModel):
    name: str
    email: str
    date: str
    time: str
    guests: int
    location: Optional[str] = None
    dietary: Optional[str] = None

class ReservationResponse(ReservationCreate):
    id: str
    timestamp: datetime # Add timestamp for response model

@app.middleware("http")
async def check_db_connection(request, call_next):
    """
    Middleware to check if Firestore DB is initialized before processing requests.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Backend service not ready: Database not initialized. Check server logs for Firebase config errors.")
    response = await call_next(request)
    return response

@app.post("/api/reservations", response_model=ReservationResponse, status_code=201)
async def create_reservation(reservation: ReservationCreate):
    """
    Creates a new reservation in Firestore.
    """
    try:
        reservation_data = reservation.dict()
        reservation_data["timestamp"] = firestore.SERVER_TIMESTAMP # Use server timestamp for consistency

        # Firestore path: artifacts/{appId}/users/{userId}/reservations
        # Ensure your Firestore security rules allow this write operation.
        doc_ref = await db.collection(f"artifacts/{APP_ID}/users/{DEMO_USER_ID}/reservations").add(reservation_data)

        # Fetch the created document to get the server-generated timestamp and ID
        # Note: serverTimestamp() might not be immediately resolved on read.
        # For immediate resolution, you might need to wait or handle it client-side.
        # For this demo, we'll fetch it to ensure the ID is available.
        created_doc = await doc_ref.get()
        if not created_doc.exists:
            raise HTTPException(status_code=500, detail="Failed to retrieve created reservation.")

        # Convert Firestore Timestamp to datetime object for Pydantic response
        data_to_return = created_doc.to_dict()
        if 'timestamp' in data_to_return and hasattr(data_to_return['timestamp'], 'isoformat'):
            data_to_return['timestamp'] = data_to_return['timestamp'].isoformat()
        elif 'timestamp' in data_to_return and hasattr(data_to_return['timestamp'], 'to_datetime'):
            data_to_return['timestamp'] = data_to_return['timestamp'].to_datetime().isoformat()
        else:
            data_to_return['timestamp'] = datetime.now().isoformat() # Fallback for local testing

        return ReservationResponse(id=created_doc.id, **data_to_return)

    except Exception as e:
        print(f"Error creating reservation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create reservation: {str(e)}")

@app.get("/api/reservations", response_model=list[ReservationResponse])
async def get_reservations():
    """
    Retrieves all reservations for the demo user from Firestore.
    """
    try:
        reservations_ref = db.collection(f"artifacts/{APP_ID}/users/{DEMO_USER_ID}/reservations")
        # For simplicity and to avoid needing Firestore indexes for orderBy in this blueprint,
        # we fetch all and let the frontend sort. In a large scale app, use orderBy on Firestore.
        docs_list = []
        for doc in reservations_ref.stream():
            data = doc.to_dict()
            # Convert Firestore Timestamp to datetime object for Pydantic
            if 'timestamp' in data and hasattr(data['timestamp'], 'isoformat'):
                data['timestamp'] = data['timestamp'].isoformat()
            elif 'timestamp' in data and hasattr(data['timestamp'], 'to_datetime'):
                 data['timestamp'] = data['timestamp'].to_datetime().isoformat()
            else:
                data['timestamp'] = datetime.now().isoformat() # Fallback

            docs_list.append(ReservationResponse(id=doc.id, **data))

        return docs_list
    except Exception as e:
        print(f"Error fetching reservations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch reservations: {str(e)}")

@app.delete("/api/reservations/{reservation_id}", status_code=204)
async def delete_reservation(reservation_id: str):
    """
    Deletes a specific reservation from Firestore.
    """
    try:
        doc_ref = db.collection(f"artifacts/{APP_ID}/users/{DEMO_USER_ID}/reservations").document(reservation_id)
        await doc_ref.delete()
        return {} # No content for 204
    except Exception as e:
        print(f"Error deleting reservation {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete reservation: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Endpoint to check the health of the API service and database connection.
    """
    if db:
        # Attempt a small read to verify database connection
        try:
            # Try to get a non-existent document to confirm connection without side effects
            await db.collection(f"artifacts/{APP_ID}/users/{DEMO_USER_ID}/health_check").document("test").get()
            return {"status": "ok", "database": "connected"}
        except Exception as e:
            print(f"Health check failed to connect to Firestore: {e}")
            raise HTTPException(status_code=503, detail="Database connection failed.")
    else:
        raise HTTPException(status_code=503, detail="Backend service not ready: Database not initialized.")

