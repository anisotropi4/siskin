import os
from itertools import cycle, tee, product
import numpy as np
from fiona.errors import DriverError
from pandas.api.types import is_numeric_dtype, is_integer_dtype
from pandas.api.types import is_float_dtype


def archive(filepath):
    """
    Archive a file to the 'archive' directory.
    Create the 'archive' directory first if it doesn't exist.

    :param filepath: filepath location of file to be archived
    """
    try:
        os.mkdir('archive')
    except FileExistsError:
        pass
    try:
        filename = os.path.basename(filepath)
        os.rename(filepath, f'archive/{filename}')
    except FileNotFoundError:
        pass

def append_gf(gf, filepath, layer, crs):
    """
    Append layer to GeoPKG filepath

    :param filepath:
    :param gf: GeoDataFrame
    :param layer: layer name
    """
    try:
        gf.to_crs(crs).to_file(filepath, driver='GPKG', mode='a', layer=layer)
    except DriverError:
        gf.to_crs(crs).to_file(filepath, driver='GPKG', layer=layer)

def pairwise(i):
    """
    Return successive overlapping pairs taken from the input iterable.

    $ pairwise('ABCDEFG') --> AB BC CD DE EF FG

    From 'https://docs.python.org/3/library/itertools.html#itertools.pairwise'
    """
    u, v = tee(i)
    next(v, None)
    return zip(u, v)


def scale_series(this_ds):
    """
    Scale values in pandas data-series by minimum value in series

    :params ds: pandas data-series
    """
    if this_ds.min() == 0.0:
        return this_ds
    return this_ds / this_ds.min()

def get_pdistindex(i, j, n):
    """
    Return compressed pdist matrix given [i, j] and size of observations n
    See http://scipy.github.io/devdocs/reference/generated/scipy.spatial.distance.pdist.html

    :param i: column index
    :param j: row index
    :param n: size of observations
    """
    if i == j:
        raise ValueError
    if i < j:
        i, j = j, i
    return n * i + j - ((i + 2) * (i + 1)) // 2

def get_meshpoints(n, m):
    """
    Return square array of points [(i, j), (i, j+1), (i+1, j+1), (i+1, j)]

    :param n: number columns
    :param m: number rows
    """
    return np.asarray(list(product(range(n), range(m)))).reshape(-1, m, 2)

def get_corners():
    """
    Returns point index values [[0, 2], [0, 3], [1, 3], [1, 2]]
    for rectangle corner points [[0, 1], [2, 3]]
    """
    u, v = tee(cycle([0, 1, 2, 3]))
    next(v, None)
    return np.asarray([next(zip(u, v)) for _ in range(4)]) // 2 + [0, 2]

def list_files(filepath):
    """
    Return filename tuple for all files under 'filepath'
    """
    files = ()
    for (d, _, filenames) in os.walk(filepath):
        files = files + tuple(f'{d}/{f}' for f in filenames)
    return files


def reduce_mem_usage(df, drop=False, output=True):
    """
    Iterate through all the columns of a DataFrame, convert non-numerical
    data to 'categorical' and modify the data type to reduce memory usage
    https://www.kaggle.com/gemartin/load-data-reduce-memory-usage

    :params df: pandas DataFrame
    """
    def get_dtype_int(this_ds, c_min, c_max):
        if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
            return this_ds.astype(np.int8)
        if c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
            return this_ds.astype(np.int16)
        if c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
            return this_ds.astype(np.int32)
        return this_ds.astype(np.int64)

    def get_dtype_float(this_ds, c_min, c_max):
        if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
            return this_ds.astype(np.float16)
        if c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
            return this_ds.astype(np.float32)
        return this_ds.astype(np.float64)
    if output:
        start_mem = df.memory_usage().sum() / 1024**2
        print(f'Memory usage of dataframe is {round(start_mem, 2)} MB')
    for col in df.columns:
        if not is_numeric_dtype(df[col]):
            try:
                df[col] = df[col].astype('category')
            except TypeError:
                if output:
                    print(f'drop {col} as not categorical')
                df = df.drop(columns=[col])
                continue
            if drop:
                df = df.drop(columns=[col])
            continue
        if is_integer_dtype(df[col]):
            df[col] = get_dtype_int(df[col], df[col].min(), df[col].max())
            continue
        if is_float_dtype(df[col]):
            df[col] = get_dtype_float(df[col], df[col].min(), df[col].max())
            continue
    if output:
        end_mem = df.memory_usage().sum() / 1024**2
        print(f'Memory usage after optimization is: {round(end_mem,2)} MB')
        print(f'Decreased by {round(100 * (start_mem - end_mem) / start_mem, 1)}')
    return df
