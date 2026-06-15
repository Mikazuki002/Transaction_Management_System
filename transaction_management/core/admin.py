# this is the adminstration 

from django.contrib import admin
from .models import Profile, OTP, Appointment, CertificateRequest, ActionLog


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "student_number", "course" , "year_level" ,"is_verified_email", "is_approved_by_registrar", "submitted_at")
    search_fields = ("student_number", "user__username", "user__first_name", "user__last_name", "user__email")
    list_filter = ("is_verified_email", "is_approved_by_registrar", "course", "year_level")
    
    def get_first_name(self, obj):
        return obj.user.first_name
    get_first_name.short_description = "First Name"

    def get_last_name(self, obj):
        return obj.user.last_name
    get_last_name.short_description = "Last Name"

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = "Email"


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'purpose', 'appointment_date', 'status', 'created_at')
    list_filter = ('status', 'appointment_date')

    def date(self, obj):
        return obj.appointment_date.strftime('%Y-%m-%d')
    
@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'certificate_type', 'status', 'requested_at')
    list_filter = ('certificate_type', 'status')


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("admin_user", "student_profile", "appointment", "certificate" , "action_type", "performed_at")
    search_fields = ("admin_user__username", "student_profile__student_number", "appointment__student__username", "certificate__student__username")
    list_filter = ("action_type", "performed_at")