from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views
#from .views import home,SignUp

urlpatterns = [
    path('', views.charGET.as_view(), name = "home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
    
    path('character_detail/<int:id>/', views.CharacterDetails.as_view(), name='character_detail'),
    path('character_detail/<int:char_id>/changedur-<int:item_id>', views.change_item_durability, name='change_item_durability'),
    path('character_detail/<int:char_id>/change-coins', views.change_coins, name='change_coins'),
    path('character_detail/<int:char_id>/change-health', views.change_health, name='change_health'),
    path('character_detail/<int:char_id>/use-skill/<int:skill_id>', views.char_use_skill, name='use_skill'),
    path('character_detail/<int:char_id>/move_eq-<int:item_id>', views.MoveItemToEq.as_view(), name='move_item_to_eq'),
    path('character_detail/<int:char_id>/take_dur-<int:item_id>', views.TakeItemDurFromAttack.as_view(), name='take_attack_dur_from_item'),
    path('character_detail/<int:char_id>/take_ammo-<int:item_id>-<int:item_amount>', views.TakeAmmoFromAttack.as_view(), name='take_ammo_from_attack'),
    path('character_detail/<int:char_id>/calculate_hit-<int:dmg>-<int:ap>-<str:parts>-<int:multiplier>-<str:final_multiplier>', views.calculateGettingHit.as_view(), name='calculate_getting_hit'),
    path('character_detail/<int:char_id>/<int:item_id>;<str:place>', views.char_wear_item, name='wear_item'),
    path('character_detail/<int:char_id>/<int:it1_id>-<int:it2_id>', views.char_swap_item, name='swap_item'),
    path('character_detail/<int:char_id>/swap_side/<str:hand>', views.swap_side_to_hand, name='swap_side'),
    path('character_add', views.charPOST.as_view(), name="character_add"),
    path('character_add_skills/<id>/', views.CharacterSkills.as_view(), name="character_add_skills"),
    
    path('skills/', views.Skills.as_view(), name='skills'),
    path('skills/<id>/', views.SkillDetail.as_view(), name='skill_detail'),
    
    path('character_add_skills/<char_id>/delete/<skill_id>', views.skill_delete, name='skill_delete'),
    path('character_add_skills/<char_id>/upgrade/<skill_id>', views.skill_upgrade, name='skill_upgrade'),
    path('character_add_skills/<char_id>/downgrade/<skill_id>', views.skill_downgrade, name='skill_downgrade'),
    
    path('character_add_skills/<int:char_id>/up/<str:stat>', views.UpgradeCharacterStats.as_view(), name='stat-upgrade'),
    path('character_add_skills/<int:char_id>/down/<str:stat>', views.DowngradeCharacterStats.as_view(), name='stat-downgrade'),
    path('character_add_skills/<int:char_id>/change_owner', views.char_change_owner, name='char_change_owner'),

    path('char-delete/<int:char_id>', views.DeleteCharacter.as_view(), name='delete_character'),
    
    path('items/ch<int:char_id>', views.ItemsView.as_view(), name='items'),
    path('items/<int:char_id>del<int:obj_id>-<int:amount>', views.del_eq_item, name='del_eq_item'),
    path('items/sell<int:item_id>;<int:char_id>;<int:mod>;<int:amount>', views.sell_item, name='sell_item'),
    path('items/give<int:item_id>;<int:from_char>;<int:to_char>;<int:amount>', views.give_item, name='give_item'),
    path('items/<int:id>', views.ItemDetailView.as_view(), name='item_detail'),
    path('items/setFound-<int:id>-<int:state>-<int:char_id>', views.changeItemFoundState.as_view(), name='change_found_state'),
    
    path('guest/', views.log_as_guest, name='log_as_guest'),
    path('gmpanel/', views.GMPanel.as_view(), name='gm_panel'),
    path('gmpanel/end_round', views.end_round, name='end_round'),
    path('gmpanel/add_effect', views.AddEffect.as_view(), name='add_effect'),
    path('gmpanel/reset-skills/<str:mode>', views.reset_skills, name='reset_skills'),
    
    path('info/', views.Info.as_view(), name='info'),
    path('info/acc-rules/', views.AccRules.as_view(), name='info_acc_rules'),
    path('city/', views.CityView.as_view(), name='city_view'),
    path('city/buyitem-<int:item_id>-<int:character_id>-<int:amount>', views.BuyItem.as_view(), name='buy_item'),
    path('city/<int:char_id>h<int:val>', views.healCharacter.as_view(), name='heal_character'),
    path('city/fixitem', views.fix_item, name='fix_item'),
    path('makerequest/<int:char_id>;<str:model>;<str:objects_model>;<int:object1_id>;<int:object2_id>;<str:field>;<str:title>;<str:to_reverse>;<int:amount>', views.makeRequest.as_view(), name='make_request'),
    path('gmpanel/rq<int:rq_id>-<int:status>-<int:all>', views.RequestHandling.as_view(), name='handling_request'),
    
    path('info/classes/<int:id>', views.ClassView.as_view(), name='class_info'),
    path('info/classes/', views.ClassesView.as_view(), name='classes'),
    
    path('info/races/<int:id>', views.RaceView.as_view(), name='race_info'),
    path('info/races/', views.RacesView.as_view(), name='races'),

    path('info/effects/', views.InfoEffects.as_view(), name='info_effects'),
    
    path('update_field/<int:id>', views.update_field, name='update_field')
]

urlpatterns = format_suffix_patterns(urlpatterns)

handler404 = "DunnoRPG.views.view_404"