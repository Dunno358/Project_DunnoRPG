from django.urls import path
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.home, name = "home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
]