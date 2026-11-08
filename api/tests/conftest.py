"""Test env, set before the app (and its cached settings) is imported."""

import os

os.environ.setdefault("SKIP_APPCHECK", "1")
if os.getenv("FIRESTORE_EMULATOR_HOST"):
    # Emulator runs only: never point tests at a real project.
    os.environ["GOOGLE_CLOUD_PROJECT"] = "demo-trip-planner"
