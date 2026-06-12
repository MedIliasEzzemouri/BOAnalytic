-- ══════════════════════════════════════════════════════════════
--  BO_WATCH — Base de Données MySQL
--  Système de Veille Juridique Automatisée
--  Auteur : Marouan (Plastima - DUT IDIA)
-- ══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS bo_watch
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE bo_watch;

-- ══════════════════════════════════════════════════════════════
--  1. USER — Utilisateurs du dashboard
-- ══════════════════════════════════════════════════════════════

CREATE TABLE user (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    role            ENUM('admin', 'viewer') NOT NULL DEFAULT 'viewer',
    actif           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- ══════════════════════════════════════════════════════════════
--  2. BULLETIN_OFFICIEL — Bulletins PDF uploadés ou scrapés
-- ══════════════════════════════════════════════════════════════

CREATE TABLE bulletin_officiel (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    numero                  VARCHAR(20) NOT NULL UNIQUE,
    date_publication        DATE NOT NULL,
    fichier_pdf             VARCHAR(500) NOT NULL,
    nb_pages                INT DEFAULT 0,
    nb_annonces_legales     INT DEFAULT 0,
    nb_annonces_judiciaires INT DEFAULT 0,
    source                  ENUM('scraping', 'manuel') NOT NULL DEFAULT 'manuel',
    statut                  ENUM('en_attente', 'en_cours', 'traite', 'erreur') NOT NULL DEFAULT 'en_attente',
    message_erreur          TEXT DEFAULT NULL,
    uploaded_by             INT DEFAULT NULL,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (uploaded_by) REFERENCES user(id) ON DELETE SET NULL,
    INDEX idx_numero (numero),
    INDEX idx_date (date_publication),
    INDEX idx_statut (statut)
) ENGINE=InnoDB;


-- ══════════════════════════════════════════════════════════════
--  3. ARTICLE_ENTREPRISE — Annonces Section I (légales)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE article_entreprise (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    bulletin_id         INT NOT NULL,
    nom_entreprise      VARCHAR(300) DEFAULT NULL,
    texte_annonce       TEXT NOT NULL,
    type_annonce        ENUM('creation', 'modification', 'cession', 'liquidation') DEFAULT NULL,
    score_classification FLOAT DEFAULT NULL,
    score_ner           FLOAT DEFAULT NULL,
    source_nom          ENUM('ner', 'sommaire', 'regex') DEFAULT NULL,
    page_bulletin       INT DEFAULT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bulletin_id) REFERENCES bulletin_officiel(id) ON DELETE CASCADE,
    INDEX idx_bulletin (bulletin_id),
    INDEX idx_type (type_annonce),
    INDEX idx_nom (nom_entreprise),
    FULLTEXT INDEX idx_texte (texte_annonce)
) ENGINE=InnoDB;


-- ══════════════════════════════════════════════════════════════
--  4. ARTICLE_MAHAKIM — Annonces Section II (judiciaires)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE article_mahakim (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    bulletin_id         INT NOT NULL,
    nom_entreprise      VARCHAR(300) DEFAULT NULL,
    texte_annonce       TEXT NOT NULL,
    type_procedure      VARCHAR(100) DEFAULT NULL,
    score_ner           FLOAT DEFAULT NULL,
    tribunal            VARCHAR(200) DEFAULT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bulletin_id) REFERENCES bulletin_officiel(id) ON DELETE CASCADE,
    INDEX idx_bulletin (bulletin_id),
    INDEX idx_nom (nom_entreprise),
    FULLTEXT INDEX idx_texte (texte_annonce)
) ENGINE=InnoDB;


-- ══════════════════════════════════════════════════════════════
--  5. TIER — Partenaires commerciaux de Plastima
-- ══════════════════════════════════════════════════════════════

CREATE TABLE tier (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nom             VARCHAR(300) NOT NULL,
    nom_normalise   VARCHAR(300) NOT NULL,
    type_tier       ENUM('client', 'fournisseur') NOT NULL,
    secteur         VARCHAR(100) DEFAULT NULL,
    ville           VARCHAR(100) DEFAULT NULL,
    rc_numero       VARCHAR(50) DEFAULT NULL,
    actif           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_nom (nom_normalise),
    INDEX idx_type (type_tier),
    INDEX idx_actif (actif)
) ENGINE=InnoDB;


-- ══════════════════════════════════════════════════════════════
--  6. ALERTE — Résultats du matching (pipeline complet)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE alerte (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    tier_id                 INT NOT NULL,
    article_entreprise_id   INT DEFAULT NULL,
    article_mahakim_id      INT DEFAULT NULL,
    nom_detecte             VARCHAR(300) NOT NULL,
    nom_tier                VARCHAR(300) NOT NULL,
    score_similarite        FLOAT NOT NULL,
    type_annonce            VARCHAR(50) DEFAULT NULL,
    statut                  ENUM('nouvelle', 'vue', 'traitee', 'ignoree') NOT NULL DEFAULT 'nouvelle',
    priorite                ENUM('haute', 'moyenne', 'basse') NOT NULL DEFAULT 'moyenne',
    commentaire             TEXT DEFAULT NULL,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    traitee_at              DATETIME DEFAULT NULL,
    traitee_par             INT DEFAULT NULL,

    FOREIGN KEY (tier_id) REFERENCES tier(id) ON DELETE CASCADE,
    FOREIGN KEY (article_entreprise_id) REFERENCES article_entreprise(id) ON DELETE CASCADE,
    FOREIGN KEY (article_mahakim_id) REFERENCES article_mahakim(id) ON DELETE CASCADE,
    FOREIGN KEY (traitee_par) REFERENCES user(id) ON DELETE SET NULL,
    INDEX idx_tier (tier_id),
    INDEX idx_statut (statut),
    INDEX idx_priorite (priorite),
    INDEX idx_score (score_similarite),
    INDEX idx_created (created_at)
) ENGINE=InnoDB;


-- ══════════════════════════════════════════════════════════════
--  COMPTE ADMIN INITIAL — à créer via Python, PAS via SQL
-- ══════════════════════════════════════════════════════════════
--
-- Le hash bcrypt ne peut PAS être généré ici. Crée le premier admin
-- en lançant ce one-liner Python depuis le dossier backend/ :
--
--   python -c "
-- from passlib.context import CryptContext;
-- from database import SessionLocal;
-- from models import User;
-- pwd = CryptContext(schemes=['bcrypt']);
-- db = SessionLocal();
-- db.add(User(nom='Admin', email='admin@plastima.ma',
--             password_hash=pwd.hash('change_me_now'),
--             role='admin', actif=True));
-- db.commit();
-- print('Admin créé')"
--
-- Pense à changer le mot de passe immédiatement après la première
-- connexion via PUT /api/auth/users/{id}/role n'est pas suffisant —
-- il faut un endpoint de changement de password (à ajouter).
-- ══════════════════════════════════════════════════════════════
