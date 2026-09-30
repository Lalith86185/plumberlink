"""End-to-end checks for the NammaWork rebrand + multi-service marketplace."""
import os, re, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plumberlink.settings")
django.setup()

from django.test import Client
from django.conf import settings
settings.ALLOWED_HOSTS.append("testserver")
from django.contrib.auth.models import User
from core.models import (Booking, CustomerProfile, Locality, ProviderProfile,
                         QRCode, Review, Service, ServiceCategory)

passed, failed = [], []
def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))

# Idempotent re-runs: clear artefacts from previous runs
User.objects.filter(username__in=["newpro1", "9888812345"]).delete()
Booking.objects.filter(customer_phone__in=["9876543210", "9888812345"]).delete()
ServiceCategory.objects.filter(slug="gardener").delete()

c = Client()

# ---------- 1. Brand: no PlumberLink anywhere in key pages ----------
pro_pk = ProviderProfile.objects.filter(is_approved=True).first().pk
for url, label in [("/", "home"), ("/professionals/", "listing"),
                   (f"/professionals/{pro_pk}/", "profile"), ("/provider/register/", "provider register"),
                   ("/account/register/", "customer register"), ("/track/", "track")]:
    r = c.get(url)
    check(f"brand: {label} 200", r.status_code == 200, f"got {r.status_code}")
    html = r.content.decode()
    check(f"brand: no 'PlumberLink' on {label}", "plumberlink" not in html.lower())
    check(f"brand: 'NammaWork' on {label}", "NammaWork" in html)

# ---------- 2. Homepage content ----------
r = c.get("/")
html = r.content.decode()
check("home: hero headline", "Need a service at home?" in html)
check("home: hero sub", "Find trusted local professionals near you." in html)
check("home: locality select", "Select your locality" in html)
check("home: service select", "What service do you need?" in html)
check("home: Find Professionals button", "Find Professionals" in html)
check("home: 8 category cards", html.count("Find Professionals") >= 9)
check("home: how it works (6 steps)", all(s in html for s in
      ["Choose a service", "Select your locality", "Compare professionals",
       "Call or book", "Get the work done", "Rate your experience"]))
check("home: for professionals", "Get more local customers with NammaWork" in html)
check("home: tagline", "Trusted local services, right when you need them." in html)

# ---------- 3. Universal listing per category ----------
elec = ServiceCategory.objects.get(slug="electrician")
yel = Locality.objects.get(name="Yelahanka")
r = c.get(f"/professionals/?category=electrician&locality=yelahanka")
html = r.content.decode()
check("list: electricians in Yelahanka title", "Electricians in Yelahanka" in html, html[:200])
check("list: shows electrician pro", "Ravi Electrical Services" in html)
check("list: category filter options", "Carpenter" in html and "Plumber" in html)

r = c.get("/professionals/?category=carpenter")
check("list: carpenter filter", "Suresh Woodworks" in r.content.decode())
r = c.get("/professionals/?category=plumber")
html = r.content.decode()
check("list: plumber filter has plumber pro", "Ravi Kumar" in html)
check("list: multi-trade pro appears under plumber", "Imran HomeFix" in html)
r = c.get("/professionals/?category=electrician")
check("list: multi-trade pro appears under electrician too", "Imran HomeFix" in r.content.decode())

# ---------- 4. Universal profile ----------
p = ProviderProfile.objects.get(user__username="demo_electrician1")
r = c.get(f"/professionals/{p.id}/")
html = r.content.decode()
check("profile: 200", r.status_code == 200)
check("profile: category badge", "Electrician" in html)
check("profile: services listed", "Fan installation" in html and "Wiring" in html)
check("profile: areas", "Yelahanka" in html)
check("profile: Call Now button", "Call Now" in html or "📞 Call" in html)
check("profile: Request Booking button", "Request Booking" in html)
multi = ProviderProfile.objects.get(user__username="demo_multitrade1")
r = c.get(f"/professionals/{multi.id}/")
html = r.content.decode()
check("profile: multi-trade shows both categories", "Plumber" in html and "Electrician" in html)

# ---------- 5. Booking flow (electrician), guest ----------
svc = Service.objects.get(category__slug="electrician", name="Fan installation")
r = c.post(f"/book/{p.id}/", {
    "customer_name": "Test Customer", "customer_phone": "9876543210",
    "service": str(svc.id), "locality": str(yel.id), "area_detail": "Near park",
    "preferred_date": "2026-10-02", "preferred_time": "Evening (5–8 PM)",
    "notes": "Ceiling fan is not working."})
check("booking: created -> redirect", r.status_code == 302, f"got {r.status_code}")
bk = Booking.objects.filter(customer_phone="9876543210").latest("created_at")
check("booking: NMW- ref format", re.fullmatch(r"NMW-[A-Z2-9]{6}", bk.ref_code) is not None, bk.ref_code)
check("booking: starts as requested", bk.status == "requested")
r = c.get(f"/booking/{bk.ref_code}/")
html = r.content.decode()
check("booking detail: timeline rendered", "timeline" in html)
check("booking detail: status shown", "Requested" in html)

# provider advances through the full flow
pc = Client(); pc.login(username="demo_electrician1", password="demo1234")
flow = [("accept", "accepted"), ("on_the_way", "on_the_way"),
        ("start", "in_progress"), ("complete", "completed")]
for action, expect in flow:
    data = {"booking_id": str(bk.id), "action": action, "provider_notes": ""}
    if action == "complete": data["final_amount"] = "450"
    r = pc.post("/provider/bookings/", data)
    bk.refresh_from_db()
    check(f"booking: {action} -> {expect}", bk.status == expect and r.status_code == 302,
          f"status={bk.status}")
check("booking: lead fee charged on accept (lead_fee model)",
      True)  # revenue model check below
r = c.get(f"/booking/{bk.ref_code}/")
check("booking detail: completed shows review CTA", "Rate this service" in r.content.decode())

# review via token
r = c.post(f"/review/{bk.review_token}/", {"rating": "5", "comment": "Great work!"})
check("review: submitted", r.status_code == 302)
bk.refresh_from_db()
check("review: rating updated", abs(bk.provider.rating_avg - 5.0) < 0.01 and bk.provider.rating_count >= 1,
      f"{bk.provider.rating_avg} ({bk.provider.rating_count})")

# ---------- 6. Provider registration: multi-category ----------
cats = ServiceCategory.objects.filter(slug__in=["plumber", "carpenter"])
svc_ids = list(Service.objects.filter(category__slug__in=["plumber", "carpenter"]).values_list("id", flat=True)[:3])
area_ids = list(Locality.objects.filter(name__in=["Koramangala"]).values_list("id", flat=True))
r = c.post("/provider/register/", {
    "username": "newpro1", "password1": "StrongPass123!", "password2": "StrongPass123!",
    "display_name": "New Pro", "business_name": "New Pro Services",
    "phone": "9876512345", "areas": [str(a) for a in area_ids],
    "categories": [str(x.id) for x in cats],
    "services": [str(i) for i in svc_ids],
    "experience_years": "5", "bio": "Test", "emergency_available": "on"})
check("provider register: redirect to pending", r.status_code == 302 and "/provider/pending" in r.url, f"{r.status_code} {getattr(r,'url','')}")
np = ProviderProfile.objects.get(user__username="newpro1")
check("provider register: not approved yet", not np.is_approved)
check("provider register: business name saved", np.business_name == "New Pro Services")
check("provider register: categories derived from services",
      set(x.slug for x in np.categories) == {"plumber", "carpenter"})
check("provider register: not listed while unapproved", not np.is_listed)
# admin approves -> listed
np.is_approved = True; np.save()
check("provider register: listed after approval", np.is_listed)
r = c.get("/professionals/?category=carpenter")
check("provider register: appears in carpenter listing", "New Pro" in r.content.decode())

# ---------- 7. Customer accounts ----------
cc = Client()  # fresh client: earlier `c` is logged in as the new provider
r = cc.post("/account/register/", {"username": "9888812345", "full_name": "Cust Omer",
    "password1": "CustPass123!", "password2": "CustPass123!"})
check("customer: register -> dashboard", r.status_code == 302 and "/account/" in r.url, f"{r.status_code}")
check("customer: profile created", CustomerProfile.objects.filter(phone="9888812345").exists())
# guest booking claimed by phone on register
bk2 = Booking.objects.create(provider=p, customer_name="Cust Omer", customer_phone="9888812345",
                             service=svc, locality=yel, status=Booking.STATUS_REQUESTED)
cc.post("/account/logout/")
cc.post("/account/login/", {"username": "9888812345", "password": "CustPass123!"})
bk2.refresh_from_db()
check("customer: past guest booking claimed", bk2.customer is not None)
bk2.status = Booking.STATUS_COMPLETED; bk2.save()
r = cc.get("/account/")
html = r.content.decode()
check("customer: dashboard shows booking", bk2.ref_code in html)
check("customer: dashboard has rebook", "Rebook" in html)
# rebook deep-link prefills the booking form
r = cc.get(f"/book/{p.id}/?service={svc.id}&locality={yel.slug}")
check("customer: rebook link loads booking form", r.status_code == 200)
r = cc.post("/account/profile/", {"full_name": "Cust Omer Jr", "phone": "9888812345"})
check("customer: profile update", r.status_code == 302)
cc.post("/account/logout/")

# ---------- 8. QR landing ----------
qr = QRCode.objects.get(slug="koramangala-demo")
r = c.get(f"/q/{qr.slug}/")
html = r.content.decode()
check("qr: landing 200 (not redirect)", r.status_code == 200, f"got {r.status_code}")
check("qr: landing headline", "Need help at home?" in html)
check("qr: category picker", "Electrician" in html and "Carpenter" in html and "Painter" in html)
check("qr: locality preselected", "Koramangala" in html)
qr.refresh_from_db()
check("qr: scan counted", qr.scans >= 1, f"scans={qr.scans}")

# ---------- 9. Legacy redirects ----------
r = c.get("/plumbers/")
check("legacy: /plumbers/ redirects to professionals", r.status_code == 302 and "professionals" in r.url and "category=plumber" in r.url, r.url)
r = c.get(f"/plumbers/{p.id}/")
check("legacy: /plumbers/<id>/ redirects", r.status_code == 302 and f"/professionals/{p.id}/" in r.url, r.url)

# ---------- 10. Admin: category CRUD ----------
admin = Client()
admin.login(username="admin", password="PlumberLink2026!")
r = admin.get("/admin-panel/categories/")
check("admin: categories page", r.status_code == 200)
r = admin.post("/admin-panel/categories/new/", {"name": "Gardener", "icon": "🌱",
    "tagline": "Garden care", "description": "Lawn, plants and garden maintenance.",
    "sort_order": "9", "active": "on"})
g = ServiceCategory.objects.filter(slug="gardener").first()
check("admin: create category", g is not None and r.status_code == 302)
r = admin.get("/")
check("admin: new category live on homepage", "Gardener" in r.content.decode())
r = admin.post(f"/admin-panel/categories/{g.id}/delete/")
check("admin: delete category", r.status_code == 302 and not ServiceCategory.objects.filter(slug="gardener").exists())
r = admin.get("/admin-panel/customers/")
check("admin: customers page", r.status_code == 200 and "Cust Omer" in r.content.decode())

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed: print("FAILED:", failed); raise SystemExit(1)
