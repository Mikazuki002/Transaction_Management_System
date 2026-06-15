

from django.conf import settings #import wide project settings
from django.contrib.auth.models import User #built-in user model for authentiction (such as username, email, password)
from django.db import models #defining database models (e.g, tables, etc)
import uuid #
from datetime import datetime, timedelta #handling dates and time
from django.utils import timezone


#THis function allows for file uploads
#defines for WHERE the uploaded files goes/stored in media as follows (media/ directory)
# exmple media file path; media/documents/user_5/my_id_card.png
def upload_documents(instance, filename):
    return f"documents/user_{instance.user.id}/{filename}" #will return the file path on where the data is stored


# --------------------------- PROFILING MODEL---------------------------
class Profile(models.Model):
    #allows to only create a one to one relationship
    # one email = one account
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_number = models.CharField(max_length=50, unique=True)
    course = models.CharField(max_length=100, blank=True)
    year_level = models.CharField(max_length=10, blank=True)
    cor_id = models.FileField(upload_to='uploads/cor_id/', blank=True, null=True) # Uploading file of the students
    is_verified_email = models.BooleanField(default=False) #OTP verification that will be sent on their respective email
    is_approved_by_registrar = models.BooleanField(default=False) #registrar approval towards the accounts

    #uploading document: COR or student ID
    document = models.FileField(upload_to=upload_documents, null=True, blank=True) #allows the users to send their documents
    submitted_at = models.DateTimeField(null=True, blank=True) #create a time frame
    is_rejected = models.BooleanField(default=False) # checks the student account whether rejected or not 'False as Default'
    rejection_reason = models.TextField(null=True, blank=True) # This allows to display the rejection reason of the student

    # function that will search base on the username and student number
    def __str__(self):
        return f"{self.user.username} ({self.student_number})"

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return datetime.utcnow() >self.expires_at.replace(tzinfo=None)
    
    def __str__(self):
        return f"OTP for {self.user.email} - {self.code}"
    

class Appointment(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Declined", "Declined"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appointments")
    purpose = models.CharField(max_length=255)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now=True)

    approved_by = models.ForeignKey(
            User,
            on_delete = models.SET_NULL,
            null = True,
            blank = True,
            related_name="approved_appointments"
        )
    def __str__(self):
        return f"{self.student.username} - {self.appointment_date} ({self.status})"
    
    
    
class CertificateRequest(models.Model):
    CERTIFICATE_CHOICES = [
        ('good_moral', 'Good Moral Certificate'),
        ('enrollment', 'Certificate of Enrollment'),
        ('registration_form', 'Registration Form'),
        ('cog', 'Certificate of Grades'),
        ('diploma', 'Diploma'),
    ]

    student = models.ForeignKey(User,on_delete=models.CASCADE)
    certificate_type = models.CharField(max_length=50, choices=CERTIFICATE_CHOICES)
    purpose = models.TextField(blank=True, null=True)
    supporting_document = models.FileField(upload_to='certificates/', blank=True, null=True)

    # NOTIFICATION
    requested_at = models.DateTimeField(auto_now_add=True)   # when student submitted
    pickup_date = models.DateField(null=True, blank=True)
    pickup_time = models.TimeField(null=True, blank=True)
    is_notified = models.BooleanField(default=False)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('Pending', 'Pending'),
            ('Approved', 'Approved'),
            ('Released', 'Released'),
            ('Declined', 'Declined')
        ],
        default='Pending'
    )



    # Field for showing who approved/reject 
    approved_by = models.ForeignKey(
        User,
        on_delete = models.SET_NULL,
        null = True,
        blank = True,
        related_name = "approved_certificates"
    )

    def __str__(self):
        return f"{self.student.username} - {self.certificate_type} ({self.status})"
    
class RegistrarProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=100, default="Registrar")


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    employee_id = models.CharField(max_length = 50)
    role = models.CharField(max_length = 100, default = "Administrator")

    def __str__(self):
        return f"{self.user.username} (Admin)"
    
class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('Registrar', 'Registrar'),
        ('Administrator', 'Administrator'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
    

class ActionLog(models.Model):
    ACTION_TYPES = [
        ("APPROVE", "Approved Profile"),
        ("REJECT", "Rejected Profile"),
        ("UPDATE", "Updated Profile"),
        ("APPOINTMENT", "Processed Appointment"),
        ("CERTIFICATE", "Processed Certificate Request"),
    ]

    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="action_logs")
    student_profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name="logs")
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    message = models.TextField()
    performed_at = models.DateTimeField(auto_now_add=True)


    appointment = models.ForeignKey('Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='action_logs')
    certificate = models.ForeignKey('CertificateRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='action_logs')
    def __str__(self):
        return f"{self.admin_user} - {self.action_type} - {self.performed_at}"