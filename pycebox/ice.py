from __future__ import division

import six

from matplotlib import colors, cm
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd


def get_grid_points(x, num_grid_points):
    if num_grid_points is None:
        return x.unique()
    else:
        # unique is necessary, because if num_grid_points is too much larger
        # than x.shape[0], there will be duplicate quantiles (even with
        # interpolation)
        return x.quantile(np.linspace(0, 1, num_grid_points)).unique()


def get_quantiles(x):
    return np.greater.outer(x, x).sum(axis=1) / x.size


def ice(data, column, predict, num_grid_points=None):
    """
    Generate ICE curves for given column and model.

    predict is a function generating the model predictions that accepts a DataFrame with the same number of columns as
    data.

    If num_grid_points is None, column varies over its unique values in data.
    If num_grid_points is not None, column varies over num_grid_pts values, evenly spaced at its quantiles in data.
    """
    x_s = get_grid_points(data[column], num_grid_points)
    ice_data = to_ice_data(data, column, x_s)
    ice_data['ice_y'] = predict(ice_data.values)

    other_columns = list(data.columns)
    other_columns.remove(column)
    ice_data = ice_data.pivot_table(values='ice_y', index=other_columns, columns=column).T

    return ice_data


def ice_plot(ice_data, frac_to_plot=1., x_quantile=False, plot_pdp=False,
             centered=False, centered_quantile=0.,
             color_by=None, cmap=None,
             ax=None, pdp_kwargs=None, **kwargs):
    """
    Plot the given ICE data

    If frace_to_plot is less than one, randomly samples that fraction of ICE
    curves to plot

    If `x_quantile` is `True`, the plotted x-coordinates are quantiles of
    `ice_data.index`.

    If `plot_pdp` is `True`, plot the partial dependence estimate.  When this
    is `True`, passes `pdp_kwargs` to plot(...).

    If `centered` is true, each ICE curve is is centered to zero at the
    percentile (closest to) `centered_quantile`.

    If `color_by` is not `None`, use the following procedure to color the ICE
    curves.
        * If `color_by` is a string, color the ICE curves by the given variable
          in the column index of `ice_data`.
        * If `color_by` is callable, color the ICE curves by its return value
          when applied to a `DataFrame` created by the columns of `ice_data`.
    If `cmap` is not `None`, use it to choose colors based on `color_by`.

    Keyword arguments are passed to plot(...)
    """
    if not ice_data.index.is_monotonic_increasing:
        ice_data = ice_data.sort_index()

    if centered:
        quantiles = get_quantiles(ice_data.index)
        centered_quantile_iloc = np.abs(quantiles - centered_quantile).argmin()
        ice_data = ice_data - ice_data.iloc[centered_quantile_iloc]

    if frac_to_plot < 1.:
        n_cols = ice_data.shape[1]
        icols = np.random.choice(n_cols, size=frac_to_plot * n_cols, replace=False)
        plot_ice_data = ice_data.iloc[:, icols]
    else:
        plot_ice_data = ice_data

    if x_quantile:
        x = get_quantiles(ice_data.index)
    else:
        x = ice_data.index


    if ax is None:
        _, ax = plt.subplots()

    if color_by is not None:
        if isinstance(color_by, six.string_types):
            colors_raw = plot_ice_data.columns.get_level_values(color_by).values
        elif hasattr(color_by, '__call__'):
            col_df = pd.DataFrame(list(plot_ice_data.columns.values), columns=plot_ice_data.columns.names)
            colors_raw = color_by(col_df)
        else:
            raise ValueError('color_by must be a string or function')

        norm = colors.Normalize(colors_raw.min(), colors_raw.max())
        m = cm.ScalarMappable(norm=norm, cmap=cmap)

        for color_raw, (_, ice_curve) in zip(colors_raw, plot_ice_data.iteritems()):
            c = m.to_rgba(color_raw)
            ax.plot(x, ice_curve, c=c, **kwargs)
    else:
        ax.plot(x, plot_ice_data, **kwargs)

    if plot_pdp:
        pdp_kwargs = pdp_kwargs or {}
        pdp_data = pdp(ice_data)
        ax.plot(x, pdp_data, **pdp_kwargs)

    return ax


def pdp(ice_data):
    """
    Calculate a partial dependence plot from an ICE `DataFrame`
    """
    return ice_data.mean(axis=1)


def to_ice_data(data, column, x_s):
    """
    Create the DataFrame necessary for ICE calculations
    """
    ice_data = pd.DataFrame(np.repeat(data.values, x_s.size, axis=0), columns=data.columns)
    ice_data[column] = np.tile(x_s, data.shape[0])

    return ice_data
