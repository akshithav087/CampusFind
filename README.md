# CampusFind

A lost and found portal for the GNITS campus community.

## Features

- Submit lost and found reports with an optional photo.
- Browse, search, and filter open reports.
- View each report on its own detail page.
- Message a reporter without showing their email address publicly.
- Let the reporter confirm an item was returned from a private email link.

## Requirements

- Python 3
- PostgreSQL
- Gmail SMTP credentials or another SMTP account

## Setup

1. Create a PostgreSQL database named `campus_lost_found`.
2. Create a root `.env` file with the following settings:

   ```text
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=campus_lost_found
   DB_USER=postgres
   DB_PASSWORD=YOUR_DATABASE_PASSWORD
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=YOUR_SENDER_GMAIL
   SMTP_PASSWORD=YOUR_GOOGLE_APP_PASSWORD
   SMTP_FROM=
   SMTP_USE_TLS=true
   FRONTEND_BASE_URL=http://127.0.0.1:5000
   ```

   `SMTP_FROM` can stay blank to use `SMTP_USERNAME`. For Gmail, use an App Password instead of the regular account password. Keep `.env` private.

3. Create or update the database tables from the project root:

   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d campus_lost_found -f ".\database\schema.sql"
   ```

   Adjust the `psql.exe` path if PostgreSQL is installed elsewhere.

4. Install the Python packages:

   ```powershell
   python -m pip install -r backend/requirements.txt
   ```

5. Start the web app:

   ```powershell
   python backend/app.py
   ```

6. Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Flask serves both the website and API. Local confirmation links work on the computer running Flask; set `FRONTEND_BASE_URL` to the public site address after deployment.

## Public deployment

The `render.yaml` Blueprint deploys the complete app from GitHub, including Flask, PostgreSQL, persistent photo storage, and Gmail SMTP settings. Connect the repository in Render, select **Blueprint**, and enter `SMTP_USERNAME` and `SMTP_PASSWORD` when prompted. Keep those secrets in Render, not in GitHub.

The Blueprint uses paid Render resources so photos and reports persist and email can be sent. At current minimum plans, expect roughly **$13/month** for the web service, database, and 1 GB photo disk, plus any usage above included limits. Check Render's current [pricing](https://render.com/pricing) before deploying.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check Flask and database connectivity |
| GET | `/api/items` | List open reports |
| GET | `/api/items?q=bottle` | Search reports |
| GET | `/api/items?status=lost` | Filter by lost or found |
| GET | `/api/items/<item_id>` | Get report details without reporter email |
| POST | `/api/items` | Create a report |
| POST | `/api/items/<item_id>/contact` | Email a message and return-confirmation link to the reporter |
| POST | `/api/items/<item_id>/confirm-return` | Confirm return using the emailed token |

## Notes

- Run `database/schema.sql` again against an existing database to add new report fields.
- Contact messages and confirmation emails require valid SMTP settings.
- The report API accepts optional `item_date` and `image_url` fields for compatible clients.
- Uploaded photos are stored in `backend/uploads/` and are excluded from version control.
