def buscar_productos(self, consulta):
    """Busca productos en tu BD existente con toda la información relacionada"""
    from chat.models import Productos, Categorias
    
    palabras = consulta.lower().split()
    productos_relacionados = []
    
    # Búsqueda en múltiples campos
    for palabra in palabras:
        productos = Productos.objects.filter(
            nombre_producto__icontains=palabra
        ) | Productos.objects.filter(
            descripcion__icontains=palabra
        ) | Productos.objects.filter(
            marca__icontains=palabra
        ) | Productos.objects.filter(
            contenido__icontains=palabra
        )
        
        # También buscar por categoría
        categorias = Categorias.objects.filter(nombre_categoria__icontains=palabra)
        for cat in categorias:
            productos = productos | Productos.objects.filter(categoria=cat)
        
        productos_relacionados.extend(productos[:5])
    
    # Eliminar duplicados
    productos_unicos = list({p.id_producto: p for p in productos_relacionados}.values())
    
    resultados = []
    for p in productos_unicos[:10]:
        info_producto = {
            "id": p.id_producto,
            "nombre": p.nombre_producto or "Producto",
            "descripcion": p.descripcion[:200] + "..." if len(p.descripcion) > 200 else p.descripcion,
            "marca": p.marca,
            "precio": f"${p.precio_venta:,.2f}" if p.precio_venta else "Consultar precio",
            "contenido": p.contenido,
            "codigo": p.codigo,
            "tiene_iva": "Sí" if p.tiene_iva else "No",
        }
        
        # Agregar información de categoría si existe
        if p.categoria:
            info_producto["categoria"] = p.categoria.nombre_categoria
        
            
        # Agregar fechas si existen
        if p.fecha_venc:
            info_producto["fecha_vencimiento"] = p.fecha_venc.strftime("%d/%m/%Y")
        
        resultados.append(info_producto)
    
    return resultados