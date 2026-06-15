from django.urls import path, include
from . import views
from django.contrib import admin
from core import views
from django.contrib.auth import views as auth_views

app_name = "core"

urlpatterns = [
    # THESE ARE FOR WAITING AREA
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    # path("verify/", views.verify_otp, name="verify_otp"),

    # LOGOUT
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # THESE ARE FOR APPROVALS
    path("waiting-for-approval/", views.waiting_for_approval, name="waiting_for_approval"),
    path("approvals/", views.approval_list, name="approval_list"),
    path("approvals/approve/<int:profile_id>/", views.approve_profile, name="approve_profile"),
    path("approvals/reject/<int:profile_id>/", views.reject_profile, name="reject_profile"),

    

    # THESE ARE FOR APPOINTMENTS
    path("appointments/", views.student_appointments, name="student_appointments"),
    path("registrar/appointments/", views.registrar_appointments, name="registrar_appointments"),
    path("registrar/appointments/update/<int:appointment_id>/<str:status>/", views.update_appointment_status, name="update_appointment_status"),
    path("registrar/dashboard/", views.registrar_dashboard, name='registrar_dashboard'),

    # THESE ARE FOR CERTIFICATES
    path('certificates/', views.certificate_request_view, name='certificate_request'),
    path("registrar/certificates/", views.registrar_certificates, name="registrar_certificates"),
    path("registrar/certificates/update/<int:cert_id>/<str:status>/", views.update_certificate_status, name="update_certificate_status"),


    # THESE ARE FOR REGISTRAR
    path("registrar/register/", views.registrar_register, name="registrar_register"),


    # THESE ARE FOR ADMIN
    path("admin-register/", views.admin_register, name="admin_register"),
    
    # THESE ARE THE STUDENT PATH
    path('student/dashboard/', views.student_dashboard, name="student_dashboard"),

    path("waiting/<int:user_id>/", views.waiting_status, name="waiting_status"),
    path("waiting-status/<int:profile_id>/", views.waiting_status, name="waiting_status"),


    #Rejected FRAME FOR STUDENT
    path("account-rejected/", views.account_rejected, name="account_rejected"),

    # urls.py
    path('account-rejected/<str:token>/', views.account_rejected, name='account_rejected'),
    path('accept-rejection/', views.accept_rejection, name='accept_rejection'),
    path("registrar/appointments/bulk-update/", views.bulk_update_appointments, name="bulk_update_appointments"),
    path("admin/live-students/", views.live_student_report, name="live_student_records"),

    # URLS FOR REPORTS
    path('export-students/', views.export_students, name='export_students'),
     path("reports/requests-summary/", views.export_request_summary, name="export_request_summary"),
    path("reports/certificates-issued/", views.export_certificate_issuance, name="export_certificate_issuance"),
    path("reports/top-certificates/", views.export_top_certificates, name="export_top_certificates"),
    path("reports/processing-performance/", views.export_processing_performance, name="export_processing_performance"),
]