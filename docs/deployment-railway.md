# Railway deployment

The public portfolio deployment uses four Railway services in one project:

1. `app`, built from this repository with `/.railway/app.toml`
2. `worker`, built from the same repository with `/.railway/worker.toml`
3. Railway PostgreSQL
4. Railway Redis

Only the `app` service needs a public domain. PostgreSQL, Redis, and the worker remain private.

## Create the project

1. Create an empty Railway project.
2. Add PostgreSQL from the database templates and keep the service name `Postgres`.
3. Add Redis from the database templates and keep the service name `Redis`.
4. Add the GitHub repository as a service and name it `app`.
5. Set its custom config file to `/.railway/app.toml`.
6. Generate a public Railway domain for `app`.
7. Add the same GitHub repository again as a second service and name it `worker`.
8. Set its custom config file to `/.railway/worker.toml` and do not generate a public domain.

Railway builds both source services from the root Dockerfile. The app configuration provides the health check. The worker configuration replaces the Docker start command with the RQ worker command.

## Shared variables

Set these variables on both `app` and `worker`:

```env
APP_ENV=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
SESSION_SECRET=generate-a-unique-random-value
ENCRYPTION_KEY=generate-a-fernet-key
DEMO_MODE=true
SHOWCASE_MODE=true
DEMO_ADMIN_EMAIL=demo@evalforge.dev
DEMO_ADMIN_PASSWORD=paste-a-generated-random-password
DEFAULT_LANGUAGE=en
DEFAULT_CURRENCY=PLN
```

Generate the three secrets locally and paste the results into Railway sealed variables:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
python -c 'import secrets; print(secrets.token_urlsafe(24))'
```

Never copy values from the local `.env` file into source control. The PostgreSQL URL supplied by Railway is normalized to the installed Psycopg driver by application configuration.

## Public showcase behavior

`SHOWCASE_MODE=true` makes the deployment read only. It disables registration, credentials, model synchronization, content changes, experiment execution, reviews, report generation, and deletion. The seeded demonstration account and results remain available for portfolio visitors.

Local development keeps `SHOWCASE_MODE=false`, so all product functions remain enabled.

## Verify the deployment

1. Confirm that the `app` deployment reports a healthy `/health` endpoint.
2. Confirm that the `worker` deployment is listening on the `experiments` queue.
3. Sign in with the demonstration account.
4. Verify that the showcase banner is visible.
5. Open the dashboard, prompts, datasets, experiments, providers, models, and reports.
6. Confirm that registration and mutation controls are absent.

The worker is intentionally deployed even though public showcase actions are read only. This demonstrates the production architecture and allows the same project configuration to be reused later with `SHOWCASE_MODE=false`.
