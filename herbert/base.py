import os
import numpy as np
from itertools import cycle, tee, product

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

def pairwise(i):
    """
    Return successive overlapping pairs taken from the input iterable.

    $ pairwise('ABCDEFG') --> AB BC CD DE EF FG

    From 'https://docs.python.org/3/library/itertools.html#itertools.pairwise'
    """
    u, v = tee(i)
    next(v, None)
    return zip(u, v)


def scale_series(ds):
    """
    Scale values in pandas data-series by minimum value in series

    :params ds: pandas data-series
    """
    if ds.min() == 0.0:
        return ds
    return ds / ds.min()

def get_pdistindex(i, j, M):
    """
    Return compressed pdist matrix given [i, j] and size of observations M
    See http://scipy.github.io/devdocs/reference/generated/scipy.spatial.distance.pdist.html

    :param i: column index
    :param j: row index
    :param M:
    """
    if i == j:
        raise ValueError
    if i < j:
        i, j = j, i
    return M * i + j - ((i + 2) * (i + 1)) // 2

def get_meshpoints(xn, yn):
    """
    Return square array of points [(n, m), (n, m+1), (n+1, m+1), (n+1, m)]

    :param nx:
    :param ny:
    """
    xl, yl = range(xn), range(yn)
    return np.asarray(list(product(xl, yl))).reshape(-1, yn, 2)

def restack(xn, yn):
    """
    Return square array of points [(n, m), (n, m+1), (n+1, m+1), (n+1, m)]

    :param nx:
    :param ny:
    """
    r = point_array(xn, yn)
    s = [r[:-1, :-1], r[:-1, 1:], r[1:, 1:], r[1:, :-1]]
    return np.hstack([i.reshape(-1, 2) for i in s]).reshape(-1, 4, 2)

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
    for (d, dirnames, filenames) in os.walk(filepath):
        files = files + tuple('{}/{}'.format(d, f) for f in filenames)
    return files

def reduce_mem_usage(df, drop=False, output=True):
    """ iterate through all the columns of a DataFrame, convert non-numerical
        data to 'categorical' and modify the data type to reduce memory usage
        https://www.kaggle.com/gemartin/load-data-reduce-memory-usage

    :params df: pandas DataFrame
    """
    from pandas.api.types import is_numeric_dtype, is_integer_dtype
    from pandas.api.types import is_float_dtype
    if output:
        start_mem = df.memory_usage().sum() / 1024**2
        print('Memory usage of dataframe is {:.2f} MB'.format(start_mem))
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
        c_min = df[col].min()
        c_max = df[col].max()
        if is_integer_dtype(df[col]):
            if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                df[col] = df[col].astype(np.int8)
                continue
            if c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                df[col] = df[col].astype(np.int16)
                continue
            if c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                df[col] = df[col].astype(np.int32)
                continue
            df[col] = df[col].astype(np.int64)
            continue
        if is_float_dtype(df[col]):
            if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                df[col] = df[col].astype(np.float16)
                continue
            if c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                df[col] = df[col].astype(np.float32)
                continue
            df[col] = df[col].astype(np.float64)
            continue
    if output:
        end_mem = df.memory_usage().sum() / 1024**2
        print('Memory usage after optimization is: {:.2f} MB'.format(end_mem))
        print('Decreased by {:.1f}%'.format(100 * (start_mem - end_mem) / start_mem))
    return df
