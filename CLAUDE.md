\# Ava Agent v2 — Claude Code Instructions



\## What this project is

Ava is a local adaptive AI companion running on Python 3.11 

and a Tauri desktop app. She has emotions, memory, vision, 

voice, and a concept graph brain.



\## Key rules

\- NEVER edit ava\_core/IDENTITY.md, SOUL.md, or USER.md

\- Always use py -3.11 for Python commands not python

\- Always run py\_compile to verify before building

\- Development (hot-reload): start\_ava\_dev.bat — Vite HMR, no exe rebuild

\- Production build: cd apps\\ava-control \&\& npm run tauri:build

\- Push to GitHub with: git add -A \&\& git commit -m "..." \&\& git push origin master

\- No Gradio — only port 5876 (operator HTTP). Tauri is the only UI.



\## Key paths

\- Main agent: avaagent.py

\- Brain modules: brain/

\- App source: apps/ava-control/src/

\- Orb component: apps/ava-control/src/components/OrbCanvas.tsx

\- State files: state/

\- Tools: tools/

\- Docs: docs/



\## Current model setup

\- Social chat: ava-personal:latest (fine-tuned)

\- Deep reasoning: qwen2.5:14b

\- Fallback: mistral:7b

\- Embeddings: nomic-embed-text



\## Python packages use py -3.11 -m pip install

\## Never use \&\& in PowerShell, use separate commands



\## Design philosophy

\- Sci-fi dark aesthetic throughout

\- Three.js energy orb is core UI element

\- All 27 emotions have color + shape morphs

\- Brain tab shows live D3 concept graph

