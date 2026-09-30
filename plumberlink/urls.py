from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from django.conf import settings

from core import views as v

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Customer site
    path("", v.home, name="home"),
    path("plumbers/", v.provider_list, name="provider_list"),
    path("plumbers/<int:pk>/", v.provider_detail, name="provider_detail"),
    path("book/<int:provider_id>/", v.booking_create, name="booking_create"),
    path("booking/<str:ref>/", v.booking_detail, name="booking_detail"),
    path("track/", v.booking_track, name="booking_track"),
    path("review/<str:token>/", v.review_create, name="review_create"),
    path("q/<slug:slug>/", v.qr_redirect, name="qr_redirect"),
    # Provider area
    path("provider/register/", v.provider_register, name="provider_register"),
    path("provider/login/", v.provider_login, name="provider_login"),
    path("provider/logout/", v.provider_logout, name="provider_logout"),
    path("provider/pending/", v.provider_pending, name="provider_pending"),
    path("provider/", v.provider_dashboard, name="provider_dashboard"),
    path("provider/bookings/", v.provider_bookings, name="provider_bookings"),
    path("provider/profile/", v.provider_profile, name="provider_profile"),
    path("provider/reviews/", v.provider_reviews, name="provider_reviews"),
    path("provider/earnings/", v.provider_earnings, name="provider_earnings"),
    # Admin panel
    path("admin-panel/", v.admin_dashboard, name="admin_dashboard"),
    path("admin-panel/providers/", v.admin_providers, name="admin_providers"),
    path("admin-panel/bookings/", v.admin_bookings, name="admin_bookings"),
    path("admin-panel/reviews/", v.admin_reviews, name="admin_reviews"),
    path("admin-panel/qr/", v.admin_qr_list, name="admin_qr_list"),
    path("admin-panel/qr/new/", v.admin_qr_create, name="admin_qr_create"),
    path("admin-panel/qr/<slug:slug>/", v.admin_qr_detail, name="admin_qr_detail"),
    path("admin-panel/settings/", v.admin_settings, name="admin_settings"),
    # Pilot media serving (images only; use object storage/CDN at real scale)
    re_path(r"^media/(?P<path>.*\.(png|jpg|jpeg|webp|gif))$", v.media_serve, name="media_serve"),
]
