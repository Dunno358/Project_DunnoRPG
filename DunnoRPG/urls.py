from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.charGET.as_view(), name = "home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
    
    path('character_detail/<int:id>/', views.CharacterDetails.as_view(), name='character_detail'),
    path('character_detail/<int:char_id>/move_eq-<int:item_id>', views.MoveItemToEq.as_view(), name='move_item_to_eq'),
    path('character_detail/<int:char_id>/<int:item_id>;<str:place>', views.char_wear_item, name='wear_item'),
    path('character_detail/<int:char_id>/<int:it1_id>-<int:it2_id>', views.char_swap_item, name='swap_item'),
    path('character_add', views.charPOST.as_view(), name="character_add"),
    path('character_add_skills/<id>/', views.CharacterSkills.as_view(), name="character_add_skills"),
    
    path('skills/', views.Skills.as_view(), name='skills'),
    path('skills/<id>/', views.SkillDetail.as_view(), name='skill_detail'),
    
    path('character_add_skills/<char_id>/delete/<skill_id>', views.skill_delete, name='skill_delete'),
    path('character_add_skills/<char_id>/upgrade/<skill_id>', views.skill_upgrade, name='skill_upgrade'),
    path('character_add_skills/<char_id>/downgrade/<skill_id>', views.skill_downgrade, name='skill_downgrade'),
    
    path('character_add_skills/<int:char_id>/up/<str:stat>', views.UpgradeCharacterStats.as_view(), name='stat-upgrade'),
    path('character_add_skills/<int:char_id>/down/<str:stat>', views.DowngradeCharacterStats.as_view(), name='stat-downgrade'),

    path('char-delete/<int:char_id>', views.DeleteCharacter.as_view(), name='delete_character'),
    
    path('items/ch<int:char_id>', views.ItemsView.as_view(), name='items'),
    path('items/<int:char_id>del<int:obj_id>', views.del_eq_item, name='del_eq_item'),
    path('items/<int:id>', views.ItemDetailView.as_view(), name='item_detail'),
    
    path('items/setFound-<int:id>-<int:state>-<int:char_id>', views.changeItemFoundState.as_view(), name='change_found_state'),
    
    path('guest/', views.log_as_guest, name='log_as_guest'),
    path('gmpanel/', views.GMPanel.as_view(), name='gm_panel'),
    
    path('info/', views.Info.as_view(), name='info'),
    path('info/acc-rules/', views.AccRules.as_view(), name='info_acc_rules'),
    path('makerequest/<int:char_id>;<str:model>;<str:objects_model>;<int:object1_id>;<int:object2_id>;<str:field>;<str:title>;<str:to_reverse>', views.makeRequest.as_view(), name='make_request'),
    path('gmpanel/rq<int:rq_id>-<int:status>-<int:all>', views.RequestHandling.as_view(), name='handling_request'),
    
    path('info/effects/', views.InfoEffects.as_view(), name='info_effects')
]

urlpatterns = format_suffix_patterns(urlpatterns)

handler404 = "DunnoRPG.views.view_404"