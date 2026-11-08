"""Firebase Admin app + Firestore client. The API is the only writer of AI fields (PLAN.md 5).

On Cloud Run this uses the service account (ADC). Locally, set FIRESTORE_EMULATOR_HOST and
FIREBASE_AUTH_EMULATOR_HOST to use the emulators.

Collections: users, trips (+ messages, plans), shares, cache_places, cache_videos (PLAN.md 7.1).
"""

from functools import lru_cache

import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore import Client

from app.config import get_settings


@lru_cache
def firebase_app() -> firebase_admin.App:
    project = get_settings().google_cloud_project
    return firebase_admin.initialize_app(options={"projectId": project} if project else None)


def db() -> Client:
    return firestore.client(firebase_app())
