from fastapi import FastAPI
import sqlite3
import os

app = FastAPI()

DB_PATH = "/data/ranking.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_scores (
            user_id TEXT PRIMARY KEY,
            score REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/score")
def update_score(user_id: str, score: float):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO user_scores (user_id, score, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id)
        DO UPDATE SET
            score = excluded.score,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, score))

    conn.commit()
    conn.close()

    return {"status": "updated", "user": user_id, "score": score}

@app.get("/leaderboard")
def get_leaderboard():
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            user_id,
            score,
            RANK() OVER (ORDER BY score DESC) AS user_rank
        FROM user_scores
        ORDER BY score DESC
        LIMIT 10
    """)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"leaderboard": results}