## 1. Feature Overview

- Name: Authentication & Account Access
- Summary: Provides account signup, login/logout, JWT cookie session handling, password reset, email verification, and social login/linking.
- Target user: End users of the platform.
- Business value: Controls who can access product modules and enables secure account recovery and onboarding.

## 2. Problem Statement

- The feature solves identity, session, and account recovery.
- Without it, users cannot safely sign in, recover accounts, or use role-based modules.

## 3. Current Behavior

- Signup requires `username`, `password`, `email`, `name`, `last_name`; rejects duplicate username/email.
- Login validates credentials and sets secure cookies: access token, refresh token, and refresh expiry metadata.
- Logout clears auth cookies.
- Token verify/refresh uses cookies (not bearer header).
- Password reset flow: request token (rate-limited), validate token, confirm new password with Django password validation.
- Email verification flow: verify token and mark `EmailVerification.is_verified`; resend is rate-limited.
- Social auth supports Google, Discord, GitHub, Facebook, Microsoft when env credentials exist.
- Social flow supports `mode=login` and `mode=link`; prevents unlinking last available login method.

## 4. User Flows

### 4.1 Main Flow

1. User signs up.
2. System creates user, assigns groups (`user`, `blackdesert`, `financial` when existing), creates default budgets, creates email verification record.
3. User logs in with username/password.
4. System sets JWT cookies and user can access protected modules.

### 4.2 Alternative Flows

1. User clicks social authorize endpoint.
2. System creates OAuth state and returns provider authorize URL.
3. On callback, system links to existing account by provider or email, or creates a new account.

### 4.3 Error Scenarios

- Invalid credentials returns error.
- Expired/invalid reset or verification token returns error.
- Too many reset/verification attempts returns `429`.
- Social callback with invalid state/provider/code returns error or redirect with error payload.

## 5. Functional Requirements

- The system must authenticate users and issue refresh/access cookies.
- The system must support signout by clearing all auth cookies.
- The user can request password reset without revealing if email exists.
- The system must support email verification token workflow.
- The user can connect/disconnect social providers.
- The system should prevent account lockout by blocking unlink of the only login method.

## 6. Business Rules

- Password reset token expiry: 30 minutes.
- Email verification token expiry: 1440 minutes.
- Rate limit: 5 token requests/hour per IP and 3/hour per user.
- Token request invalidates previous unused token of same type.
- Social provider must be enabled by client ID + client secret in settings.
- Social link mode requires authenticated user.

## 7. Data Model (Business View)

- `User`: core account.
- `UserToken`: reset/verification token hash, expiry, usage, IP telemetry.
- `EmailVerification`: verified flag and timestamp per user.
- `SocialAuthState`: temporary OAuth state for login/link.
- `SocialAccount`: linked provider identity per user.

## 8. Interfaces

- APIs:
  - `/auth/token/`, `/auth/token/verify/`, `/auth/token/refresh/`
  - `/auth/signup`, `/auth/signout`, `/auth/csrf/`
  - `/auth/password-reset/request|validate|confirm/`
  - `/auth/email/verify/`, `/auth/email/resend-verification/`
  - `/auth/social/providers/`, `/auth/social/<provider>/authorize|callback/`
  - `/auth/social/accounts/`, `/auth/social/accounts/<provider>/unlink/`

## 9. Dependencies

- Depends on Django `User` and group membership.
- Uses mailer queue for reset/verification emails.
- Uses budget service to auto-create default budgets.
- Uses SimpleJWT for token handling.

## 10. Limitations / Gaps

- Login error currently returns `404` for invalid credentials (unusual semantic).
- Some serializers are validated without hard fail (`raise_exception=False`), so validation feedback can be inconsistent.
- Social profile email trust varies by provider semantics.

## 11. Opportunities

- Add explicit account lockout/step-up auth policy.
- Add UI-facing status for pending email verification.
- Add provider-specific consent scope management and audit detail.

## 12. Acceptance Criteria

- Given valid credentials, when user calls login, then auth cookies are issued and status is success.
- Given invalid reset token, when user confirms new password, then operation fails with token error.
- Given user already verified, when resend verification is requested, then response indicates already verified.
- Given a user has one social account and no password login, when unlink is requested, then unlink is denied.

## 13. Assumptions

- Frontend consumes cookies and CSRF as designed.
- Group names are provisioned in environment/one-off scripts.
- Email delivery is asynchronous through queue workers.
