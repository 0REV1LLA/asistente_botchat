from django.contrib import admin
from django import forms

from .models import Productos


class ProductosAdminForm(forms.ModelForm):
    class Meta:
        model = Productos
        fields = '__all__'


@admin.register(Productos)
class ProductosAdmin(admin.ModelAdmin):
    form = ProductosAdminForm
    list_display = ('nombre_producto', 'compuesto', 'categoria', 'requiere_recipe', 'precio_venta')
    list_filter = ('categoria', 'requiere_recipe')
    search_fields = ('nombre_producto', 'compuesto', 'marca', 'codigo')
