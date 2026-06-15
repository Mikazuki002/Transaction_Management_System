from django import forms
from django.contrib.auth.models import User
from .models import Profile
from django.core.exceptions import ValidationError
from .models import Appointment
from .models import CertificateRequest
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from .models import AdminProfile
from django.core.validators import RegexValidator


YEAR_LEVEL_CHOICES = [
    ("1st Year", "1st Year"),
    ("2nd Year", "2nd Year"),
    ("3rd Year", "3rd Year"),
    ("4th Year", "4th Year"),
]
class StudentRegistrationForm(forms.ModelForm):
    # --- User fields ---
    username = forms.CharField(
        max_length=50,
        validators=[RegexValidator(r'^[\w\s]+$', 'Username can only contain letters, numbers, and spaces.')],

        widget=forms.TextInput(attrs={"placeholder": "Username"})
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "School Email Address"})
    )

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "First Name"})
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "Last Name"})
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password"})
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm Password"})
    )

    # --- Profile-specific fields ---
    student_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": "Student Number"})
    )

    course = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Course"})
    )

    year_level = forms.ChoiceField(
        choices=YEAR_LEVEL_CHOICES,
        widget=forms.Select()
    )

    document = forms.FileField(
        required=True,
        label="Upload COR / School ID"
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "confirm_password",
            "student_number",
            "course",
            "year_level",
            "document",
        ]

    # -----------------------------
    # VALIDATION AREA
    # -----------------------------
    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        cpw = cleaned.get("confirm_password")

        if pw and cpw and pw != cpw:
            raise ValidationError("Passwords do not match.")
        return cleaned

    def clean_email(self):
        email = self.cleaned_data.get("email")

        # allow ANY valid email
        if not email.lower().endswith("@cvsu.edu.ph"):
            raise forms.ValidationError("Only CVSU institutional email is allowed!")

        # if User.objects.filter(email=email).exists():
        #     raise ValidationError("This email is already registered")
        
        return email



    def clean_student_number(self):
        student_number = self.cleaned_data.get("student_number")
        if Profile.objects.filter(student_number=student_number).exists():
            raise ValidationError("This student number is already registered.")
        return student_number

    
# Form for verifying OTP input
class OTPForm(forms.Form):
    code = forms.CharField(max_length=6)



# Creating the appointment form
class AppointmentForms(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["purpose", "appointment_date", "appointment_time"]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "appointment_time": forms.TimeInput(attrs={"type": "time"})
        }

class CertificateRequestForm(forms.ModelForm):
    class Meta:
        model = CertificateRequest
        fields = ['certificate_type', 'purpose', 'supporting_document']
        widgets = {
            'certificate_type': forms.Select(attrs={'class': 'form-control'}),
            'purpose': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter purpose for this certificate.'}),
        }

# Custom login form (Django-compatible)
class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )





# REGISTRAR
REGISTRAR_ACCESS_CODE = "REGISTRAR_CVSU_1906" # This is the code for registrar
class RegistrarRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    access_code = forms.CharField(max_length=20, help_text="Enter Registrar Access Code")


    class Meta:
        model = User
        fields = ["username", "email", "password", "confirm_password", "first_name", "last_name", "access_code"]


    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")


        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Password do not match")
        
        # Check the registrar access code
        code = cleaned_data.get("access_code")
        if code != REGISTRAR_ACCESS_CODE:
            raise forms.ValidationError("Invalid Registrar Access Code")

        return cleaned_data
    


    def save(self, commit=True):
        user = super().save(commit=False)


        # Set password
        user.set_password(self.cleaned_data["password"])

        # make registrar staff member ONLY
        user.is_staff = True
        user.is_superuser= False

        user.is_active = True # Ensure login
        if commit:
            user.save()


        return user
    


# ADMIN
# This is the admin access code
ADMIN_ACCESS_CODE = "CVSU-ADMIN-2025" # This code is changeable accordingly

class AdminRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(max_length=100)
    employee_id = forms.CharField(max_length=50)
    access_code = forms.CharField(max_length=50)

    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ["username", "email", "password"]

        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()

        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("confirm_password")

        if p1 != p2:
            raise forms.ValidationError("Passwords do not match.")

        # Validate admin access code
        code = cleaned_data.get("access_code")
        if code != ADMIN_ACCESS_CODE:
            raise forms.ValidationError("Invalid admin access code.")

        return cleaned_data

    def save(self, commit=True):
        
        """
        # Create superuser
        user = User(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            first_name=self.cleaned_data["full_name"],
            is_staff=True,       # allows access to admin dashboard
            is_superuser=True,   # full Django admin access
        )
        user.set_password(self.cleaned_data["password"])

        """
        user = super().save(commit = False)

        user.first_name = self.cleaned_data["full_name"]
        user.set_password(self.cleaned_data["password"])
        user.is_staff = True
        user.is_superuser = False

        if commit:
            user.save()

            # Create admin profile
            AdminProfile.objects.create(
                user=user,
                employee_id=self.cleaned_data["employee_id"]
            )

        return user
