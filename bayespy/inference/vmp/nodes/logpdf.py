######################################################################
# Copyright (C) 2015 Jaakko Luttinen
#
# This file is licensed under Version 3.0 of the GNU General Public
# License. See LICENSE for a text of the license.
######################################################################

######################################################################
# This file is part of BayesPy.
#
# BayesPy is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# BayesPy is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BayesPy.  If not, see <http://www.gnu.org/licenses/>.
######################################################################

import numpy as np

from .expfamily import ExponentialFamily, useconstructor
from .stochastic import Distribution
from .node import Moments


class LogPDFDistribution(Distribution):
    pass


class LogPDF(ExponentialFamily):
    """
    General node with arbitrary probability density function
    """


    def __init__(self, logpdf, *parents, **kwargs):

        self._logpdf = logpdf

        super().__init__(logpdf,
                         *parents,
                         initialize=False,
                         **kwargs)


    @classmethod
    def _constructor(cls, logpdf, *parents, approximation=None, shape=None, samples=10, **kwargs):
        r"""
        Constructs distribution and moments objects.
        """

        if approximation is not None:
            raise NotImplementedError() #self._distribution = approximation._constructor

        dims = ( shape, )

        _distribution = LogPDFDistribution()

        _moments = np.nan

        _parent_moments = [Moments()] * len(parents)

        parent_plates = [_distribution.plates_from_parent(i, parent.plates)
                         for (i, parent) in enumerate(parents)]

        return (parents,
                kwargs,
                dims, 
                cls._total_plates(kwargs.get('plates'),
                                  *parent_plates),
                _distribution, 
                _moments, 
                _parent_moments)


    def _get_message_and_mask_to_parent(self, index):
        def logpdf_sampler(x):
            inputs = [self.parents[j].random() if j != index
                      else x
                      for j in range(len(self.parents))]
            return self._logpdf(self.random(), *inputs)
        mask = self._distribution.compute_mask_to_parent(index, self.mask)
        return (logpdf_sampler, mask)


    def observe(self, x, *args, mask=True):
        """
        Fix moments, compute f and propagate mask.
        """

        # Compute fixed moments
        if not np.isnan(self._moments):
            u = self._moments.compute_fixed_moments(x, *args, mask=mask)
        else:
            u = (x,) + args

        # Check the dimensionality of the observations
        for (i,v) in enumerate(u):
            # This is what the dimensionality "should" be
            s = self.plates + self.dims[i]
            t = np.shape(v)
            if s != t:
                msg = "Dimensionality of the observations incorrect."
                msg += "\nShape of input: " + str(t)
                msg += "\nExpected shape: " + str(s)
                msg += "\nCheck plates."
                raise Exception(msg)

        # Set the moments
        self._set_moments(u, mask=mask)

        # Observed nodes should not be ignored
        self.observed = mask
        self._update_mask()

