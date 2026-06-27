# RS256 Public Token Signing Design

## Goal

Passport Auth should issue public app access tokens that application backends can verify locally without sharing a signing secret. Passport Auth keeps the private signing key. Application backends receive only public verification material from the dashboard.

## Token Contract

Public access tokens will move from `HS256` to `RS256`.

Access token header:

- `alg`: `RS256`
- `typ`: `JWT`
- `kid`: stable key id derived from the active public key

Access token claims:

- `iss`: configured public token issuer
- `aud`: configured public token audience
- `sub`: Passport Auth user id
- `email`: user email
- `role`: user role
- `type`: `access`
- `iat`: issued-at Unix timestamp
- `exp`: expiry Unix timestamp

Refresh tokens remain opaque random tokens stored hashed by Passport Auth. They are not JWTs and are not exposed to application backends for local verification.

## Key Handling

Passport Auth signs access tokens with an RSA private key. The private key is loaded from configuration and never returned by an API.

Production must explicitly configure the private key. Development can fall back to a generated in-memory key so local flows keep working without setup.

The dashboard settings response exposes:

- public key PEM
- JWKS JSON for JWT libraries that prefer JWK sets
- signing algorithm
- key id
- issuer
- audience

No dashboard reset or rotation flow is included in this change.

## Dashboard

The dashboard Settings page gets a read-only Token verification section. It shows the public PEM, JWKS, issuer, audience, algorithm, and key id so backend developers can copy them into their verifier configuration.

The UI must not show or accept a private key.

## API Behavior

`POST /api/v1/auth/token` and `POST /api/v1/auth/refresh` will issue RS256 access tokens.

`GET /api/v1/auth/me` will verify RS256 access tokens using Passport Auth's active public key and will reject tokens with invalid signature, algorithm, type, issuer, audience, expiry, or missing subject/email claims.

Dashboard JWTs stay unchanged and continue to use the existing dashboard signing secret.

## Testing

Add focused tests for:

- issued public access tokens have `alg=RS256`, `kid`, `iss`, `aud`, `iat`, and user claims
- public tokens verify with the exported public key
- forged/tampered public tokens are rejected
- dashboard settings returns public verification material and never exposes a private key
- existing public login/token/me flow still works

