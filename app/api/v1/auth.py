from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.schemas.auth import RegisterRequest, LoginRequest, Token
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    user_repo = UserRepository(db)
    return AuthService(user_repo)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    return auth_service.register_user(request)

@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    return auth_service.authenticate_user(request)
