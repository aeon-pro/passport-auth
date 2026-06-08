# Passport Auth Local App

This is a tiny standalone client app for testing Passport Auth hosted pages and public APIs.

## Run

```bash
cd examples/local-app
node server.mjs
```

Open `http://localhost:5173`.

## Passport Auth Dashboard Settings

For this local app, save these values in Passport Auth:

- Application domain: `http://localhost:5173`
- Allowed origins: `http://localhost:5173`
- Redirect URLs: `http://localhost:5173/auth/callback`

Keep the auth domain pointed at your Passport Auth deployment, for example
`https://auth.alactic.net`. If you are running Passport Auth locally, use
`http://localhost:8000` as the Passport Auth URL inside this demo app.
