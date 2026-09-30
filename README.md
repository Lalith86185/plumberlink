# PlumberLink 🔧 — Local Home-Service Marketplace (MVP)

Find trusted plumbers in Bengaluru. Customers search by locality, call or book,
track the booking, and leave a review. Providers get a dashboard; the admin gets
approvals, QR codes, revenue and stats.

**Stack:** Python · Django 6 · SQLite (pilot) / PostgreSQL (production) ·
plain HTML/CSS/JS, mobile-first. No build step, no JS framework — easy to maintain.

## Quick start (local)

```bash
cd plumberlink
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_demo        # clearly-marked demo data
./venv/bin/python manage.py createsuperuser  # your admin login
./venv/bin/python manage.py runserver
```

Open http://localhost:8000

| Who | URL | Login |
|---|---|---|
| Customer site | `/` | none needed — bookings work with name + phone |
| Provider register / login | `/provider/register/` · `/provider/login/` | demo: `demo_plumber1` / `demo1234` |
| Admin panel | `/admin-panel/` | your superuser |
| Full Django admin | `/django-admin/` | your superuser |

Remove demo data any time: `python manage.py purge_demo`

## Project layout

```
plumberlink/          Django project (settings, urls, wsgi)
core/                 The whole app: models, views, forms, admin, templates, static
  templates/core/     Customer pages, provider dashboard, admin panel
  static/core/css/    One mobile-first stylesheet
  management/commands/ seed_demo · purge_demo · regen_qr
media/                Uploaded profile photos + generated QR PNGs
render.yaml           One-click deploy to Render.com (web + free Postgres)
Dockerfile            Alternative container deploy
start_render.sh       Production start: migrate → regen QR → gunicorn
run_pilot.sh          Run on this machine (dev/pilot helper)
```

## Database structure

SQLite file `db.sqlite3` for the pilot; set `DATABASE_URL=postgres://…` to use
PostgreSQL in production (needs `psycopg[binary]`, already in requirements).

| Table | Purpose | Key fields |
|---|---|---|
| `auth_user` | Login accounts (providers + admins) | username, password (hashed) |
| `core_locality` | Service areas | name, slug, city, active |
| `core_servicecategory` | Trade: Plumber (live); Electrician… (coming soon) | name, slug, active |
| `core_service` | Bookable job types (tap repair, pipe leakage…) | category →, name, active |
| `core_providerprofile` | Plumber public profile (1 per user) | user →, display_name, phone, photo, bio, experience_years, work hours/days, is_available, **is_approved**, is_featured, is_demo, rating_avg/count |
| `core_providerprofile_areas` | M2M: localities served | profile ↔ locality |
| `core_providerservice` | Services offered + optional starting price | provider →, service →, price_from |
| `core_booking` | Booking requests | ref_code (PLB-XXXXXX), provider →, customer_name/phone, service →, locality →, area_detail (landmark only), preferred_date/time, status, final_amount, review_token |
| `core_review` | One review per booking (via private link) | booking → (unique), provider →, rating 1–5, comment |
| `core_qrcode` | Printable QR codes | name, slug, venue_type, locality → (optional filter), image PNG, scans |
| `core_platformsettings` | Singleton (id=1): revenue model + amounts | revenue_model, lead_fee_amount, commission_percent, subscription_monthly |
| `core_earning` | Revenue ledger | provider →, booking →, kind, amount, note |

Booking lifecycle: `requested → accepted → completed` (or `rejected`/`cancelled`).
Reviews are only accepted on `completed` bookings, via the booking's secret
`review_token` link — one review per booking, no fake reviews possible.

Privacy: only a landmark/area is stored (`area_detail`); exact customer
addresses are never collected or displayed.

## How to add real plumbers

1. Send them to **`/provider/register/`** — they fill name, phone, areas,
   services, hours. Their profile is created **unapproved** (hidden).
2. You verify them (call them, check ID/work), then **Admin → Providers →
   Pending → Approve**. They're instantly listed.
3. Or add them yourself in `/django-admin/` → Provider profiles.

## How to generate QR codes

**Admin → QR codes → New QR code**: name it (e.g. *"Sunrise Apartments — lobby"*),
pick the venue type and optionally a locality. The QR opens the plumber list
pre-filtered to that locality, and every scan is counted.

Open the QR → **Download PNG** or **Print poster** ("NEED A PLUMBER? Scan…").
If the site's public URL ever changes: `python manage.py regen_qr`.

## How to make money (all three models built in)

**Admin → Settings → Revenue model.** Switching is instant; past earnings stay.

| Model | How it charges | When |
|---|---|---|
| **Lead fee** (default, best for pilot) | ₹49 per accepted lead | auto-recorded when a provider *accepts* a booking |
| **Commission** | 10% of job value | auto-recorded when a booking is marked *completed* (provider enters final amount) |
| **Subscription** | ₹499/month premium listing | record manually in Django admin → Earnings (auto-billing later) |

Revenue lives in **Admin → Overview** and each provider sees their own charges
under **Dashboard → Earnings & leads**. For the pilot, collect via UPI from
providers weekly against the Earnings ledger.

## Monthly operating cost (pilot)

| Setup | Cost |
|---|---|
| **This machine + tunnel** (testing only) | ₹0 — not for real customers |
| **Render.com: web (free) + Postgres (free)** | **₹0** — sleeps after 15 min idle; fine for pilot |
| Render web (starter, no sleep) + Postgres | ~₹650 + ~₹500 ≈ **₹1,150/mo** |
| Custom domain (optional) | ~₹800/yr |
| SMS/OTP verification (later, e.g. MSG91) | ~₹0.15–0.25/SMS, pay as you go |

Recommended: start on Render free tier (₹0), upgrade when bookings are daily.

## Deploy to Render (real public URL, ~15 min)

1. Push this folder to a GitHub repo.
2. Render dashboard → **New → Blueprint** → select the repo (`render.yaml`).
3. Wait for the build; note the `https://plumberlink-xxxx.onrender.com` URL.
4. Visit `/django-admin/` → create provider/admin accounts; `/admin-panel/qr/`
   → regenerate QR codes (the start script already re-baked the public URL).
5. `python manage.py purge_demo` equivalent: delete demo rows in Django admin
   (filter `is_demo`), then onboard real plumbers.

Caveats for scale: user-uploaded photos live on ephemeral disk on free Render —
move to S3/Cloudinary before heavy use; switch `DATABASE_URL` is already
supported in settings.

## Security notes

- Change `PLUMBERLINK_SECRET_KEY` in production (Render generates one).
- `DEBUG=0` in production; `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` set from env.
- Passwords hashed with Django's default hashers; provider approval is manual.
- Customer phone numbers are visible only to the chosen provider and admin —
  never on public pages.
