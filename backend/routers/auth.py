"""
LegalEye — Auth Router (Login / Register / JWT)
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    LoginRequest, TokenResponse, RegisterRequest,
    UserCreateRequest, UserUpdateRequest, RoleUpdateRequest, ActifUpdateRequest,
)
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, ALLOW_REGISTRATION

log = logging.getLogger("legaleye.auth")

router = APIRouter(prefix="/api/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)

# Rôles valides (colonne `user.role`, String).
#   admin       — contrôle total (utilisateurs, tiers, bulletins, alertes, exports)
#   responsable — Responsable opérationnel : bulletins (upload + retraiter/supprimer),
#                 alertes, exports. PAS de gestion utilisateurs ni tiers.
#   operateur   — upload de bulletins + traitement des alertes ; lecture seule du reste.
VALID_ROLES = ("admin", "responsable", "operateur")

# Rôle par défaut d'un nouveau compte (le moins privilégié).
DEFAULT_ROLE = "operateur"

# bcrypt tronque silencieusement au-delà de 72 octets : on refuse explicitement.
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_BYTES = 72


# ══════════════════════════════════════════════════════════════
#  HELPERS MOTS DE PASSE (bcrypt direct, sans passlib)
# ══════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def valider_password(password: str):
    if len(password) < PASSWORD_MIN_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Le mot de passe doit faire au moins {PASSWORD_MIN_LEN} caractères",
        )
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Le mot de passe ne peut pas dépasser {PASSWORD_MAX_BYTES} octets",
        )


# ══════════════════════════════════════════════════════════════
#  RATE LIMITING LOGIN (anti brute-force)
#  Fenêtre glissante en mémoire, par (IP, email). Par worker uvicorn :
#  avec N workers le plafond effectif est N × MAX_LOGIN_ATTEMPTS, ce qui
#  reste une protection suffisante contre le brute-force en ligne.
# ══════════════════════════════════════════════════════════════

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60

_login_failures: dict[str, list[float]] = defaultdict(list)
_login_lock = Lock()


def _rate_limit_key(request: Request, email: str) -> str:
    client_ip = request.client.host if request.client else "?"
    return f"{client_ip}|{email.lower()}"


def _check_rate_limit(key: str):
    now = time.monotonic()
    with _login_lock:
        attempts = _login_failures[key] = [
            t for t in _login_failures[key] if now - t < LOGIN_WINDOW_SECONDS
        ]
        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            log.warning("Rate limit login déclenché pour %s", key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de tentatives. Réessaie dans quelques minutes.",
            )


def _record_failure(key: str):
    with _login_lock:
        _login_failures[key].append(time.monotonic())


def _clear_failures(key: str):
    with _login_lock:
        _login_failures.pop(key, None)


# ══════════════════════════════════════════════════════════════
#  HELPERS JWT
# ══════════════════════════════════════════════════════════════

def create_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency FastAPI : vérifie le JWT et renvoie l'utilisateur connecté."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise jwt.InvalidTokenError("Token sans sub")
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if user is None or not user.actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou désactivé",
        )
    return user


def require_roles(*roles: str):
    """Fabrique une dependency qui n'autorise que les rôles listés."""
    autorises = set(roles)

    def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in autorises:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Droits insuffisants pour cette action",
            )
        return current_user

    return _guard


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency : restreint l'accès aux admins."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits administrateur requis",
        )
    return current_user


# Dépendances métier (composées sur require_roles) :
#   - bulletins upload/scan/sync  → tous les rôles connectés
#   - bulletins retraiter/supprimer → admin + responsable
#   - exports rapports             → admin + responsable
#   - alertes (traiter)            → tous les rôles connectés (= get_current_user)
require_bulletins_upload = require_roles("admin", "responsable", "operateur")
require_bulletins_full = require_roles("admin", "responsable")
require_export = require_roles("admin", "responsable")


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _rate_limit_key(request, data.email)
    _check_rate_limit(key)

    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.actif:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    _clear_failures(key)
    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        nom=user.nom,
        role=user.role,
    )


@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """
    Inscription publique : tout nouveau compte est créé en **operateur**
    (le rôle le moins privilégié). Désactivée par défaut en production
    (ALLOW_REGISTRATION=false) : les bulletins, alertes et tiers sont des
    données internes ; un admin promeut ensuite si besoin.
    """
    if not ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Inscription désactivée. Contacte un administrateur.",
        )

    valider_password(data.password)

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    # Sécurité : on ignore data.role et on force le rôle le moins privilégié.
    user = User(
        nom=data.nom,
        email=data.email,
        password_hash=hash_password(data.password),
        role=DEFAULT_ROLE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        nom=user.nom,
        role=user.role,
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    """Renvoie l'utilisateur connecté (utile pour le frontend)."""
    return {
        "id": current_user.id,
        "nom": current_user.nom,
        "email": current_user.email,
        "role": current_user.role,
    }


# ══════════════════════════════════════════════════════════════
#  ADMIN — Gestion des utilisateurs
# ══════════════════════════════════════════════════════════════

@router.get("/users")
def lister_utilisateurs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Liste tous les utilisateurs (admin only)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "nom": u.nom,
            "email": u.email,
            "role": u.role,
            "actif": u.actif,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.put("/users/{user_id}/role")
def changer_role(
    user_id: int,
    data: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Promeut/rétrograde un utilisateur. Rôles : admin | responsable | operateur."""
    if data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Role invalide (admin|responsable|operateur)",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # Garde-fou : on ne se rétrograde pas soi-même par accident.
    if user.id == current_user.id and data.role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Tu ne peux pas te retirer ton propre rôle admin",
        )

    user.role = data.role
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/users")
def creer_utilisateur(
    data: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Crée un utilisateur avec le rôle choisi (admin only)."""
    if data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Role invalide (admin|responsable|operateur)",
        )
    valider_password(data.password)
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    user = User(
        nom=data.nom,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "nom": user.nom, "email": user.email, "role": user.role, "actif": user.actif, "created_at": user.created_at}


@router.put("/users/{user_id}")
def modifier_utilisateur(
    user_id: int,
    data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Modifie nom/email/password (admin only). Champs dans le corps de requête."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if data.nom:
        user.nom = data.nom
    if data.email:
        existing = db.query(User).filter(User.email == data.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        user.email = data.email
    if data.password:
        valider_password(data.password)
        user.password_hash = hash_password(data.password)
    db.commit()
    return {"id": user.id, "nom": user.nom, "email": user.email, "role": user.role, "actif": user.actif, "created_at": user.created_at}


@router.delete("/users/{user_id}")
def supprimer_utilisateur(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Supprime un utilisateur (admin only). Impossible sur soi-même."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Tu ne peux pas supprimer ton propre compte")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur {user.email} supprimé"}


@router.put("/users/{user_id}/actif")
def activer_desactiver(
    user_id: int,
    data: ActifUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Active ou désactive un compte (admin only)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.id == current_user.id and not data.actif:
        raise HTTPException(status_code=400, detail="Tu ne peux pas te désactiver toi-même")
    user.actif = data.actif
    db.commit()
    return {"id": user.id, "email": user.email, "actif": user.actif}
