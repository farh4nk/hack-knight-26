import uuid
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)

def test_sync_new_user_and_auto_seed_baby():
    test_sub = f"google_test_{uuid.uuid4()}"
    user_payload = {
        "id": test_sub,
        "email": f"{test_sub}@example.com",
        "name": "Alex Smith",
        "avatar_url": "https://lh3.googleusercontent.com/test-pic"
    }

    # First sync: creates user and seeds primary baby
    response = client.post("/api/users/sync", json=user_payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["id"] == test_sub
    assert data["user"]["email"] == f"{test_sub}@example.com"
    assert data["user"]["name"] == "Alex Smith"
    assert data["baby"]["parent_id"] == test_sub
    assert data["baby"]["name"] == ""
    baby_id = data["baby"]["id"]

    # Fetch baby via parent user ID
    get_res = client.get(f"/api/users/{test_sub}/baby")
    assert get_res.status_code == 200
    assert get_res.json()["baby"]["id"] == baby_id

    # Update baby profile
    update_res = client.put(f"/api/babies/{baby_id}", json={
        "name": "Test Baby",
        "bedtime": "19:30",
        "wake_time": "06:30",
        "voice_id": "test_elevenlabs_voice_123"
    })
    assert update_res.status_code == 200
    updated_baby = update_res.json()["baby"]
    assert updated_baby["name"] == "Test Baby"
    assert updated_baby["bedtime"] == "19:30"
    assert updated_baby["voice_id"] == "test_elevenlabs_voice_123"

    # Second sync for same user: should retain updated baby
    resync_response = client.post("/api/users/sync", json={
        "id": test_sub,
        "email": f"{test_sub}@example.com",
        "name": "Alex Smith Updated",
        "avatar_url": "https://lh3.googleusercontent.com/test-pic"
    })
    assert resync_response.status_code == 200
    resync_data = resync_response.json()
    assert resync_data["user"]["name"] == "Alex Smith Updated"
    assert resync_data["baby"]["id"] == baby_id
    assert resync_data["baby"]["name"] == "Test Baby"
