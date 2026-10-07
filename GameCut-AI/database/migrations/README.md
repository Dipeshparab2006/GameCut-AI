# Database migrations

Apply migrations once, in lexical order, to each environment after backing up
the database. `001_durable_job_orchestration.sql` upgrades the original queue
to include durable lease metadata and an append-only `ai_job_events` table.

For a fresh environment, import `database.sql`; it already contains the final
schema. Existing deployments should execute the migration with a DBA account:

```powershell
& C:\xampp\mysql\bin\mysql.exe -u <user> -p gamecut_ai < 001_durable_job_orchestration.sql
```

Never run a migration automatically from a web request. Review it in staging,
verify a database backup, and record the applied migration in deployment
automation.
