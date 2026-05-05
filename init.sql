-- ============================================
-- Ecollection - Script de création de la BDD
-- ============================================
-- Application Flutter de gamification de la marche
-- Compatible MySQL / MariaDB
-- ============================================

CREATE DATABASE IF NOT EXISTS ecollection
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecollection;

-- ============================================
-- Table : Rarity
-- Niveaux de rareté des badges (ex: Common, Rare, SSR...)
-- Créée en premier car référencée par Badge
-- ============================================
CREATE TABLE Rarity (
    rarityId    INT             AUTO_INCREMENT PRIMARY KEY,
    rarityName  VARCHAR(50)     NOT NULL UNIQUE,
    pointsGiven BIGINT          NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- ============================================
-- Table : User
-- Comptes utilisateurs de l'application
-- ============================================
CREATE TABLE User (
    userId              INT             AUTO_INCREMENT PRIMARY KEY,
    avatarUrl           VARCHAR(500)    NULL,
    email               VARCHAR(255)    NOT NULL UNIQUE,
    password            VARCHAR(255)    NOT NULL,
    nickname            VARCHAR(100)    NOT NULL UNIQUE,
    dateCreation        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    homeLatitude        FLOAT           NULL,
    homeLongitude       FLOAT           NULL,
    numberTotalOfSteps  INT             NOT NULL DEFAULT 0,
    score               BIGINT          NOT NULL DEFAULT 0,
    currentStreak       INT             NOT NULL DEFAULT 0,
    lastActiveDate      DATE            NULL
) ENGINE=InnoDB;

-- ============================================
-- Table : Badge
-- Définition des badges disponibles dans le jeu
-- ============================================
CREATE TABLE Badge (
    badgeId     INT             AUTO_INCREMENT PRIMARY KEY,
    imageName   VARCHAR(255)    NOT NULL,
    description VARCHAR(500)    NOT NULL,
    name        VARCHAR(100)    NOT NULL,
    rarityId    INT             NOT NULL,

    CONSTRAINT fk_badge_rarity
        FOREIGN KEY (rarityId) REFERENCES Rarity(rarityId)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================
-- Table : BadgePossessed
-- Badges obtenus par les utilisateurs
-- Clé primaire composite (badgeId, userId)
-- ============================================
CREATE TABLE BadgePossessed (
    badgeId     INT             NOT NULL,
    userId      INT             NOT NULL,
    quantity    INT             NOT NULL DEFAULT 1,
    obtention   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (badgeId, userId),

    CONSTRAINT fk_badgepossessed_badge
        FOREIGN KEY (badgeId) REFERENCES Badge(badgeId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_badgepossessed_user
        FOREIGN KEY (userId) REFERENCES User(userId)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================
-- Table : TaskType
-- Types/difficultés de tâches (Easy, Medium, Hard, Infernal)
-- ============================================
CREATE TABLE TaskType (
    taskTypeId  INT             AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)     NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ============================================
-- Table : Task
-- Définition des tâches disponibles
-- ============================================
CREATE TABLE Task (
    taskId          INT             AUTO_INCREMENT PRIMARY KEY,
    taskTypeId      INT             NOT NULL,
    name            VARCHAR(100)    NOT NULL,
    description     TEXT            NOT NULL,
    objective       INT             NOT NULL,
    time            TIME            NULL,
    metricType      VARCHAR(50)     NOT NULL DEFAULT 'steps'
                    COMMENT 'Type de métrique : steps, altitude, distance_from_home',
    requiresHome    BOOLEAN         NOT NULL DEFAULT FALSE,
    resetPeriodDays INT             NULL
                    COMMENT 'Nombre de jours avant reset des tâches (NULL = pas de reset)',

    CONSTRAINT fk_task_tasktype
        FOREIGN KEY (taskTypeId) REFERENCES TaskType(taskTypeId)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================
-- Table : SelectedTask
-- Tâches acceptées/en cours par les utilisateurs
-- Clé primaire composite (userId, taskId)
-- ============================================
CREATE TABLE SelectedTask (
    userId      INT             NOT NULL,
    taskId      INT             NOT NULL,
    progress    INT             NOT NULL DEFAULT 0,
    startDate   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(20)     NOT NULL DEFAULT 'active'
                COMMENT 'Statut : active, completed, cancelled',

    PRIMARY KEY (userId, taskId),

    CONSTRAINT fk_selectedtask_user
        FOREIGN KEY (userId) REFERENCES User(userId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_selectedtask_task
        FOREIGN KEY (taskId) REFERENCES Task(taskId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT chk_selectedtask_status
        CHECK (status IN ('active', 'completed', 'cancelled'))
) ENGINE=InnoDB;

-- ============================================
-- Table : TaskRewards
-- Récompenses associées à chaque tâche (badges gagnés)
-- Supporte les récompenses aléatoires via dropRate
-- ============================================
-- FONCTIONNEMENT DU LOOT ALÉATOIRE :
--
-- Une tâche peut avoir PLUSIEURS lignes dans cette table.
-- Le champ dropRate définit la probabilité (en %) d'obtenir
-- chaque badge. Le backend tire au sort en pondérant par
-- les dropRate de chaque entrée.
--
-- Exemple pour la tâche "Speedrunner" :
--   taskId=2, badgeId=5  (Common),  dropRate=60.00  → 60% de chance
--   taskId=2, badgeId=8  (Rare),    dropRate=30.00  → 30% de chance
--   taskId=2, badgeId=12 (SSR),     dropRate=10.00  → 10% de chance
--
-- Pour une récompense GARANTIE (non aléatoire) :
--   taskId=1, badgeId=3,            dropRate=100.00 → toujours obtenu
-- ============================================
CREATE TABLE TaskRewards (
    rewardId        INT             AUTO_INCREMENT PRIMARY KEY,
    taskId          INT             NOT NULL,
    badgeId         INT             NOT NULL,
    numberOfBadges  INT             NOT NULL DEFAULT 1,
    dropRate        DECIMAL(5,2)    NOT NULL DEFAULT 100.00
                    COMMENT 'Probabilité de drop en % (100 = garanti, <100 = aléatoire)',

    CONSTRAINT fk_taskrewards_task
        FOREIGN KEY (taskId) REFERENCES Task(taskId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_taskrewards_badge
        FOREIGN KEY (badgeId) REFERENCES Badge(badgeId)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT chk_droprate_range
        CHECK (dropRate > 0 AND dropRate <= 100)
) ENGINE=InnoDB;

-- ============================================
-- Index pour optimiser les requêtes fréquentes
-- ============================================

-- Classement par score (leaderboard)
CREATE INDEX idx_user_score ON User(score DESC);

-- Recherche des tâches actives d'un utilisateur
CREATE INDEX idx_selectedtask_status ON SelectedTask(userId, status);

-- Badges d'un utilisateur
CREATE INDEX idx_badgepossessed_user ON BadgePossessed(userId);

-- Récompenses d'une tâche (utile pour le tirage aléatoire)
CREATE INDEX idx_taskrewards_task ON TaskRewards(taskId);

-- ============================================
-- Données initiales : Types de tâches (difficultés)
-- ============================================
INSERT INTO TaskType (name) VALUES
    ('Easy'),
    ('Medium'),
    ('Hard'),
    ('Infernal');

-- ============================================
-- Données initiales : Raretés de badges
-- ============================================
INSERT INTO Rarity (rarityName, pointsGiven) VALUES
    ('RR',     100),
    ('SR',     500),
    ('SSR',    2000),
    ('UR',     10000),
    ('SECRET', 50000);