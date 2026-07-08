from dataclasses import dataclass
from typing import Optional

@dataclass
class Movimiento:
    articulo: str
    descripcion: str
    almacen: str
    fecha: str
    documento: str
    cantidad: float
    valor_trans: float
    cantidad_acumulada: Optional[float] = 0.0
    valor_acumulado: Optional[float] = 0.0
    comentario: str = ""
    grupo_articulo: str = ""
    serie: str = ""
    unidad_medida: str = ""

@dataclass
class PrecioPromedio:
    articulo: str
    descripcion: str
    precio_unitario: float

@dataclass
class InventarioItem:
    stock: float = 0.0
    comprometido: float = 0.0
    solicitado: float = 0.0
    disponible: float = 0.0