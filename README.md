# NammaWork 🔧 — Trusted local services, right when you need them (MVP)

Find trusted local professionals in Bengaluru — plumbers, electricians,
carpenters and more. Customers search by locality and service, call or book,
track the booking, and leave a review. Professionals get a dashboard; the admin
gets approvals, QR codes, revenue and stats.

**Stack:** Python · Django 6 · SQLite (pilot) / PostgreSQL (production) ·
plain HTML/CSS/JS, mobile-first. No build step, no JS framework — easy to maintain.

## Quick start (local)

```bash
cd plumberlink
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_catalog     # 8 service categories + services
./venv/bin/python manage.py seed_demo        # clearly-marked demo data
./venv/bin/python manage.py createsuperuser  # your admin login
./venv/bin/python manage.py runserver
```

Open http://localhost:8000

| Who | URL | Login |
|---|---|---|
| Customer site | `/` | optional — guest bookings work with name + phone; `/account/` for accounts |
| Professional register / login | `/provider/register/` · `/provider/login/` | demo: `demo_plumber1` / `demo1234` |
| Admin panel | `/admin-panel/` | your superuser |
| Full Django admin | `/django-admin/` | your superuser |

Demo accounts: `demo_plumber1`, `demo_electrician1`, `demo_carpenter1`,
`demo_multitrade1` (all password `demo1234`).

Remove demo data any time: `python manage.py purge_demo`

## Project layout

```
plumberlink/          Django project (settings, urls, wsgi)
core/                 The whole app: models, views, forms, admin, templates, static
  templates/core/     Customer pages, provider dashboard, admin panel
  static/core/css/    One mobile-first stylesheet
  management/commands/ seed_catalog · seed_demo · purge_demo · regen_qr
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
| `auth_user` | Login accounts (professionals + admins) | username, password (hashed) |
| `core_locality` | Service areas | name, slug, city, active |
| `core_servicecategory` | Service category (Plumber, Electrician, Carpenter, …) | name, slug, icon, active |
| `core_service` | Bookable job types (tap repair, fan installation…) | category →, name, active |
| `core_providerprofile` | Professional public profile (1 per user); categories derived from offered services | user →, display_name, business_name, phone, photo, bio, experience_years, work hours/days, is_available, **is_approved**, is_featured, is_demo, rating_avg/count |
| `core_providerprofile_areas` | M2M: localities served | profile ↔ locality |
| `core_providerservice` | Services offered + optional starting price | provider →, service →, price_from |
| `core_customerprofile` | Optional customer account (phone = username) | user → (unique), phone, full_name |
| `core_booking` | Booking requests | ref_code (NMW-XXXXXX), provider →, customer → (optional), customer_name/phone, service →, locality →, area_detail (landmark only), preferred_date/time, status, final_amount, review_token |
| `core_review` | One review per booking (via private link) | booking → (unique), provider →, rating 1–5, comment |
| `core_qrcode` | Printable QR codes → service-picker landing page | name, slug, venue_type, locality → (optional filter), image PNG, scans |
| `core_platformsettings` | Singleton (id=1): revenue model + amounts | revenue_model, lead_fee_amount, commission_percent, subscription_monthly |
| `core_earning` | Revenue ledger | provider →, booking →, kind, amount, note |

Booking lifecycle: `requested → accepted → on_the_way → in_progress → completed`
(or `rejected`/`cancelled`). Professionals move bookings forward step by step;
each step posts to the customer's **track page** timeline.

Customers can book as guests (name + phone) or create an account
(`/account/`). On register/login, past guest bookings made with the same phone
are claimed automatically. Customer dashboard shows active + past bookings,
review links, rebook shortcuts, and profile editing.

Reviews are only accepted on `completed` bookings, via the booking's secret
`review_token` link — one review per booking, no fake reviews possible.

Privacy: only a landmark/area is stored (`area_detail`); exact customer
addresses are never collected or displayed.

Note: profiles do **not** claim "verified" status — pending profiles say
"pending admin approval", and review says "quick verification by our team".

## How to add real professionals

1. Send them to **`/provider/register/`** — they fill name, phone, areas,
   then tick the services they offer (grouped by category). Their profile is
   created **unapproved** (hidden).
2. You verify them (call them, check ID/work), then **Admin → Professionals →
   Pending → Approve**. They're instantly listed under every category they
   serve.
3. Or add them yourself in `/django-admin/` → Professional profiles.
4. New category? **Admin → Categories → New category**, then add services —
   no code changes needed.

## How to generate QR codes

**Admin → QR codes → New QR code**: name it (e.g. *"Sunrise Apartments — lobby"*),
pick the venue type and optionally a locality. The QR opens a service-picker
landing page (customer picks the service they need, pre-filtered to that
locality), and every scan is counted.

Open the QR → **Download PNG** or **Print poster** ("NEED HELP AT HOME? Scan…").
If the site's public URL ever changes: `python manage.py regen_qr`.

## How to make money (all three models built in)

**Admin → Settings → Revenue model.** Switching is instant; past earnings stay.

| Model | How it charges | When |
|---|---|---|
| **Lead fee** (default, best for pilot) | ₹49 per accepted lead | auto-recorded when a professional *accepts* a booking |
| **Commission** | 10% of job value | auto-recorded when a booking is marked *completed* (provider enters final amount) |
| **Subscription** | ₹499/month premium listing | record manually in Django admin → Earnings (auto-billing later) |

Revenue lives in **Admin → Overview** and each professional sees their own charges
under **Dashboard → Earnings & leads**. For the pilot, collect via UPI from
professionals weekly against the Earnings ledger.

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
3. Wait for the build; note the `https://nammawork-xxxx.onrender.com` URL.
4. `python manage.py seed_catalog` (service categories), then visit
   `/django-admin/` → create provider/admin accounts; `/admin-panel/qr/` →
   regenerate QR codes (the start script already re-baked the public URL).
5. `python manage.py purge_demo` equivalent: delete demo rows in Django admin
   (filter `is_demo`), then onboard real professionals.

Caveats for scale: user-uploaded photos live on ephemeral disk on free Render —
move to S3/Cloudinary before heavy use; switch `DATABASE_URL` is already
supported in settings.

## Security notes

- Change `PLUMBERLINK_SECRET_KEY` in production (Render generates one).
- `DEBUG=0` in production; `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` set from env.
- Passwords hashed with Django's default hashers; professional approval is manual.
- Customer phone numbers are visible only to the chosen professional and admin —
  never on public pages.
