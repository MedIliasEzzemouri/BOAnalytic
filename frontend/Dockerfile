# ====================================================================
#  Frontend React + Vite - Image Docker multi-stage
#  Stage 1 : build du bundle (node)
#  Stage 2 : service du bundle via nginx
# ====================================================================

# ── Stage 1 : build ──
FROM node:20-alpine AS builder

WORKDIR /app

# Cache des dependances : on copie d'abord les manifestes
COPY frontend/package.json ./
RUN npm install --legacy-peer-deps

# Puis le code et le build
COPY frontend/ ./

# IMPORTANT : VITE_API_URL=/ force axios a utiliser des URLs relatives.
# Sans cette ligne, le code fallback sur "http://localhost:8000" qui n'est
# PAS expose par Docker en production. Avec VITE_API_URL=/, les appels API
# vont sur /api/... (meme domaine) et nginx les proxie vers backend:8000.
ENV VITE_API_URL=/
RUN npm run build


# ── Stage 2 : nginx ──
FROM nginx:1.27-alpine

# Configuration nginx custom (reverse-proxy vers le backend + SPA fallback)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Bundle compile
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
