from django.urls import path
from . import views

urlpatterns = [
    path('dunnorpg/',views.dunnorpg, name='DunnoRPG')
]