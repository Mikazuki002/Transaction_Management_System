
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.contrib.auth import authenticate, login
from .forms import StudentRegistrationForm, OTPForm
from django.contrib.auth.models import User
from django.conf import settings
from .models import Profile, OTP
from django.utils import timezone
from django.core.mail import send_mail
import random
from datetime import timedelta
from django.db import IntegrityError
# from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import AppointmentForms
from django.contrib import messages
from .models import Appointment, Profile
from datetime import date, datetime
from .forms import CertificateRequestForm
from .models import CertificateRequest
from django.contrib.auth.decorators import login_required
from .forms import RegistrarRegistrationForm
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from .models import AdminProfile
from .forms import AdminRegistrationForm
from .utils import get_user_role
from .models import RegistrarProfile
from django.core.paginator import Paginator
from .utils import header_context
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.db.models import Case, When, Value, IntegerField
from .utils import log_action
from .models import ActionLog
from django.db.models.functions import TruncDate, TruncMonth, TruncYear, TruncWeek
from django.http import JsonResponse
@never_cache
@login_required
def student_dashboard(request):
    """
    Student landing page after registration or login
    shows quick links and status summary
    """

    # Allow open access for testing
    user = request.user if request.user.is_authenticated else None
    profile = None
    appointments = []
    certificates = []
    account_status = "Unverified"

    # Get student profile if logged in
    if user:
        try:
            profile = Profile.objects.get(user=user)
            if profile.is_approved_by_registrar:
                account_status = None  # No need to show anything
            elif not profile.is_verified_email:
                account_status = "Please verify your email to activate your account."
            else:
                account_status = "Your account is pending registrar approval."

        except Profile.DoesNotExist:
            profile = None

        # Get student's appointments and certificates if logged in

        appointments = Appointment.objects.filter(student=user).order_by('-created_at')
        certificates = CertificateRequest.objects.filter(student=user).order_by('-requested_at')

        # Paginate (5 per page)
        app_paginator = Paginator(appointments, 5)
        cert_paginator = Paginator(certificates, 5)

        app_page_number = request.GET.get("app_page")
        cert_page_number = request.GET.get("cert_page")

        app_page_obj = app_paginator.get_page(app_page_number)
        cert_page_obj = cert_paginator.get_page(cert_page_number)
    
    else:
        # For anonymous visitors — no queries using user
        profile = None
        appointments = []
        certificates = []
        account_status = "Guest Access (Testing Mode)"

    # Ensuring view triggers notifications
    released_certs = CertificateRequest.objects.filter(
        student=request.user,
        status='Released',
        is_notified=False
    )

    show_popup = False
    if released_certs.exists():
        show_popup = True
        # mark notified so modal only shows once
        released_certs.update(is_notified=True)


    context = {
        "profile": profile,
        "appointments": appointments,
        "certificates": certificates,
        "account_status": account_status,
        "app_page_obj": app_page_obj,
        "cert_page_obj": cert_page_obj,
        "messages": messages.get_messages(request),
        "show_popup": show_popup,
        "released_certs": released_certs,
    }
    # --- Certificate Pickup Notification ---
    if user:
        now = timezone.localtime()

        certs_to_notify = CertificateRequest.objects.filter(
            student=user,
            status="Released",
            is_notified=False,
            pickup_date__lte=now.date(),
            pickup_time__lte=now.time(),
        )

        if certs_to_notify.exists():
            show_popup = True

            for c in certs_to_notify:
                messages.success(
                    request,
                    f"📌 {c.get_certificate_type_display()} is ready! "
                    f"Pickup on {c.pickup_date} at {c.pickup_time}."
                )

            certs_to_notify.update(is_notified=True)

    return render(request, "core/student_dashboard.html", context)

def register(request):
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                is_active=False  # user cannot login yet
            )

            # Staff status
            user.is_staff = False
            user.save()

            Profile.objects.create(
                user=user,
                student_number=form.cleaned_data["student_number"],
                course=form.cleaned_data["course"],
                year_level=form.cleaned_data["year_level"],
                document=request.FILES.get("document"),
                submitted_at=timezone.now(),
                is_verified_email=True,  # always true since no OTP
                is_approved_by_registrar=False

            )

            # direct redirect to pending page
            # login(request, user)  # temporary login to show the page
            return redirect("core:waiting_status", user_id=user.id)

        else:
            print("Form Errors:", form.errors)

    else:
        form = StudentRegistrationForm()

    return render(request, "core/register.html", {"form": form})


@never_cache
def waiting_for_approval(request):
    """
    Redirects logged-in pending students to their waiting page.
    Guests or non-pending users are sent to login.
    """
    if request.user.is_authenticated:
        user = request.user
        profile = getattr(user, "profile", None)
        if profile and not profile.is_approved_by_registrar:
            return redirect("core:waiting_status", user_id=user.id)

    messages.info(request, "Please log in to view your approval status.")
    return redirect("core:login")


def waiting_status(request, user_id):
    user = User.objects.filter(id=user_id).first()
    if not user:
        messages.error(request, "This account does not exist or was rejected.")
        return redirect("core:login")

    profile = getattr(user, "profile", None)
    if not profile:
        messages.error(request, "Profile not found.")
        return redirect("core:login")

    # If rejected → show rejection message
    if hasattr(profile, "is_rejected") and profile.is_rejected:
        return render(request, "core/waiting_status.html", {
            "student": user,
            "profile": profile,
            "rejected": True,
            "reject_message": profile.rejection_reason,
        })

    # If approved → show approved message in waiting_status.html
    if profile.is_approved_by_registrar:
        return render(request, "core/waiting_status.html", {
            "student": user,
            "profile": profile,
            "approved": True,
        })

    # Pending → show normal waiting page
    return render(request, "core/waiting_status.html", {
        "student": user,
        "profile": profile,
    })


# THIS IS THE VIEW FOR THE DASHBOARD/LOGIN MENU
def login_view(request):
    if request.method == "POST":
        email_or_username = request.POST.get("email")
        password = request.POST.get("password")

        # Try to get username if email was entered
        try:
            user_obj = User.objects.get(email=email_or_username)
            username = user_obj.username
        except User.DoesNotExist:
            username = email_or_username

        # Custom authentication for inactive students
        try:
            user = User.objects.get(username=username)
            # Allow pending students to login temporarily
            # Custom authentication for inactive students
            if not user.is_active and hasattr(user, 'profile') and not user.profile.is_approved_by_registrar:
                if user.check_password(password):
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    login(request, user)
                    # ★ NEW: Redirect using user_id so the page still works after session ends
                    return redirect("core:waiting_status", user_id=user.id)


                else:
                    messages.error(request, "Invalid credentials.")
                    return redirect("core:login")
        except User.DoesNotExist:
            user = None

        # Standard authentication for active users
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            # Redirect pending students to waiting page
            if hasattr(user, 'profile') and not user.profile.is_approved_by_registrar:
                return redirect("core:waiting_for_approval")

            # Admins and staff
            if user.is_superuser or user.is_staff:
                return redirect("core:registrar_dashboard")

            # Regular student
            return redirect("core:student_dashboard")
        else:
            messages.error(request, "Invalid email/username or password.")
            return redirect("core:login")

    return render(request, "core/login.html")



# LOGOUT FRAME
def logout_view(request):
    list(messages.get_messages(request))  # clears any pending messages
    logout(request)
    return redirect("core:login")

def pending_approval(request):
    """
        This code handles the pending request of the accounts
    
    """

    #after verification, show pending screen until registrar approves
    is_approved = False
    if request.user.is_authenticated:
        try:
            is_approved = request.user.profile.is_approved_by_registrar
        except Profile.DoesNotExist:
            is_approved = False
    return render(request, "core/pending_approval.html", {"is_approved": is_approved})

# registrar can view the list of pending verifications
# but this will required the login for the staff
from django.contrib.auth.decorators import user_passes_test

def staff_check(user):
    return user.is_staff or user.is_superuser

@user_passes_test(staff_check)
def approval_list(request):
    # display all profiles that have been submitted and are not yet approved yet
    profiles = Profile.objects.filter(is_approved_by_registrar=False).order_by('-submitted_at')

    context_text = header_context(request)
    context_text["profiles"] = profiles

    return render(request, "core/approval_list.html", context_text)

@user_passes_test(staff_check)
def approve_profile(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    profile.is_approved_by_registrar = True
    profile.save()

    # activate the user account so they can login
    user = profile.user
    user.is_active = True
    user.save()

    # Save log activity
    log_action(
        admin_user=request.user,
        student_profile=profile,
        action_type="APPROVE",
        message=f"Approved student Account ({profile.user.get_full_name})"
    )

    # send notification
    send_mail(
        "Account Approved",
        f"Hello {profile.user.get_full_name() or profile.user.username}, your account has been approved by the registrar. You can now login",
        settings.DEFAULT_FROM_EMAIL,
        [profile.user.email],
        fail_silently=True,
    )

    messages.success(request, f"Approved {profile.user.get_full_name() or profile.user.username}")
    return redirect("core:approval_list")


@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def reject_profile(request, profile_id):
    """
    Registrar rejects a student's account.
    Stores rejection reason and redirects registrar back to approval_list.
    Student will see message in waiting_status.html.
    """
    profile = get_object_or_404(Profile, id=profile_id)
    user = profile.user

    if request.method == "POST":
        reason = request.POST.get("reason", "Your account has been rejected.")

        # Save rejection state instead of deleting profile/user
        profile.is_rejected = True
        profile.rejection_reason = reason
        profile.is_approved_by_registrar = False
        profile.save()

        # Keep the user inactive so they cannot log in
        user.is_active = False
        user.save()

         # save action log
        log_action(
            admin_user=request.user,
            student_profile=profile,
            action_type="REJECT",
            message=f"Rejected student account ({profile.user.get_full_name()}). Reason: {reason}"
        )

        messages.error(request, f"Rejected {user.get_full_name()} — reason saved.")
        return redirect("core:approval_list")

    return render(request, "core/reject_reason_form.html", {"profile": profile})


# Delete only after they see the message

@require_POST
def accept_rejection(request):
    """
    Deletes a rejected student's profile and user account when they acknowledge the rejection.
    """
    student_id = request.POST.get("student_id")  # we pass this hidden input from the form
    profile = get_object_or_404(Profile, id=student_id)
    user = profile.user

    # Delete profile and user from DB
    profile.delete()
    user.delete()

    messages.success(request, "Your rejected account has been removed.")
    return redirect("core:register")  # redirect to registration page

# This si the view for showing the student their account is reject
def account_rejected(request, token):
    """
    Shows the rejection message to the student.
    """
    # Clear all leftover messages for the current session
    list(messages.get_messages(request))
    try:
        reject_message = force_str(urlsafe_base64_decode(token))
    except Exception:
        reject_message = "Your account has been rejected. You can try to register again."

    return render(request, "core/account_rejected.html", {
        "reject_message": reject_message
    })

# helping the function to check if the user is staff
def is_registrar(user):
    return user.is_staff # can be adjust to have a custom role system


@login_required
def student_appointments(request):
    user = request.user
    today = date.today()

    # Available times for dropdown
    all_times = ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM",
                 "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"]

    booked_times = []
    selected_date = request.POST.get('appointment_date', None)
    if selected_date:
        # Get all times already fully booked (5 students)
        booked_times = [
            t for t in all_times 
            if Appointment.objects.filter(appointment_date=selected_date, 
                                          appointment_time=datetime.strptime(t, "%I:%M %p").time()
                                         ).count() >= 5
        ]

    # Filter available times
    available_times = [t for t in all_times if t not in booked_times]

    # Get all appointments for the student, ordered by most recent
    appointments = Appointment.objects.filter(student=user).order_by('-appointment_date', '-appointment_time')

    if request.method == 'POST':
        post_data = request.POST.copy()
        if 'appointment_time' in post_data:
            # Convert AM/PM string to 24-hour format for form
            try:
                t = datetime.strptime(post_data['appointment_time'], "%I:%M %p").time()
                post_data['appointment_time'] = t.strftime("%H:%M")
            except ValueError:
                messages.error(request, "Invalid time format")
                return redirect('core:student_appointments')

        form = AppointmentForms(post_data)
        if form.is_valid():
            appointment_date = form.cleaned_data['appointment_date']
            appointment_time = form.cleaned_data['appointment_time']

            # Blocks any past dates to appear
            if appointment_date < date.today():
                messages.error(request, "You cannot book an appointment in the past. Cause 'Past' is 'Past' for a reason")
                return redirect('core:student_appointments')

            # Prevent same student from double-booking
            if Appointment.objects.filter(
                student=user,
                appointment_date=appointment_date,
                appointment_time=appointment_time
            ).exists():
                messages.error(request, "You already booked this time slot.")
                return redirect('core:student_appointments')

            # Limit 5 students per time slot
            if Appointment.objects.filter(
                appointment_date=appointment_date,
                appointment_time=appointment_time
            ).count() >= 5:
                messages.error(request, f"All slots for {appointment_time.strftime('%I:%M %p')} are FULL!")
                return redirect('core:student_appointments')

            # Save appointment
            appointment = form.save(commit=False)
            appointment.student = user
            appointment.status = 'Pending'
            appointment.save()

            messages.success(request, "Appointment booked successfully!")
            return redirect('core:student_appointments')


        else:
            messages.error(request, "Please correct the errors below")
    else:
        form = AppointmentForms()

    return render(request, 'core/student_appointments.html', {
        'form': form,
        'appointments': appointments,
        'available_times': available_times,
        'booked_times': booked_times,
        'today': date.today(),
    })


@never_cache
# @user_passes_test(is_registrar)
def registrar_appointments(request):
    appointments = Appointment.objects.annotate(
    status_order=Case(
        When(status='Pending', then=Value(0)),   # Pending first
        When(status='Approved', then=Value(1)),
        When(status='Declined', then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )
).order_by('status_order', 'appointment_date', 'appointment_time')

    # Pagination: Show only 5 appointments per page
    paginator = Paginator(appointments, 5)  # 5 appointments per page
    page_number = request.GET.get('page')  # Get the page number from the query params
    page_obj = paginator.get_page(page_number)  # Get the current page object

    context = header_context(request)  # This gives profile, initials, role
    context['appointments'] = page_obj

    return render(request, "core/registrar_appointments.html", context)

def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Get all actions for this appointment
    logs = ActionLog.objects.filter(appointment=appointment).order_by('-performed_at')
    
    context = {
        'appointment': appointment,
        'logs': logs
    }
    return render(request, 'core/appointment_detail.html', context)

# Checks the admin user and display in the Dashboard of the student
def update_appointment_status(request, appointment_id, status):
    appointment = get_object_or_404(Appointment, id = appointment_id)
    if appointment.status != "Pending":
        return redirect("core:registrar_appointments")

    appointment.status = status
    appointment.save()

    if status == "Approved":
        appointment.approved_by = request.user
    elif status == "Declined":
        appointment.approved_by = request.user
    else:
        appointment.approved_by = None

    appointment.save()

    # Save log
    log_action(
        admin_user=request.user,
        student_profile=appointment.student.profile,
        appointment=appointment,
        action_type=status.upper(),
        message=f"{status} appointment request for {appointment.student.username} "
                f"on {appointment.appointment_date} at {appointment.appointment_time}."
    )

    return redirect("core:registrar_appointments")


def certificate_detail(request, cert_id):
    cert = get_object_or_404(CertificateRequest, id=cert_id)
    
    # Get all actions for this certificate
    logs = ActionLog.objects.filter(certificate=cert).order_by('-performed_at')
    
    context = {
        'certificate': cert,
        'logs': logs
    }
    return render(request, 'core/certificate_detail.html', context)

# @user_passes_test(is_registrar)
def update_certificate_status(request, cert_id, status):
    cert = get_object_or_404(CertificateRequest, id=cert_id)
    cert.status = status

    # storing who performed the action
    cert.approved_by = request.user


    # Only capture pickup info on release
    if status == "Released":
        cert.pickup_date = request.POST.get("pickup_date")
        cert.pickup_time = request.POST.get("pickup_time")
        cert.is_notified = False  # allow popup on student dashboard
    cert.save()

    # Save log
    log_action(
        admin_user=request.user,
        student_profile=cert.student.profile,
        certificate=cert,
        action_type=status.upper(),
        message=f"{status} certificate request ({cert.certificate_type}) for {cert.student.username}."
    )

    messages.success(request, f"Certificate Request {status.lower()} successfully")
    return redirect("core:registrar_certificates")
@never_cache
@login_required(login_url='/login/')
def registrar_dashboard(request):
    today = date.today()
    month_start = today.replace(day=1)

    # Logged-in user profile
    user = request.user
    profile = getattr(user, 'profile', None)
    role = get_user_role(user) # This gets all the role from the DataBase
    # Generate initials (e.g., "AA")


    if user.first_name and user.last_name:
        initials = f"{user.first_name[0]}{user.last_name[0]}".upper()
    else:
        initials = user.username[:2].upper()

    pending_profiles = Profile.objects.filter(
        is_verified_email=True, is_approved_by_registrar=False
    ).count()
    processing_appointments = Appointment.objects.filter(status="Pending").count()
    completed_today = Appointment.objects.filter(
        status="Approved", appointment_date=today
    ).count()
    total_this_month = Appointment.objects.filter(
        created_at__date__gte=month_start
    ).count()

    # Build recent activity list
    recent_profiles = Profile.objects.order_by('-submitted_at')[:3]
    recent_appointments = Appointment.objects.order_by('-created_at')[:3]

    recent_activity = []

    for p in recent_profiles:
        recent_activity.append({
            "type": "Profile",
            "text": f"New student registered: {p.user.get_full_name()} (ID: {p.student_number})",
            "time": p.submitted_at,
        })
    for a in recent_appointments:
        recent_activity.append({
            "type": "Appointment",
            "text": f"{a.purpose} appointment from {a.student.username} ({a.status})",
            "time": a.created_at,
        })

    recent_activity = sorted(recent_activity, key=lambda x: x["time"], reverse=True)[:5]

    # Live student records (ADMIN ONLY)
    # Live student records (Admin / Registrar)
    students = None

    if user.is_staff or user.is_superuser:
        sort = request.GET.get("sort", "student_number")
        order = request.GET.get("order", "asc")

        allowed_sorts = {
            "student_number": "student_number",
            "name": "user__last_name",
            "course": "course",
            "year": "year_level",
            "status": "is_approved_by_registrar",
            "date": "submitted_at",
        }

        sort_field = allowed_sorts.get(sort, "student_number")
        if order == "desc":
            sort_field = f"-{sort_field}"

        student_qs = Profile.objects.select_related("user").order_by(sort_field)

        paginator = Paginator(student_qs, 10)  # 10 students per page
        page_number = request.GET.get("page")
        students = paginator.get_page(page_number)

    context = {
        "pending_profiles": pending_profiles,
        "processing_appointments": processing_appointments,
        "completed_today": completed_today,
        "total_this_month": total_this_month,
        "recent_activity": recent_activity,
        "students": students,

        # Added so header displays correctly
        "profile": profile,
        "initials": initials,
        "role": role,
    }

    return render(request, "core/registrar_website.html", context)

@never_cache
# REGISTRAR: Allows to view ll certificate request
def registrar_certificates(request):
    # Fetch all certificate requests, sorted by requested_at
    certificates = CertificateRequest.objects.annotate(
    status_order=Case(
        When(status='Pending', then=Value(0)),
        When(status='Approved', then=Value(1)),
        When(status='Declined', then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )
).order_by('status_order', '-requested_at')


    # Pagination: Show only 5 requests at a time
    paginator = Paginator(certificates, 5)  # 5 certificates per page
    page_number = request.GET.get('page')  # Get the page number from the query params
    page_obj = paginator.get_page(page_number)  # Get the current page object

    context_head = header_context(request)
    context_head["page_obj"] = page_obj  # Pass the page object to the template

    return render(request, "core/registrar_certificates.html", context_head)



# THIS IS THE FUNCTION TO REQUEST CERTIFICATE FOR STUDENT
@login_required
def certificate_request_view(request):
    user = request.user

    # If user is not logged in (guest view)
    if not user.is_authenticated:
        form = CertificateRequestForm()
        previous_request = []  # no real data for guest
        messages.info(request, "You are viewing as a guest. Please log in to submit a request.")
        return render(request, 'core/certificate_request.html', {
            'form': form,
            'previous_request': previous_request,
            'guest_view': True,
        })

    # --- If logged in user ---
    if request.method == "POST":
        form = CertificateRequestForm(request.POST, request.FILES)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.student = user
            certificate.save()
            # Use messages to show success after submission
            messages.success(request, "Your certificate request has been submitted successfully!")
            
            # Redirect to the same page to reset the form and success flag
            return redirect('core:certificate_request')  # Ensure this URL is correct for your template

        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CertificateRequestForm()

    # Show previous requests only for logged-in users
    previous_request = CertificateRequest.objects.filter(student=user).order_by('-requested_at')

    # No need to pop session here, we rely on the messages framework instead
    return render(request, 'core/certificate_request.html', {
        'form': form,
        'previous_request': previous_request,
    })



def admin_register(request):
    if request.method == "POST":
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            # Save user WITHOUT committing to DB yet
            user = form.save(commit=False)

            # Set admin privileges
            user.is_staff = True
            user.is_superuser = True

            # Hash the password
            user.set_password(form.cleaned_data["password"])
            user.save()

            # Optional admin profile
            AdminProfile.objects.create(user=user)

            # Render template with success context
            return render(request, "core/admin_register.html", {
                "form": AdminRegistrationForm(),  # empty form
                "success": "Admin account created successfully! Please login."
            })
        
    else:
        form = AdminRegistrationForm()

    return render(request, "core/admin_register.html", {"form": form})



def is_admin(user):
    return user.is_superuser

def is_registrar(user):
    return user.is_staff and not user.is_superuser




# This is for REGISTRAR REGISTER
def registrar_register(request):
    """Registrar REGISTRATION"""
    
    # Force logout if any user is logged in
    if request.user.is_authenticated:
        logout(request)

    if request.method == "POST":
        form = RegistrarRegistrationForm(request.POST)
        if form.is_valid():
            # Save user
            user = form.save()

            # Create registrar profile
            RegistrarProfile.objects.create(user=user, role="Registrar")

            # Success message — shown on the same page
            messages.success(
                request,
                "Registrar account created successfully. Please proceed to login."
            )

            # Render the same page so popup appears
            return render(request, "core/registrar_register.html", {
                "form": RegistrarRegistrationForm()  # empty form
            })

        else:
            # Form invalid — show errors in popups
            messages.error(request, "Please correct the errors in the form below.")
            return render(request, "core/registrar_register.html", {"form": form})

    else:
        form = RegistrarRegistrationForm()

    return render(request, "core/registrar_register.html", {"form": form})


def dashboard(request):
    role = get_user_role(request.user)

    return render(request, "core/dashboard.html", {
        "user_role": role,
    })


def approve_user(request, user_id):
    profile = Profile.objects.get(user_id=user_id)
    profile.is_approved_by_registrar = True
    profile.save()

    # Save log
    log_action(
        admin_user=request.user, 
        student_profile=profile,
        action_type="APPROVE",
        message=f"Approved the account of {profile.user.get_full_name()}."
    )

    messages.success(request, "User approved successfully.")
    return redirect("registrar_dashboard")


def reject_user(request, user_id):
    profile = Profile.objects.get(user_id=user_id)
    profile.is_approved_by_registrar = False
    profile.save()

    # Save log
    log_action(
        admin_user=request.user, 
        student_profile=profile,
        action_type="REJECT",
        message=f"Rejected the account of {profile.user.get_full_name()}."
    )

    messages.error(request, "User rejected.")
    return redirect("registrar_dashboard")




# Bulking approval and rejection
def bulk_update_appointments(request):
    action = request.POST.get("action")
    appointment_ids = request.POST.getlist("appointment_ids")

    if not appointment_ids:
        messages.error(request, "No appointments selected.")
        return redirect("core:registrar_appointments")

    if action not in ["approve", "decline"]:
        messages.error(request, "Invalid bulk action.")
        return redirect("core:registrar_appointments")

    status = "Approved" if action == "approve" else "Declined"

    appointments = Appointment.objects.filter(
        id__in=appointment_ids,
        status="Pending"
    )

    for appointment in appointments:
        appointment.status = status
        appointment.approved_by = request.user
        appointment.save()

        log_action(
            admin_user=request.user,
            student_profile=appointment.student.profile,
            appointment=appointment,
            action_type=status.upper(),
            message=f"{status} appointment (bulk action) for "
                    f"{appointment.student.username} on "
                    f"{appointment.appointment_date} at {appointment.appointment_time}."
        )

    messages.success(
        request,
        f"{appointments.count()} appointment(s) {status.lower()} successfully."
    )

    return redirect("core:registrar_appointments")



# Show Student Record
@login_required
def live_student_report(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    students = Profile.objects.select_related("user").order_by("-submitted_at")

    data = []
    for profile in students:
        data.append({
            "id": profile.id,
            "name": f"{profile.user.first_name} {profile.user.last_name}",
            "email": profile.user.email,
            "student_id": profile.student_number,
            "status": "Approved" if profile.is_approved_by_registrar else "Pending",
            "created_at": profile.submitted_at.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({"students": data})




# EXPORTING DATA/INFORMATION
from django.http import HttpResponse
import csv
def export_students(request):
    # Create the HttpResponse object with CSV header
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="students.csv"'},
    )

    writer = csv.writer(response)
    # Write header row
    writer.writerow(['Student Number', 'Last Name', 'First Name', 'Course', 'Year', 'Status', 'Submitted At'])

    # Write student data
    students = Profile.objects.all()  # you can filter if needed
    for s in students:
        status = 'Approved' if s.is_approved_by_registrar else 'Rejected' if s.is_rejected else 'Pending'
        writer.writerow([s.student_number, s.user.last_name, s.user.first_name,
                         s.course, s.year_level, status, s.submitted_at])

    return response



# REPORTS IMPORTs
#THESE ARE THE REPORTS CATALOGUE
from django.db.models import Count
@login_required
def export_request_summary(request):
    if not request.user.is_superuser:
        return HttpResponse(status=403)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="detailed_certificate_summary.csv"'

    writer = csv.writer(response)

    # 1️⃣ Overall Certificate Requests by Status
    writer.writerow(["=== OVERALL APPOINTMENT STATUS ==="])
    writer.writerow(["Status", "Total Requests"])

    status_data = Appointment.objects.values("status").annotate(total=Count("id"))
    for row in status_data:
        writer.writerow([row["status"], row["total"]])
    writer.writerow([])

    #  Certificate Requests by Course and Year
    writer.writerow(["=== CERTIFICATE REQUESTS BY COURSE & YEAR ==="])
    writer.writerow(["Certificate Type", "Year Level", "Course", "Total Requests", "Total Students"])

    certificate_data = (
        CertificateRequest.objects
        .values("certificate_type", "student__profile__year_level", "student__profile__course")
        .annotate(
            total_requests=Count("id"),
            total_students=Count("student", distinct=True)
        )
        .order_by("certificate_type", "student__profile__year_level", "student__profile__course")
    )

    for row in certificate_data:
        writer.writerow([
            row["certificate_type"],
            row["student__profile__year_level"],
            row["student__profile__course"],
            row["total_requests"],
            row["total_students"]
        ])
    writer.writerow([])

    
    # Most Requested Certificates
    writer.writerow(["=== MOST REQUESTED CERTIFICATES ==="])
    writer.writerow(["Certificate Type", "Total Requests"])

    most_requested = (
        CertificateRequest.objects
        .values("certificate_type")
        .annotate(total_requests=Count("id"))
        .order_by("-total_requests")
    )

    for row in most_requested:
        writer.writerow([row["certificate_type"], row["total_requests"]])
    writer.writerow([])

    # Daily Certificate Requests
    writer.writerow(["=== DAILY CERTIFICATE REQUESTS ==="])
    writer.writerow(["Date", "Certificate Type", "Total Requests"])

    daily_data = (
        CertificateRequest.objects
        .annotate(day=TruncDate("requested_at"))
        .values("day", "certificate_type")
        .annotate(total_requests=Count("id"))
        .order_by("day", "certificate_type")
    )

    for row in daily_data:
        writer.writerow([row["day"], row["certificate_type"], row["total_requests"]])
    writer.writerow([])

    # Weekly Certificate Requests
    writer.writerow(["=== WEEKLY CERTIFICATE REQUESTS ==="])
    writer.writerow(["Week Start", "Certificate Type", "Total Requests"])

    weekly_data = (
        CertificateRequest.objects
        .annotate(week=TruncWeek("requested_at"))
        .values("week", "certificate_type")
        .annotate(total_requests=Count("id"))
        .order_by("week", "certificate_type")
    )

    for row in weekly_data:
        writer.writerow([row["week"], row["certificate_type"], row["total_requests"]])
    writer.writerow([])

    #  Monthly Certificate Requests
    writer.writerow(["=== MONTHLY CERTIFICATE REQUESTS ==="])
    writer.writerow(["Month", "Certificate Type", "Total Requests"])

    monthly_data = (
        CertificateRequest.objects
        .annotate(month=TruncMonth("requested_at"))
        .values("month", "certificate_type")
        .annotate(total_requests=Count("id"))
        .order_by("month", "certificate_type")
    )

    for row in monthly_data:
        writer.writerow([row["month"], row["certificate_type"], row["total_requests"]])
    writer.writerow([])

    return response


@login_required
def export_certificate_issuance(request):
    if not request.user.is_superuser:
        return HttpResponse(status=403)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="issuance_and_appointments_records.csv"'
    )

    writer = csv.writer(response)

    # CERTIFICATE ISSUANCE RECORDS
    writer.writerow(["=== CERTIFICATE ISSUANCE RECORDS ==="])
    writer.writerow(["Student Username","Certificate Type","Status","Requested At","Approved By"])

    certificates = CertificateRequest.objects.select_related(
        "student",
        "approved_by"
    )

    for c in certificates:
        writer.writerow([c.student.username,c.certificate_type,c.status,c.requested_at,c.approved_by.username if c.approved_by else "-"])

    # Blank line between sections
    writer.writerow([])
    writer.writerow([])

    # APPOINTMENT RECORDS
    writer.writerow(["=== APPOINTMENT RECORDS ==="])
    writer.writerow(["Student Username","Appointment Date","Appointment Time","Status","Approved By"])

    appointments = Appointment.objects.select_related(
        "student",
        "approved_by"
    )

    for a in appointments:writer.writerow([a.student.username,a.appointment_date,a.appointment_time,a.status,a.approved_by.username if a.approved_by else "-"])

    return response





@login_required
def export_top_certificates(request):
    if not request.user.is_superuser:
        return HttpResponse("Unauthorized", status=403)
    
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="certificate_statistics.csv"'

    # DAILY SUMMARY
    daily_data = (CertificateRequest.objects.annotate(day=TruncDate("requested_at")).values("day", "certificate_type").annotate(total_requests=Count("id")).order_by("day", "-total_requests"))

    response.write("=== DAILY SUMMARY ===\n")
    response.write("Date,Certificate Type,Total Requests\n")
    for row in daily_data:
        response.write(
            f"{row['day']},{row['certificate_type']},{row['total_requests']}\n"
        )

    response.write("\n")

    # MONTHLY SUMMARY
    monthly_data = (
        CertificateRequest.objects
        .annotate(month=TruncMonth("requested_at"))
        .values("month", "certificate_type")
        .annotate(total_requests=Count("id"))
        .order_by("month", "-total_requests")
    )

    response.write("=== MONTHLY SUMMARY ===\n")
    response.write("Month,Certificate Type,Total Requests\n")
    for row in monthly_data:
        response.write(
            f"{row['month']},{row['certificate_type']},{row['total_requests']}\n"
        )

    response.write("\n")

    # YEARLY SUMMARY
    
    yearly_data = (
        CertificateRequest.objects
        .annotate(year=TruncYear("requested_at"))
        .values("year", "certificate_type")
        .annotate(total_requests=Count("id"))
        .order_by("year", "-total_requests")
    )

    response.write("=== YEARLY SUMMARY ===\n")
    response.write("Year,Certificate Type,Total Requests\n")
    for row in yearly_data:
        response.write(
            f"{row['year']},{row['certificate_type']},{row['total_requests']}\n"
        )

    response.write("\n")

    
    # Course and Certificate breakdown
    course_certificate_data = (
        CertificateRequest.objects
        .values(
            "student__profile__course",
            "certificate_type"
        )
        .annotate(
            total_students=Count("student", distinct=True),
            total_requests=Count("id")
        )
        .order_by("student__profile__course", "-total_requests")
    )

    response.write("=== COURSE BREAKDOWN ===\n")
    response.write("Course,Certificate Type,Total Students,Total Requests\n")
    for row in course_certificate_data:
        response.write(
            f"{row['student__profile__course']},"
            f"{row['certificate_type']},"
            f"{row['total_students']},"
            f"{row['total_requests']}\n"
        )

    return response

@login_required
def export_processing_performance(request):
    if not request.user.is_superuser:
        return HttpResponse(status=403)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="processing_performance.csv"'

    writer = csv.writer(response)

    # Certificate Request
    writer.writerow(["=== CERTIFICATE REQUESTS ==="])
    writer.writerow(["Student", "Certificate Type", "Status", "Requested At", "Approved By"])

    certificates = CertificateRequest.objects.select_related("student", "approved_by")
    for c in certificates:
        writer.writerow([
            c.student.username,
            c.certificate_type,
            c.status,
            c.requested_at.strftime("%Y-%m-%d %H:%M"),
            c.approved_by.username if c.approved_by else "-"
        ])

    writer.writerow([])
    writer.writerow([])

    # Appointments
    writer.writerow(["=== APPOINTMENTS ==="])
    writer.writerow(["Student", "Appointment Date", "Appointment Time", "Status", "Approved By"])

    appointments = Appointment.objects.select_related("student", "approved_by")
    for a in appointments:
        writer.writerow([
            a.student.username,
            a.appointment_date.strftime("%Y-%m-%d"),
            a.appointment_time.strftime("%H:%M") if a.appointment_time else "-",
            a.status,
            a.approved_by.username if a.approved_by else "-"
        ])

    writer.writerow([])
    writer.writerow([])

    # Students accounts
    writer.writerow(["=== STUDENT ACCOUNTS ==="])
    writer.writerow(["Username", "Full Name", "Email", "Status", "Approved/Declined By", "Submitted At"])

    profiles = Profile.objects.select_related("user").all().order_by("-submitted_at")
    for p in profiles:
        status = "Approved" if p.is_approved_by_registrar else "Rejected" if p.is_rejected else "Pending"
        # Find admin/staff who approved/rejected
        log = ActionLog.objects.filter(student_profile=p, action_type__in=["APPROVE", "REJECT"]).order_by("-performed_at").first()
        admin_name = log.admin_user.username if log else "-"
        
        writer.writerow([
            p.user.username,
            f"{p.user.first_name} {p.user.last_name}".strip(),
            p.user.email,
            status,
            admin_name,
            p.submitted_at.strftime("%Y-%m-%d %H:%M")
        ])

    return response


# Release notification
def release_certificate(request, cert_id):
    certificate = get_object_or_404(CertificateRequest, id=cert_id)
    certificate.status = "Released"
    certificate.approved_by = request.user
    certificate.save()

    from django.contrib import messages
    messages.success(request, "📄 Your certificate request has been released!")

    return redirect("student_dashboard")
