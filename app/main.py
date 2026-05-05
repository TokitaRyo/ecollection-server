from fastapi import FastAPI
import mysql.connector
import os

app = FastAPI()

# Database connection settings
db_config = {
    "host": "db",
    "user": "user",
    "password": "password",
    "database": "ranking_db"
}

@app.post("/score")
def update_score(user_id: str, score: float):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    # Upsert logic: Insert new or update existing score
    query ="""
    INSERT INTO user_scores (user_id, score)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE score = VALUES(score)
    """

    cursor.execute(query, (user_id, score))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "updated", "user": user_id, "score": score}

@app.get("/leaderboard")
def get_leaderboard():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    # The SQL Window Function logic
    query = """
    SELECT user_id, score, 
           RANK() OVER (ORDER BY score DESC) as user_rank 
    FROM user_scores 
    LIMIT 10
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"leaderboard": results}