from fastapi import FastAPI
import firebase_admin
from firebase_admin import credentials, firestore

app = FastAPI()

cred = credentials.Certificate("/app/firebase-key.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

@app.get("/")
def root():
    return {"status": "ok", "database": "firebase"}

@app.post("/score")
def update_score(user_id: str, score: int):
    user_ref = db.collection("user_scores").document(user_id)

    user_ref.set({
        "user_id": user_id,
        "score": score
    }, merge=True)

    return {
        "status": "updated",
        "user_id": user_id,
        "score": score
    }

@app.get("/leaderboard")
def get_leaderboard():
    docs = (
        db.collection("user_scores")
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(10)
        .stream()
    )

    leaderboard = []
    rank = 1

    for doc in docs:
        data = doc.to_dict()
        leaderboard.append({
            "rank": rank,
            "user_id": data.get("user_id"),
            "score": data.get("score")
        })
        rank += 1

    return {"leaderboard": leaderboard}

POINTS = {
    "recycling": 10,
    "vegetarian_meal": 15,
    "walking": 20,
}

@app.post("/action")
def log_action(user_id: str, action: str):
    pts = POINTS.get(action, 5)

    ref = db.collection("user_scores").document(user_id)
    snap = ref.get()

    data = snap.to_dict() if snap.exists else {}
    current = data.get("score", 0)

    new_score = current + pts

    ref.set({
        "user_id": user_id,
        "score": new_score,
        "last_action": action
    }, merge=True)

    return {
        "user_id": user_id,
        "action": action,
        "added": pts,
        "total": new_score
    }