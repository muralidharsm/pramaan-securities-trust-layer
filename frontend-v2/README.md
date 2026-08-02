# PRAMAAN Frontend (v2)

This directory contains the high-fidelity, demo-ready prototype frontend for the **PRAMAAN** dual-engine authenticity layer.

Built with:
- React + TypeScript
- Vite
- TailwindCSS v4
- shadcn/ui

## Running the Application

To run the full stack locally, you need two terminal windows: one for the FastAPI backend and one for this Vite frontend.

### 1. Start the Backend (Terminal 1)
Open a terminal in the root of the repository (`pramaan-securities-trust-layer/`):

```bash
cd backend
pip install -r requirements.txt
fastapi dev app/main.py --port 8000
```
This will start the PRAMAAN API engine at `http://localhost:8000`.

### 2. Start the Frontend (Terminal 2)
Open a second terminal in this directory (`frontend-v2/`):

```bash
npm install
npm run dev
```
The frontend will be available at `http://localhost:5173`. 
API calls to `/api/v1/*` are automatically proxied to the backend via Vite.

## Views Available

1. **Investor Verifier (`/verify`)**: WhatsApp-style interface testing claims and official circulars.
2. **Issuer Console (`/issuer`)**: Form to seal documents and commit them to the transparency log.
3. **SEBI Regulator Console (`/console`)**: Dashboard for log entries, Merkle proofs, and mock fraud patterns.
