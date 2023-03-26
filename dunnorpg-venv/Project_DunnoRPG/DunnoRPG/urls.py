from django.urls import path
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.home, name = "home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
    path('character_detail/<id>/', views.character_detail, name='character_detail'),
    path('character_add', views.character_add, name="character_add")
]