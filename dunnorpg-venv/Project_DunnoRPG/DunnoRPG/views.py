from django.http import HttpResponse
from django.template import loader

def register_view(request):
    template = loader.get_template('register.html')
    return HttpResponse(template.render())

# Create your views here.
