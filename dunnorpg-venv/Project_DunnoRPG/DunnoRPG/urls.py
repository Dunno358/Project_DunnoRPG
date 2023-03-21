from django.urls import path
from . import views

urlpatterns = [
    path('dunnorpg/',views.register_view, name='DunnoRPG')
]