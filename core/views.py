import io
import mimetypes
from functools import wraps

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Count, F, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    BOOKING_TRANSITIONS, BookingForm, BookingTrackForm, CustomerProfileForm,
    CustomerRegistrationForm, PlatformSettingsForm, ProviderBookingActionForm,
    ProviderProfileForm, ProviderRegistrationForm, ProviderServicesForm, QRCodeForm,
    ReviewForm, ServiceCategoryForm,
)
from .models import (
    Booking, CustomerProfile, Earning, Locality, PlatformSettings, ProviderProfile, QRCode,
    Review, Service, ServiceCategory,
)


# ---------------------------------------------------------------- helpers

def provider_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        try:
            profile = request.user.provider_profile
        except ProviderProfile.DoesNotExist:
            messages.error(request, "This account is not registered as a provider.")
            return redirect("home")
        if not profile.is_approved:
            return redirect("provider_pending")
        request.provider = profile
        return view(request, *args, **kwargs)
    return wrapper


def build_qr_image(qr: QRCode) -> str:
    """(Re)generate the QR PNG for a QRCode row. Returns the public target URL."""
    target = f"{settings.PUBLIC_BASE_URL}{reverse('qr_redirect', kwargs={'slug': qr.slug})}"
    img = qrcode.make(target, box_size=12, border=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr.image.save(f"{qr.slug}.png", ContentFile(buf.getvalue()), save=False)
    qr.save(update_fields=["image"])
    return target


def charge_for_booking(booking: Booking):
    """Apply the platform's revenue model when a booking moves forward."""
    cfg = PlatformSettings.get()
    if booking.status == Booking.STATUS_ACCEPTED and cfg.revenue_model == PlatformSettings.REVENUE_LEAD_FEE:
        if not booking.earnings.filter(kind=Earning.KIND_LEAD_FEE).exists():
            Earning.objects.create(
                booking=booking, provider=booking.provider,
                kind=Earning.KIND_LEAD_FEE, amount=cfg.lead_fee_amount,
                note=f"Lead fee for booking {booking.ref_code}")
    if booking.status == Booking.STATUS_COMPLETED and cfg.revenue_model == PlatformSettings.REVENUE_COMMISSION:
        if booking.final_amount and not booking.earnings.filter(kind=Earning.KIND_COMMISSION).exists():
            amount = booking.final_amount * cfg.commission_percent / 100
            Earning.objects.create(
                booking=booking, provider=booking.provider,
                kind=Earning.KIND_COMMISSION, amount=round(amount, 2),
                note=f"{cfg.commission_percent}% commission on ₹{booking.final_amount} ({booking.ref_code})")


def review_url(booking: Booking) -> str:
    return f"{settings.PUBLIC_BASE_URL}{reverse('review_create', kwargs={'token': booking.review_token})}"


# ---------------------------------------------------------------- customer

def home(request):
    localities = Locality.objects.filter(active=True)
    categories = ServiceCategory.objects.filter(active=True).prefetch_related("services")
    locality_slug = request.GET.get("locality", "")
    category_slug = request.GET.get("category", "")
    if locality_slug or category_slug:
        params = []
        if locality_slug:
            params.append(f"locality={locality_slug}")
        if category_slug:
            params.append(f"category={category_slug}")
        return redirect(f"{reverse('professional_list')}?{'&'.join(params)}")
    return render(request, "core/home.html", {
        "localities": localities, "categories": categories,
        "selected_locality": locality_slug, "selected_category": category_slug,
    })


def provider_list(request):
    providers = (ProviderProfile.objects
                 .filter(is_approved=True, is_available=True)
                 .select_related("user")
                 .prefetch_related("areas", "offered_services__service__category"))
    locality_slug = request.GET.get("locality", "")
    category_slug = request.GET.get("category", "")
    service_id = request.GET.get("service", "")
    emergency = request.GET.get("emergency", "")
    locality = None
    if locality_slug:
        locality = get_object_or_404(Locality, slug=locality_slug, active=True)
        providers = providers.filter(areas=locality)
    category = None
    if category_slug:
        category = get_object_or_404(ServiceCategory, slug=category_slug, active=True)
        providers = providers.filter(offered_services__service__category=category)
    service = None
    if service_id:
        service = get_object_or_404(Service, pk=service_id, active=True)
        if category and service.category_id != category.id:
            raise Http404
        providers = providers.filter(offered_services__service=service)
    if emergency:
        providers = providers.filter(emergency_available=True)
    services_qs = Service.objects.filter(active=True)
    if category:
        services_qs = services_qs.filter(category=category)
    return render(request, "core/provider_list.html", {
        "providers": providers.distinct(),
        "localities": Locality.objects.filter(active=True),
        "categories": ServiceCategory.objects.filter(active=True),
        "services": services_qs.order_by("sort_order"),
        "locality": locality, "category": category,
        "service": service, "emergency": emergency,
    })


def provider_detail(request, pk):
    provider = get_object_or_404(
        ProviderProfile.objects.select_related("user").prefetch_related(
            "areas", "offered_services__service__category"),
        pk=pk, is_approved=True, is_available=True)
    reviews = provider.reviews.select_related("booking").order_by("-created_at")[:20]
    # Services grouped by category for the universal profile layout.
    services_by_category = []
    for cat in provider.categories:
        offered = [ps for ps in provider.offered_services.all()
                   if ps.service.category_id == cat.id]
        if offered:
            services_by_category.append((cat, offered))
    return render(request, "core/provider_detail.html",
                  {"provider": provider, "reviews": reviews,
                   "services_by_category": services_by_category})


def booking_create(request, provider_id):
    provider = get_object_or_404(ProviderProfile, pk=provider_id,
                                 is_approved=True, is_available=True)
    initial = {}
    if request.user.is_authenticated and hasattr(request.user, "customer_profile"):
        cp = request.user.customer_profile
        initial = {"customer_name": request.user.get_full_name() or request.user.first_name,
                   "customer_phone": cp.phone}
    if request.method == "POST":
        form = BookingForm(request.POST, provider=provider)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.provider = provider
            if request.user.is_authenticated and hasattr(request.user, "customer_profile"):
                booking.customer = request.user
            booking.save()
            messages.success(request, f"Booking request {booking.ref_code} sent to {provider.display_name}.")
            return redirect("booking_detail", ref=booking.ref_code)
    else:
        # "Rebook" deep-link: ?service=<id>&locality=<slug>
        if request.GET.get("service"):
            initial["service"] = request.GET.get("service")
        if request.GET.get("locality"):
            initial["locality"] = request.GET.get("locality")
        form = BookingForm(provider=provider, initial=initial)
    return render(request, "core/booking_form.html", {"form": form, "provider": provider})


def booking_detail(request, ref):
    booking = get_object_or_404(
        Booking.objects.select_related("provider", "service", "locality"),
        ref_code__iexact=ref.strip())
    can_review = (booking.status == Booking.STATUS_COMPLETED
                  and not hasattr(booking, "review"))
    flow = Booking.STATUS_FLOW
    flow_index = flow.index(booking.status) if booking.status in flow else -1
    flow_labels = dict(Booking.STATUS_CHOICES)
    return render(request, "core/booking_detail.html",
                  {"booking": booking, "can_review": can_review,
                   "review_link": review_url(booking) if can_review else "",
                   "flow": flow, "flow_index": flow_index,
                   "flow_labels": flow_labels})


def booking_track(request):
    booking = None
    if request.method == "POST":
        form = BookingTrackForm(request.POST)
        if form.is_valid():
            booking = Booking.objects.filter(
                ref_code__iexact=form.cleaned_data["ref_code"].strip(),
                customer_phone=form.cleaned_data["phone"]).first()
            if booking:
                return redirect("booking_detail", ref=booking.ref_code)
            messages.error(request, "No booking found with that reference and phone number.")
    else:
        form = BookingTrackForm()
    return render(request, "core/booking_track.html", {"form": form})


def review_create(request, token):
    booking = get_object_or_404(Booking.objects.select_related("provider"), review_token=token)
    if hasattr(booking, "review"):
        messages.info(request, "Thanks — a review has already been submitted for this booking.")
        return redirect("professional_detail", pk=booking.provider_id)
    if booking.status != Booking.STATUS_COMPLETED:
        messages.warning(request, "You can submit a review after the service is marked completed.")
        return redirect("booking_detail", ref=booking.ref_code)
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.provider = booking.provider
            review.customer_name = booking.customer_name
            review.save()  # triggers provider.refresh_rating()
            messages.success(request, "Thank you! Your review helps other customers.")
            return redirect("professional_detail", pk=booking.provider_id)
    else:
        form = ReviewForm()
    return render(request, "core/review_form.html", {"form": form, "booking": booking})


def qr_redirect(request, slug):
    """Service-independent QR landing: count the scan, let the customer pick a
    trade (and locality), then go to the universal professional listing."""
    qr = get_object_or_404(QRCode, slug=slug, is_active=True)
    QRCode.objects.filter(pk=qr.pk).update(scans=F("scans") + 1)
    categories = ServiceCategory.objects.filter(active=True).prefetch_related("services")
    return render(request, "core/qr_landing.html", {
        "qr": qr, "categories": categories,
        "localities": Locality.objects.filter(active=True),
    })


def media_serve(request, path):
    if ".." in path or path.startswith(("/", "\\")):
        raise Http404
    full = (settings.MEDIA_ROOT / path).resolve()
    if settings.MEDIA_ROOT.resolve() not in full.parents and full != settings.MEDIA_ROOT.resolve():
        raise Http404
    if not full.is_file():
        raise Http404
    ctype = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
    return FileResponse(open(full, "rb"), content_type=ctype)


# ---------------------------------------------------------------- provider auth

def provider_register(request):
    if request.user.is_authenticated and hasattr(request.user, "provider_profile"):
        return redirect("provider_dashboard")
    if request.method == "POST":
        form = ProviderRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registered! Your profile is pending admin approval.")
            return redirect("provider_pending")
    else:
        form = ProviderRegistrationForm()
    categories = ServiceCategory.objects.filter(active=True).order_by("sort_order", "name")
    service_groups = [(c, list(c.services.filter(active=True).order_by("sort_order")))
                      for c in categories]
    selected_services = set(form["services"].value() or [])
    return render(request, "core/provider_register.html", {
        "form": form, "service_groups": service_groups,
        "selected_services": {str(v) for v in selected_services},
    })


def provider_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin_dashboard")
        if hasattr(request.user, "provider_profile"):
            return redirect("provider_dashboard")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect("admin_dashboard")
            if hasattr(user, "provider_profile"):
                if user.provider_profile.is_approved:
                    return redirect("provider_dashboard")
                return redirect("provider_pending")
            messages.error(request, "This account is not a provider account.")
            logout(request)
    else:
        form = AuthenticationForm()
    return render(request, "core/provider_login.html", {"form": form})


def provider_logout(request):
    logout(request)
    messages.info(request, "Logged out.")
    return redirect("home")


@login_required
def provider_pending(request):
    try:
        profile = request.user.provider_profile
    except ProviderProfile.DoesNotExist:
        return redirect("home")
    if profile.is_approved:
        return redirect("provider_dashboard")
    return render(request, "core/provider_pending.html", {"profile": profile})


# ---------------------------------------------------------------- provider area

@provider_required
def provider_dashboard(request):
    p = request.provider
    counts = (p.bookings.values("status").annotate(n=Count("id")))
    by_status = {c["status"]: c["n"] for c in counts}
    earnings_total = p.charges.aggregate(t=Sum("amount"))["t"] or 0
    recent = p.bookings.select_related("service", "locality").order_by("-created_at")[:8]
    return render(request, "core/p_dashboard.html", {
        "profile": p, "by_status": by_status,
        "total_bookings": sum(by_status.values()),
        "earnings_total": earnings_total,
        "recent": recent,
        "review_link_base": settings.PUBLIC_BASE_URL,
    })


@provider_required
def provider_bookings(request):
    p = request.provider
    status = request.GET.get("status", "")
    bookings = p.bookings.select_related("service", "locality").order_by("-created_at")
    if status:
        bookings = bookings.filter(status=status)
    if request.method == "POST":
        form = ProviderBookingActionForm(request.POST)
        booking = get_object_or_404(Booking, pk=request.POST.get("booking_id"), provider=p)
        if form.is_valid():
            action = form.cleaned_data["action"]
            new_status = BOOKING_TRANSITIONS.get((booking.status, action))
            if not new_status:
                messages.error(request, "That action is not valid for this booking's status.")
                return redirect("provider_bookings")
            booking.status = new_status
            if action == "complete":
                booking.final_amount = form.cleaned_data["final_amount"]
            booking.provider_notes = form.cleaned_data["provider_notes"]
            booking.save()
            charge_for_booking(booking)
            messages.success(request, f"Booking {booking.ref_code}: {booking.get_status_display()}.")
            return redirect("provider_bookings")
    else:
        form = ProviderBookingActionForm()
    return render(request, "core/p_bookings.html", {
        "profile": p, "bookings": bookings, "form": form,
        "active_status": status,
        "status_choices": Booking.STATUS_CHOICES,
    })


@provider_required
def provider_profile(request):
    p = request.provider
    if request.method == "POST":
        if "save_services" in request.POST:
            sform = ProviderServicesForm(request.POST, provider=p)
            pform = ProviderProfileForm(instance=p)
            if sform.is_valid():
                sform.save()
                messages.success(request, "Services and pricing updated.")
                return redirect("provider_profile")
        else:
            pform = ProviderProfileForm(request.POST, request.FILES, instance=p)
            sform = ProviderServicesForm(provider=p)
            if pform.is_valid():
                pform.save()
                messages.success(request, "Profile updated.")
                return redirect("provider_profile")
    else:
        pform = ProviderProfileForm(instance=p)
        sform = ProviderServicesForm(provider=p)
    # Services grouped by category — the same editor works for every trade.
    service_groups = []
    for cat in ServiceCategory.objects.filter(active=True).order_by("sort_order", "name"):
        rows = []
        for svc in cat.services.filter(active=True).order_by("sort_order"):
            rows.append({
                "check": sform[f"svc_{svc.id}"],
                "price": sform[f"price_{svc.id}"],
            })
        if rows:
            service_groups.append((cat, rows))
    return render(request, "core/p_profile.html",
                  {"profile": p, "pform": pform, "sform": sform,
                   "service_groups": service_groups})


@provider_required
def provider_reviews(request):
    p = request.provider
    reviews = p.reviews.select_related("booking").order_by("-created_at")
    return render(request, "core/p_reviews.html", {"profile": p, "reviews": reviews})


@provider_required
def provider_earnings(request):
    p = request.provider
    charges = p.charges.select_related("booking").order_by("-created_at")
    total = charges.aggregate(t=Sum("amount"))["t"] or 0
    cfg = PlatformSettings.get()
    return render(request, "core/p_earnings.html", {
        "profile": p, "charges": charges, "total": total, "cfg": cfg,
    })


# ---------------------------------------------------------------- admin panel

@staff_member_required
def admin_dashboard(request):
    providers = ProviderProfile.objects.all()
    bookings = Booking.objects.all()
    status_counts = bookings.values("status").annotate(n=Count("id"))
    by_status = {c["status"]: c["n"] for c in status_counts}
    earnings = Earning.objects.aggregate(t=Sum("amount"))["t"] or 0
    by_kind = (Earning.objects.values("kind").annotate(n=Count("id"), t=Sum("amount")))
    scans = QRCode.objects.aggregate(t=Sum("scans"))["t"] or 0
    reviews = Review.objects.all()
    avg_rating = reviews.aggregate(a=models.Avg("rating"))["a"] or 0
    ctx = {
        "providers_total": providers.count(),
        "pending": providers.filter(is_approved=False).count(),
        "listed": providers.filter(is_approved=True, is_available=True).count(),
        "demo_providers": providers.filter(is_demo=True).count(),
        "customers_total": CustomerProfile.objects.count(),
        "categories_total": ServiceCategory.objects.filter(active=True).count(),
        "bookings_total": bookings.count(),
        "by_status": by_status,
        "status_choices": Booking.STATUS_CHOICES,
        "earnings_total": earnings,
        "by_kind": by_kind,
        "qr_scans": scans,
        "qr_count": QRCode.objects.count(),
        "reviews_total": reviews.count(),
        "avg_rating": round(avg_rating, 1),
        "recent_bookings": bookings.select_related("provider", "service")[:10],
        "pending_providers": providers.filter(is_approved=False).order_by("-created_at")[:10],
        "cfg": PlatformSettings.get(),
    }
    return render(request, "core/a_dashboard.html", ctx)


@staff_member_required
def admin_providers(request):
    tab = request.GET.get("tab", "pending")
    qs = ProviderProfile.objects.select_related("user").prefetch_related("areas").order_by("-created_at")
    if tab == "pending":
        qs = qs.filter(is_approved=False)
    elif tab == "listed":
        qs = qs.filter(is_approved=True)
    elif tab == "demo":
        qs = qs.filter(is_demo=True)
    if request.method == "POST":
        profile = get_object_or_404(ProviderProfile, pk=request.POST.get("provider_id"))
        action = request.POST.get("action")
        if action == "approve":
            profile.is_approved = True
            messages.success(request, f"{profile.display_name} approved and listed.")
        elif action == "reject":
            profile.is_approved = False
            messages.info(request, f"{profile.display_name} rejected / hidden.")
        elif action == "feature":
            profile.is_featured = True
            messages.success(request, f"{profile.display_name} marked as featured.")
        elif action == "unfeature":
            profile.is_featured = False
            messages.info(request, f"{profile.display_name} unfeatured.")
        elif action == "delete":
            name = profile.display_name
            profile.user.delete()  # cascades to profile
            messages.warning(request, f"{name} and their account removed (spam/fake cleanup).")
            return redirect(f"{reverse('admin_providers')}?tab={tab}")
        profile.save()
        return redirect(f"{reverse('admin_providers')}?tab={tab}")
    return render(request, "core/a_providers.html", {
        "providers": qs, "tab": tab,
        "pending_count": ProviderProfile.objects.filter(is_approved=False).count(),
    })


@staff_member_required
def admin_bookings(request):
    status = request.GET.get("status", "")
    qs = Booking.objects.select_related("provider", "service", "locality").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    return render(request, "core/a_bookings.html", {
        "bookings": qs[:200], "active_status": status,
        "status_choices": Booking.STATUS_CHOICES,
    })


@staff_member_required
def admin_reviews(request):
    if request.method == "POST" and request.POST.get("action") == "delete":
        review = get_object_or_404(Review, pk=request.POST.get("review_id"))
        provider = review.provider
        review.delete()
        provider.refresh_rating()
        messages.warning(request, "Review removed (spam/fake cleanup).")
        return redirect("admin_reviews")
    reviews = Review.objects.select_related("provider", "booking").order_by("-created_at")[:200]
    return render(request, "core/a_reviews.html", {"reviews": reviews})


@staff_member_required
def admin_qr_list(request):
    codes = QRCode.objects.select_related("locality").order_by("-created_at")
    return render(request, "core/a_qr_list.html", {"codes": codes})


@staff_member_required
def admin_qr_create(request):
    if request.method == "POST":
        form = QRCodeForm(request.POST)
        if form.is_valid():
            qr = form.save()
            target = build_qr_image(qr)
            messages.success(request, f"QR code created. It opens: {target}")
            return redirect("admin_qr_detail", slug=qr.slug)
    else:
        form = QRCodeForm()
    return render(request, "core/a_qr_form.html", {"form": form})


@staff_member_required
def admin_qr_detail(request, slug):
    qr = get_object_or_404(QRCode.objects.select_related("locality", "service_category"), slug=slug)
    target = f"{settings.PUBLIC_BASE_URL}{reverse('qr_redirect', kwargs={'slug': qr.slug})}"
    if request.method == "POST" and request.POST.get("action") == "regen":
        target = build_qr_image(qr)
        messages.success(request, "QR image regenerated.")
    return render(request, "core/a_qr_detail.html", {"qr": qr, "target": target})


@staff_member_required
def admin_settings(request):
    cfg = PlatformSettings.get()
    if request.method == "POST":
        form = PlatformSettingsForm(request.POST, instance=cfg)
        if form.is_valid():
            form.save()
            messages.success(request, "Platform settings saved.")
            return redirect("admin_settings")
    else:
        form = PlatformSettingsForm(instance=cfg)
    return render(request, "core/a_settings.html", {"form": form, "cfg": cfg})


# ---------------------------------------------------------------- customer accounts

def _claim_guest_bookings(user, phone):
    """Link past guest bookings made with this phone number to the account."""
    Booking.objects.filter(
        customer__isnull=True, customer_phone=phone).update(customer=user)


def customer_register(request):
    if request.user.is_authenticated:
        return redirect("customer_dashboard")
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            _claim_guest_bookings(user, user.username)
            login(request, user)
            messages.success(request, "Welcome to NammaWork! Your account is ready.")
            return redirect("customer_dashboard")
    else:
        form = CustomerRegistrationForm()
    return render(request, "core/c_register.html", {"form": form})


def customer_login(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "customer_profile"):
            return redirect("customer_dashboard")
        if hasattr(request.user, "provider_profile"):
            return redirect("provider_dashboard")
        if request.user.is_staff:
            return redirect("admin_dashboard")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if hasattr(user, "customer_profile"):
                _claim_guest_bookings(user, user.customer_profile.phone)
                return redirect("customer_dashboard")
            if hasattr(user, "provider_profile"):
                return redirect("provider_dashboard")
            if user.is_staff:
                return redirect("admin_dashboard")
            messages.error(request, "This account is not a customer account.")
            logout(request)
    else:
        form = AuthenticationForm()
    return render(request, "core/c_login.html", {"form": form})


def customer_logout(request):
    logout(request)
    messages.info(request, "Logged out.")
    return redirect("home")


def customer_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        try:
            request.customer = request.user.customer_profile
        except CustomerProfile.DoesNotExist:
            messages.error(request, "Please log in with a customer account.")
            return redirect("customer_login")
        return view(request, *args, **kwargs)
    return wrapper


@customer_required
def customer_dashboard(request):
    bookings = (request.user.customer_bookings
                .select_related("provider", "service__category", "locality")
                .order_by("-created_at"))
    active_statuses = [Booking.STATUS_REQUESTED, Booking.STATUS_ACCEPTED,
                       Booking.STATUS_ON_THE_WAY, Booking.STATUS_IN_PROGRESS]
    return render(request, "core/c_dashboard.html", {
        "active_bookings": bookings.filter(status__in=active_statuses),
        "past_bookings": bookings.exclude(status__in=active_statuses),
        "flow": Booking.STATUS_FLOW,
    })


@customer_required
def customer_profile(request):
    if request.method == "POST":
        form = CustomerProfileForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("customer_dashboard")
    else:
        form = CustomerProfileForm(user=request.user)
    return render(request, "core/c_profile.html", {"form": form})


# ---------------------------------------------------------------- admin: categories & customers

@staff_member_required
def admin_categories(request):
    cats = (ServiceCategory.objects.all()
            .annotate(n_services=Count("services", distinct=True),
                      n_providers=Count("services__providers", distinct=True))
            .order_by("sort_order", "name"))
    return render(request, "core/a_categories.html", {"categories": cats})


@staff_member_required
def admin_category_edit(request, pk=None):
    cat = get_object_or_404(ServiceCategory, pk=pk) if pk else None
    if request.method == "POST":
        form = ServiceCategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{form.instance.name}' saved.")
            return redirect("admin_categories")
    else:
        form = ServiceCategoryForm(instance=cat)
    services = cat.services.order_by("sort_order") if cat else []
    return render(request, "core/a_category_form.html",
                  {"form": form, "category": cat, "services": services})


@staff_member_required
def admin_category_delete(request, pk):
    cat = get_object_or_404(ServiceCategory, pk=pk)
    if request.method == "POST":
        name = cat.name
        cat.delete()  # cascades to its services and provider-service links
        messages.warning(request, f"Category '{name}' and its services removed.")
        return redirect("admin_categories")
    return render(request, "core/a_category_confirm_delete.html", {"category": cat})


@staff_member_required
def admin_customers(request):
    customers = (CustomerProfile.objects.select_related("user")
                 .annotate(n_bookings=Count("user__customer_bookings"))
                 .order_by("-created_at"))
    return render(request, "core/a_customers.html", {"customers": customers})
