from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.home.as_view(), name = "home"),
    #path('', views.home, name = "home"),

    path("signup/", views.SignUp.as_view(), name="signup"),
    path('character_detail/<id>/', views.character_detail, name='character_detail'),

    path('character_add', views.character_add, name="character_add"),

    path('character_edit/<id>', views.character_edit, name="character_edit"),
    path('character_add_skills/<id>/', views.character_add_skills, name="character_add_skills"),
    path('skills/', views.skills, name='skills'),
    path('skills/<id>/', views.skill_detail, name='skill_detail'),
    path('character_add_skills/<char_id>/delete/<skill_id>', views.skill_delete, name='skill_delete'),
    
    path('rest_test',views.rest_test.as_view(),name='rest_test')
]

urlpatterns = format_suffix_patterns(urlpatterns)