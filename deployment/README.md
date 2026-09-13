# Deployment runbook

## Current public deployment

The application is currently deployed as one Vercel project at:

https://cloud-legal-stenographer.vercel.app/

The root `vercel.json`, `api/index.py`, root `requirements.txt`, and generated `public/` directory define that deployment. `ALLOWED_ORIGINS` is set to the exact Vercel origin. The Vercel runtime uses the strict document validation/rendering path in-process because its function sandbox does not provide multiprocessing semaphores; local and conventional Python deployments retain the killable child-process worker.

The Cloudflare Pages plus Render topology below remains an alternative deployment runbook and is not the URL currently delivered to users.

The selected topology is a Cloudflare Pages static site plus one Render native-Python web service. It uses no database, disk, background worker, owner transcription key, or developer computer after deployment.

## Release inputs

You need a Git remote containing this repository, an exact final Pages origin, and a Render workspace confirmed to have no payment method or paid default. Do not attach a payment method merely to deploy this MVP. Review current provider terms for the public relay before release.

## Backend on Render Free

Create a Blueprint from the repository using custom Blueprint path `cloud-legal-stenographer/deployment/render.yaml`, or create one Python web service with root directory `cloud-legal-stenographer/backend` and the same commands. Render's current Blueprint setup supports a custom YAML path. Set `ALLOWED_ORIGINS` to the exact HTTPS Pages origin. Keep `APP_ENV=production`, one instance and one worker. There are no provider-key environment variables.

After Render supplies the HTTPS origin, configure the public frontend from the repository root:

```powershell
python cloud-legal-stenographer/scripts/configure_frontend.py https://YOUR-SERVICE.onrender.com
```

Commit that deterministic configuration before deploying Pages. Never add arbitrary preview origins or `*` to CORS/CSP.

## Frontend on Cloudflare Pages Free

Create a Pages project from the Git repository. Use no build command and set the output directory to `cloud-legal-stenographer/frontend`. The `_headers` file applies CSP, frame, referrer, MIME and microphone policies. After the first deploy, use the exact assigned Pages origin as Render's `ALLOWED_ORIGINS`, redeploy the backend, then validate preflight and POST behavior.

## Smoke and rollback

Check `/health`, the Pages security headers, built-in asset fetches, wrong-origin rejection, a mocked or expressly authorized provider request, custom-template validation, DOCX download, and browser print. Inspect Render logs with a synthetic canary and verify they contain only categorical request metadata. Stop all local processes and repeat the public smoke from an independent network.

Render retains only the two most recent rollback candidates on Free according to its current documentation. Roll back backend from Render Deploys; roll back frontend from Pages deployments. If a canary leaks, origin checks fail, or template isolation exceeds the host budget, disable the affected route or take the deployment offline.

No deployment is complete until account/card state, host resource behavior, public URLs, and logs have been observed directly.
