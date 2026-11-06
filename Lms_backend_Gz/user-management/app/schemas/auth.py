from typing import Literal, Self

from pydantic import Field, StrictBool, ValidationInfo, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.permissions.roles import Role
from app.schemas.common import RequestSchema, ResponseSchema, SuccessResponse
from app.schemas.summaries import InstitutionRef
from app.schemas.types import (
    EmailAddress,
    FirstName,
    Identifier,
    LastName,
    OpaqueToken,
    Password,
    PublicIdOut,
    Timestamp,
)


def _passwords_match(value: str, info: ValidationInfo) -> str:
    new_password = info.data.get("new_password")
    if new_password is not None and value != new_password:
        raise PydanticCustomError("PASSWORD_MISMATCH", "Passwords do not match")
    return value


# ====================================================================== requests


class LoginRequest(RequestSchema):
    identifier: Identifier = Field(description="Email address or username")
    password: Password


class SignupRequestBody(RequestSchema):
    first_name: FirstName
    last_name: LastName
    email: EmailAddress
    password: Password


class SignupConfirmRequest(RequestSchema):
    email: EmailAddress
    code: str = Field(strict=True, pattern=r"^[0-9]{6,10}$", examples=["482913"])


class RefreshTokenRequest(RequestSchema):
    refresh_token: OpaqueToken | None = Field(
        default=None, description="Omit when the browser sends the refresh cookie (X-Session-Transport: cookie)"
    )


class LogoutRequest(RequestSchema):
    all_sessions: StrictBool = Field(default=False, description="Sign out of every device, not just this one")


class ForgotPasswordRequest(RequestSchema):
    identifier: Identifier = Field(description="Email address or username")


class VerifyOtpRequest(RequestSchema):
    identifier: Identifier = Field(description="The same email or username used for forgot-password")
    otp: str = Field(strict=True, pattern=r"^[0-9]{6,10}$", examples=["482913"])


class ResetPasswordRequest(RequestSchema):
    reset_token: OpaqueToken = Field(description="From verify-otp, or the token in the emailed link")
    new_password: Password
    confirm_password: Password

    _match = field_validator("confirm_password")(_passwords_match)


class ChangePasswordRequest(RequestSchema):
    current_password: Password
    new_password: Password
    confirm_password: Password

    _match = field_validator("confirm_password")(_passwords_match)


# ====================================================================== responses


class TokenOut(ResponseSchema):
    access_token: str
    refresh_token: str | None = Field(description="Null for browser sessions: it is set as an httpOnly cookie instead")
    token_type: str = "Bearer"
    expires_in: int = Field(description="Access token lifetime in seconds", examples=[900])
    refresh_expires_in: int = Field(description="Refresh token lifetime in seconds", examples=[604800])


class AuthUserOut(ResponseSchema):
    user_id: PublicIdOut
    full_name: str
    email: str | None
    username: str
    role: Role
    institution: InstitutionRef | None = Field(description="The user's organisation (institution or employer)")
    scopes: list[str] = Field(default_factory=list, description="Admin scopes; every scope for super admins")
    must_change_password: bool = Field(description="When true, call change-password before anything else")
    mfa_enabled: bool
    mfa_setup_required: bool = Field(description="When true, enrol in two-factor authentication before anything else")


class MfaChallengeOut(ResponseSchema):
    mfa_token: str = Field(description="Send to POST /auth/mfa/verify with the code from the authenticator app")
    expires_in: int = Field(examples=[300])
    methods: list[str] = Field(default_factory=lambda: ["totp", "recovery_code"])


class LoginResponse(SuccessResponse):
    code: Literal["SUCCESS", "MFA_REQUIRED"] = "SUCCESS"  # type: ignore[assignment]
    token: TokenOut | None = Field(description="Null when code is MFA_REQUIRED")
    user: AuthUserOut | None = Field(description="Null when code is MFA_REQUIRED")
    mfa_challenge: MfaChallengeOut | None = None


class MfaVerifyRequest(RequestSchema):
    mfa_token: OpaqueToken
    code: str | None = Field(default=None, strict=True, pattern=r"^[0-9]{6}$", examples=["492817"])
    recovery_code: str | None = Field(default=None, strict=True, min_length=10, max_length=20, examples=["k7m2p-9xq4r"])

    @model_validator(mode="after")
    def _one_method(self) -> Self:
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError("Send either code or recovery_code")
        return self


class PasswordConfirmRequest(RequestSchema):
    password: Password


class MfaCodeRequest(RequestSchema):
    code: str = Field(strict=True, pattern=r"^[0-9]{6}$", examples=["492817"])


class MfaPasswordAndCodeRequest(RequestSchema):
    password: Password
    code: str = Field(strict=True, pattern=r"^[0-9]{6}$", examples=["492817"])


class MfaStatusOut(ResponseSchema):
    enabled: bool
    required: bool = Field(description="Mandatory for this role")
    recovery_codes_remaining: int


class MfaSetupOut(ResponseSchema):
    secret: str = Field(description="Base32 secret for manual entry in the authenticator app")
    otpauth_uri: str = Field(description="Render as a QR code for the authenticator app")


class MfaStatusResponse(SuccessResponse):
    mfa: MfaStatusOut


class MfaSetupResponse(SuccessResponse):
    mfa_setup: MfaSetupOut


class RecoveryCodesResponse(SuccessResponse):
    recovery_codes: list[str] = Field(description="Shown once. Each code signs in once if the phone is lost.")


class PasswordResetTokenOut(ResponseSchema):
    reset_token: str
    expires_in: int = Field(examples=[900])


class VerifyOtpResponse(SuccessResponse):
    password_reset: PasswordResetTokenOut


class SessionOut(ResponseSchema):
    session_id: PublicIdOut
    is_current: bool
    ip_address: str | None
    user_agent: str | None
    created_time: Timestamp
    last_active_time: Timestamp
    expires_time: Timestamp


class SessionListResponse(SuccessResponse):
    sessions: list[SessionOut]


class SignupStartedOut(ResponseSchema):
    email: str
    expires_in: int = Field(description="Seconds until the emailed code expires")


class SignupStartedResponse(SuccessResponse):
    signup: SignupStartedOut
