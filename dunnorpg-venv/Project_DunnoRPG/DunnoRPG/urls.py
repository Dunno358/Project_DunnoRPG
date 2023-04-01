from django.urls import path
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.home, name = "home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
    path('character_detail/<id>/', views.character_detail, name='character_detail'),
    path('character_add', views.character_add, name="character_add"),
    path('character_add_skills/<id>/', views.character_add_skills, name="character_add_skills"),
    path('skills/', views.skills, name='skills'),
    path('skills/<id>/', views.skill_detail, name='skill_detail')
]