import pandas as pd

class PriceCalculator:
    """Calcula precio promedio de compra a partir de los movimientos de PD"""
    @staticmethod
    def calcular(movimientos_df: pd.DataFrame) -> pd.DataFrame:
        """
        Recibe un DataFrame con columnas 'Número de artículo', 'Cantidad', 'Valor trans.',
        'Descripción'. Devuelve DataFrame con columnas: Artículo, Descripción Artículo,
        Precio U. Compra par trimestre.
        """
        if movimientos_df.empty:
            return pd.DataFrame()

        df = movimientos_df.copy()
        df['Cantidad'] = pd.to_numeric(df['Cantidad'], errors='coerce')
        df['Valor trans.'] = pd.to_numeric(df['Valor trans.'], errors='coerce')

        mask = (df['Cantidad'].notna() &
                df['Valor trans.'].notna() &
                (df['Cantidad'].abs() > 0))
        df_valid = df[mask].copy()
        if df_valid.empty:
            return pd.DataFrame()

        df_valid['Cantidad_abs'] = df_valid['Cantidad'].abs()
        df_valid['Valor_abs'] = df_valid['Valor trans.'].abs()

        resultado = df_valid.groupby('Número de artículo').agg(
            Cantidad_abs=('Cantidad_abs', 'sum'),
            Valor_abs=('Valor_abs', 'sum'),
            Descripción=('Descripción', lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else "")
        ).reset_index()

        resultado['Precio U. Compra par trimestre'] = (
            resultado['Valor_abs'] / resultado['Cantidad_abs']
        ).round(4)

        resultado = resultado.rename(columns={
            'Número de artículo': 'Artículo',
            'Descripción': 'Descripción Artículo'
        })[['Artículo', 'Descripción Artículo', 'Precio U. Compra par trimestre']]

        return resultado