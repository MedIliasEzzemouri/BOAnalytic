# LegalEye — Frontend

Interface de veille juridique pour Plastima Casablanca. Design issu du **MCP Stitch**
(thème « Heritage »), converti en application **Vite + React + TypeScript + Tailwind CSS**.

## Démarrage

```bash
npm install
npm run dev      # http://localhost:5173
```

L'API backend FastAPI doit tourner sur `http://localhost:8000` (configurable via
`VITE_API_URL` dans `.env`).

## Scripts

| Commande         | Rôle                                  |
| ---------------- | ------------------------------------- |
| `npm run dev`    | Serveur de développement (port 5173)  |
| `npm run build`  | Build de production (`dist/`)         |
| `npm run lint`   | Vérification TypeScript               |

## Structure

```
src/
  api/client.ts        Client axios + endpoints (JWT Bearer auto, 401 → /login)
  auth/AuthContext.tsx Session JWT, rôles admin/viewer
  components/          Layout (sidebar/topbar), Icon, badges, UI partagés
  pages/               Login, Register, Dashboard, Alertes, AlerteDetail,
                       Bulletins, Tiers, Utilisateurs, NotFound
  lib/format.ts        Helpers de formatage (dates, scores)
  types.ts             Types alignés sur les schémas Pydantic du backend
```

## Écrans

- **Login / Register** — authentification ; tout nouveau compte est `viewer`.
- **Dashboard** — KPI, répartition des alertes, top tiers, dernières alertes.
- **Alertes** — liste filtrable (statut, priorité, recherche) + détail avec
  capture annotée, comparaison BO/partenaire et décision administrative.
- **Bulletins** — liste, filtres, import PDF (admin), retraitement, suppression.
- **Tiers** — registre des partenaires, CRUD (admin).
- **Utilisateurs** — gestion des rôles et activation (admin uniquement).

> Les HTML sources générés par Stitch sont conservés dans `.stitch-src/` (ignoré par git).
