# medical/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from random import randint
from django.utils import timezone
from django.conf import settings
from django.urls import reverse


class CustomUser(AbstractUser):

    phone = models.CharField(max_length=15, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    otp = models.CharField(max_length=10, null=True, blank=True)

    def generate_otp(self):

        if not self.pk:
            self.save()
        timestamp_part = str(int(timezone.now().timestamp() * 1000))[-4:]
        otp_number = f"{randint(1000, 9999)}{str(self.pk)}{timestamp_part}"[:10]

        self.otp = otp_number
        self.save()


AUTH_USER_MODEL = settings.AUTH_USER_MODEL



GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
]

APPOINTMENT_STATUS_CHOICES = [
    ('Scheduled', 'Scheduled'),
    ('Completed', 'Completed'),
    ('Cancelled', 'Cancelled'),
    ('Rescheduled', 'Rescheduled'),
    ('Pending', 'Pending'),
]


class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()

    author = models.CharField(max_length=100)
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    date_posted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):

        return reverse('blog_single', kwargs={'pk': self.pk})


class Comment(models.Model):
    blog_post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')

    author = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    author_name = models.CharField(max_length=100, blank=True, null=True)
    author_email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    content = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Comment by {self.author_name or (self.author.username if self.author else 'Anonymous')} on {self.blog_post.title}"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="A comprehensive description of the department and its main focus.")
    image = models.ImageField(upload_to='department_images/', blank=True, null=True, help_text="Image representing the department.")

    def __str__(self):
        return self.name


class DepartmentService(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='services')
    title = models.CharField(max_length=100)
    description = models.TextField(help_text="Brief description of this specific service.")
    icon_class = models.CharField(max_length=50, help_text="e.g., flaticon-stethoscope, flaticon-flask")

    def __str__(self):
        return f"{self.title} ({self.department.name})"



class Doctor(models.Model):

    user = models.OneToOneField(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')

    name = models.CharField(max_length=100)
    specialization = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')
    qualification = models.CharField(max_length=200, help_text="e.g., MBBS, MD, MS")
    experience_years = models.IntegerField(default=0)
    profile_picture = models.ImageField(upload_to='doctor_profiles/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    availability_info = models.TextField(blank=True, null=True, help_text="e.g., Mon-Fri 9 AM - 5 PM")
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Patient(models.Model):

    user = models.OneToOneField(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_profile')

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS_CHOICES, default='Pending')

    # Razorpay-related fields
    order_id = models.CharField(max_length=100, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    amount = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appt for {self.patient.user.username} with {self.doctor.name} on {self.appointment_date}"

