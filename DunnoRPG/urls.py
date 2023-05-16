from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.charGET.as_view(), name = "home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
    path('character_detail/<id>/', views.CharacterDetails.as_view(), name='character_detail'),
    path('character_add', views.charPOST.as_view(), name="character_add"),
    path('character_add_skills/<id>/', views.CharacterSkills.as_view(), name="character_add_skills"),
    path('skills/', views.Skills.as_view(), name='skills'),
    path('skills/<id>/', views.SkillDetail.as_view(), name='skill_detail'),
    path('character_add_skills/<char_id>/delete/<skill_id>', views.skill_delete, name='skill_delete'),
    path('guest/', views.log_as_guest, name='log_as_guest'),
    path('gmpanel/', views.GMPanel.as_view(), name='gm_panel')
]

urlpatterns = format_suffix_patterns(urlpatterns)