import re

from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.hashers import check_password
from django.utils import timezone

from .constants import SUPERADMIN_CEDULA
from .models import Clientes


def latest_eligible_birth_date(today=None):
    today = today or timezone.localdate()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:
        return today.replace(year=today.year - 18, day=28)


def validate_strong_password(password):
    requirements = (
        (len(password) >= 16, 'La contraseña debe tener al menos 16 caracteres.'),
        (re.search(r'[A-Z]', password), 'Debe contener al menos una letra mayúscula.'),
        (re.search(r'[a-z]', password), 'Debe contener al menos una letra minúscula.'),
        (re.search(r'[0-9]', password), 'Debe contener al menos un número.'),
        (re.search(r'[!@#$%^&*(),.?":{}|<>]', password), 'Debe contener al menos un carácter especial.'),
    )
    for is_valid, message in requirements:
        if not is_valid:
            raise forms.ValidationError(message)
    return password


class LoginForm(forms.Form):
    cedula = forms.CharField(max_length=50)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    captcha = CaptchaField(label='Verificación de seguridad')

    def clean_cedula(self):
        cedula = self.cleaned_data['cedula'].strip()
        if cedula != SUPERADMIN_CEDULA and not re.fullmatch(r'[0-9]{7,8}', cedula):
            raise forms.ValidationError('La cédula debe contener entre 7 y 8 dígitos.')
        return cedula


class RegistrationForm(forms.Form):
    nombre = forms.CharField(max_length=150)
    apellido = forms.CharField(max_length=150)
    cedula = forms.RegexField(
        regex=r'^[0-9]{7,8}$',
        error_messages={'invalid': 'La cédula debe contener entre 7 y 8 dígitos.'},
    )
    correo = forms.EmailField()
    patologia = forms.ChoiceField(choices=(
        ('hipertension', 'Hipertensión'),
        ('diabetes', 'Diabetes'),
        ('oftalmologico', 'Oftalmológico'),
        ('pediatrico', 'Pediátrico'),
        ('ginecologico', 'Ginecológico'),
        ('otro', 'Otros'),
    ))
    genero = forms.ChoiceField(choices=(('hombre', 'Hombre'), ('mujer', 'Mujer')))
    direccion = forms.CharField(max_length=255)
    n_telefono = forms.RegexField(
        regex=r'^[0-9]{11}$',
        error_messages={'invalid': 'El teléfono debe contener exactamente 11 dígitos.'},
    )
    fecha_nacimiento = forms.DateField(input_formats=['%Y-%m-%d'])
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    confirm_password = forms.CharField(strip=False, widget=forms.PasswordInput)
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'Debes aceptar las políticas y los términos de uso.'},
    )
    captcha = CaptchaField(label='Verificación de seguridad')

    def clean_cedula(self):
        cedula = self.cleaned_data['cedula']
        if Clientes.objects.filter(cedula=cedula).exists():
            raise forms.ValidationError('Esta cédula no está disponible para el registro.')
        return cedula

    def clean_correo(self):
        correo = self.cleaned_data['correo'].strip()
        if Clientes.objects.filter(correo__iexact=correo).exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado.')
        return correo

    def clean_fecha_nacimiento(self):
        fecha_nacimiento = self.cleaned_data['fecha_nacimiento']
        if fecha_nacimiento > latest_eligible_birth_date():
            raise forms.ValidationError('Debes tener al menos 18 años para registrarte.')
        return fecha_nacimiento

    def clean_password(self):
        return validate_strong_password(self.cleaned_data['password'])

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Las contraseñas no coinciden.')
        return cleaned_data


class PasswordResetRequestForm(forms.Form):
    correo = forms.EmailField()
    captcha = CaptchaField(label='Verificación de seguridad')


class SuperadminPasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label='Contraseña actual',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'password-input'}),
    )
    new_password = forms.CharField(
        label='Nueva contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'password-input'}),
    )
    confirm_password = forms.CharField(
        label='Confirmar nueva contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'password-input'}),
    )

    def __init__(self, *args, cliente, **kwargs):
        self.cliente = cliente
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        password = self.cleaned_data['current_password']
        if not check_password(password, self.cliente.password):
            raise forms.ValidationError('La contraseña actual es incorrecta.')
        return password

    def clean_new_password(self):
        return validate_strong_password(self.cleaned_data['new_password'])

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'Las contraseñas no coinciden.')
        return cleaned_data
