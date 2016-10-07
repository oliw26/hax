"""Helper functions for doing cuts/selections on dataframes,
while printing out the passthrough info.
"""
import pandas as pd
import numpy as np

import hax

import logging
log = logging.getLogger('hax.cuts')

# Dictionary mapping id of DataFrame objects to list of cut information applied to it.
# Weakrefs might have been nice here... but as DataFrames are mutable, they can't be hashed
# which means we can't place them in a lookup-by-hash container.
CUT_HISTORY = dict()
UNNAMED_DESCRIPTION = 'Unnamed'


def history(d):
    """Return pandas dataframe describing cuts history on dataframe."""
    d_id = id(d)
    if d_id not in CUT_HISTORY:
        raise ValueError("Cut history for this data not available.")
    hist = pd.DataFrame(CUT_HISTORY[d_id], columns=['selection_desc', 'n_before', 'n_after'])
    hist['n_removed'] = hist.n_before - hist.n_after
    hist['fraction_passed'] = hist.n_after / hist.n_before
    hist['cumulative_fraction_left'] = hist.n_after / hist.iloc[0].n_before
    return hist


def selection(d, bools, desc=UNNAMED_DESCRIPTION,
              return_passthrough_info=False, quiet=None, _invert=False, force_repeat=False):
    """Returns d[bools], print out passthrough info.
     - data on which to perform the selection (pandas dataframe)
     - bools: boolean array of same length as d. If True, row will be in selection returned.
     - return_passthrough_info: if True (default False), return d[bools], len_d_before, len_d_now instead
     - quiet: prints passthrough info if False, not if True.
              The default is controlled by the hax init option 'print_passthrough_info'
     - _invert: inverts bools before applying them
     - force_repeat: do the selection even if a cut with an identical description has already been performed.
    """
    if quiet is None:
        quiet = hax.config['print_passthrough_info']

    global CUT_HISTORY
    prev_cuts = CUT_HISTORY.get(id(d), [])
    n_before = n_now = len(d)

    # The last part of the function has two entry points, so we need to call this instead of return:
    def get_retval():
        if return_passthrough_info:
            return d, n_before, n_now
        return d

    def message(desc, n_before, n_now):
        return "%s selection: %d rows removed (%0.2f%% passed)" % (desc, n_before - n_now, n_now / n_before * 100)

    if desc != UNNAMED_DESCRIPTION and not force_repeat:
        # Check if this cut has already been done
        for c in prev_cuts:
            if c['selection_desc'] == desc:
                log.debug("%s selection already performed on this data; cut skipped. Use force_repeat=True to repeat. "
                          "Showing historical passthrough info." % desc)
                if not quiet:
                    print(message(c['selection_desc'], c['n_before'], c['n_after']))
                return get_retval()

    # Actually do the cut
    d = d[bools]
    n_now = len(d)

    if not quiet:
        print(message(desc, n_before, n_now))

    CUT_HISTORY[id(d)] = prev_cuts + [dict(selection_desc=desc, n_before=n_before, n_after=n_now)]

    return get_retval()


def cut(d, bools, **kwargs):
    """Same as do_selection, with bools inverted. That is, specify which rows you do NOT want to select."""
    return selection(d, True ^ bools, **kwargs)


def notnan(d, axis, **kwargs):
    """Require that d[axis] is not NaN. See selection for options and return value."""
    kwargs.setdefault('desc', '%s not NaN' % axis)
    return selection(d, True ^ np.isnan(d[axis]), **kwargs)


def isfinite(d, axis, **kwargs):
    """Require d[axis] finite. See selection for options and return value."""
    kwargs.setdefault('desc', 'Finite %s' % axis)
    return selection(d, np.isfinite(d[axis]), **kwargs)


def above(d, axis, threshold, **kwargs):
    """Require d[axis] > threshold. See selection for options and return value."""
    kwargs.setdefault('desc', '%s above %s' % (axis, threshold))
    return selection(d, d[axis] > threshold, **kwargs)


def below(d, axis, threshold, **kwargs):
    """Require d[axis] < threshold. See selection for options and return value."""
    kwargs.setdefault('desc', '%s below %s' % (axis, threshold))
    return selection(d, d[axis] < threshold, **kwargs)


##
# Range selection helpers
##
def range_selection(d, axis, bounds, **kwargs):
    """Select elements from d for which bounds[0] <= d[axis] < bounds[1].
    kwargs are same as 'selection' method.
    """
    if kwargs.get('_invert', False):
        kwargs.setdefault('desc', '%s NOT in [%s, %s)' % (axis, bounds[0], bounds[1]))
    else:
        kwargs.setdefault('desc', '%s in [%s, %s)' % (axis, bounds[0], bounds[1]))
    return selection(d, (d[axis] > bounds[0]).values & (d[axis] < bounds[1]).values, **kwargs)


def range_cut(*args, **kwargs):
    """Cut elements in a range from the data; see range_selection docstring."""
    kwargs['_invert'] = True
    return range_selection(*args, **kwargs)


def range_selections(d, *selection_tuples, **kwargs):
    """Do selections based on one or more (axis, bounds) tuples.
     - data on which to perform the selection (pandas dataframe)
     - selection_tuples: one or more tuples like (axis, (low_bound, high_bound)). See range_selection.
     - kwargs are same as 'selection' method.
    """
    for stuff in selection_tuples:
        if 'desc' in kwargs:
            # Make sure each cut has a unique description.
            _kwargs = kwargs.copy()
            _kwargs['desc'] += ' (%s)' % (stuff[0])
        else:
            _kwargs = kwargs
        d = range_selection(d, *stuff, **_kwargs)
    return d


def range_cuts(*args, **kwargs):
    """Do cuts based on one or more (axis, bounds) tuples. See range_selections docstring."""
    kwargs['_invert'] = True
    range_selections(*args, **kwargs)