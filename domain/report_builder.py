import pandas as pd
import datetime as dt
from typing import List, Dict, Optional
from infrastructure.hana_repository import HanaRepository

class ReportBuilder:
    """Construye los DataFrames para los reportes finales"""

    @staticmethod
    def convertir_a_float(valor) -> float:
        if valor is None:
            return 0.0
        s = str(valor).strip()
        if s == "":
            return 0.0
        # Formato europeo
        if s.count(",") == 1 and s.count(".") > 1:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def obtener_datos_por_mes_anio(df_mov: pd.DataFrame,
                                   precios_pd: pd.DataFrame) -> pd.DataFrame:
        """
        Procesa un DataFrame de movimientos para obtener cantidades y valores
        por mes/año (valores absolutos). Retorna pivote con columnas
        período_cantidad, período_valor y totales anuales.
        """
        if df_mov.empty:
            return pd.DataFrame()

        df = df_mov.copy()
        df['Cantidad'] = df['Cantidad'].astype(str).apply(ReportBuilder.convertir_a_float)
        df['Valor trans.'] = df['Valor trans.'].astype(str).apply(ReportBuilder.convertir_a_float)

        precio_dict = {}
        if precios_pd is not None and not precios_pd.empty:
            precio_dict = dict(zip(precios_pd['Artículo'],
                                   precios_pd['Precio U. Compra par trimestre']))

        df['Fecha'] = pd.to_datetime(df['Fecha de contabilización'],
                                     format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['Fecha'])

        meses_map = {1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun',
                     7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dic'}
        df['Año'] = df['Fecha'].dt.year
        df['Mes'] = df['Fecha'].dt.month
        df['MesNombre'] = df['Mes'].map(meses_map)
        df['MesAño'] = df['MesNombre'] + '-' + df['Año'].astype(str)

        df['Cantidad_neta'] = df['Cantidad'].abs()
        df['Valor_neta'] = df['Valor trans.'].abs()

        # Recalcular si valor es cero y cantidad > 0
        mask_valor_cero = (df['Valor_neta'] == 0) & (df['Cantidad_neta'] > 0)
        if mask_valor_cero.any():
            df.loc[mask_valor_cero, 'Valor_neta'] = (
                df.loc[mask_valor_cero, 'Cantidad_neta'] *
                df.loc[mask_valor_cero, 'Número de artículo'].map(precio_dict).fillna(0)
            )

        pivot_cant = pd.pivot_table(df, values='Cantidad_neta',
                                    index='Número de artículo',
                                    columns='MesAño', aggfunc='sum', fill_value=0)
        pivot_val = pd.pivot_table(df, values='Valor_neta',
                                   index='Número de artículo',
                                   columns='MesAño', aggfunc='sum', fill_value=0)

        descripciones = df.groupby('Número de artículo')['Descripción'].first().fillna('')

        resultado = pd.DataFrame(index=pivot_cant.index)
        resultado['Artículo'] = resultado.index
        resultado['Descripción Artículo'] = descripciones

        for col in pivot_cant.columns:
            resultado[f'{col}_cantidad'] = pivot_cant[col]
            resultado[f'{col}_valor'] = pivot_val[col].round(4)

        # Totales anuales
        años_unicos = df['MesAño'].str.split('-').str[1].unique()
        for año in años_unicos:
            cols_cant = [c for c in pivot_cant.columns if año in c]
            if cols_cant:
                resultado[f'total_{año}_cantidad'] = pivot_cant[cols_cant].sum(axis=1)
                resultado[f'total_{año}_valor'] = pivot_val[cols_cant].sum(axis=1).round(4)

        return resultado


    @staticmethod
    def construir_dataframe_reportes(df_base: pd.DataFrame,
                                    secciones: list,
                                    unidades_dict: Dict[str, str],
                                    inventarios_dict: Dict[str, Dict[str, float]],
                                    incluir_saldo_inicial: bool = True) -> pd.DataFrame:
        columnas_base = ['Artículo', 'Descripción Artículo', 'Unidad Medida']
        if incluir_saldo_inicial:
            columnas_base.append('Saldo Inicial')

        todas_columnas = columnas_base.copy()
        for sec in secciones:
            tipo = sec["tipo"]
            periodos = sec["periodos"]
            for p in periodos:
                periodo_col = p.replace('-', '_')
                todas_columnas.extend([f"{tipo}_{periodo_col}_cantidad", f"{tipo}_{periodo_col}_valor"])
            años_tipo = set(p.split('-')[1] for p in periodos)
            for año in sorted(años_tipo):
                todas_columnas.extend([f"{tipo}_total_{año}_cantidad", f"{tipo}_total_{año}_valor"])

        todas_columnas.append('Precio U. Compra par trimestre')
        todas_columnas.extend(["Stock", "Comprometido", "Solicitado", "Disponible"])

        filas = []
        for _, row_base in df_base.iterrows():
            articulo = row_base['Artículo']
            fila = {col: 0 for col in todas_columnas}
            fila.update({
                'Artículo': articulo,
                'Descripción Artículo': row_base.get('Descripción Artículo', ''),
                'Unidad Medida': unidades_dict.get(articulo, 'UND'),
                'Precio U. Compra par trimestre': row_base.get('Precio U. Compra par trimestre', 0)
            })
            if incluir_saldo_inicial:
                fila['Saldo Inicial'] = row_base.get('Saldo Inicial Cantidad', 0)

            for sec in secciones:
                tipo = sec["tipo"]
                datos_tipo = sec["datos"]
                art_data = datos_tipo[datos_tipo['Artículo'] == articulo]
                if not art_data.empty:
                    row = art_data.iloc[0]
                    for p in sec["periodos"]:
                        col = p.replace('-', '_')
                        fila[f"{tipo}_{col}_cantidad"] = row.get(f"{p}_cantidad", 0) or 0
                        fila[f"{tipo}_{col}_valor"] = row.get(f"{p}_valor", 0) or 0
                    años_tipo = set(p.split('-')[1] for p in sec["periodos"])
                    for año in años_tipo:
                        fila[f"{tipo}_total_{año}_cantidad"] = row.get(f"total_{año}_cantidad", 0) or 0
                        fila[f"{tipo}_total_{año}_valor"] = row.get(f"total_{año}_valor", 0) or 0

            inv = inventarios_dict.get(articulo, {})
            fila["Stock"] = inv.get("Stock", 0)
            fila["Comprometido"] = inv.get("Comprometido", 0)
            fila["Solicitado"] = inv.get("Solicitado", 0)
            fila["Disponible"] = inv.get("Disponible", 0)
            filas.append(fila)

        return pd.DataFrame(filas, columns=todas_columnas)