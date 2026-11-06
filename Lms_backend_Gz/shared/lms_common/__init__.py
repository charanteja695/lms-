"""lms_common: code every LMS microservice reuses.

Deliberately small and stable. It holds conventions that are already fixed across the platform
(see ../README.md and lms-backend/README.md), not speculative abstractions:

    lms_common.ids        public 64-bit id generation/parsing
    lms_common.envelopes   {status, code, message, ...} response shapes, PageContext
    lms_common.pagination  keyset-friendly offset pagination with a bounded, safe count
    lms_common.auth        verify (never issue) access tokens against user-management's JWKS
    lms_common.access_state  read the Redis keys user-management publishes on suspend/delete/sign-out
    lms_common.events      transactional-outbox event envelope + an idempotent stream consumer

No service-specific schemas, models or business rules belong here.
"""
