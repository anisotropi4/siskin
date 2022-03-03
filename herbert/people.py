import pandas as pd

def get_density(df):
    """
    Return population per m^2 density from pandas dataframe.

    :param df: dataframe with 'population' and 'area' columns
    """
    return (1.0E6 * df['population'] / df['area'] ).round(1)

