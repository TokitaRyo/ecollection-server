"""
Ecollection — Script de seed des données de jeu
Exécuter une seule fois après le déploiement initial.

Usage :
  python seed_data.py

Nécessite :
  - firebase-admin
  - Le fichier firebase-credentials.json à la racine
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json"))
firebase_admin.initialize_app(cred)
db = firestore.client()


# ============================================
# 1. Raretés
# ============================================
print("Insertion des raretes...")

rarities = {}
rarity_data = [
    {"rarityName": "Common",    "pointsGiven": 100},
    {"rarityName": "Rare",      "pointsGiven": 500},
    {"rarityName": "Epic",      "pointsGiven": 2000},
    {"rarityName": "Legendary", "pointsGiven": 10000},
    {"rarityName": "SSR",       "pointsGiven": 50000},
]

for r in rarity_data:
    _, ref = db.collection("rarities").add(r)
    rarities[r["rarityName"]] = ref.id
    print(f"  OK {r['rarityName']} ({r['pointsGiven']} pts) -> {ref.id}")


# ============================================
# 2. Types de tâches (difficultés)
# ============================================
print("\nInsertion des types de taches...")

task_types = {}
for name in ["Easy", "Medium", "Hard", "Infernal"]:
    _, ref = db.collection("taskTypes").add({"name": name})
    task_types[name] = ref.id
    print(f"  OK {name} -> {ref.id}")


# ============================================
# 3. Badges (12 — 1 image unique chacun)
# ============================================
print("\nInsertion des badges...")

badge_defs = [
    # Common (3)
    {"name": "Premiers Pas", "description": "Tu as fait tes premiers pas dans l'aventure. Chaque voyage commence par un seul pas !", "imageName": "smile.png",    "rarity": "Common"},
    {"name": "Eco-Citoyen",  "description": "Tu as choisi tes pieds plutot que ta voiture. La planete te remercie.",                  "imageName": "apple.png",    "rarity": "Common"},
    {"name": "Pas a Pas",    "description": "La regularite paie toujours. Continue comme ca !",                                       "imageName": "grape.png",    "rarity": "Common"},

    # Rare (3)
    {"name": "Sentier Vert", "description": "Tu as prouve que la nature se merite. Les plus beaux paysages sont au bout du chemin.", "imageName": "cat.png",      "rarity": "Rare"},
    {"name": "Leve-Tot",     "description": "Marcher avant l'aube, seul avec le monde. Un moment rare que tu as su capturer.",       "imageName": "orange.png",   "rarity": "Rare"},
    {"name": "Explorateur",  "description": "Quitter sa zone de confort pour decouvrir de nouveaux horizons, c'est ca l'aventure.",  "imageName": "sunglass.png", "rarity": "Rare"},

    # Epic (2)
    {"name": "Force de la Nature", "description": "Pluie, vent, soleil - rien ne t'arrete. Tu es devenu un element de la nature.", "imageName": "dog.png",  "rarity": "Epic"},
    {"name": "Nomade",             "description": "30km loin de chez toi, a pied. Tu redefinis le sens du mot liberte.",           "imageName": "bird.png", "rarity": "Epic"},

    # Legendary (2)
    {"name": "Legende Urbaine", "description": "On raconte qu'un marcheur a traverse la ville entiere a pied. C'etait toi.",          "imageName": "diamond.png", "rarity": "Legendary"},
    {"name": "Tour du Monde",   "description": "Tes pas cumules feraient le tour de la Terre. Enfin presque. Mais on y croit.",       "imageName": "ruby.png",    "rarity": "Legendary"},

    # SSR (2)
    {"name": "Etoile Verte",       "description": "Le badge ultime. Tu incarnes l'esprit d'Ecollection : marcher pour un monde meilleur. Respect eternel.", "imageName": "special1.jpg", "rarity": "SSR"},
    {"name": "Titan des Sentiers", "description": "Seuls les plus determines atteignent ce niveau. Tu es une legende vivante de la marche.",                "imageName": "special2.jpg", "rarity": "SSR"},
]

badges = {}
for b in badge_defs:
    _, ref = db.collection("badges").add({
        "name": b["name"],
        "description": b["description"],
        "imageName": b["imageName"],
        "rarityId": rarities[b["rarity"]],
    })
    badges[b["name"]] = ref.id
    print(f"  OK [{b['rarity']}] {b['name']} ({b['imageName']}) -> {ref.id}")


# ============================================
# 4. Tâches (15) — rewards adaptés aux 12 badges restants
# ============================================
print("\nInsertion des taches...")

task_defs = [
    # ----- EASY -----
    {
        "name": "Little Walker",
        "description": "Walk 3,000 steps in less than 24h.",
        "difficulty": "Easy",
        "objective": 3000,
        "time": "24:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 1,
        "rewards": [
            {"badge": "Premiers Pas", "dropRate": 70, "nb": 1},
            {"badge": "Pas a Pas",    "dropRate": 30, "nb": 1},
        ],
    },
    {
        "name": "Morning Stroll",
        "description": "Walk 1,500 steps in less than 2 hours.",
        "difficulty": "Easy",
        "objective": 1500,
        "time": "02:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 1,
        "rewards": [
            {"badge": "Pas a Pas",   "dropRate": 80, "nb": 1},
            {"badge": "Eco-Citoyen", "dropRate": 20, "nb": 1},
        ],
    },
    {
        "name": "Eco Walk",
        "description": "Walk 5,000 steps in a day. That's a car trip you saved!",
        "difficulty": "Easy",
        "objective": 5000,
        "time": "24:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 1,
        "rewards": [
            {"badge": "Eco-Citoyen",  "dropRate": 60, "nb": 1},
            {"badge": "Premiers Pas", "dropRate": 30, "nb": 1},
            {"badge": "Pas a Pas",    "dropRate": 10, "nb": 1},
        ],
    },

    # ----- MEDIUM -----
    {
        "name": "Urban Explorer",
        "description": "Walk 10,000 steps in less than 12 hours.",
        "difficulty": "Medium",
        "objective": 10000,
        "time": "12:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 3,
        "rewards": [
            {"badge": "Pas a Pas",    "dropRate": 50, "nb": 1},
            {"badge": "Explorateur",  "dropRate": 35, "nb": 1},
            {"badge": "Sentier Vert", "dropRate": 15, "nb": 1},
        ],
    },
    {
        "name": "Climbing Machine",
        "description": "Reach 500m of altitude in less than 24h.",
        "difficulty": "Medium",
        "objective": 500,
        "time": "24:00",
        "metricType": "altitude",
        "requiresHome": False,
        "resetPeriodDays": 5,
        "rewards": [
            {"badge": "Sentier Vert", "dropRate": 55, "nb": 1},
            {"badge": "Nomade",       "dropRate": 30, "nb": 1},
            {"badge": "Leve-Tot",     "dropRate": 15, "nb": 1},
        ],
    },
    {
        "name": "Neighborhood Escape",
        "description": "Walk at least 5km away from home.",
        "difficulty": "Medium",
        "objective": 5000,
        "time": "12:00",
        "metricType": "distance_from_home",
        "requiresHome": True,
        "resetPeriodDays": 3,
        "rewards": [
            {"badge": "Explorateur", "dropRate": 60, "nb": 1},
            {"badge": "Eco-Citoyen", "dropRate": 25, "nb": 1},
            {"badge": "Nomade",      "dropRate": 15, "nb": 1},
        ],
    },
    {
        "name": "Weekend Warrior",
        "description": "Walk 20,000 steps in less than 24 hours.",
        "difficulty": "Medium",
        "objective": 20000,
        "time": "24:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 7,
        "rewards": [
            {"badge": "Sentier Vert",       "dropRate": 45, "nb": 1},
            {"badge": "Leve-Tot",           "dropRate": 40, "nb": 1},
            {"badge": "Force de la Nature", "dropRate": 15, "nb": 1},
        ],
    },

    # ----- HARD -----
    {
        "name": "Bannished",
        "description": "Stay at least 30km away from home for 24 hours.",
        "difficulty": "Hard",
        "objective": 30000,
        "time": "24:00",
        "metricType": "distance_from_home",
        "requiresHome": True,
        "resetPeriodDays": 7,
        "rewards": [
            {"badge": "Nomade",             "dropRate": 50, "nb": 1},
            {"badge": "Force de la Nature", "dropRate": 30, "nb": 1},
            {"badge": "Legende Urbaine",    "dropRate": 15, "nb": 1},
            {"badge": "Etoile Verte",       "dropRate": 5,  "nb": 1},
        ],
    },
    {
        "name": "Summit Hunter",
        "description": "Reach 1,500m of altitude in less than 48 hours.",
        "difficulty": "Hard",
        "objective": 1500,
        "time": "48:00",
        "metricType": "altitude",
        "requiresHome": False,
        "resetPeriodDays": 7,
        "rewards": [
            {"badge": "Nomade",             "dropRate": 40, "nb": 1},
            {"badge": "Force de la Nature", "dropRate": 30, "nb": 1},
            {"badge": "Tour du Monde",      "dropRate": 20, "nb": 1},
            {"badge": "Titan des Sentiers", "dropRate": 10, "nb": 1},
        ],
    },
    {
        "name": "Marathon Day",
        "description": "Walk 42,195 steps in less than 24 hours. The real marathon experience.",
        "difficulty": "Hard",
        "objective": 42195,
        "time": "24:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 7,
        "rewards": [
            {"badge": "Sentier Vert",       "dropRate": 40, "nb": 1},
            {"badge": "Force de la Nature", "dropRate": 30, "nb": 1},
            {"badge": "Legende Urbaine",    "dropRate": 20, "nb": 1},
            {"badge": "Tour du Monde",      "dropRate": 10, "nb": 1},
        ],
    },
    {
        "name": "Far From Home",
        "description": "Walk at least 15km away from home in less than 12 hours.",
        "difficulty": "Hard",
        "objective": 15000,
        "time": "12:00",
        "metricType": "distance_from_home",
        "requiresHome": True,
        "resetPeriodDays": 5,
        "rewards": [
            {"badge": "Nomade",          "dropRate": 45, "nb": 1},
            {"badge": "Explorateur",     "dropRate": 30, "nb": 1},
            {"badge": "Legende Urbaine", "dropRate": 20, "nb": 1},
            {"badge": "Etoile Verte",    "dropRate": 5,  "nb": 1},
        ],
    },

    # ----- INFERNAL -----
    {
        "name": "Speedrunner",
        "description": "Walk 2,000,000 steps in less than a month.",
        "difficulty": "Infernal",
        "objective": 2000000,
        "time": None,
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 30,
        "rewards": [
            {"badge": "Force de la Nature", "dropRate": 30, "nb": 2},
            {"badge": "Tour du Monde",      "dropRate": 30, "nb": 1},
            {"badge": "Legende Urbaine",    "dropRate": 20, "nb": 1},
            {"badge": "Titan des Sentiers", "dropRate": 15, "nb": 1},
            {"badge": "Etoile Verte",       "dropRate": 5,  "nb": 1},
        ],
    },
    {
        "name": "Sky Piercer",
        "description": "Reach 3,000m of cumulated altitude in less than 7 days.",
        "difficulty": "Infernal",
        "objective": 3000,
        "time": None,
        "metricType": "altitude",
        "requiresHome": False,
        "resetPeriodDays": 14,
        "rewards": [
            {"badge": "Tour du Monde",      "dropRate": 35, "nb": 1},
            {"badge": "Nomade",             "dropRate": 25, "nb": 2},
            {"badge": "Force de la Nature", "dropRate": 20, "nb": 1},
            {"badge": "Titan des Sentiers", "dropRate": 15, "nb": 1},
            {"badge": "Etoile Verte",       "dropRate": 5,  "nb": 1},
        ],
    },
    {
        "name": "The Great Exodus",
        "description": "Stay at least 50km away from home for 48 hours straight.",
        "difficulty": "Infernal",
        "objective": 50000,
        "time": "48:00",
        "metricType": "distance_from_home",
        "requiresHome": True,
        "resetPeriodDays": 14,
        "rewards": [
            {"badge": "Nomade",             "dropRate": 25, "nb": 2},
            {"badge": "Legende Urbaine",    "dropRate": 25, "nb": 1},
            {"badge": "Tour du Monde",      "dropRate": 25, "nb": 1},
            {"badge": "Titan des Sentiers", "dropRate": 15, "nb": 1},
            {"badge": "Etoile Verte",       "dropRate": 10, "nb": 1},
        ],
    },
    {
        "name": "100K Challenge",
        "description": "Walk 100,000 steps in less than 48 hours. Only legends complete this.",
        "difficulty": "Infernal",
        "objective": 100000,
        "time": "48:00",
        "metricType": "steps",
        "requiresHome": False,
        "resetPeriodDays": 14,
        "rewards": [
            {"badge": "Force de la Nature", "dropRate": 100, "nb": 1},
            {"badge": "Tour du Monde",      "dropRate": 30,  "nb": 1},
            {"badge": "Titan des Sentiers", "dropRate": 15,  "nb": 1},
            {"badge": "Etoile Verte",       "dropRate": 5,   "nb": 1},
        ],
    },
]

tasks = {}
for t in task_defs:
    _, ref = db.collection("tasks").add({
        "taskTypeId": task_types[t["difficulty"]],
        "name": t["name"],
        "description": t["description"],
        "objective": t["objective"],
        "time": t["time"],
        "metricType": t["metricType"],
        "requiresHome": t["requiresHome"],
        "resetPeriodDays": t["resetPeriodDays"],
    })
    tasks[t["name"]] = {"id": ref.id, "rewards": t["rewards"]}
    print(f"  OK [{t['difficulty']}] {t['name']} (objectif: {t['objective']} {t['metricType']}) -> {ref.id}")


# ============================================
# 5. Task Rewards
# ============================================
print("\nInsertion des recompenses...")

for task_name, task_info in tasks.items():
    for reward in task_info["rewards"]:
        db.collection("taskRewards").add({
            "taskId": task_info["id"],
            "badgeId": badges[reward["badge"]],
            "numberOfBadges": reward["nb"],
            "dropRate": reward["dropRate"],
        })
        print(f"  OK {task_name} -> {reward['badge']} ({reward['dropRate']}%, x{reward['nb']})")


# ============================================
# Résumé
# ============================================
print("\n" + "=" * 50)
print("SEED TERMINE !")
print("=" * 50)
print(f"  Raretes     : {len(rarity_data)}")
print(f"  Difficultes : {len(task_types)}")
print(f"  Badges      : {len(badge_defs)}")
print(f"  Taches      : {len(task_defs)}")
print(f"  Recompenses : {sum(len(t['rewards']) for t in task_defs)}")
print("=" * 50)
