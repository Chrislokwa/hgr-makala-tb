-- =========================================================
-- 1. CREATION DE LA BASE DE DONNEES
-- =========================================================

CREATE DATABASE suivi_medical;

-- Après création, se connecter à la base "suivi_medical"
-- puis exécuter la suite du script.


-- =========================================================
-- 2. TABLE PERSONNEL
-- =========================================================

CREATE TABLE personnel (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    postnom VARCHAR(100),
    prenom VARCHAR(100),
    email VARCHAR(150),
    num_telephone VARCHAR(30),
    role VARCHAR(50),
    est_actif BOOLEAN DEFAULT TRUE
);


-- =========================================================
-- 3. SPECIALISATIONS DU PERSONNEL
-- =========================================================

CREATE TABLE administrateur (
    id INTEGER PRIMARY KEY,
    FOREIGN KEY (id) REFERENCES personnel(id) ON DELETE CASCADE
);

CREATE TABLE agent_statistique (
    id INTEGER PRIMARY KEY,
    FOREIGN KEY (id) REFERENCES personnel(id) ON DELETE CASCADE
);

CREATE TABLE medecin (
    id INTEGER PRIMARY KEY,
    FOREIGN KEY (id) REFERENCES personnel(id) ON DELETE CASCADE
);

CREATE TABLE laborantin (
    id INTEGER PRIMARY KEY,
    FOREIGN KEY (id) REFERENCES personnel(id) ON DELETE CASCADE
);

CREATE TABLE infirmier (
    id INTEGER PRIMARY KEY,
    FOREIGN KEY (id) REFERENCES personnel(id) ON DELETE CASCADE
);


-- =========================================================
-- 4. PATIENT
-- =========================================================

CREATE TABLE patient (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    postnom VARCHAR(100),
    prenom VARCHAR(100),
    sexe VARCHAR(1),
    date_naissance DATE,
    num_telephone VARCHAR(30),
    adresse VARCHAR(255),
    situation VARCHAR(255)
);


-- =========================================================
-- 5. DOSSIER MEDICAL
-- =========================================================

CREATE TABLE dossier_medical (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    ndp VARCHAR(50),
    date_ouverture DATE,
    date_cloture DATE,
    statut VARCHAR(50),
    diagnostic VARCHAR(255),
    type_patient VARCHAR(100),
    site_maladie VARCHAR(255),
    resultat_final VARCHAR(255),

    FOREIGN KEY (patient_id)
        REFERENCES patient(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 6. CONSULTATION
-- =========================================================

CREATE TABLE consultation (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    medecin_id INTEGER NOT NULL,
    dossier_medical_id INTEGER NOT NULL,

    date DATE,
    symptomes TEXT[],
    poids NUMERIC(6,2),
    temperature NUMERIC(5,2),
    symptomes_associes TEXT[],
    comorbidites TEXT[],
    observations TEXT,
    type VARCHAR(100),

    FOREIGN KEY (patient_id)
        REFERENCES patient(id)
        ON DELETE CASCADE,

    FOREIGN KEY (medecin_id)
        REFERENCES medecin(id)
        ON DELETE CASCADE,

    FOREIGN KEY (dossier_medical_id)
        REFERENCES dossier_medical(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 7. SCHEMA THERAPEUTIQUE
-- =========================================================

CREATE TABLE schema_therapeutique (
    id SERIAL PRIMARY KEY,
    medicaments TEXT,
    posologie INTEGER,
    dosage VARCHAR(100)
);


-- =========================================================
-- 8. TRAITEMENT
-- =========================================================

CREATE TABLE traitement (
    id SERIAL PRIMARY KEY,
    dossier_medical_id INTEGER NOT NULL,
    schema_therapeutique_id INTEGER NOT NULL,

    date_debut DATE,
    date_fin_prevue DATE,
    date_fin_effective DATE,
    statut VARCHAR(50),
    resultat_final VARCHAR(255),

    FOREIGN KEY (dossier_medical_id)
        REFERENCES dossier_medical(id)
        ON DELETE CASCADE,

    FOREIGN KEY (schema_therapeutique_id)
        REFERENCES schema_therapeutique(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 9. EXAMEN
-- =========================================================

CREATE TABLE examen (
    id SERIAL PRIMARY KEY,

    medecin_id INTEGER NOT NULL,
    laborantin_id INTEGER NOT NULL,
    traitement_id INTEGER NOT NULL,

    date_prescription TIMESTAMP,
    date_reception DATE,
    type_examen VARCHAR(100),
    motif VARCHAR(255),
    nature_echantillon VARCHAR(255),
    statut VARCHAR(50),
    commentaires TEXT,
    resultat TEXT,
    observations TEXT,

    FOREIGN KEY (medecin_id)
        REFERENCES medecin(id)
        ON DELETE CASCADE,

    FOREIGN KEY (laborantin_id)
        REFERENCES laborantin(id)
        ON DELETE CASCADE,

    FOREIGN KEY (traitement_id)
        REFERENCES traitement(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 10. VISITE DE CONTROLE
-- =========================================================

CREATE TABLE visite_controle (
    id SERIAL PRIMARY KEY,

    infirmier_id INTEGER NOT NULL,
    traitement_id INTEGER NOT NULL,

    date TIMESTAMP,
    statut VARCHAR(50),
    poids NUMERIC(6,2),
    temperature NUMERIC(5,2),
    effets_secondaires TEXT,
    observance TEXT,
    observations TEXT,

    FOREIGN KEY (infirmier_id)
        REFERENCES infirmier(id)
        ON DELETE CASCADE,

    FOREIGN KEY (traitement_id)
        REFERENCES traitement(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 11. RENDEZ-VOUS
-- =========================================================

CREATE TABLE rdv (
    id SERIAL PRIMARY KEY,

    infirmier_id INTEGER NOT NULL,
    visite_controle_id INTEGER NOT NULL,

    date TIMESTAMP,
    type VARCHAR(100),
    statut VARCHAR(50),

    FOREIGN KEY (infirmier_id)
        REFERENCES infirmier(id)
        ON DELETE CASCADE,

    FOREIGN KEY (visite_controle_id)
        REFERENCES visite_controle(id)
        ON DELETE CASCADE
);