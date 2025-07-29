# medical/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.views.generic import DetailView
from django.db import IntegrityError
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
import razorpay
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


from .models import CustomUser, BlogPost, Department, Doctor, Patient, Appointment, DepartmentService
from .forms import SignupForm, LoginForm, AppointmentForm, PatientProfileForm, CommentForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# --- Logging setup  ---
import logging
logger = logging.getLogger(__name__)


import logging
import os
import random
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.db.models import Q


# --- NLP Libraries  ---
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import spacy


# --- Core Views ---

class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')

class AboutView(View):
    def get(self, request):
        return render(request, 'about.html')


class BlogView(View):
    def get(self, request):
        all_posts = BlogPost.objects.all().order_by('-date_posted')
        paginator = Paginator(all_posts, 6)
        page_number = request.GET.get('page')
        posts = paginator.get_page(page_number)
        context = {'posts': posts}
        return render(request, 'blog.html', context)

class Blog_singleView(DetailView):
    model = BlogPost
    template_name = 'blog-single.html'
    context_object_name = 'post'
    pk_url_kwarg = 'pk'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.filter(is_approved=True).order_by('date_posted')
        context['comment_form'] = CommentForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = CommentForm(request.POST)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.blog_post = self.object

            if request.user.is_authenticated:
                comment.author = request.user
                comment.author_name = request.user.get_full_name() or request.user.username
                comment.author_email = request.user.email

            comment.save()
            messages.success(request, "Your comment has been submitted for moderation.")
            return redirect(self.object.get_absolute_url())
        else:
            messages.error(request, "Please correct the errors in your comment.")
            context = self.get_context_data(object=self.object)
            context['comment_form'] = form
            return self.render_to_response(context)

class ContactView(View):
    def get(self, request):
        return render(request, 'contact.html')

class DepartmentView(View):
    def get(self, request):
        departments = Department.objects.all().order_by('name')
        context = {'departments': departments}
        return render(request, 'department.html', context)

def department_service_view(request):
    # Fetch all departments and all services
    departments = Department.objects.all()
    services = DepartmentService.objects.all()

    context = {
        'departments': departments,
        'services': services,
    }
    return render(request, 'department.html', context)

class DoctorView(View):
    def get(self, request):
        doctors = Doctor.objects.all().select_related('specialization')
        context = {'doctors': doctors}
        return render(request, 'doctor.html', context)

class HighlightView(View):
    def get(self, request):
        return render(request, 'highlight.html')

class SignupView(View):
    def post(self, request):
        form_instance = SignupForm(request.POST)
        if form_instance.is_valid():
            user = form_instance.save(commit=False)
            user.is_active = False
            user.save()
            user.generate_otp()
            send_mail(
                "CareMedicity OTP Verification",
                f"Your OTP for CareMedicity is: {user.otp}",
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )
            print('OTP sent to:', user.email)
            messages.success(request, "Account created successfully! Please verify your OTP to complete registration.")
            return redirect('verify_otp')
        else:
            return render(request, 'signup.html', {'form': form_instance})

    def get(self, request):
        form_instance = SignupForm()
        return render(request, 'signup.html', {'form': form_instance})

class OtpVerificationView(View):
    def post(self, request):
        otp = request.POST.get('otp')
        logger.info(f"Received OTP for verification: {otp}")
        try:
            u = CustomUser.objects.get(otp=otp)
            u.is_active = True
            u.is_verified = True
            u.otp = None
            u.save()

            login(request, u)
            messages.success(request, "Account verified successfully! Please complete your profile details.")
            return redirect('my_profile')

        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid OTP. Please try again.")
            return redirect('verify_otp')

    def get(self, request):
        return render(request, 'otp_verify.html')

class SigninView(View):
    def post(self, request):
        logger.info("--- SigninView POST called ---")
        form_instance = LoginForm(request.POST)
        if form_instance.is_valid():
            username = form_instance.cleaned_data['username']
            password = form_instance.cleaned_data['password']

            logger.info(f"Attempting to authenticate user: {username}")
            user = authenticate(request, username=username, password=password)

            if user is not None:
                logger.info(f"Authentication successful for user: {user.username}")
                if user.is_active:
                    logger.info(f"User {user.username} is active. Logging in.")
                    login(request, user)

                    if user.is_superuser or user.is_staff:
                        messages.success(request, f"Welcome, Admin {user.username}!")
                        return redirect('home') # Or your admin's home
                    elif hasattr(user, 'doctor_profile'):
                        messages.success(request, f"Welcome, Dr. {user.first_name}!")
                        return redirect('home') # Doctor's dashboard
                    elif hasattr(user, 'patient_profile'):
                        messages.success(request, f"Welcome, {user.first_name}!")
                        return redirect('home') # Patient's dashboard
                    else:
                        messages.success(request, f"Welcome, {user.username}!")
                        return redirect('home') # Default if no specific profile
                else:
                    logger.warning(f"User {user.username} is not active.")
                    messages.warning(request, "Your account is not active. Please verify your OTP.")
                    return redirect('verify_otp')
            else:
                logger.warning(f"Authentication failed for username: {username}")
                messages.error(request, "Invalid username or password.")
                return render(request, 'login.html', {'form': form_instance})
        else:
            logger.warning(f"SigninForm is not valid. Errors: {form_instance.errors}")
            messages.error(request, "Please correct the errors below.")
            return render(request, 'login.html', {'form': form_instance})

    def get(self, request):
        logger.info("--- SigninView GET called ---")
        if request.user.is_authenticated:

            if request.user.is_superuser or request.user.is_staff:
                return redirect('all_appointments_dashboard')
            elif hasattr(request.user, 'doctor_profile'):
                return redirect('doctor_appointments_dashboard')
            elif hasattr(request.user, 'patient_profile'):
                return redirect('my_appointments')
            else:
                return redirect('home')
        form_instance = LoginForm()
        return render(request, 'login.html', {'form': form_instance})

class SignOutView(View):
    def get(self, request):
        logout(request)
        messages.info(request, "You have been successfully logged out.")
        return redirect('signin')




class MyAppointmentsView(LoginRequiredMixin, View):
    template_name = 'my_appointments.html'

    def get(self, request):
        user = request.user
        logger.debug(f"MyAppointmentsView: User {user.username} ({user.id}) attempting to access.")


        if user.is_superuser or user.is_staff:
            logger.debug(f"MyAppointmentsView: User is admin/staff, redirecting to all_appointments_dashboard.")
            messages.info(request, "Redirecting to admin dashboard.")
            return redirect('all_appointments_dashboard')
        elif hasattr(user, 'doctor_profile'):
            logger.debug(f"MyAppointmentsView: User is doctor, redirecting to doctor_appointments_dashboard.")
            messages.info(request, "Redirecting to doctor's appointments.")
            return redirect('doctor_appointments_dashboard')

        # Logic for patients
        if hasattr(user, 'patient_profile') and user.patient_profile:
            logger.debug(f"MyAppointmentsView: User {user.username} has patient profile. Fetching appointments.")
            patient = user.patient_profile

            appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date', '-appointment_time')
            context = {
                'appointments': appointments,
                'dashboard_title': 'My Appointments'
            }
            return render(request, self.template_name, context)
        else:
            logger.debug(f"MyAppointmentsView: User {user.username} no patient profile found. Redirecting to my_profile.")
            messages.warning(request, "Please complete your patient profile to view appointments.")
            return redirect('my_profile')


class DoctorAppointmentsView(LoginRequiredMixin, View):
    template_name = 'doctor_appointments.html'

    def get(self, request):
        user = request.user
        logger.debug(f"DoctorAppointmentsView: User {user.username} ({user.id}) attempting to access.")


        if user.is_superuser or user.is_staff:
            logger.debug(f"DoctorAppointmentsView: User is admin/staff, redirecting to all_appointments_dashboard.")
            messages.info(request, "Redirecting to admin dashboard.")
            return redirect('all_appointments_dashboard')
        elif hasattr(user, 'patient_profile'):
            logger.debug(f"DoctorAppointmentsView: User is patient, redirecting to my_appointments.")
            messages.info(request, "Redirecting to your patient appointments.")
            return redirect('my_appointments')


        if hasattr(user, 'doctor_profile') and user.doctor_profile:
            doctor = user.doctor_profile

            logger.debug(f"DoctorAppointmentsView: User {user.username} has doctor profile (ID: {doctor.id}, Name: {doctor.user.get_full_name() if doctor.user else 'N/A'}). Filtering appointments for this doctor.")
            appointments = Appointment.objects.filter(doctor=doctor).order_by('-appointment_date', '-appointment_time')
            logger.debug(f"DoctorAppointmentsView: Found {appointments.count()} appointments for doctor {doctor.user.username}.")
            context = {
                'appointments': appointments,
                'dashboard_title': f"Appointments for Dr. {user.first_name} {user.last_name}"
            }
            return render(request, self.template_name, context)
        else:
            logger.debug(f"DoctorAppointmentsView: User {user.username} no doctor profile found. Redirecting to home.")
            messages.error(request, "You are not authorized to view this page or do not have a doctor profile.")
            return redirect('home')


class AllAppointmentsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'all_appointments.html'

    def test_func(self):

        return self.request.user.is_superuser or self.request.user.is_staff

    def handle_no_permission(self):

        user = self.request.user
        logger.warning(f"AllAppointmentsView: Unauthorized access attempt by {user.username} ({user.id}).")
        messages.error(self.request, "You do not have permission to view all appointments.")

        if not user.is_authenticated:

            return super().handle_no_permission()
        elif hasattr(user, 'doctor_profile'):

            return HttpResponseRedirect(reverse('doctor_appointments_dashboard'))
        elif hasattr(user, 'patient_profile'):

            return HttpResponseRedirect(reverse('my_appointments'))
        else:

            return HttpResponseRedirect(reverse('home'))

    def get(self, request):
        user = request.user
        logger.debug(f"AllAppointmentsView: User {user.username} ({user.id}) accessing (passed test_func).")


        if hasattr(user, 'doctor_profile') and not (user.is_superuser or user.is_staff):
            messages.info(request, "Redirecting to doctor's appointments.")
            return redirect('doctor_appointments_dashboard')
        elif hasattr(user, 'patient_profile') and not (user.is_superuser or user.is_staff):
            messages.info(request, "Redirecting to your patient appointments.")
            return redirect('my_appointments')


        appointments = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')
        context = {
            'appointments': appointments,
            'dashboard_title': 'All Appointments (Admin View)'
        }
        return render(request, self.template_name, context)




class MyProfileView(LoginRequiredMixin, View):
    template_name = 'my_profile.html'

    def get(self, request):
        patient_profile = None
        if hasattr(request.user, 'patient_profile') and request.user.patient_profile:
            patient_profile = request.user.patient_profile

            if 'action' in request.GET and request.GET['action'] == 'edit':
                form = PatientProfileForm(instance=patient_profile)
                return render(request, self.template_name, {
                    'form': form,
                    'user': request.user,
                    'patient_profile': patient_profile,
                    'mode': 'edit'
                })

            return render(request, self.template_name, {
                'user': request.user,
                'patient_profile': patient_profile,
                'mode': 'view'
            })

        elif 'action' in request.GET and request.GET['action'] == 'create':
            form = PatientProfileForm()
            return render(request, self.template_name, {
                'patient_profile': None,
                'form': form,
                'user': request.user,
                'mode': 'create_form'
            })
        else:
            return render(request, self.template_name, {
                'patient_profile': None,
                'user': request.user,
                'mode': 'create_prompt'
            })

    def post(self, request):
        patient_profile = None
        if hasattr(request.user, 'patient_profile') and request.user.patient_profile:
            patient_profile = request.user.patient_profile
            form = PatientProfileForm(request.POST, instance=patient_profile)
        else:
            form = PatientProfileForm(request.POST)

        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, "Your profile has been saved successfully!")
            return redirect('my_profile')
        else:
            messages.error(request, "Please correct the errors below.")
            context = {
                'form': form,
                'user': request.user,
                'patient_profile': patient_profile,
                'mode': 'edit' if patient_profile else 'create_form_with_errors'
            }
            return render(request, self.template_name, context)

class DeleteProfileView(LoginRequiredMixin, View):
    def post(self, request):
        if hasattr(request.user, 'patient_profile') and request.user.patient_profile:
            request.user.patient_profile.delete()
            messages.success(request, "Your profile has been successfully deleted.")
        else:
            messages.info(request, "No profile found to delete.")
        return redirect('my_profile')



razorpay_client = razorpay.Client(auth=("rzp_test_oCeVyBXbBVFero", "fx3Z2TYQfYCbSSY77AQ5C0QY"))

class AppointmentView(View):
    def get(self, request):
        form = AppointmentForm()
        doctors = Doctor.objects.filter(is_available=True)
        departments = Department.objects.all()
        return render(request, 'appointment.html', {
            'form': form,
            'doctors': doctors,
            'departments': departments,
        })

    def post(self, request):
        form = AppointmentForm(request.POST)
        doctors = Doctor.objects.filter(is_available=True)
        departments = Department.objects.all()
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = request.user.patient_profile  # This is correct
            appointment.amount = 500  # Fixed consultation fee
            appointment.save()
            return redirect('appointment_payment', appointment_id=appointment.id)
        return render(request, 'appointment.html', {
            'form': form,
            'doctors': doctors,
            'departments': departments,
        })


class AppointmentPaymentView(View):
    def get(self, request, appointment_id):
        appointment = Appointment.objects.get(id=appointment_id)
        payment = razorpay_client.order.create({
            'amount': appointment.amount * 100,  # Razorpay expects paise
            'currency': 'INR',
            'payment_capture': '1'
        })

        appointment.order_id = payment['id']
        appointment.save()

        context = {
            'appointment': appointment,
            'payment': payment,
            'user': request.user,
        }
        return render(request, 'appointment_payment.html', context)


@method_decorator(csrf_exempt, name='dispatch')
class AppointmentPaymentSuccessView(View):
    def post(self, request, appointment_id):
        appointment = Appointment.objects.get(id=appointment_id)
        appointment.is_paid = True
        appointment.status = 'Confirmed'
        appointment.save()
        messages.success(request, "Payment successful. Your appointment is confirmed!")
        return render(request, 'payment_success..html')


class DeleteAppointmentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)


        try:

            appointment.delete()
            messages.success(request, f"Appointment (ID: {pk}) successfully deleted.")
        except Exception as e:
            messages.error(request, f"Error deleting appointment (ID: {pk}): {e}")

        user = request.user
        if user.is_superuser or user.is_staff:
            return redirect('all_appointments_dashboard')
        elif hasattr(user, 'doctor_profile'):
            return redirect('doctor_appointments_dashboard')
        else: # Assumed patient or other user
            return redirect('my_appointments')



logger = logging.getLogger(__name__)

# SpaCy NLP Model Loading (Global Scope)
hospital_nlp = None
try:
    hospital_nlp = spacy.load("en_core_web_sm")
    logger.info("spaCy model 'en_core_web_sm' loaded successfully for Hospital Bot.")
except OSError:
    logger.error(
        "spaCy model 'en_core_web_sm' not found for Hospital Bot. Please run 'python -m spacy download en_core_web_sm'")
    hospital_nlp = None
except Exception as e:
    logger.error(f"An unexpected error occurred while loading spaCy model: {e}")
    hospital_nlp = None


# Chatbot
HOSPITAL_INTENTS_DATA_PATH = os.path.join(settings.BASE_DIR, 'medical', 'hospital_intents.json')
hospital_intents = []
hospital_vectorizer = None
hospital_clf = None

try:
    with open(HOSPITAL_INTENTS_DATA_PATH, 'r', encoding='utf-8') as f:
        hospital_intents = json.load(f)
    logger.info(
        f"Hospital Bot intents loaded successfully from {HOSPITAL_INTENTS_DATA_PATH}. {len(hospital_intents)} intents found.")

    hospital_training_sentences = []
    hospital_training_labels = []
    for intent in hospital_intents:
        for pattern in intent['patterns']:
            hospital_training_sentences.append(pattern.lower())
            hospital_training_labels.append(intent['tag'])

    if hospital_training_sentences:
        hospital_vectorizer = TfidfVectorizer()
        X_train_hospital = hospital_vectorizer.fit_transform(hospital_training_sentences)
        hospital_clf = LinearSVC()
        hospital_clf.fit(X_train_hospital, hospital_training_labels)
        logger.info("Hospital Bot intent model trained successfully.")
    else:
        logger.warning(
            "WARNING: No training sentences found for Hospital Bot intents. Intent recognition will not work.")

except FileNotFoundError:
    logger.error(f"ERROR: {HOSPITAL_INTENTS_DATA_PATH} not found. Hospital Bot intent recognition will be limited.")
    hospital_intents = []
except json.JSONDecodeError as e:
    logger.error(f"ERROR: Could not decode JSON from {HOSPITAL_INTENTS_DATA_PATH}. Check file format. Error: {e}")
    hospital_intents = []
except Exception as e:
    logger.error(f"ERROR: An unexpected error occurred during Hospital Bot model loading/training: {e}")
    import traceback

    traceback.print_exc()



def get_safe_reverse_url(url_name, *args, **kwargs):
    """
    Safely attempts to reverse a URL name.
    Returns '#' if NoReverseMatch error occurs to prevent 500 errors.
    """
    try:
        return reverse(url_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        logger.error(f"NoReverseMatch error: URL name '{url_name}' not found in urls.py. Returning '#' as fallback.")
        return "#"



def _get_hospital_bot_response_logic(user_message_str):
    user_message_lower = user_message_str.lower().strip()

    predicted_tag = "fallback"

    confidence_threshold = -0.5

    if hospital_clf and hospital_vectorizer:
        user_message_vectorized = hospital_vectorizer.transform([user_message_lower])
        confidence_scores = hospital_clf.decision_function(user_message_vectorized)
        if confidence_scores.size > 0:
            max_score_index = confidence_scores[0].argmax()
            highest_confidence = confidence_scores[0][max_score_index]
            potential_tag = hospital_clf.classes_[max_score_index]

            logger.debug(
                f"Hospital Bot DEBUG: Potential tag: {potential_tag}, Highest Confidence Score: {highest_confidence:.2f}")

            if highest_confidence > confidence_threshold:
                predicted_tag = potential_tag
            else:
                predicted_tag = "fallback"
        else:
            logger.warning("No confidence scores generated. Falling back.")
            predicted_tag = "fallback"
        logger.debug(f"Predicted intent after threshold: {predicted_tag} for message: '{user_message_lower}'")
    else:
        logger.warning("WARNING: Hospital Bot model not loaded/trained. Falling back to simple keyword matching.")
        if any(kw in user_message_lower for kw in ["hi", "hello", "hey"]):
            predicted_tag = "greeting"
        elif any(kw in user_message_lower for kw in ["bye", "goodbye", "see you"]):
            predicted_tag = "farewell"
        elif any(kw in user_message_lower for kw in ["appointment", "book appointment"]):
            predicted_tag = "appointment_query"
        elif any(kw in user_message_lower for kw in ["department", "specialty"]):
            predicted_tag = "department_query"
        elif any(kw in user_message_lower for kw in ["doctor", "physician"]):
            predicted_tag = "doctor_query"
        elif any(kw in user_message_lower for kw in ["service", "treatment"]):
            predicted_tag = "service_query"
        elif any(kw in user_message_lower for kw in ["address", "location", "where are you"]):
            predicted_tag = "hospital_address"
        elif any(kw in user_message_lower for kw in ["contact", "phone", "email"]):
            predicted_tag = "hospital_contact"
        elif any(kw in user_message_lower for kw in ["fee", "cost", "charge"]):
            predicted_tag = "consultation_fee"
        elif any(kw in user_message_lower for kw in ["hour", "open", "timing"]):
            predicted_tag = "operating_hours"
        elif any(kw in user_message_lower for kw in ["about", "what can you do", "who are you"]):
            predicted_tag = "about_bot"


    response_text = "I'm sorry, I couldn't find a suitable response. Can you rephrase that?"

    if predicted_tag in ["greeting", "farewell", "thanks", "hospital_address", "hospital_contact",
                         "operating_hours", "consultation_fee", "about_hospital",
                         "about_bot", "symptom_advice", "fallback"]:
        for intent in hospital_intents:
            if intent['tag'] == predicted_tag:
                return random.choice(intent['responses'])

    elif predicted_tag == "appointment_query":
        appointment_url = get_safe_reverse_url('appointment')
        return f"You can book an appointment online through our <a href='{appointment_url}' target='_parent'>appointment page</a>. The standard consultation fee is ₹500."

    elif predicted_tag == "department_query":
        found_dept_obj = None
        user_message_lower = user_message_str.lower().strip()

        general_listing_keywords = ["list departments", "departments", "what departments do you have",
                                    "which departments are available", "tell me about departments", "all departments"]

        if user_message_lower in general_listing_keywords or user_message_lower == "departments":
            departments = Department.objects.all()
            if departments.exists():
                dept_names = [d.name for d in departments]

                departments_list_url = get_safe_reverse_url('department')
                return (f"We have departments like: " + ", ".join(dept_names) +
                        f". Which one are you interested in? You can also view all departments on our "
                        f"<a href='{departments_list_url}' target='_parent'>Departments page</a>.")
            else:
                return "I'm sorry, I don't have information on specific departments right now. Please check our 'Departments' page."

        if hospital_nlp:
            doc = hospital_nlp(user_message_lower)
            potential_department_names = []

            for ent in doc.ents:
                if ent.label_ in ["ORG", "NORP", "PRODUCT"] or "department" in ent.text.lower():
                    cleaned_name = ent.text.lower().replace("department", "").strip()
                    if cleaned_name and cleaned_name not in ["the", "your", "our"]:
                        potential_department_names.append(cleaned_name)

            for token in doc:
                if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 2:
                    potential_department_names.append(token.text.lower())

            potential_department_names = list(set(potential_department_names))

            for p_name in potential_department_names:
                dept_matches = Department.objects.filter(name__icontains=p_name).first()
                if dept_matches:
                    found_dept_obj = dept_matches
                    break

        if not found_dept_obj:
            for dept in Department.objects.all():
                if user_message_lower == dept.name.lower() or \
                        (dept.name.lower() in user_message_lower and len(dept.name.split()) > 1) or \
                        (user_message_lower in dept.name.lower() and len(user_message_lower.split()) > 1):
                    found_dept_obj = dept
                    break

        if found_dept_obj:
            services = found_dept_obj.services.all()
            services_list = ", ".join(
                [s.title for s in services]) if services.exists() else "no specific services listed."
            return (f"Our {found_dept_obj.name} Department specializes in {found_dept_obj.description}. "
                    f"Some services offered include: {services_list}.")
        else:
            departments = Department.objects.all()
            if departments.exists():
                dept_names = [d.name for d in departments]

                departments_list_url = get_safe_reverse_url('department')
                return (f"We have departments like: " + ", ".join(dept_names) +
                        f". Which one are you interested in? You can also view all departments on our "
                        f"<a href='{departments_list_url}' target='_parent'>Departments page</a>.")
            else:
                return "I'm sorry, I don't have information on specific departments right now. Please check our 'Departments' page."

    elif predicted_tag == "doctor_query":
        found_doctor_obj = None
        user_message_lower = user_message_str.lower().strip()

        if hospital_nlp:
            doc = hospital_nlp(user_message_lower)
            potential_names = []

            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    potential_names.append(ent.text)

            for token in doc:
                if token.text.lower().startswith("dr."):
                    potential_names.append(token.text.lower().replace("dr.", "").strip())
                elif token.pos_ in ["PROPN", "NOUN"] and len(token.text) > 2:
                    potential_names.append(token.text.lower())
            potential_names = list(set(potential_names))

            for p_name in potential_names:
                doctor_matches = Doctor.objects.filter(
                    Q(user__first_name__icontains=p_name) |
                    Q(user__last_name__icontains=p_name) |
                    Q(name__icontains=p_name)
                ).first()
                if doctor_matches:
                    found_doctor_obj = doctor_matches
                    break

        specialization_match = None
        user_words = user_message_lower.split()

        if "cardiologist" in user_words or "cardiology" in user_words or "heart" in user_words:
            specialization_match = 'Cardiology'
        elif "surgical" in user_words or "surgeon" in user_words or "surgery" in user_words:
            specialization_match = 'Surgical'
        elif "neurologist" in user_words or "neurology" in user_words or "brain" in user_words:
            specialization_match = 'Neurology'
        elif "dentist" in user_words or "dental" in user_words or "teeth" in user_words:
            specialization_match = 'Dental'
        elif "ophthalmologist" in user_words or "ophthalmology" in user_words or "eye" in user_words:
            specialization_match = 'Ophthalmology'
        elif "general physician" in user_message_lower or "gp" in user_message_lower or "family doctor" in user_message_lower:
            specialization_match = 'General Practitioner'
        elif "pediatrician" in user_words or "child" in user_words or "children" in user_words:
            specialization_match = 'Pediatrics'
        elif "diabetes" in user_words or "diabetic" in user_words:
            specialization_match = 'Endocrinology'

        if found_doctor_obj:
            full_doctor_name = f"Dr. {found_doctor_obj.user.first_name} {found_doctor_obj.user.last_name}" if found_doctor_obj.user else found_doctor_obj.name
            specialization = found_doctor_obj.specialization.name if found_doctor_obj.specialization else 'General Practitioner'
            experience = f"{found_doctor_obj.experience_years} years of experience." if hasattr(found_doctor_obj,
                                                                                                'experience_years') else ''
            qualification = f"Qualification: {found_doctor_obj.qualification}." if hasattr(found_doctor_obj,
                                                                                           'qualification') else ''


            doctor_detail_url = get_safe_reverse_url('doctor_detail', args=[found_doctor_obj.id])
            if doctor_detail_url == "#":

                doctor_detail_url = get_safe_reverse_url('doctor')

            return (f"{full_doctor_name} is a {specialization}. {experience} {qualification} "
                    f"You can find more details on our <a href='{doctor_detail_url}' target='_parent'>Doctors page</a>.")
        elif specialization_match:
            doctors_by_spec = Doctor.objects.filter(
                specialization__name__icontains=specialization_match).select_related('specialization')
            if doctors_by_spec.exists():
                doctor_names = [f"Dr. {d.user.first_name} {d.user.last_name}" for d in doctors_by_spec]

                doctors_list_url = get_safe_reverse_url('doctor')
                return (f"We have {specialization_match} specialists including: " + ", ".join(doctor_names) +
                        f". Would you like details on a specific doctor? You can find more details on our "
                        f"<a href='{doctors_list_url}' target='_parent'>Doctors page</a>.")
            else:

                doctors_list_url = get_safe_reverse_url('doctor')
                return (f"I'm sorry, I don't have information on {specialization_match} specialists at the moment, or that specialization is not listed. "
                        f"Please check our <a href='{doctors_list_url}' target='_parent'>Doctors page</a>.")
        else:
            doctors = Doctor.objects.all().select_related('specialization')
            if doctors.exists():
                doctor_names = [
                    f"Dr. {d.user.first_name} {d.user.last_name} ({d.specialization.name if d.specialization else 'General'})"
                    for d in doctors]

                doctors_list_url = get_safe_reverse_url('doctor')
                return (f"Our doctors include: " + ", ".join(doctor_names) +
                        f". Who are you looking for? You can find more details on our "
                        f"<a href='{doctors_list_url}' target='_parent'>Doctors page</a>.")
            else:

                doctors_list_url = get_safe_reverse_url('doctor')
                return (f"I'm sorry, I don't have information on specific doctors right now. Please check our "
                        f"<a href='{doctors_list_url}' target='_parent'>Doctors page</a>.")

    elif predicted_tag == "service_query":
        found_service_obj = None
        user_message_lower = user_message_str.lower().strip()

        general_listing_phrases = [
            "services", "all services", "your services", "what services", "list services",
            "tell me about services", "what kind of treatments", "treatments available",
            "general services", "asking about services", "what are your medical services",
            "all treatments"
        ]

        is_general_query = False
        if user_message_lower in general_listing_phrases:
            is_general_query = True
        elif any(phrase in user_message_lower for phrase in general_listing_phrases if len(phrase) > 1):
             is_general_query = True
        elif "what are your" in user_message_lower and "service" in user_message_lower:
            is_general_query = True

        if is_general_query:
            services = DepartmentService.objects.all()
            if services.exists():
                service_names = [s.title for s in services]

                services_list_url = get_safe_reverse_url('department_service')
                return (f"We offer services like: " + ", ".join(service_names) +
                        f". What specific service are you interested in? You can also view all services on our "
                        f"<a href='{services_list_url}' target='_parent'>Services page</a>.")
            else:
                return "I'm sorry, I don't have information on specific services right now. Please check our 'Department Services' page."

        if hospital_nlp:
            doc = hospital_nlp(user_message_lower)
            potential_terms = [ent.text.lower() for ent in doc.ents if ent.label_ in ["ORG", "NORP", "PRODUCT"]] + \
                              [token.lemma_.lower() for token in doc if token.pos_ in ["NOUN", "PROPN"]]
            potential_terms = list(set(potential_terms))

            for term in potential_terms:
                for service in DepartmentService.objects.all():
                    if term in service.title.lower() or service.title.lower() in term:
                        found_service_obj = service
                        break
                if found_service_obj:
                    break

            if not found_service_obj:
                for service in DepartmentService.objects.all():
                    if user_message_lower == service.title.lower() or \
                       (user_message_lower in service.title.lower() and len(user_message_lower) > 3) or \
                       (service.title.lower() in user_message_lower and len(service.title.lower()) > 3):
                        found_service_obj = service
                        break
                    if not found_service_obj and user_message_lower in service.description.lower() and len(user_message_lower) > 3:
                        found_service_obj = service
                        break

        if found_service_obj:
            department_name = found_service_obj.department.name if found_service_obj.department else 'a general'
            return (
                f"{found_service_obj.title} is a service offered by our {department_name} department. "
                f"It involves {found_service_obj.description}.")
        else:
            services = DepartmentService.objects.all()
            if services.exists():
                service_names = [s.title for s in services]

                services_list_url = get_safe_reverse_url('department_service')
                return (f"We offer services like: " + ", ".join(service_names) +
                        f". What specific service are you interested in? You can also view all services on our "
                        f"<a href='{services_list_url}' target='_parent'>Services page</a>.")
            else:
                return "I'm sorry, I don't have information on specific services right now. Please check our 'Department Services' page."

    elif predicted_tag == "user_profile_query":

        patient_portal_url = get_safe_reverse_url('my_profile')
        return ("I am an AI chatbot and cannot access your personal profile or appointment details directly for security and privacy reasons. "
                "Please log in to your patient portal on our website "
                f"<a href='{patient_portal_url}' target='_parent'>here</a> to view your information.")

    return response_text


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_exempt, name='dispatch')
class ChatbotView(View):
    def get(self, request):
        return render(request, 'chatbot_interface.html')

    def post(self, request):
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            logger.info(f"Hospital Bot: Received message from user: '{user_message}'")

            chatbot_response_text = _get_hospital_bot_response_logic(user_message)

            logger.info(f"Hospital Bot: Generated response: '{chatbot_response_text}'")
            return JsonResponse({'response': chatbot_response_text})
        except json.JSONDecodeError:
            logger.error("Hospital Bot: Invalid JSON in request body.")
            return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
        except Exception as e:
            logger.error(f"Hospital Bot: An internal server error occurred in ChatbotView post method: {e}",
                         exc_info=True)
            return JsonResponse({'error': f'An internal server error occurred: {e}'}, status=500)
