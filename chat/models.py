from django.db import models
from datetime import date
from django.utils import timezone

class Proveedores(models.Model):
    rif = models.CharField(db_column='RIF', max_length=50, unique=True)  # Field name made lowercase.
    nombre_empresa = models.TextField(blank=True, null=True)
    direccion_empresa = models.TextField(blank=True, null=True)
    responsable = models.TextField(blank=True, null=True)
    n_telefono = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.responsable or "Proveedor Desactivado"

    class Meta:
        db_table = 'proveedores'

class Clientes(models.Model):
    class Genero(models.TextChoices):
        HOMBRE = 'hombre', 'Hombre'
        MUJER = 'mujer', 'Mujer'

    cliente_id = models.AutoField(primary_key=True)
    cedula = models.CharField(max_length=50, unique=True)
    correo = models.EmailField(blank=True, null=True, unique=True)
    nombre = models.TextField(blank=True, null=True)
    apellido = models.TextField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    patologia = models.TextField(blank=True, null=True)
    genero = models.CharField(max_length=10, choices=Genero.choices, blank=True, null=True)
    n_telefono = models.CharField(max_length=50, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    bloqueado = models.BooleanField(default=False)

    def __str__(self):
        return self.cedula or "Cliente Desactivado"

    class Meta:
        db_table = 'clientes' 


class ChatMessage(models.Model):
    class Sender(models.TextChoices):
        CLIENT = 'client', 'Cliente'
        BOT = 'bot', 'Bot'

    id = models.AutoField(primary_key=True)
    conversation_key = models.CharField(max_length=100, db_index=True)
    cliente = models.ForeignKey(
        Clientes,
        on_delete=models.SET_NULL,
        db_column='cliente',
        blank=True,
        null=True,
        related_name='chat_messages',
    )
    sender = models.CharField(max_length=10, choices=Sender.choices)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.conversation_key} - {self.get_sender_display()}"

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']

class Categorias(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre_categoria = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.nombre_categoria
    
    class Meta:
        managed = False  # ¡IMPORTANTE!
        db_table = 'categorias'

class SubCategoriasNivel1(models.Model):
    id_sub_categorias_nivel_1 = models.AutoField(primary_key=True)
    nombre_sub_categoria = models.CharField(max_length=50)
    categoria = models.ForeignKey(Categorias, on_delete=models.SET_NULL, db_column='categoria', blank=True, null=True)

    def __str__(self):
        return self.nombre_sub_categoria

    class Meta:
        managed = False  # ¡IMPORTANTE!
        db_table = 'sub_categorias_nivel_1'

class SubCategoriasNivel2(models.Model):
    id_sub_categoria_nivel_2 = models.AutoField(primary_key=True)
    nombre_sub_categoria_nivel_2 = models.CharField(max_length=50)
    sub_categoria_nivel_1 = models.ForeignKey(SubCategoriasNivel1, on_delete=models.SET_NULL, db_column='sub_categoria_nivel_1', blank=True, null=True)

    def __str__(self):
        return self.nombre_sub_categoria_nivel_2
    
    class Meta:
        managed = False  # ¡IMPORTANTE!
        db_table = 'sub_categorias_nivel_2'

class Productos(models.Model):
    id_producto = models.AutoField(primary_key=True)
    nombre_producto = models.TextField(blank=True, null=True)
    descripcion = models.TextField()
    contenido = models.TextField()
    marca = models.TextField()
    codigo = models.BigIntegerField(blank=True, null=True)
    precio_compra = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    precio_venta = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    proveedor = models.ForeignKey(Proveedores, on_delete=models.SET_NULL, db_column='proveedor', blank=True, null=True)
    fecha_elab = models.DateField(blank=True, null=True)
    fecha_venc = models.DateField(blank=True, null=True)
    categoria = models.ForeignKey(Categorias, on_delete=models.SET_NULL, db_column='categoria', blank=True, null=True)
    sub_categorias_nivel_1 = models.ForeignKey(SubCategoriasNivel1, on_delete=models.SET_NULL, db_column='sub_categorias_nivel_1', blank=True, null=True)
    tiene_iva = models.BooleanField(null=True)
    sub_categorias_nivel_2 = models.ForeignKey(SubCategoriasNivel2, on_delete=models.SET_NULL, db_column='sub_categorias_nivel_2', blank=True, null=True)

    def tiene_iva_display(self):
        return 'Sí' if self.tiene_iva else 'No'
    
    def __str__(self):
        return self.nombre_producto or "Producto Desactivado"

    class Meta:
        managed = False  # ¡IMPORTANTE!
        db_table = 'productos'

class Almacen(models.Model):
    id = models.AutoField(db_column='ID', primary_key=True)  # Field name made lowercase.
    id_producto = models.ForeignKey(Productos, on_delete=models.CASCADE, db_column='id_producto', blank=True, null=True, related_name="almacen")
    cantidad = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False  # ¡IMPORTANTE!
        db_table = 'almacen'

