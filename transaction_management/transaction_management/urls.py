"""
URL configuration for transaction_management project.

This file defines the main URL routes of the entire Django project.
It connects the project-level routes to your app-level (core) URLs.
"""

# ----------------------------------------
# Imports
# ----------------------------------------
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import views
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

# ----------------------------------------
# URL Patterns
# ----------------------------------------
urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),

    # Student State
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    # Note this will direct towards the register as home
    path("", lambda request: redirect("login"), name="home"),

    # ✅ Include all routes from the "core" app (register, verify, appointments, etc.)
    # path('', include('core.urls', namespace='core')),
    # path("registrar/", views.registrar_register, name="registrar_register"),


    # ✅ Default homepage redirect
    # When someone visits http://127.0.0.1:8000/, it will redirect to /register/
    path('', include('core.urls', namespace='core')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ----------------------------------------
# Serve uploaded files during development
# ----------------------------------------
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
