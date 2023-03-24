from django.http import HttpResponse
from django.template import loader
from .models import Users

def register_view(request):
    users = Users.objects.all().values()
    template = loader.get_template('register.html')
    context = {
        'users': users,
    }
    return HttpResponse(template.render(context, request))

# Create your views here.
