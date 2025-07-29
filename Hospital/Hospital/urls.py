"""
URL configuration for Hospital project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# Hospital/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from medical import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public
    path('', views.HomeView.as_view(), name="home"),
    path('about/', views.AboutView.as_view(), name="about"),

    path('blog/', views.BlogView.as_view(), name="blog"),
    path('blog/<int:pk>/', views.Blog_singleView.as_view(), name='blog_single'),
    path('contact/', views.ContactView.as_view(), name="contact"),
    path('department/', views.DepartmentView.as_view(), name="department"),
    path('doctor/', views.DoctorView.as_view(), name="doctor"),
    path('highlight/', views.HighlightView.as_view(), name="highlight"),
    path('department-service/', views.department_service_view, name='department_service'),

    # Authentication
    path('signup/', views.SignupView.as_view(), name="signup"),
    path('verify-otp/', views.OtpVerificationView.as_view(), name="verify_otp"),
    path('signin/', views.SigninView.as_view(), name="signin"),
    path('signout/', views.SignOutView.as_view(), name="signout"),

    # Appointment (Role-Based)
    path('appointment/', views.AppointmentView.as_view(), name='appointment'),
    path('my-appointments/', views.MyAppointmentsView.as_view(), name='my_appointments'),
    path('doctor-appointments/', views.DoctorAppointmentsView.as_view(), name='doctor_appointments_dashboard'),
    path('admin-appointments/', views.AllAppointmentsView.as_view(), name='all_appointments_dashboard'),
    path('appointment/delete/<int:pk>/', views.DeleteAppointmentView.as_view(), name='delete_appointment'),

    path('appointment/payment/<int:appointment_id>/', views.AppointmentPaymentView.as_view(), name='appointment_payment'),
    path('appointment/success/<int:appointment_id>/', views.AppointmentPaymentSuccessView.as_view(), name='appointment_payment_success'),


    # Profile
    path('my-profile/', views.MyProfileView.as_view(), name='my_profile'),
    path('my-profile/delete/', views.DeleteProfileView.as_view(), name='delete_profile'),

    path('chatbot/', views. ChatbotView.as_view(), name='chatbot'),
    path('api/chatbot/', views. ChatbotView.as_view(), name='chatbot_api'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

