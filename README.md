# KnowledgeVault

A personal knowledge management web application that lets users retrieve
their own notes, PDFs, and articles by meaning rather than by exact
keyword. Built as the MSCS 3999 capstone project at Clark University,
Fall 2026.

**Team:** Durvank Deorukhkar, Percival Tapera
**Jira project:** [Project_Link](https://clarkcapstone.atlassian.net/jira/software/projects/KV/boards/2?filter=&groupBy=none&atlOrigin=eyJpIjoiZTNiYTIwZjA5MzI3NDhjMzhhNDk0OTdhMmFmM2NiZWMiLCJwIjoiaiJ9)
**Docs:** see [`/docs`](./docs) for the Project Charter and Vision/Roadmap/Release Plan.

## Repository structure

| Path | Contents |
|---|---|
| `/backend` | FastAPI application: sample health check and placeholder upload endpoint. |
| `/frontend` | React application scaffold (created via Vite) with a placeholder landing page. |
| `/docs` | Project Charter, Vision/Roadmap/Release Plan, and future documentation. |
| `/.github/workflows` | Placeholder CI workflow, built out once test suites exist. |

## Getting started

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```
Runs at `http://localhost:8000` (interactive docs at `/docs`).

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173`.

## Status

This is the Sprint 1 scaffold submitted with Assignment 3
(Vision/Product Roadmap/Release Planning). Full ingestion, embedding,
search, and UI functionality is built incrementally starting in Sprint 1,
per the roadmap in the Vision doc.
