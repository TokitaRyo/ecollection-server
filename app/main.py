import os
import random
from datetime import datetime, date, timedelta
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
import firebase_admin
from firebase_admin import credentials, firestore, auth

FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")
from fastapi.middleware.cors import CORSMiddleware
from google.cloud.firestore_v1.base_query import FieldFilter

# ============================================
# Firebase
# ============================================

cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json"))
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI(title="Ecollection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Modèles Pydantic
# ============================================

# --- Auth ---
class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str


class LoginRequest(BaseModel):
    email: str
    password: str


# --- User ---
class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    avatarUrl: Optional[str] = None


class UpdateHomePositionRequest(BaseModel):
    homeLatitude: float
    homeLongitude: float


# --- Tasks ---
class AcceptTaskRequest(BaseModel):
    taskId: str


class UpdateProgressRequest(BaseModel):
    taskId: str
    progress: int


# --- Admin : création de contenu ---
class CreateRarityRequest(BaseModel):
    rarityName: str
    pointsGiven: int = 0


class CreateBadgeRequest(BaseModel):
    name: str
    description: str
    imageName: str
    rarityId: str


class CreateTaskTypeRequest(BaseModel):
    name: str


class CreateTaskRequest(BaseModel):
    taskTypeId: str
    name: str
    description: str
    objective: int
    time: Optional[str] = None
    metricType: str = "steps"
    requiresHome: bool = False
    resetPeriodDays: Optional[int] = None


class CreateTaskRewardRequest(BaseModel):
    taskId: str
    badgeId: str
    numberOfBadges: int = 1
    dropRate: float = 100.0


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class GiveRandomBadgeRequest(BaseModel):
    nickname: str


# ============================================
# Authentification (middleware)
# ============================================

async def get_current_user(authorization: str = Header(...)) -> dict:
    """Vérifie le token Firebase et retourne les infos de l'utilisateur."""
    try:
        token = authorization.replace("Bearer ", "")
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")


# ============================================
# Utilitaires
# ============================================

def update_streak(user_ref, user_data: dict):
    """Met à jour le streak de connexion journalier."""
    today = date.today().isoformat()
    last_active = user_data.get("lastActiveDate")

    if last_active == today:
        return

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    current_streak = user_data.get("currentStreak", 0)

    if last_active == yesterday:
        current_streak += 1
    else:
        current_streak = 1

    user_ref.update({
        "currentStreak": current_streak,
        "lastActiveDate": today,
    })


def roll_rewards(task_id: str) -> list[dict]:
    """Tire au sort les récompenses d'une tâche selon les dropRate."""
    rewards_ref = db.collection("taskRewards").where(filter=FieldFilter("taskId", "==", task_id)).stream()
    rewards = [r.to_dict() | {"id": r.id} for r in rewards_ref]

    if not rewards:
        return []

    # Récompenses garanties (dropRate == 100)
    guaranteed = [r for r in rewards if r["dropRate"] >= 100]

    # Récompenses aléatoires (dropRate < 100) → tirage pondéré
    random_pool = [r for r in rewards if r["dropRate"] < 100]
    won = list(guaranteed)

    if random_pool:
        roll = random.uniform(0, 100)
        cumulative = 0
        for reward in random_pool:
            cumulative += reward["dropRate"]
            if roll <= cumulative:
                won.append(reward)
                break

    return won


# ============================================
# Routes : Auth
# ============================================

@app.post("/auth/register", tags=["Auth"])
async def register(req: RegisterRequest):
    """Crée un compte utilisateur (Firebase Auth + Firestore)."""
    # Vérifier que le nickname est unique
    existing = db.collection("users").where(filter=FieldFilter("nickname", "==", req.nickname)).limit(1).get()
    if existing:
        raise HTTPException(status_code=400, detail="Ce nickname est déjà pris")

    try:
        user = auth.create_user(email=req.email, password=req.password)
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Document utilisateur dans Firestore
    db.collection("users").document(user.uid).set({
        "email": req.email,
        "nickname": req.nickname,
        "avatarUrl": None,
        "dateCreation": datetime.utcnow().isoformat(),
        "homeLatitude": None,
        "homeLongitude": None,
        "numberTotalOfSteps": 0,
        "score": 0,
        "currentStreak": 0,
        "lastActiveDate": None,
    })

    return {"uid": user.uid, "message": "Compte créé avec succès"}


@app.post("/auth/login", tags=["Auth"])
async def login(req: LoginRequest):
    """Connecte un utilisateur via Firebase Auth REST et retourne un ID token."""
    if not FIREBASE_WEB_API_KEY:
        raise HTTPException(500, "FIREBASE_WEB_API_KEY non configurée côté serveur")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    r = requests.post(url, json={
        "email": req.email,
        "password": req.password,
        "returnSecureToken": True,
    }, timeout=10)

    if r.status_code != 200:
        raise HTTPException(401, "Email ou mot de passe incorrect")

    data = r.json()
    return {
        "idToken": data["idToken"],
        "refreshToken": data["refreshToken"],
        "uid": data["localId"],
        "expiresIn": int(data["expiresIn"]),
    }


@app.post("/auth/refresh", tags=["Auth"])
async def refresh_token(req: RefreshTokenRequest):
    """Échange un refresh token contre un nouveau ID token."""
    if not FIREBASE_WEB_API_KEY:
        raise HTTPException(500, "FIREBASE_WEB_API_KEY non configurée côté serveur")

    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_WEB_API_KEY}"
    r = requests.post(url, data={
        "grant_type": "refresh_token",
        "refresh_token": req.refreshToken,
    }, timeout=10)

    if r.status_code != 200:
        raise HTTPException(401, "Refresh token invalide ou expiré")

    data = r.json()
    return {
        "idToken": data["id_token"],
        "refreshToken": data["refresh_token"],
        "uid": data["user_id"],
        "expiresIn": int(data["expires_in"]),
    }


# ============================================
# Routes : Utilisateur
# ============================================

@app.get("/user/profile", tags=["User"])
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Récupère le profil de l'utilisateur connecté."""
    uid = current_user["uid"]
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user_data = user_doc.to_dict()
    update_streak(user_ref, user_data)

    # Recharger après mise à jour du streak
    user_data = user_ref.get().to_dict()
    return user_data | {"uid": uid}


@app.put("/user/profile", tags=["User"])
async def update_profile(req: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    """Met à jour le nickname et/ou l'avatar."""
    uid = current_user["uid"]
    updates = {}

    if req.nickname is not None:
        existing = db.collection("users").where(filter=FieldFilter("nickname", "==", req.nickname)).limit(1).get()
        for doc in existing:
            if doc.id != uid:
                raise HTTPException(status_code=400, detail="Ce nickname est déjà pris")
        updates["nickname"] = req.nickname

    if req.avatarUrl is not None:
        updates["avatarUrl"] = req.avatarUrl

    if not updates:
        raise HTTPException(status_code=400, detail="Aucune modification fournie")

    db.collection("users").document(uid).update(updates)
    return {"message": "Profil mis à jour"}


@app.put("/user/home-position", tags=["User"])
async def update_home_position(req: UpdateHomePositionRequest, current_user: dict = Depends(get_current_user)):
    """Configure la position GPS du domicile (nécessaire pour certaines tâches)."""
    uid = current_user["uid"]
    db.collection("users").document(uid).update({
        "homeLatitude": req.homeLatitude,
        "homeLongitude": req.homeLongitude,
    })
    return {"message": "Position du domicile mise à jour"}


# ============================================
# Routes : Classement (Leaderboard)
# ============================================

@app.get("/leaderboard", tags=["Leaderboard"])
async def get_leaderboard(limit: int = 50):
    """Retourne le classement des joueurs par score décroissant."""
    users = (
        db.collection("users")
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    leaderboard = []
    for rank, user in enumerate(users, start=1):
        data = user.to_dict()
        leaderboard.append({
            "rank": rank,
            "uid": user.id,
            "nickname": data.get("nickname"),
            "avatarUrl": data.get("avatarUrl"),
            "score": data.get("score", 0),
            "currentStreak": data.get("currentStreak", 0),
        })

    return leaderboard


@app.get("/leaderboard/me", tags=["Leaderboard"])
async def get_my_rank(current_user: dict = Depends(get_current_user)):
    """Retourne le rang de l'utilisateur connecté."""
    uid = current_user["uid"]
    user_doc = db.collection("users").document(uid).get()

    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    my_score = user_doc.to_dict().get("score", 0)

    # Compter les joueurs avec un score supérieur
    higher = (
        db.collection("users")
        .where(filter=FieldFilter("score", ">", my_score))
        .count()
        .get()
    )
    rank = higher[0][0].value + 1

    return {"rank": rank, "score": my_score}


# ============================================
# Routes : Tâches
# ============================================

@app.get("/tasks", tags=["Tasks"])
async def list_tasks(current_user: dict = Depends(get_current_user)):
    """Liste toutes les tâches disponibles avec leur difficulté et rewards."""
    uid = current_user["uid"]
    user_doc = db.collection("users").document(uid).get()
    user_data = user_doc.to_dict()
    has_home = user_data.get("homeLatitude") is not None

    tasks = db.collection("tasks").stream()
    result = []

    for task in tasks:
        task_data = task.to_dict()

        # Récupérer le type de tâche (difficulté)
        task_type_doc = db.collection("taskTypes").document(task_data["taskTypeId"]).get()
        task_type_name = task_type_doc.to_dict()["name"] if task_type_doc.exists else "Unknown"

        # Récupérer les rewards
        rewards = db.collection("taskRewards").where(filter=FieldFilter("taskId", "==", task.id)).stream()
        reward_list = []
        for r in rewards:
            r_data = r.to_dict()
            badge_doc = db.collection("badges").document(r_data["badgeId"]).get()
            badge_data = badge_doc.to_dict() if badge_doc.exists else {}
            reward_list.append({
                "badgeId": r_data["badgeId"],
                "badgeName": badge_data.get("name", "Unknown"),
                "imageName": badge_data.get("imageName"),
                "numberOfBadges": r_data.get("numberOfBadges", 1),
                "dropRate": r_data.get("dropRate", 100),
            })

        # Vérifier si le joueur a déjà cette tâche en cours
        selected = (
            db.collection("selectedTasks")
            .where(filter=FieldFilter("userId", "==", uid))
            .where(filter=FieldFilter("taskId", "==", task.id))
            .where(filter=FieldFilter("status", "==", "active"))
            .limit(1)
            .get()
        )

        locked = task_data.get("requiresHome", False) and not has_home

        result.append({
            "taskId": task.id,
            "name": task_data["name"],
            "description": task_data["description"],
            "objective": task_data["objective"],
            "time": task_data.get("time"),
            "metricType": task_data.get("metricType", "steps"),
            "requiresHome": task_data.get("requiresHome", False),
            "resetPeriodDays": task_data.get("resetPeriodDays"),
            "difficulty": task_type_name,
            "rewards": reward_list,
            "locked": locked,
            "inProgress": len(selected) > 0,
        })

    return result


@app.post("/tasks/accept", tags=["Tasks"])
async def accept_task(req: AcceptTaskRequest, current_user: dict = Depends(get_current_user)):
    """Accepter une tâche (la démarrer)."""
    uid = current_user["uid"]

    # Vérifier que la tâche existe
    task_doc = db.collection("tasks").document(req.taskId).get()
    if not task_doc.exists:
        raise HTTPException(status_code=404, detail="Tâche introuvable")

    task_data = task_doc.to_dict()

    # Vérifier si la tâche nécessite une position domicile
    if task_data.get("requiresHome", False):
        user_doc = db.collection("users").document(uid).get()
        if user_doc.to_dict().get("homeLatitude") is None:
            raise HTTPException(status_code=400, detail="Configurez votre position domicile pour cette tâche")

    # Vérifier que la tâche n'est pas déjà en cours
    existing = (
        db.collection("selectedTasks")
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("taskId", "==", req.taskId))
        .where(filter=FieldFilter("status", "==", "active"))
        .limit(1)
        .get()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Tâche déjà en cours")

    db.collection("selectedTasks").add({
        "userId": uid,
        "taskId": req.taskId,
        "progress": 0,
        "startDate": datetime.utcnow().isoformat(),
        "status": "active",
    })

    return {"message": "Tâche acceptée"}


@app.get("/tasks/active", tags=["Tasks"])
async def get_active_tasks(current_user: dict = Depends(get_current_user)):
    """Liste les tâches en cours de l'utilisateur avec leur progression."""
    uid = current_user["uid"]

    selected = (
        db.collection("selectedTasks")
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("status", "==", "active"))
        .stream()
    )

    result = []
    for sel in selected:
        sel_data = sel.to_dict()
        task_doc = db.collection("tasks").document(sel_data["taskId"]).get()

        if not task_doc.exists:
            continue

        task_data = task_doc.to_dict()
        objective = task_data["objective"]
        progress = sel_data.get("progress", 0)
        percentage = min(round((progress / objective) * 100), 100) if objective > 0 else 0

        # Calculer le temps restant
        time_remaining = None
        if task_data.get("time"):
            start = datetime.fromisoformat(sel_data["startDate"])
            parts = task_data["time"].split(":")
            hours = int(parts[0]) if len(parts) > 0 else 0
            minutes = int(parts[1]) if len(parts) > 1 else 0
            deadline = start + timedelta(hours=hours, minutes=minutes)
            remaining = deadline - datetime.utcnow()
            if remaining.total_seconds() > 0:
                time_remaining = str(remaining).split(".")[0]
            else:
                time_remaining = "00:00:00"

        result.append({
            "selectedTaskId": sel.id,
            "taskId": sel_data["taskId"],
            "name": task_data["name"],
            "description": task_data["description"],
            "objective": objective,
            "progress": progress,
            "percentage": percentage,
            "metricType": task_data.get("metricType", "steps"),
            "startDate": sel_data["startDate"],
            "timeRemaining": time_remaining,
        })

    return result


@app.put("/tasks/progress", tags=["Tasks"])
async def update_task_progress(req: UpdateProgressRequest, current_user: dict = Depends(get_current_user)):
    """Met à jour la progression d'une tâche (appelé par le tracker de l'app)."""
    uid = current_user["uid"]

    # Trouver la tâche sélectionnée active
    selected = (
        db.collection("selectedTasks")
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("taskId", "==", req.taskId))
        .where(filter=FieldFilter("status", "==", "active"))
        .limit(1)
        .get()
    )

    if not selected:
        raise HTTPException(status_code=404, detail="Tâche active introuvable")

    sel_doc = selected[0]
    sel_ref = db.collection("selectedTasks").document(sel_doc.id)

    # Récupérer l'objectif
    task_doc = db.collection("tasks").document(req.taskId).get()
    if not task_doc.exists:
        raise HTTPException(status_code=404, detail="Tâche introuvable")

    task_data = task_doc.to_dict()
    objective = task_data["objective"]

    # Mettre à jour la progression
    new_progress = min(req.progress, objective)
    sel_ref.update({"progress": new_progress})

    # Vérifier si la tâche est terminée
    if new_progress >= objective:
        sel_ref.update({"status": "completed"})

        # Tirer les récompenses
        won_rewards = roll_rewards(req.taskId)
        badges_won = []

        user_ref = db.collection("users").document(uid)
        user_data = user_ref.get().to_dict()
        total_points = 0

        for reward in won_rewards:
            badge_id = reward["badgeId"]
            nb = reward.get("numberOfBadges", 1)

            # Ajouter ou mettre à jour BadgePossessed
            badge_query = (
                db.collection("badgesPossessed")
                .where(filter=FieldFilter("userId", "==", uid))
                .where(filter=FieldFilter("badgeId", "==", badge_id))
                .limit(1)
                .get()
            )

            if badge_query:
                bp_ref = db.collection("badgesPossessed").document(badge_query[0].id)
                current_qty = badge_query[0].to_dict().get("quantity", 0)
                bp_ref.update({"quantity": current_qty + nb})
            else:
                db.collection("badgesPossessed").add({
                    "userId": uid,
                    "badgeId": badge_id,
                    "quantity": nb,
                    "obtention": datetime.utcnow().isoformat(),
                })

            # Calculer les points (via la rareté du badge)
            badge_doc = db.collection("badges").document(badge_id).get()
            if badge_doc.exists:
                rarity_id = badge_doc.to_dict().get("rarityId")
                rarity_doc = db.collection("rarities").document(rarity_id).get()
                if rarity_doc.exists:
                    total_points += rarity_doc.to_dict().get("pointsGiven", 0) * nb

                badges_won.append({
                    "badgeId": badge_id,
                    "badgeName": badge_doc.to_dict().get("name"),
                    "quantity": nb,
                })

        # Mettre à jour le score
        user_ref.update({
            "score": user_data.get("score", 0) + total_points,
            "numberTotalOfSteps": user_data.get("numberTotalOfSteps", 0) + (
                new_progress if task_data.get("metricType") == "steps" else 0
            ),
        })

        return {
            "completed": True,
            "badgesWon": badges_won,
            "pointsEarned": total_points,
        }

    return {"completed": False, "progress": new_progress, "objective": objective}


@app.post("/tasks/cancel", tags=["Tasks"])
async def cancel_task(req: AcceptTaskRequest, current_user: dict = Depends(get_current_user)):
    """Annuler une tâche en cours."""
    uid = current_user["uid"]

    selected = (
        db.collection("selectedTasks")
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("taskId", "==", req.taskId))
        .where(filter=FieldFilter("status", "==", "active"))
        .limit(1)
        .get()
    )

    if not selected:
        raise HTTPException(status_code=404, detail="Tâche active introuvable")

    db.collection("selectedTasks").document(selected[0].id).update({
        "status": "cancelled",
    })

    return {"message": "Tâche annulée"}


# ============================================
# Routes : Badges
# ============================================

@app.get("/badges", tags=["Badges"])
async def get_my_badges(current_user: dict = Depends(get_current_user)):
    """Liste tous les badges obtenus par l'utilisateur."""
    uid = current_user["uid"]

    possessed = db.collection("badgesPossessed").where(filter=FieldFilter("userId", "==", uid)).stream()

    result = []
    for bp in possessed:
        bp_data = bp.to_dict()
        badge_doc = db.collection("badges").document(bp_data["badgeId"]).get()

        if not badge_doc.exists:
            continue

        badge_data = badge_doc.to_dict()

        # Récupérer la rareté
        rarity_name = "Unknown"
        rarity_doc = db.collection("rarities").document(badge_data.get("rarityId", "")).get()
        if rarity_doc.exists:
            rarity_name = rarity_doc.to_dict().get("rarityName", "Unknown")

        result.append({
            "badgeId": bp_data["badgeId"],
            "name": badge_data["name"],
            "description": badge_data["description"],
            "imageName": badge_data["imageName"],
            "rarity": rarity_name,
            "quantity": bp_data.get("quantity", 1),
            "obtention": bp_data.get("obtention"),
        })

    return result


@app.get("/badges/{badge_id}", tags=["Badges"])
async def get_badge_detail(badge_id: str):
    """Détail d'un badge spécifique."""
    badge_doc = db.collection("badges").document(badge_id).get()

    if not badge_doc.exists:
        raise HTTPException(status_code=404, detail="Badge introuvable")

    badge_data = badge_doc.to_dict()

    rarity_name = "Unknown"
    points = 0
    rarity_doc = db.collection("rarities").document(badge_data.get("rarityId", "")).get()
    if rarity_doc.exists:
        rarity_data = rarity_doc.to_dict()
        rarity_name = rarity_data.get("rarityName", "Unknown")
        points = rarity_data.get("pointsGiven", 0)

    return {
        "badgeId": badge_id,
        "name": badge_data["name"],
        "description": badge_data["description"],
        "imageName": badge_data["imageName"],
        "rarity": rarity_name,
        "pointsGiven": points,
    }


# ============================================
# Routes : Admin (création de contenu)
# ============================================

@app.post("/admin/rarities", tags=["Admin"])
async def create_rarity(req: CreateRarityRequest):
    """Créer un niveau de rareté."""
    doc_ref = db.collection("rarities").add({
        "rarityName": req.rarityName,
        "pointsGiven": req.pointsGiven,
    })
    return {"id": doc_ref[1].id, "message": "Rareté créée"}


@app.post("/admin/task-types", tags=["Admin"])
async def create_task_type(req: CreateTaskTypeRequest):
    """Créer un type de tâche (difficulté)."""
    doc_ref = db.collection("taskTypes").add({"name": req.name})
    return {"id": doc_ref[1].id, "message": "Type de tâche créé"}


@app.post("/admin/badges", tags=["Admin"])
async def create_badge(req: CreateBadgeRequest):
    """Créer un badge."""
    doc_ref = db.collection("badges").add({
        "name": req.name,
        "description": req.description,
        "imageName": req.imageName,
        "rarityId": req.rarityId,
    })
    return {"id": doc_ref[1].id, "message": "Badge créé"}


@app.post("/admin/tasks", tags=["Admin"])
async def create_task(req: CreateTaskRequest):
    """Créer une tâche."""
    doc_ref = db.collection("tasks").add({
        "taskTypeId": req.taskTypeId,
        "name": req.name,
        "description": req.description,
        "objective": req.objective,
        "time": req.time,
        "metricType": req.metricType,
        "requiresHome": req.requiresHome,
        "resetPeriodDays": req.resetPeriodDays,
    })
    return {"id": doc_ref[1].id, "message": "Tâche créée"}


@app.post("/admin/task-rewards", tags=["Admin"])
async def create_task_reward(req: CreateTaskRewardRequest):
    """Associer une récompense (badge) à une tâche avec un taux de drop."""
    if req.dropRate <= 0 or req.dropRate > 100:
        raise HTTPException(status_code=400, detail="dropRate doit être entre 0 et 100")

    doc_ref = db.collection("taskRewards").add({
        "taskId": req.taskId,
        "badgeId": req.badgeId,
        "numberOfBadges": req.numberOfBadges,
        "dropRate": req.dropRate,
    })
    return {"id": doc_ref[1].id, "message": "Récompense créée"}


@app.post("/admin/badges/give-random", tags=["Admin"])
async def give_random_badge(req: GiveRandomBadgeRequest):
    """Donne un badge aléatoire (tirage uniforme) à un utilisateur identifié par son nickname."""
    # Trouver l'utilisateur par nickname
    user_query = (
        db.collection("users")
        .where(filter=FieldFilter("nickname", "==", req.nickname))
        .limit(1)
        .get()
    )
    if not user_query:
        raise HTTPException(status_code=404, detail=f"Aucun utilisateur avec le nickname '{req.nickname}'")

    user_doc = user_query[0]
    uid = user_doc.id

    # Tirer un badge aléatoire (uniforme)
    all_badges = list(db.collection("badges").stream())
    if not all_badges:
        raise HTTPException(status_code=404, detail="Aucun badge disponible en base")

    chosen = random.choice(all_badges)
    badge_id = chosen.id
    badge_data = chosen.to_dict()

    # Ajouter ou incrémenter dans badgesPossessed
    bp_query = (
        db.collection("badgesPossessed")
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("badgeId", "==", badge_id))
        .limit(1)
        .get()
    )
    if bp_query:
        bp_ref = db.collection("badgesPossessed").document(bp_query[0].id)
        new_quantity = bp_query[0].to_dict().get("quantity", 0) + 1
        bp_ref.update({"quantity": new_quantity})
    else:
        new_quantity = 1
        db.collection("badgesPossessed").add({
            "userId": uid,
            "badgeId": badge_id,
            "quantity": 1,
            "obtention": datetime.utcnow().isoformat(),
        })

    # Récupérer la rareté + points associés
    rarity_name = "Unknown"
    points = 0
    rarity_doc = db.collection("rarities").document(badge_data.get("rarityId", "")).get()
    if rarity_doc.exists:
        rarity_data = rarity_doc.to_dict()
        rarity_name = rarity_data.get("rarityName", "Unknown")
        points = rarity_data.get("pointsGiven", 0)

    # Ajouter les points au score utilisateur
    if points:
        user_data = user_doc.to_dict()
        db.collection("users").document(uid).update({
            "score": user_data.get("score", 0) + points,
        })

    return {
        "uid": uid,
        "nickname": req.nickname,
        "badge": {
            "badgeId": badge_id,
            "name": badge_data.get("name"),
            "description": badge_data.get("description"),
            "imageName": badge_data.get("imageName"),
            "rarity": rarity_name,
        },
        "quantityNow": new_quantity,
        "pointsEarned": points,
    }


@app.post("/admin/seed", tags=["Admin"])
async def seed_initial_data():
    """Insère les données initiales (raretés + types de tâches)."""
    # Raretés
    rarities = [
        {"rarityName": "Common", "pointsGiven": 100},
        {"rarityName": "Rare", "pointsGiven": 500},
        {"rarityName": "Epic", "pointsGiven": 2000},
        {"rarityName": "Legendary", "pointsGiven": 10000},
        {"rarityName": "SSR", "pointsGiven": 50000},
    ]
    for r in rarities:
        db.collection("rarities").add(r)

    # Types de tâches
    task_types = ["Easy", "Medium", "Hard", "Infernal"]
    for t in task_types:
        db.collection("taskTypes").add({"name": t})

    return {"message": "Données initiales insérées"}


# ============================================
# Health check
# ============================================

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
