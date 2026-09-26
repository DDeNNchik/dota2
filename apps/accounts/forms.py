from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Hero, Profile, Role

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label='Email', required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        labels = {
            'username': 'Имя пользователя',
            'password1': 'Пароль',
            'password2': 'Повторите пароль',
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Аккаунт с таким email уже существует.')
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            'avatar', 'description', 'country', 'age', 'dota_nickname', 'steam_id',
            'preferred_roles', 'favorite_heroes', 'microphone_available', 'availability', 'timezone',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Расскажите, какого тиммейта вы ищете…'}),
            'country': forms.TextInput(attrs={'placeholder': 'Например, Украина'}),
            'dota_nickname': forms.TextInput(attrs={'placeholder': 'Ваш никнейм в Dota 2'}),
            'steam_id': forms.URLInput(attrs={'placeholder': 'https://steamcommunity.com/id/...'}),
            'preferred_roles': forms.CheckboxSelectMultiple(),
            'favorite_heroes': forms.CheckboxSelectMultiple(),
            'availability': forms.TextInput(attrs={'placeholder': 'Например, будни после 19:00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_roles'].queryset = Role.objects.all()
        self.fields['favorite_heroes'].queryset = Hero.objects.all()

    def clean_steam_id(self):
        steam_id = self.cleaned_data['steam_id'].strip()
        if steam_id and not steam_id.startswith('https://steamcommunity.com/'):
            raise forms.ValidationError('Укажите ссылку на профиль Steam Community.')
        return steam_id
