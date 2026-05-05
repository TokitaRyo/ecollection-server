from fastapi import FastAPI, HTTPException
import mysql.connector
import time
import os

app = FastAPI()

# Database configuration using environment variables
db_config = {
    "host": "db", # This MUST match the service name in docker-compose
    "user": "user",
    "password": "password",
    "database": "ranking_db"
}

def get_db_connection():
    """Retries connection until MySQL is ready."""
    while True:
        try:
            conn = mysql.connector.connect(**db_config)
            return conn
        except mysql.connector.Error as err:
            print(f"Database not ready yet... {err}")
            time.sleep(2)

@app.post("/score")
def update_score(user_id: str, score: float):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
        INSERT INTO user_scores (user_id, score) 
        VALUES (%s, %s) 
        ON DUPLICATE KEY UPDATE score = VALUES(score)
        """
        cursor.execute(query, (user_id, score))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "user": user_id, "score": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/leaderboard")
def get_leaderboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # SQL Window function for ranking
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))