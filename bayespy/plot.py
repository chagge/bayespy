######################################################################
# Copyright (C) 2011-2013 Jaakko Luttinen
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


import os, sys
import tempfile

import numpy as np
import scipy.sparse as sp
from scipy import special
import matplotlib.pyplot as plt
from matplotlib import animation
#from matplotlib.pyplot import *

from bayespy.inference.vmp.nodes.categorical import CategoricalMoments
from bayespy.inference.vmp.nodes.gaussian import GaussianMoments
from bayespy.inference.vmp.nodes.beta import BetaMoments
from bayespy.inference.vmp.nodes.beta import DirichletMoments
from bayespy.inference.vmp.nodes.node import Node

from bayespy.utils import (misc,
                           random,
                           linalg)


# Users can use pyplot via this module
pyplot = plt


def pdf(Z, x, *args, name=None, **kwargs):
    """
    Plot probability density function of a scalar variable.
    """
    try:
        lpdf = Z.logpdf(x)
    except AttributeError:
        lpdf = Z(x)
    p = np.exp(lpdf)
    retval = plt.plot(x, p, *args, **kwargs)

    if name is None:
        try:
            name = Z.name
        except AttributeError:
            pass

    if name:
        plt.title(r'$q(%s)$' % (name))
        plt.xlabel(r'$%s$' % (name))
        
    return retval


def contour(Z, x, y, n=None, **kwargs):
    """
    Plot 2-D probability density function of a 2-D variable.
    """
    XY = misc.grid(x, y)
    try:
        lpdf = Z.logpdf(XY)
    except AttributeError:
        lpdf = Z(XY)
    p = np.exp(lpdf)
    shape = (np.size(x), np.size(y))
    X = np.reshape(XY[:,0], shape)
    Y = np.reshape(XY[:,1], shape)
    P = np.reshape(p, shape)
    if n is not None:
        levels = np.linspace(0, np.amax(P), num=n+2)[1:-1]
        return plt.contour(X, Y, P, levels, **kwargs)
    else:
        return plt.contour(X, Y, P, **kwargs)
        


def plot_gaussian_mc(X, scale=2, **kwargs):
    """
    Parameters:
    X : node
        Node with Gaussian Markov chain moments.
    """
    timeseries_gaussian(X, axis=-2, scale=scale, **kwargs)


def plot_gaussian(X, axis=-1, scale=2, **kwargs):
    """
    Parameters:
    X : node
        Node with Gaussian moments.
    axis : int
        The index of the time axis.
    """
    X = X._convert(GaussianMoments)
    u_X = X.get_moments()
    x = u_X[0]
    xx = misc.get_diag(u_X[1], ndim=len(X.dims[0]))
    std = scale * np.sqrt(xx - x**2)
    #std = scale * np.sqrt(np.einsum('...ii->...i', xx) - x**2)
    
    return _timeseries_mean_and_error(x, std, axis=axis, **kwargs)


def plot(Y, axis=-1, scale=2, center=False, **kwargs):
    """
    Plot a variable or an array as 1-D function with errors
    """
    if misc.is_numeric(Y):
        return _timeseries_mean_and_error(Y, None, axis=axis, center=center, **kwargs)

    if isinstance(Y, Node):
        # Try Gaussian plotting
        try:
            Y = Y._convert(GaussianMoments)
        except GaussianMoments.NoConverterError:
            pass
        else:
            return plot_gaussian(Y, axis=axis, scale=scale, center=center, **kwargs)

    (mu, var) = Y.get_mean_and_variance()
    std = np.sqrt(var)
    
    return _timeseries_mean_and_error(mu, std, 
                                      axis=axis,
                                      scale=scale,
                                      center=center, 
                                      **kwargs)


# Some backward compatibility
def timeseries_gaussian_mc(*args, center=True, **kwargs):
    return plot_gaussian_mc(*args, center=center, **kwargs)
def timeseries_gaussian(*args, center=True, **kwargs):
    return plot_gaussian(*args, center=center, **kwargs)
timeseries_normal = timeseries_gaussian
def timeseries(*args, center=True, **kwargs):
    return plot(*args, center=center, **kwargs)


def _timeseries_mean_and_error(y, std, *args, axis=-1, center=True, **kwargs):
    # TODO/FIXME: You must multiply by ones(plates) in order to plot
    # broadcasted plates properly

    y = np.atleast_1d(y)
    shape = list(np.shape(y))

    # Get and remove the length of the time axis
    T = shape.pop(axis)

    # Move time axis to first
    y = np.rollaxis(y, axis)
    if std is not None:
        std = np.rollaxis(std, axis)
    
    y = np.reshape(y, (T, -1))
    if std is not None:
        std = np.reshape(std, (T, -1))

    # Remove 1s
    shape = [s for s in shape if s > 1]

    # Calculate number of rows and columns
    shape = misc.multiply_shapes(shape, (1,1))
    if len(shape) > 2:
        raise Exception("Can plot only in 2 dimensions (rows and columns)")
    (M, N) = shape

    # Prefer plotting to rows
    if M == 1:
        M = N
        N = 1

    # Plot each timeseries
    ax0 = plt.subplot(M, N, 1)
    for i in range(M*N):
        if i > 0:
            # Share x axis between all subplots
            ax = plt.subplot(M, N, i+1, sharex=ax0)
        else:
            ax = ax0

        # Autoscale the axes to data and use tight y and x axes
        ax.autoscale(enable=True, tight=True)
        ax.set_ylim(auto=True)

        if i < (M-1)*N:
            # Remove x tick labels from other than the last row
            plt.setp(ax.get_xticklabels(), visible=False)

        if std is None:
            #plt.plot(y[:,i], *args, **kwargs)
            errorplot(y=y[:,i], **kwargs)
        else:
            if len(args) > 0:
                raise Exception("Can't handle extra arguments")
            errorplot(y=y[:,i], error=std[:,i], **kwargs)

        if center:
            # Center the zero level on y-axis
            ylim = ax.get_ylim()
            vmax = np.max(np.abs(ylim))
            ax.set_ylim([-vmax, vmax])

    # Remove height space between subplots
    plt.subplots_adjust(hspace=0)

def _blob(x, y, area, colour):
    """
    Draws a square-shaped blob with the given area (< 1) at
    the given coordinates.
    """
    hs = np.sqrt(area) / 2
    xcorners = np.array([x - hs, x + hs, x + hs, x - hs])
    ycorners = np.array([y - hs, y - hs, y + hs, y + hs])
    plt.fill(xcorners, ycorners, colour, edgecolor=colour)

def _rectangle(x, y, width, height, **kwargs):
    _x = x - width/2
    _y = y - height/2
    rectangle = plt.Rectangle((_x, _y), 
                              width,
                              height,
                              **kwargs)
    plt.gca().add_patch(rectangle)
    return
    
    
def hinton(W, error=None, vmax=None, square=True):
    """
    Draws a Hinton diagram for visualizing a weight matrix. 

    Temporarily disables matplotlib interactive mode if it is on, 
    otherwise this takes forever.

    Originally copied from
    http://wiki.scipy.org/Cookbook/Matplotlib/HintonDiagrams
    """
    reenable = False
    if plt.isinteractive():
        plt.ioff()
        reenable = True
        
    #P.clf()
    (height, width) = W.shape
    if not vmax:
        #vmax = 2**np.ceil(np.log(np.max(np.abs(W)))/np.log(2))
        if error is not None:
            vmax = np.max(np.abs(W) + error)
        else:
            vmax = np.max(np.abs(W))

    plt.fill(0.5+np.array([0,width,width,0]),
             0.5+np.array([0,0,height,height]),
             'gray')
    plt.axis('off')
    if square:
        plt.axis('equal')
    plt.gca().invert_yaxis()
    for x in range(width):
        for y in range(height):
            _x = x+1
            _y = y+1
            w = W[y,x]
            _w = np.abs(w)
            if w > 0:
                _c = 'white'
            else:
                _c = 'black'
            if error is not None:
                e = error[y,x]
                if e < 0:
                    print(e, _w, vmax)
                    raise Exception("BUG? Negative error")
                if _w + e > vmax:
                    print(e, _w, vmax)
                    raise Exception("BUG? Value+error greater than max")
                _rectangle(_x,
                           _y, 
                           min(1, np.sqrt((_w+e)/vmax)),
                           min(1, np.sqrt((_w+e)/vmax)),
                           edgecolor=_c,
                           fill=False)
            _blob(_x, _y, min(1, _w/vmax), _c)
                
    if reenable:
        plt.ion()
        #P.show()

def matrix(A):
    A = np.atleast_2d(A)
    vmax = np.max(np.abs(A))
    return  plt.imshow(A, 
                       interpolation='nearest', 
                       cmap='RdBu_r',
                       vmin=-vmax,
                       vmax=vmax)

def new_matrix(A, vmax=None):
    A = np.atleast_2d(A)
    if vmax is None:
        vmax = np.max(np.abs(A))

    (M, N) = np.shape(A)

    for i in range(M):
        for j in range(N):
            pass
    
def gaussian_array(X, rows=-2, cols=-1, scale=1):

    # Get mean and second moment
    (x, xx) = X.get_moments()
    ndim = len(X.dims[0])
    shape = X.get_shape(0)
    size = len(X.get_shape(0))

    # Compute standard deviation
    xx = misc.get_diag(xx, ndim=ndim)
    std = np.sqrt(xx - x**2)

    # Force explicit elements when broadcasting
    x = x * np.ones(shape)
    std = std * np.ones(shape)

    # Preprocess the axes to 0,...,ndim
    if rows < 0:
        rows += size
    if cols < 0:
        cols += size
    if rows < 0 or rows >= size:
        raise ValueError("Row axis invalid")
    if cols < 0 or cols >= size:
        raise ValueError("Column axis invalid")

    # Put the row and column axes to the end
    axes = [i for i in range(size) if i not in (rows, cols)] + [rows, cols]
    x = np.transpose(x, axes=axes)
    std = np.transpose(std, axes=axes)

    # Remove non-row and non-column axes that have length 1
    squeezed_shape = tuple([sh for sh in np.shape(x)[:-2] if sh != 1])
    x = np.reshape(x, squeezed_shape+np.shape(x)[-2:])
    std = np.reshape(std, squeezed_shape+np.shape(x)[-2:])

    # Make explicit four axes
    x = misc.atleast_nd(x, 4)
    std = misc.atleast_nd(std, 4)

    if np.ndim(x) != 4:
        raise ValueError("Can not plot arrays with over 4 axes")

    M = np.shape(x)[0]
    N = np.shape(x)[1]
    vmax = np.max(np.abs(x) + scale*std)
    #plt.subplots(M, N, sharey=True, sharex=True, fig_kw)
    ax = [plt.subplot(M, N, i*N+j+1) for i in range(M) for j in range(N)]
    for i in range(M):
        for j in range(N):
            plt.subplot(M, N, i*N+j+1)
            #plt.subplot(M, N, i*N+j+1, sharey=ax[0], sharex=ax[0])
            if scale == 0:
                hinton(x[i,j], vmax=vmax)
            else:
                hinton(x[i,j], vmax=vmax, error=scale*std[i,j])
            #matrix(x[i,j])

def timeseries_categorical_mc(Z):

    # Make sure that the node is categorical
    Z = Z._convert(CategoricalMoments)

    # Get expectations (and broadcast explicitly)
    z = Z._message_to_child()[0] * np.ones(Z.get_shape(0))

    # Compute the subplot layout
    z = misc.atleast_nd(z, 4)
    if np.ndim(z) != 4:
        raise ValueError("Can not plot arrays with over 4 axes")
    M = np.shape(z)[0]
    N = np.shape(z)[1]

    #print("DEBUG IN PLOT", Z.get_shape(0), np.shape(z))

    # Plot Hintons
    for i in range(M):
        for j in range(N):
            plt.subplot(M, N, i*N+j+1)
            hinton(z[i,j].T, vmax=1.0, square=False)


def beta_hinton(P):
    """
    Plot a beta distributed random variable as a Hinton diagram
    """

    # Make sure that the node is beta
    P._convert(BetaMoments)

    # Compute exp( <log p> )
    p = np.exp(P._message_to_child()[0][...,0])

    # Explicit broadcasting
    p = p * np.ones(P.plates)

    # Plot Hinton diagram
    hinton(p, vmax=1.0, square=False)

    return
    

def dirichlet_hinton(P, square=True):
    """
    Plot a beta distributed random variable as a Hinton diagram
    """

    # Make sure that the node is beta
    P._convert(DirichletMoments)

    # Compute exp( <log p> )
    p = np.exp(P._message_to_child()[0])

    # Explicit broadcasting
    p = p * np.ones(P.plates+(1,))

    # Plot Hinton diagram
    hinton(p, vmax=1.0, square=square)

    return

    
class Plotter():
    def __init__(self, plotter, **kwargs):
        self._kwargs = kwargs
        self._plotter = plotter
    def __call__(self, X):
        self._plotter(X, **self._kwargs)
        
class GaussianMarkovChainPlotter(Plotter):
    def __init__(self, **kwargs):
        super().__init__(timeseries_gaussian_mc, **kwargs)

class GaussianTimeseriesPlotter(Plotter):
    def __init__(self, **kwargs):
        super().__init__(timeseries_gaussian, **kwargs)

class GaussianHintonPlotter(Plotter):
    def __init__(self, **kwargs):
        super().__init__(gaussian_array, **kwargs)

class CategoricalMarkovChainPlotter(Plotter):
    def __init__(self, **kwargs):
        super().__init__(timeseries_categorical_mc, **kwargs)

## def matrix_animation_BACKUP(A, filename=None, fps=25, **kwargs):

##     fig = plt.gcf()

##     A = np.atleast_3d(A)
##     vmax = np.max(np.abs(A))
##     x = plt.imshow(A[0],
##                    interpolation='nearest',
##                    cmap='RdBu_r',
##                    vmin=-vmax,
##                    vmax=vmax,
##                    **kwargs)
##     s = plt.title('t = %d' % 0)

##     if filename is not None:
##         (_, base_fname) = tempfile.mkstemp(suffix='', prefix='')

##     def animate(nframe):
##         s.set_text('t = %d' % nframe)
##         x.set_array(A[nframe])
##         if filename is not None:
##             fname = '%s_%05d.png' % (base_fname, nframe)
##             plt.savefig(fname)
##             if nframe == np.shape(A)[0] - 1:
##                 os.system("ffmpeg -r %d -i %s_%%05d.png -r 25 -y %s"
##                           % (fps, base_fname, filename))
##                 os.system("rm %s_*.png" % base_fname)
    
##         return (x, s)

##     anim = animation.FuncAnimation(fig, animate,
##                                    frames=np.shape(A)[0],
##                                    interval=1000/fps,
##                                    blit=False,
##                                    repeat=False)

##     return anim

def matrix_animation(A, filename=None, fps=25, **kwargs):

    fig = plt.gcf()

    A = np.atleast_3d(A)
    vmax = np.max(np.abs(A))
    x = plt.imshow(A[0],
                   interpolation='nearest',
                   cmap='RdBu_r',
                   vmin=-vmax,
                   vmax=vmax,
                   **kwargs)
    s = plt.title('t = %d' % 0)

    def animate(nframe):
        s.set_text('t = %d' % nframe)
        x.set_array(A[nframe])
        return (x, s)

    anim = animation.FuncAnimation(fig, animate,
                                   frames=np.shape(A)[0],
                                   interval=1000/fps,
                                   blit=False,
                                   repeat=False)
        
    return anim

def save_animation(anim, filename, fps=25, bitrate=5000, fig=None):

    # A bug in numpy/matplotlib causes this not to work in python3.3:
    # https://github.com/matplotlib/matplotlib/issues/1891
    #
    # So the following command does not work currently..
    #
    # anim.save(filename, fps=fps)

    if fig is None:
        fig = plt.gcf()
        
    writer = animation.FFMpegFileWriter(fps=fps, bitrate=bitrate)
    writer.setup(fig, filename, 100)
    anim.save(filename, 
              fps=fps,
              writer=writer,
              bitrate=bitrate)
    return

 
## def matrix_movie(A, filename, 
##                  fps=25,
##                  title='Matrix Movie',
##                  artist='BayesPy',
##                  dpi=100,
##                  **kwargs):

##     # A bug in numpy/matplotlib causes this not to work in python3.3:
##     # https://github.com/matplotlib/matplotlib/issues/1891

##     FFMpegWriter = animation.FFMpegFileWriter()
##     #FFMpegWriter = animation.writers['ffmpeg']
##     metadata = dict(title=title,
##                     artist=artist)
##     writer = FFMpegWriter(fps=fps, metadata=metadata)        
##     #writer = FFMpegWriter(fps=fps, metadata=metadata)        
        
##     A = np.atleast_3d(A)
##     vmax = np.max(np.abs(A))
##     x = plt.imshow(A[0],
##                    interpolation='nearest',
##                    cmap='RdBu_r',
##                    vmin=-vmax,
##                    vmax=vmax,
##                    **kwargs)
##     s = plt.title('t = %d' % 0)
##     fig = plt.gcf()
    
##     with writer.saving(fig, filename, dpi):
##         for (t, a) in enumerate(A):
##             x.set_array(a)
##             s.set_text('t = %d' % t)
##             plt.draw()
##             #writer.grab_frame()

def binary_matrix(A):
    A = np.atleast_2d(A)
    G = np.zeros(np.shape(A) + (3,))
    G[A] = [0,0,0]
    G[np.logical_not(A)] = [1,1,1]
    plt.imshow(G, interpolation='nearest')

def gaussian_mixture(w, mu, Sigma):
    pass

def gaussian_mixture_logpdf(x, w, mu, Sigma):
    # Shape(x)      = (N, D)
    # Shape(w)      = (K,)
    # Shape(mu)     = (K, D)
    # Shape(Sigma)  = (K, D, D)
    # Shape(result) = (N,)

    # Dimensionality
    D = np.shape(x)[-1]

    # Cholesky decomposition of the covariance matrix
    U = misc.m_chol(Sigma)

    # Reshape x:
    # Shape(x)     = (N, 1, D)
    x = np.expand_dims(x, axis=-2)

    # (x-mu) and (x-mu)'*inv(Sigma)*(x-mu):
    # Shape(v)     = (N, K, D)
    # Shape(z)     = (N, K)
    v = x - mu
    z = np.einsum('...i,...i', v, misc.m_chol_solve(U, v))

    # Log-determinant of Sigma:
    # Shape(ldet)  = (K,)
    ldet = misc.m_chol_logdet(U)

    # Compute log pdf for each cluster:
    # Shape(lpdf)  = (N, K)
    lpdf = misc.gaussian_logpdf(z, 0, 0, ldet, D)
    
    

def matrixplot(A, colorbar=False):
    if sp.issparse(A):
        A = A.toarray()
    plt.imshow(A, interpolation='nearest')
    if colorbar:
        plt.colorbar()


def contourplot(x1, x2, y, colorbar=False, filled=True):
    """ Plots 2D contour plot. x1 and x2 are 1D vectors, y contains
    the function values. y.size must be x1.size*x2.size. """
    
    y = np.reshape(y, (len(x2),len(x1)))
    if filled:
        plt.contourf(x1, x2, y)
    else:
        plt.contour(x1, x2, y)
    if colorbar:
        plt.colorbar()
        

def errorplot(y=None, error=None, x=None, lower=None, upper=None,
              color=(0,0,0,1), **kwargs):

    # Default inputs
    if x is None:
        x = np.arange(np.size(y))

    # Parse errors (lower=lower/error/upper, upper=upper/error/lower)
    if lower is None:
        if error is not None:
            lower = error
        elif upper is not None:
            lower = upper
    if upper is None:
        if error is not None:
            upper = error
        elif lower is not None:
            upper = lower

    # Plot errors
    if (lower is not None) and (upper is not None):
        #print(np.max(lower))
        #print(np.max(upper))
        l = y - lower
        u = y + upper
        plt.fill_between(x,
                         u,
                         l,
                         facecolor=(0.6,0.6,0.6,1),
                         edgecolor=(0,0,0,0),
                         linewidth=0,
                         interpolate=True)
    # Plot function
    plt.plot(x, y, color=color, **kwargs)

#def multiplot(plot_function, *args, **kwargs):
    

def m_plot(x, Y, style):
    Y = np.atleast_2d(Y)
    M = Y.shape[-2]
    for i in range(M):
        plt.subplot(M,1,i+1)
        plt.plot(x, Y[i], style)

## def multi_errorplot(Y, error=None, x=None, lower=None, upper=None):

##     for m in range(M):
##         for n in range(N):
##             plt.subplot(M,N,m*N+n)
##             errorplot(Y[m][n],
##                       error=error[m][n],
##                       x=x[m][n],
##                       lower=lower[m][n],
##                       upper=upper[m][n])

def m_errorplot(x, Y, L, U):
    Y = np.atleast_2d(Y)
    L = np.atleast_2d(L)
    U = np.atleast_2d(U)
    M = Y.shape[-2]
    ## print(np.shape(Y))
    ## print(np.shape(L))
    ## print(np.shape(U))
    ## print(np.shape(M))
    for i in range(M):
        plt.subplot(M,1,i+1)
        lower = Y[i] - L[i]
        upper = Y[i] + U[i]
        #print(upper-lower)
        #if np.any(lower>=upper):
            #print('WTF?!')
        plt.fill_between(x,
                         upper,
                         lower,
                         #where=(upper>=lower),
                         facecolor=(0.6,0.6,0.6,1),
                         edgecolor=(0,0,0,0),
                         #edgecolor=(0.6,0.6,0.6,1),
                         linewidth=0,
                         interpolate=True)
        plt.plot(x, Y[i], color=(0,0,0,1))
        plt.ylabel(str(i))


def plotmatrix(X):
    """
    Creates a matrix of marginal plots.

    On diagonal, are marginal plots of each variable. Off-diagonal plot (i,j)
    shows the joint marginal density of x_i and x_j.
    """
    return X.plotmatrix()

    
def _pdf_t(mu, s2, nu, axes=None, scale=4, color='k'):
    """
    """
    s = np.sqrt(s2)
    x = np.linspace(mu-scale*s, mu+scale*s, num=100)
    y2 = (x-mu)**2 / s2
    lpdf = random.t_logpdf(y2, np.log(s2), nu, 1)
    p = np.exp(lpdf)
    if axes is None:
        axes = plt
    return axes.plot(x, p, color=color)


def _pdf_gamma(a, b, axes=None, scale=4, color='k'):
    """
    """
    if np.size(a) != 1 or np.size(b) != 1:
        raise ValueError("Parameters must be scalars")
    mean = a/b
    v = scale*np.sqrt(a/b**2)
    m = max(0, mean-v)
    n = mean + v
    x = np.linspace(m, n, num=100)
    logx = np.log(x)
    lpdf = random.gamma_logpdf(b*x,
                               logx,
                               a*logx,
                               a*np.log(b),
                               special.gammaln(a))
    p = np.exp(lpdf)
    if axes is None:
        axes = plt
    return axes.plot(x, p, color=color)


def _contour_t(mu, Cov, nu, axes=None, scale=4, transpose=False, colors='k'):
    """
    """
    if np.shape(mu) != (2,) or np.shape(Cov) != (2,2) or np.shape(nu) != ():
        print(np.shape(mu), np.shape(Cov), np.shape(nu))
        raise ValueError("Only 2-d t-distribution allowed")
    
    if transpose:
        mu = mu[[1,0]]
        Cov = Cov[np.ix_([1,0],[1,0])]

    s = np.sqrt(np.diag(Cov))
    x0 = np.linspace(mu[0]-scale*s[0], mu[0]+scale*s[0], num=100)
    x1 = np.linspace(mu[1]-scale*s[1], mu[1]+scale*s[1], num=100)
    X0X1 = misc.grid(x0, x1)
    Y = X0X1 - mu
    L = linalg.chol(Cov)
    logdet_Cov = linalg.chol_logdet(L)
    Z = linalg.chol_solve(L, Y)
    Z = linalg.inner(Y, Z, ndim=1)
    lpdf = random.t_logpdf(Z, logdet_Cov, nu, 2)
    p = np.exp(lpdf)
    shape = (np.size(x0), np.size(x1))
    X0 = np.reshape(X0X1[:,0], shape)
    X1 = np.reshape(X0X1[:,1], shape)
    P = np.reshape(p, shape)
    if axes is None:
        axes = plt
    return axes.contour(X0, X1, P, colors=colors)


def _contour_gaussian_gamma(mu, s2, a, b, axes=None, transpose=False):
    """
    """
    pass