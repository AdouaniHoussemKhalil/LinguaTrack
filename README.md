# LinguaTrack API

LinguaTrack est une application intelligente de correction de texte en français.

Elle permet :
- Correction des fautes d’orthographe
- Correction de conjugaison
- Amélioration du vocabulaire
- Analyse des erreurs fréquentes
- Génération d’exercices personnalisés

---

## 🚀 Stack Technique

- Backend : FastAPI
- Base de données : PostgreSQL
- ORM : SQLAlchemy
- Containerisation : Docker
- Documentation API : Swagger (automatique via FastAPI)

---

## 🏗️ Architecture
backend/
│
├── app/
│ ├── main.py
│ ├── core/
│ ├── models/
│ ├── schemas/
│ ├── routers/
│ ├── services/
│ └── utils/
│
├── Dockerfile
├── docker-compose.yml
└── requirements.txt

## ▶️ Installer
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv


## ▶️ Lancer le projet


### 1️⃣ Build & Run avec Docker

```bash
docker-compose up --build