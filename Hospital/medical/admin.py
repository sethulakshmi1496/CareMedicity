from django.contrib import admin
from .models import CustomUser, Department, Doctor, Patient, BlogPost, Appointment,DepartmentService,Comment

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Department)
admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(BlogPost)
admin.site.register(Appointment)
admin.site.register(DepartmentService)
admin.site.register(Comment)