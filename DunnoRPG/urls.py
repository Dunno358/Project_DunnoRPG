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
    path('character_add_skills/<char_id>/upgrade/<skill_id>', views.skill_upgrade, name='skill_upgrade'),
    path('character_add_skills/<char_id>/downgrade/<skill_id>', views.skill_downgrade, name='skill_downgrade'),
    path('guest/', views.log_as_guest, name='log_as_guest'),
    path('gmpanel/', views.GMPanel.as_view(), name='gm_panel'),
    path('info/', views.Info.as_view(), name='info'),
    path('info/acc-rules/', views.AccRules.as_view(), name='info_acc_rules')
]

urlpatterns = format_suffix_patterns(urlpatterns)