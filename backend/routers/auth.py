"""
LegalEye — Auth Router (Login / Register / JWT)
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt, JWTError

from database import get_db
from models import User
from schemas import LoginRequest, TokenResponse, RegisterRequest
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


# ══════════════════════════════════════════════════════════════
#  HELPERS JWT
# ══════════════════════════════════════════════════════════════

def create_token(user_id: int, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
            raise JWTError("Token sans sub")
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).get(user_id)
    if user is None or not user.actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou désactivé",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency : restreint l'accès aux admins."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits administrateur requis",
        )
    return current_user


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.actif:
        raise HTTPException(status_code=403, detail="Compte désactivé")

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
    Inscription publique : tout nouveau compte est créé en **viewer**.
    Pour promouvoir un viewer en admin, voir PUT /api/auth/users/{id}/role
    (réservé aux admins).
    """
    if len(data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Le mot de passe doit faire au moins 8 caractères",
        )

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    # Sécurité : on ignore data.role et on force "viewer".
    user = User(
        nom=data.nom,
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        role="viewer",
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
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Promeut/rétrograde un utilisateur. Role valide : 'admin' ou 'viewer'."""
    if role not in ("admin", "viewer", "responsable", "operateur"):
        raise HTTPException(status_code=400, detail="Role invalide (admin|viewer|responsable|operateur)")

    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # Garde-fou : on ne se rétrograde pas soi-même par accident.
    if user.id == current_user.id and role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Tu ne peux pas te retirer ton propre rôle admin",
        )

    user.role = role
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/users")
def creer_utilisateur(
    data: RegisterRequest,
    role: str = "viewer",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Crée un utilisateur avec le rôle choisi (admin only)."""
    if role not in ("admin", "viewer", "responsable", "operateur"):
        raise HTTPException(status_code=400, detail="Role invalide")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (min 8 caractères)")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    user = User(
        nom=data.nom,
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "nom": user.nom, "email": user.email, "role": user.role, "actif": user.actif, "created_at": user.created_at}


@router.put("/users/{user_id}")
def modifier_utilisateur(
    user_id: int,
    nom: str | None = None,
    email: str | None = None,
    password: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Modifie nom/email/password (admin only)."""
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if nom:
        user.nom = nom
    if email:
        existing = db.query(User).filter(User.email == email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        user.email = email
    if password:
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Mot de passe trop court (min 8 caractères)")
        user.password_hash = pwd_context.hash(password)
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
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur {user.email} supprimé"}


@router.put("/users/{user_id}/actif")
def activer_desactiver(
    user_id: int,
    actif: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Active ou désactive un compte (admin only)."""
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.id == current_user.id and not actif:
        raise HTTPException(status_code=400, detail="Tu ne peux pas te désactiver toi-même")
    user.actif = actif
    db.commit()
    return {"id": user.id, "email": user.email, "actif": user.actif}
