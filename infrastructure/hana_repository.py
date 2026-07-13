import threading
import pyodbc
from infrastructure.cache import LRUCache

class HanaConnectionPool:
    """Pool de conexiones thread-safe para HANA"""
    def __init__(self, host, port, user, password, max_connections=5):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.max_connections = max_connections
        self._connections = []
        self._lock = threading.Lock()
        self._conn_str = (
            f'DRIVER={{HDBODBC}};'
            f'SERVERNODE={host}:{port};'
            f'UID={user};'
            f'PWD={password};'
            f'DATABASE=SBO_ORODELTI_PROD;'
            f'TIMEOUT=30;'
        )

    def get_connection(self):
        with self._lock:
            if self._connections:
                return self._connections.pop()
            return pyodbc.connect(self._conn_str, timeout=30)

    def return_connection(self, conn):
        with self._lock:
            if len(self._connections) < self.max_connections:
                self._connections.append(conn)
            else:
                conn.close()

    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            else:
                result = cursor.fetchall()
            cursor.close()
            return result
        finally:
            self.return_connection(conn)


class HanaRepository:
    """Repositorio para acceder a SAP HANA con caché y consultas masivas"""
    def __init__(self, host, port, user, password, max_connections=5):
        self.pool = HanaConnectionPool(host, port, user, password, max_connections)
        self.cache_comentarios_pd = LRUCache()
        self.cache_comentarios_em = LRUCache()
        self.cache_grupos = LRUCache()
        self.cache_unidades = LRUCache()
        self.batch_size = 100

    # ------------------------------------------------------------------
    # Consultas masivas de comentarios (schema y tabla separados)
    # ------------------------------------------------------------------
    def _obtener_comentarios_masivos(self, documentos, schema, tabla):
        if not documentos:
            return {}
        docs_validos = [str(d) for d in documentos if d is not None and str(d).strip().isdigit()]
        if not docs_validos:
            return {}
        placeholders = ','.join(['?'] * len(docs_validos))
        query = f'SELECT "DocNum", "Comments" FROM "{schema}"."{tabla}" WHERE "DocNum" IN ({placeholders})'
        try:
            results = self.pool.execute_query(query, params=docs_validos, fetch_all=True)
            comentarios = {}
            if results:
                for row in results:
                    comentarios[str(row[0])] = str(row[1]).strip() if row[1] else ""
            return comentarios
        except Exception as e:
            print(f"⚠️ Error en consulta masiva {schema}.{tabla}: {e}")
            return {}

    def obtener_comentarios_masivos_pd(self, documentos):
        return self._obtener_comentarios_masivos(documentos, 'SBO_ORODELTI_PROD', 'OPOR')

    def obtener_comentarios_masivos_em(self, documentos):
        return self._obtener_comentarios_masivos(documentos, 'SBO_ORODELTI_PROD', 'OIGN')

    def obtener_comentarios_masivos_im(self, documentos):
        return self._obtener_comentarios_masivos(documentos, 'SBO_ORODELTI_PROD', 'OWTR')

    def obtener_comentarios_masivos_sm(self, documentos):
        return self._obtener_comentarios_masivos(documentos, 'SBO_ORODELTI_PROD', 'OIGE')

    # ------------------------------------------------------------------
    # Consultas masivas de series (schema y tabla separados)
    # ------------------------------------------------------------------
    def _obtener_series(self, documentos, schema, tabla, serie_ordinario):
        if not documentos:
            return {}
        docs_validos = [str(d) for d in documentos if d is not None and str(d).strip().isdigit()]
        if not docs_validos:
            return {}
        placeholders = ','.join(['?'] * len(docs_validos))
        query = f'''
            SELECT "DocNum",
                   CASE WHEN "Series" = {serie_ordinario} THEN 'Ordinario' ELSE '' END AS "Series"
            FROM "{schema}"."{tabla}"
            WHERE "DocNum" IN ({placeholders})
        '''
        try:
            results = self.pool.execute_query(query, params=docs_validos, fetch_all=True)
            series = {}
            if results:
                for row in results:
                    series[str(row[0])] = str(row[1]).strip() if row[1] else ""
            return series
        except Exception as e:
            print(f"⚠️ Error en consulta series {schema}.{tabla}: {e}")
            return {}

    def obtener_series_sm(self, documentos):
        return self._obtener_series(documentos, 'SBO_ORODELTI_PROD', 'OIGE', 341)

    def obtener_series_em(self, documentos):
        return self._obtener_series(documentos, 'SBO_ORODELTI_PROD', 'OIGN', 336)

    # ------------------------------------------------------------------
    # Obtener grupos de artículos (ya estaba correcto)
    # ------------------------------------------------------------------
    def obtener_grupos_masivos(self, articulos):
        if not articulos:
            return {}
        articulos_validos = [str(a).strip() for a in articulos if a is not None and str(a).strip()]
        if not articulos_validos:
            return {}
        resultados = {}
        for i in range(0, len(articulos_validos), self.batch_size):
            batch = articulos_validos[i:i+self.batch_size]
            placeholders = ','.join(['?'] * len(batch))
            query = f'''
                SELECT o."ItemCode", o2."ItmsGrpNam"
                FROM "SBO_ORODELTI_PROD"."OITM" o
                INNER JOIN "SBO_ORODELTI_PROD"."OITB" o2 ON o."ItmsGrpCod" = o2."ItmsGrpCod"
                WHERE o."ItemCode" IN ({placeholders})
            '''
            try:
                results = self.pool.execute_query(query, params=batch, fetch_all=True)
                if results:
                    for row in results:
                        resultados[row[0]] = str(row[1]).strip() if row[1] else ""
            except Exception as e:
                print(f"⚠️ Error en consulta grupos: {e}")
                for articulo in batch:
                    if articulo not in resultados:
                        resultados[articulo] = ""
        return resultados

    # ------------------------------------------------------------------
    # Obtener unidades de medida
    # ------------------------------------------------------------------
    def obtener_unidades_masivas(self, articulos):
        if not articulos:
            return {}
        articulos_validos = [str(a).strip() for a in articulos if a is not None and str(a).strip()]
        if not articulos_validos:
            return {}
        resultados = {}
        for i in range(0, len(articulos_validos), self.batch_size):
            batch = articulos_validos[i:i+self.batch_size]
            placeholders = ','.join(['?'] * len(batch))
            query = f'SELECT "ItemCode", "InvntryUom" FROM "SBO_ORODELTI_PROD"."OITM" WHERE "ItemCode" IN ({placeholders})'
            try:
                results = self.pool.execute_query(query, params=batch, fetch_all=True)
                if results:
                    for row in results:
                        resultados[row[0]] = str(row[1]).strip() if row[1] else "UND"
            except Exception as e:
                print(f"Error en consulta unidades: {e}")
                for articulo in batch:
                    if articulo not in resultados:
                        resultados[articulo] = "UND"
        return resultados

    # ------------------------------------------------------------------
    # Obtener inventarios (stock, comprometido, solicitado, disponible)
    # ------------------------------------------------------------------
    def obtener_inventarios_masivos(self, articulos):
        if not articulos:
            return {}
        articulos_validos = [str(a).strip() for a in articulos if a is not None and str(a).strip()]
        if not articulos_validos:
            return {}
        resultados = {}
        for i in range(0, len(articulos_validos), self.batch_size):
            batch = articulos_validos[i:i+self.batch_size]
            placeholders = ','.join(['?'] * len(batch))
            query = f'''
                SELECT "ItemCode", "OnHand" AS "Stock", "IsCommited" AS "Comprometido",
                       "OnOrder" AS "Solicitado",
                       ("OnHand" - "IsCommited" + "OnOrder") AS "Disponible"
                FROM "SBO_ORODELTI_PROD"."OITW"
                WHERE 
                "ItemCode" IN ({placeholders})
            '''
            #--"WhsCode" = 'GEN D1_3' AND 
            try:
                results = self.pool.execute_query(query, params=batch, fetch_all=True)
                if results:
                    for row in results:
                        resultados[row[0]] = {
                            "Stock": float(row[1]) if row[1] is not None else 0.0,
                            "Comprometido": float(row[2]) if row[2] is not None else 0.0,
                            "Solicitado": float(row[3]) if row[3] is not None else 0.0,
                            "Disponible": float(row[4]) if row[4] is not None else 0.0
                        }
            except Exception as e:
                print(f"Error en consulta inventarios: {e}")
                for articulo in batch:
                    if articulo not in resultados:
                        resultados[articulo] = {"Stock": 0.0, "Comprometido": 0.0, "Solicitado": 0.0, "Disponible": 0.0}
        return resultados
    

    def obtener_proveedores_masivos(self, articulos):
        if not articulos:
            return {}
        articulos_validos = [str(a).strip() for a in articulos if a is not None and str(a).strip()]
        if not articulos_validos:
            return {}
        resultados = {}
        for i in range(0, len(articulos_validos), self.batch_size):
            batch = articulos_validos[i:i+self.batch_size]
            # 1. Inicializar todos los artículos del batch con valores por defecto
            for articulo in batch:
                resultados[articulo] = {
                    "codigo": "",
                    "nombre": "",
                    "unidad_medida_compra": "",
                    "factor_conversion": 1.0,
                    "ultimo_precio_compra": 0.0
                }
            placeholders = ','.join(['?'] * len(batch))
            query = f'''
                SELECT T0."ItemCode", T2."CardCode", T2."CardName",
                    T0."BuyUnitMsr", T0."NumInBuy", T1."Price"
                FROM "SBO_ORODELTI_PROD"."OITM" T0
                INNER JOIN (
                    SELECT P1."ItemCode", P1."Price", P0."CardCode", P1."Currency",
                        P0."DocDate",
                        ROW_NUMBER() OVER (
                            PARTITION BY P1."ItemCode"
                            ORDER BY P0."DocDate" DESC, P0."DocEntry" DESC
                        ) AS RN
                    FROM "SBO_ORODELTI_PROD"."OPCH" P0
                    INNER JOIN "SBO_ORODELTI_PROD"."PCH1" P1
                        ON P0."DocEntry" = P1."DocEntry"
                ) T1 ON T0."ItemCode" = T1."ItemCode"
                LEFT JOIN "SBO_ORODELTI_PROD"."OCRD" T2
                    ON T1."CardCode" = T2."CardCode"
                WHERE T1.RN = 1
                AND T0."ItemCode" IN ({placeholders})
                GROUP BY T0."ItemCode", T2."CardCode",
                    T2."CardName", T0."BuyUnitMsr", T0."NumInBuy", T1."Price"
            '''
            try:
                results = self.pool.execute_query(query, params=batch, fetch_all=True)
                if results:
                    for row in results:
                        item = str(row[0]).strip() if row[0] else ""
                        codigo = str(row[1]).strip() if row[1] else ""
                        nombre = str(row[2]).strip() if row[2] else ""
                        unidad_medida_compra = str(row[3]).strip() if row[3] else ""
                        factor_conversion = float(row[4]) if row[4] is not None else 1.0
                        ultimo_precio_compra = float(row[5]) if row[5] is not None else 0.0
                        # Sobrescribir solo si el artículo existe en el batch
                        if item in resultados:
                            resultados[item] = {
                                "codigo": codigo,
                                "nombre": nombre,
                                "unidad_medida_compra": unidad_medida_compra,
                                "factor_conversion": factor_conversion,
                                "ultimo_precio_compra": ultimo_precio_compra
                            }
            except Exception as e:
                print(f"Error en consulta proveedores: {e}")
                # ya están inicializados con valores por defecto, no es necesario hacer nada
        return resultados