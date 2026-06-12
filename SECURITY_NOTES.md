# LegalEye — Notes de sécurité (remédiation 2026-06-12)

## Fait automatiquement

| Correctif | Détail |
|---|---|
| `SECRET_KEY` JWT rotée | Nouvelle clé dans `.env`. Toutes les sessions actives sont invalidées (re-login requis). |
| Mots de passe hors des URLs | Les endpoints admin `/api/auth/users/*` prennent désormais un corps JSON. Les anciens appels passaient le mot de passe en query string → visible dans les logs nginx. |
| Inscription publique désactivée | `ALLOW_REGISTRATION=false` dans `.env`. Les comptes se créent depuis la page Utilisateurs (admin). |
| Anti brute-force login | 5 échecs / 15 min par (IP, email) → HTTP 429. |
| Path traversal upload | Le numéro de bulletin n'accepte plus que des chiffres ; vérification des magic bytes `%PDF-` ; plafond 100 Mo. |
| Rôles alignés sur la BDD | Seuls `admin` et `viewer` existent (l'ENUM MySQL ne connaît pas `responsable`/`operateur` — leur attribution provoquait une erreur 500). |
| python-jose → PyJWT | python-jose est abandonné (CVE-2024-33663/33664). passlib retiré, bcrypt en direct. |
| Erreurs 500 non bavardes | `/api/exports/rapport-global` ne renvoie plus le détail des exceptions au client (loggé serveur uniquement). |

## À faire MANUELLEMENT (impossible à automatiser sans toucher la prod)

1. **Mots de passe MySQL** (`DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`) : ils ont fuité
   avec ce dépôt. `MYSQL_*` n'est lu par l'image MySQL qu'au PREMIER démarrage
   du volume — changer `.env` ne suffit pas. Sur le serveur :
   ```sql
   ALTER USER 'legaleye'@'%' IDENTIFIED BY '<nouveau_mot_de_passe>';
   ALTER USER 'root'@'localhost' IDENTIFIED BY '<nouveau_root>';
   FLUSH PRIVILEGES;
   ```
   Puis mettre les mêmes valeurs dans `.env` (`DB_PASSWORD` **et** `MYSQL_PASSWORD`)
   et redémarrer le backend.

2. **Comptes admin seedés** : `database/init/01_seed_initial.sql` contient les
   hashes bcrypt des comptes `admin@plastima.ma`, `rhazlani@plastima.ma` et
   `youness@plastima.ma`. Les hashes ont circulé avec le dépôt → faire changer
   les 3 mots de passe via la page Utilisateurs (ou regénérer le seed avec de
   nouveaux hashes avant toute nouvelle installation).

3. **HTTPS** : le stack expose le port 80 en clair. Mettre un reverse-proxy TLS
   (Caddy / Traefik / certbot+nginx) devant avant toute exposition hors LAN.

4. **Sauvegardes** : `scripts/backup_legaleye.ps1` existe — vérifier qu'il est
   planifié (Task Scheduler) et que la restauration a été testée une fois.
