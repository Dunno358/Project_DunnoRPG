from django import forms
from django.test import TestCase
from DunnoRPG.forms import CharacterForm
from django.contrib.auth.models import User
    
    
class CharacterFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_user1', password='test_password1')
        self.form_data = {
            'owner': 'test_user1',
            'name': 'test_char1',
            'race': 'Niziołek',
            'size': 'M',
            'HP': '25',
            'INT': '2',
            'SIŁ': '5',
            'ZRE': '3',
            'CHAR': '4',
            'CEL': '6'
        }
        
    def test_form_valid(self):
        form = CharacterForm(data=self.form_data,user=self.user)
        self.assertTrue(form.is_valid())
        
    def test_form_invalid(self):
        form_data = self.form_data.copy()
        form_data['name'] = ''
        form = CharacterForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        
    def test_form_save(self):
        form = CharacterForm(data=self.form_data,user=self.user)
        self.assertTrue(form.is_valid())
        character = form.save()
        
        self.assertEqual(character.name, 'test_char1')
        self.assertEqual(character.owner, 'test_user1')
        self.assertEqual(character.race, 'Niziołek')
        self.assertEqual(character.size, 'M')
        
    def test_labels(self):
        form = CharacterForm(data=self.form_data,user=self.user) 
        self.assertEqual(form.fields['INT'].label, '(+0) INT:')
        self.assertEqual(form.fields['SIŁ'].label, '(+0) SIŁ:')
        self.assertEqual(form.fields['ZRE'].label, '(+0) ZRE:')
        self.assertEqual(form.fields['CHAR'].label, '(+0) CHAR:')
        self.assertEqual(form.fields['CEL'].label, '(+0) CEL:')
        
    def test_fields_widgets(self):
        form = CharacterForm(data=self.form_data, user=self.user)
        self.assertIsInstance(form.fields['owner'].widget, forms.TextInput)
        self.assertIsInstance(form.fields['name'].widget, forms.TextInput)
        self.assertIsInstance(form.fields['race'].widget, forms.Select)
        self.assertIsInstance(form.fields['size'].widget, forms.TextInput)
        self.assertIsInstance(form.fields['HP'].widget, forms.TextInput)
        self.assertIsInstance(form.fields['INT'].widget, forms.NumberInput)
        self.assertIsInstance(form.fields['SIŁ'].widget, forms.NumberInput)
        self.assertIsInstance(form.fields['ZRE'].widget, forms.NumberInput)
        self.assertIsInstance(form.fields['CHAR'].widget, forms.NumberInput)
        self.assertIsInstance(form.fields['CEL'].widget, forms.NumberInput)
        
        self.assertEqual(form.fields['owner'].widget.attrs, {
        'value': 'owner will be added automatically',
        'class': 'text-center ms-1 invisible',
        'maxlength': '100'
    })
        
        self.assertEqual(form.fields['name'].widget.attrs, {
        'placeholder': "Character's name",
        'class': 'ms-2 text-center rounded',
        'maxlength': '100'
    })
        
        self.assertEqual(form.fields['race'].widget.attrs, {
        'class': 'text-center border border-warning bg-dark text-white-50 rounded'
    })
        
        self.assertEqual(form.fields['size'].widget.attrs, {
        'value': 'M',
        'class': 'text-center ms-5 invisible bg-transparent w-25',
        'maxlength': '50'
    })
        
        self.assertEqual(form.fields['HP'].widget.attrs, {
        'value': 25,
        'class': 'w-25 ms-3 invisible',
        'maxlength': '5'
    })
        
        self.assertEqual(form.fields['INT'].widget.attrs, {
        'class': 'w-25 ms-3 text-center rounded',
        'value': 0,
        'min': 0
    })
        
        self.assertEqual(form.fields['SIŁ'].widget.attrs, {
        'class': 'w-25 ms-3 text-center rounded',
        'value': 0,
        'min': 0
    })
        
        self.assertEqual(form.fields['ZRE'].widget.attrs, {
        'class': 'w-25 ms-2 text-center rounded',
        'value': 0,
        'min': 0
    })
        
        self.assertEqual(form.fields['CHAR'].widget.attrs, {
        'class': 'w-25 text-center rounded',
        'value': 0,
        'min': 0
    })
        
        self.assertEqual(form.fields['CEL'].widget.attrs, {
        'class': 'w-25 ms-2 text-center rounded',
        'value': 0,
        'min': 0
    })
    