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

def restack(xn, yn):
    """
    Return square array of points [(n, m), (n, m+1), (n+1, m+1), (n+1, m)]

    :param nx:
    :param ny:
    """
    xl, yl = range(xn), range(yn)
    r = np.asarray(list(product(xl, yl))).reshape(-1, yn, 2)
    s = [r[:-1, :-1], r[:-1, 1:], r[1:, 1:], r[1:, :-1]]
    return np.hstack([i.reshape(-1, 2) for i in s]).reshape(-1, 4, 2)
