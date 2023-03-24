from django.template import loader
from django.shortcuts import render, redirect
from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponse
from .models import Users
from .forms import RegisterForm

def register_view(request):
    template = loader.get_template('register.html')
    context = {}

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user

    form = RegisterForm()
    return HttpResponse(template.render(context, request))

"""            body = {
                'name': form.cleaned_data['name'],
                'password': form.cleaned_data['password'],
                'role': form.cleaned_data['role']
            }"""

# Create your views here.
