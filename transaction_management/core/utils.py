from .models import AdminProfile, RegistrarProfile, Profile
from django.shortcuts import redirect
from .models import ActionLog
def get_user_role(user):
    if hasattr(user, 'registrarprofile') and user.registrarprofile is not None:
        return user.registrarprofile.role
    if hasattr(user, 'adminprofile') and user.adminprofile is not None:
        return user.adminprofile.role
    if hasattr(user, 'profile') and user.profile is not None:
        return "Student"
    return "Unknown"

def header_context(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    registrar_profile = getattr(request.user, "registrarprofile", None)
    # Get Role
    role = get_user_role(user)

    # Create Initials
    if user.first_name and user.last_name:
        initials = f"{user.first_name[0]}{user.last_name[0]}".upper()

    else:
        initials = user.username[:2].upper()


    return{
        "profile": profile,
        "role": role,
        "initials": initials,
    }



def pending_student_redirect(get_response):
    def middleware(request):
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile and not profile.is_approved_by_registrar:
                # Allow only the waiting page
                if request.path != "/waiting-status/":
                    return redirect("core:waiting_for_approval")
        return get_response(request)
    return middleware

def log_action(admin_user, student_profile=None, action_type=None, message="", appointment=None, certificate=None):
    ActionLog.objects.create(
        admin_user=admin_user,
        student_profile=student_profile,
        appointment=appointment,
        certificate=certificate,
        action_type=action_type,
        message=message
    )
