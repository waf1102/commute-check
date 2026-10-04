import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import secrets
from dotenv import load_dotenv

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from jose import JWTError, jwt
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, UserCreate, UserOut

# Load environment variables
load_dotenv()

# Security constants
SECRET_KEY = os.getenv("SECRET_KEY", "")
if SECRET_KEY in {"", "your-secret-key", "replace-with-a-random-secret"}:
    SECRET_KEY = secrets.token_urlsafe(48)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/login", auto_error=False)

router = APIRouter(prefix="/api", tags=["authentication"])


def get_password_hash(password: str) -> str:
    # bcrypt works with bytes, so encode the password
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt works with bytes, so encode and decode as necessary
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    session: Session = Depends(get_session),
) -> Optional[User]:
    if token is None:
        return None
    return await get_current_user(token, session)


@router.get("/auth/me", response_model=UserOut)
@router.get("/me", response_model=UserOut)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/register")
def register_user(user_data: UserCreate, session: Session = Depends(get_session)):
    # Check if user with this email already exists
    existing_user = session.exec(
        select(User).where(func.lower(User.email) == user_data.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    hashed_password = get_password_hash(user_data.password)
    user = User(email=user_data.email, hashed_password=hashed_password)
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(400, "User with this email already exists") from exc
    session.refresh(user)
    return {
        "message": "User registered successfully",
        "user": UserOut.model_validate(user),
        "access_token": create_access_token({"sub": user.email}),
        "token_type": "bearer",
    }


@router.post("/login", response_model=dict)
async def login_for_access_token(
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        if "application/json" in request.headers.get("content-type", ""):
            data = await request.json()
        else:
            data = await request.form()
        username = data.get("username") or data.get("email")
        password = data.get("password")
    except (ValueError, AttributeError):
        raise HTTPException(400, "Email and password are required")
    if (
        not isinstance(username, str)
        or not isinstance(password, str)
        or not username
        or not password
    ):
        raise HTTPException(400, "Email and password are required")
    user = session.exec(
        select(User).where(func.lower(User.email) == username.strip().lower())
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }
