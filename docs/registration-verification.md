# Registration and live service verification

Registration is available from the sign-in screen. POST /api/register accepts email, display_name and a password of 10–4096 characters, creates a unique account, and returns the normal authenticated session (201). Duplicate normalized email returns409. Invalid input returns422; untrusted origins return403. Registration grants no project role. The empty-project screen displays the account ID for an administrator to assign membership.

This user-requested addition extends the previous frozen delivery's bootstrap-only account creation. Historical delivery specifications and their hashes remain unchanged.

Real Chromium against the persistent manual-demo API passed creation, reload persistence, case-insensitive duplicate rejection, sign-out/sign-in, no project membership, invalid input and origin rejection. Reproduce with:
```bash
cd /mnt/relex-kai
PLAYWRIGHT_BROWSERS_PATH=/mnt/relex-kai/.tools/browsers node scripts/product/verify-registration.mjs
```
Safe report: .runtime/registration-browser.json.

Persistent runtime:
- HTTP: 127.0.0.1:18080, PID141725.
- Worker: PID141726 (no listening port; polls durable jobs).
- PostgreSQL: 127.0.0.1:15432.
- Qdrant: 127.0.0.1:16333.
- Schema/collection: manual_demo; existing session configuration preserved.
- Private runtime config: .runtime/manual/service-env.json. Do not publish it.
- Logs: .runtime/manual/http.log and worker.log.
PIDs are observations, not permanent identifiers.

Full live browser run register_20260919 passed login/CSRF, malformed upload recovery and upload acceptance, then failed real ingestion at privacy_ready/provider_unavailable. Direct synthetic probes of both configured generation and embedding endpoints returned HTTP429, insufficient_quota/project_spend_limit_exceeded. This is an unresolved external provider billing/quota prerequisite. No fake service replaced it, and end-to-end AI verification is NOT marked passed.

After restoring quota for the configured provider project, retry failed jobs through the UI and rerun the real browser verification with a fresh run ID as documented in quickstart.md. The application health response only reports models configured_unverified; database/index readiness is not model success.
