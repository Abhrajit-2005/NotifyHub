from fastapi import HTTPException, status
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import RegisterRequest, LoginRequest, Token
from app.schemas.user import UserResponse

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def register_user(self, register_data: RegisterRequest) -> UserResponse:
        existing_user = self.user_repo.get_by_email(register_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        hashed_pwd = hash_password(register_data.password)
        user = self.user_repo.create(email=register_data.email, password_hash=hashed_pwd)
        return UserResponse.model_validate(user)

    def authenticate_user(self, login_data: LoginRequest) -> Token:
        user = self.user_repo.get_by_email(login_data.email)
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive"
            )

        access_token = create_access_token(subject=str(user.id))
        return Token(access_token=access_token, token_type="bearer")
