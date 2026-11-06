from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response, status

from app.api import session_cookie
from app.api.deps import (
    AuthServiceDep,
    CurrentAuthAllowingPasswordChange,
    MfaServiceDep,
    SessionIdParam,
    SettingsDep,
    SignupServiceDep,
    rate_limit,
)
from app.api.responses import errors
from app.core.exceptions import AuthenticationError
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MfaChallengeOut,
    MfaCodeRequest,
    MfaPasswordAndCodeRequest,
    MfaSetupOut,
    MfaSetupResponse,
    MfaStatusOut,
    MfaStatusResponse,
    MfaVerifyRequest,
    PasswordConfirmRequest,
    RecoveryCodesResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SessionListResponse,
    SessionOut,
    SignupConfirmRequest,
    SignupRequestBody,
    SignupStartedOut,
    SignupStartedResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in",
    description="Log in with email **or** username. Returns tokens and the signed-in user. "
    "If two-factor authentication is on, returns `code: MFA_REQUIRED` with an `mfa_challenge` instead: "
    "call `POST /auth/mfa/verify`. If `user.must_change_password` or `user.mfa_setup_required` is true, "
    "finish that step before using other endpoints.",
    dependencies=[Depends(rate_limit("login", "LOGIN_RATE_LIMIT_PER_MINUTE", 60))],
    responses=errors(401, 403, 422, 429),
)
async def login(
    body: LoginRequest, service: AuthServiceDep, request: Request, response: Response, settings: SettingsDep
) -> LoginResponse:
    outcome = await service.login(body.identifier, body.password)
    if isinstance(outcome, MfaChallengeOut):
        return LoginResponse(
            code="MFA_REQUIRED",
            message="Enter the 6-digit code from your authenticator app.",
            token=None,
            user=None,
            mfa_challenge=outcome,
        )
    token = session_cookie.deliver(request, response, outcome.token, settings)
    return LoginResponse(message="Logged in successfully.", token=token, user=outcome.user)


@router.post(
    "/register",
    response_model=SignupStartedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sign up as an individual learner",
    description="Emails a code to confirm the address; the account is created by `POST /auth/register/verify`. "
    "Calling it again sends a new code (the old one stops working).",
    dependencies=[Depends(rate_limit("signup", "SIGNUP_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(403, 409, 422, 429),
)
async def register(body: SignupRequestBody, service: SignupServiceDep) -> SignupStartedResponse:
    expires_in = await service.start(
        first_name=body.first_name, last_name=body.last_name, email=body.email, password=body.password
    )
    return SignupStartedResponse(
        message="We sent a code to your email.",
        signup=SignupStartedOut(email=body.email.lower(), expires_in=expires_in),
    )


@router.post(
    "/register/verify",
    response_model=LoginResponse,
    summary="Confirm the emailed code: creates the account and signs in",
    dependencies=[Depends(rate_limit("signup_verify", "OTP_VERIFY_RATE_LIMIT_PER_MINUTE", 60))],
    responses=errors(400, 409, 422, 429),
)
async def register_verify(
    body: SignupConfirmRequest, service: SignupServiceDep, request: Request, response: Response, settings: SettingsDep
) -> LoginResponse:
    issued = await service.confirm(email=body.email, code=body.code)
    token = session_cookie.deliver(request, response, issued.token, settings)
    return LoginResponse(message="Welcome! Your account is ready.", token=token, user=issued.user)


@router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="Log out",
    description='Ends the current session. Send `{"all_sessions": true}` to log out of every device.',
    responses=errors(401, 422),
)
async def logout(
    auth: CurrentAuthAllowingPasswordChange,
    service: AuthServiceDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    body: Annotated[LogoutRequest | None, Body()] = None,
) -> SuccessResponse:
    all_sessions = bool(body and body.all_sessions)
    await service.logout(auth.user, auth.session, all_sessions=all_sessions)
    session_cookie.clear(request, response, settings)
    return SuccessResponse(message="Logged out of all devices." if all_sessions else "Logged out successfully.")


@router.post(
    "/refresh-token",
    response_model=LoginResponse,
    summary="Refresh tokens",
    description="Exchange a refresh token for a new access token **and** a new refresh token. "
    "Each refresh token works once; reusing an old one ends the session. Browsers send no body and the header "
    "`X-Session-Transport: cookie`; the refresh token then travels only in an httpOnly cookie.",
    dependencies=[Depends(rate_limit("refresh-token", "REFRESH_RATE_LIMIT_PER_MINUTE", 60))],
    responses=errors(401, 403, 422, 429),
)
async def refresh_token(
    service: AuthServiceDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    body: Annotated[RefreshTokenRequest | None, Body()] = None,
) -> LoginResponse:
    raw = (body.refresh_token if body else None) or session_cookie.read(request, settings)
    if not raw:
        raise AuthenticationError("Your session has expired. Please log in again.", code="INVALID_REFRESH_TOKEN")
    issued = await service.refresh(raw)
    token = session_cookie.deliver(request, response, issued.token, settings)
    return LoginResponse(message="Tokens refreshed successfully.", token=token, user=issued.user)


@router.post(
    "/forgot-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset",
    description="Emails a one-time code and a reset link. The response is always the same, "
    "whether or not the account exists.",
    dependencies=[Depends(rate_limit("forgot-password", "FORGOT_PASSWORD_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(422, 429),
)
async def forgot_password(body: ForgotPasswordRequest, service: AuthServiceDep) -> SuccessResponse:
    await service.forgot_password(body.identifier)
    return SuccessResponse(message="If an account exists for these details, a reset code has been sent to its email.")


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    summary="Verify the reset code",
    description="Exchanges the emailed code for a short-lived `reset_token`.",
    dependencies=[Depends(rate_limit("verify-otp", "OTP_VERIFY_RATE_LIMIT_PER_MINUTE", 60))],
    responses=errors(400, 422, 429),
)
async def verify_otp(body: VerifyOtpRequest, service: AuthServiceDep) -> VerifyOtpResponse:
    reset = await service.verify_otp(body.identifier, body.otp)
    return VerifyOtpResponse(message="Code verified. You can now set a new password.", password_reset=reset)


@router.post(
    "/reset-password",
    response_model=SuccessResponse,
    summary="Set a new password",
    description="Use the `reset_token` from verify-otp, or the `token` from an emailed reset or account set-up link. "
    "All existing sessions are ended.",
    dependencies=[Depends(rate_limit("reset-password", "RESET_PASSWORD_RATE_LIMIT_PER_MINUTE", 60))],
    responses=errors(400, 422, 429),
)
async def reset_password(body: ResetPasswordRequest, service: AuthServiceDep) -> SuccessResponse:
    await service.reset_password(body.reset_token, body.new_password)
    return SuccessResponse(message="Password updated. Please log in with your new password.")


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    summary="Change your password",
    description="Requires the current password. Ends all sessions, including this one.",
    responses=errors(400, 401, 422),
)
async def change_password(
    body: ChangePasswordRequest,
    auth: CurrentAuthAllowingPasswordChange,
    service: AuthServiceDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
) -> SuccessResponse:
    await service.change_password(auth.user, body.current_password, body.new_password)
    session_cookie.clear(request, response, settings)
    return SuccessResponse(message="Password changed. Please log in again.")


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List your active sessions",
    description="Devices where you are currently logged in, most recently active first.",
    responses=errors(401),
)
async def list_sessions(auth: CurrentAuthAllowingPasswordChange, service: AuthServiceDep) -> SessionListResponse:
    sessions = await service.list_sessions(auth.user)
    return SessionListResponse(
        message="Sessions retrieved successfully.",
        sessions=[
            SessionOut(
                session_id=s.public_id,
                is_current=s.id == auth.session.id,
                ip_address=s.ip_address,
                user_agent=s.user_agent,
                created_time=s.created_at,
                last_active_time=s.last_used_at,
                expires_time=s.expires_at,
            )
            for s in sessions
        ],
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=SuccessResponse,
    summary="Log out a device",
    responses=errors(401, 404),
)
async def end_session(
    session_id: SessionIdParam, auth: CurrentAuthAllowingPasswordChange, service: AuthServiceDep
) -> SuccessResponse:
    await service.end_session(auth.user, session_id)
    return SuccessResponse(message="The device has been logged out.")


# ====================================================================== two-factor authentication


@router.post(
    "/mfa/verify",
    response_model=LoginResponse,
    summary="Complete login with a two-factor code",
    description="Send the `mfa_token` from login with either the current 6-digit `code` or one unused `recovery_code`.",
    dependencies=[Depends(rate_limit("mfa-verify", "MFA_VERIFY_RATE_LIMIT_PER_MINUTE", 60))],
    responses=errors(401, 403, 422, 429),
)
async def verify_mfa(
    body: MfaVerifyRequest, service: AuthServiceDep, request: Request, response: Response, settings: SettingsDep
) -> LoginResponse:
    issued = await service.verify_mfa(body.mfa_token, body.code, body.recovery_code)
    token = session_cookie.deliver(request, response, issued.token, settings)
    return LoginResponse(message="Logged in successfully.", token=token, user=issued.user)


@router.get("/mfa", response_model=MfaStatusResponse, summary="Two-factor status", responses=errors(401))
async def mfa_status(auth: CurrentAuthAllowingPasswordChange, mfa: MfaServiceDep) -> MfaStatusResponse:
    return MfaStatusResponse(
        message="Two-factor status retrieved successfully.",
        mfa=MfaStatusOut(
            enabled=auth.mfa_enabled,
            required=mfa.is_required(auth.user),
            recovery_codes_remaining=await mfa.remaining_recovery_codes(auth.user) if auth.mfa_enabled else 0,
        ),
    )


@router.post(
    "/mfa/setup",
    response_model=MfaSetupResponse,
    summary="Start two-factor set-up",
    description="Confirms the password and returns a secret and `otpauth://` URI to show as a QR code. "
    "Nothing changes until `POST /auth/mfa/enable` succeeds.",
    responses=errors(400, 401, 409, 422),
)
async def mfa_setup(
    body: PasswordConfirmRequest, auth: CurrentAuthAllowingPasswordChange, mfa: MfaServiceDep
) -> MfaSetupResponse:
    secret, uri = await mfa.start_setup(auth.user, body.password)
    return MfaSetupResponse(
        message="Scan the QR code with your authenticator app, then confirm with a code.",
        mfa_setup=MfaSetupOut(secret=secret, otpauth_uri=uri),
    )


@router.post(
    "/mfa/enable",
    response_model=RecoveryCodesResponse,
    summary="Turn on two-factor authentication",
    description="Confirms set-up with the first code and returns recovery codes. They are shown only once.",
    responses=errors(400, 401, 422),
)
async def mfa_enable(
    body: MfaCodeRequest, auth: CurrentAuthAllowingPasswordChange, mfa: MfaServiceDep
) -> RecoveryCodesResponse:
    codes = await mfa.enable(auth.user, body.code)
    return RecoveryCodesResponse(
        message="Two-factor authentication is on. Store these recovery codes somewhere safe.", recovery_codes=codes
    )


@router.post(
    "/mfa/disable",
    response_model=SuccessResponse,
    summary="Turn off two-factor authentication",
    description="Not allowed for roles where two-factor authentication is mandatory (`MFA_REQUIRED_FOR_ROLE`).",
    responses=errors(400, 401, 403, 422),
)
async def mfa_disable(
    body: MfaPasswordAndCodeRequest, auth: CurrentAuthAllowingPasswordChange, mfa: MfaServiceDep
) -> SuccessResponse:
    await mfa.disable(auth.user, body.password, body.code)
    return SuccessResponse(message="Two-factor authentication is off.")


@router.post(
    "/mfa/recovery-codes",
    response_model=RecoveryCodesResponse,
    summary="Replace recovery codes",
    description="Invalidates all previous recovery codes.",
    responses=errors(400, 401, 422),
)
async def mfa_recovery_codes(
    body: MfaPasswordAndCodeRequest, auth: CurrentAuthAllowingPasswordChange, mfa: MfaServiceDep
) -> RecoveryCodesResponse:
    codes = await mfa.regenerate_recovery_codes(auth.user, body.password, body.code)
    return RecoveryCodesResponse(
        message="New recovery codes created. Previous codes no longer work.", recovery_codes=codes
    )


_unused = (MfaSetupOut, MfaStatusOut)
