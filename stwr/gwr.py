# Main GWR classes
__author__ = "STWR is XiangQue xiangq@uidaho.edu and GWR,MGWR is Taylor Oshan Tayoshan@gmail.com"

import copy
import numpy as np
import numpy.linalg as la
from scipy.stats import t
from scipy.special import factorial
from itertools import combinations as combo
from spglm.family import Gaussian, Binomial, Poisson
from spglm.glm import GLM, GLMResults
from spglm.iwls import iwls, _compute_betas_gwr
from spglm.utils import cache_readonly
from .diagnostics import get_AIC, get_AICc, get_BIC, corr
from .kernels import *
from .summary import *

fk = {'gaussian': fix_gauss, 'bisquare': fix_bisquare, 'exponential': fix_exp,
      'spt_bisquare':fix_spt_bisquare,'spt_gwr_gaussian':fix_spt_gwr_gaussian}
ak = {'gaussian': adapt_gauss, 'bisquare': adapt_bisquare,
      'exponential': adapt_exp,'spt_bisquare':adapt_spt_bisquare,'spt_gwr_gaussian':spt_gwr_gaussian}


class GWR(GLM):
    """
    Geographically weighted regression. Can currently estimate Gaussian,
    Poisson, and logistic models(built on a GLM framework). GWR object prepares
    model input. Fit method performs estimation and returns a GWRResults object.

    Parameters
    ----------
    coords        : array-like
                    n*2, collection of n sets of (x,y) coordinates of
                    observatons; also used as calibration locations is
                    'points' is set to None

    y             : array
                    n*1, dependent variable

    X             : array
                    n*k, independent variable, exlcuding the constant

    bw            : scalar
                    bandwidth value consisting of either a distance or N
                    nearest neighbors; user specified or obtained using
                    Sel_BW

    family        : family object
                    underlying probability model; provides
                    distribution-specific calculations

    offset        : array
                    n*1, the offset variable at the ith location. For Poisson model
                    this term is often the size of the population at risk or
                    the expected size of the outcome in spatial epidemiology
                    Default is None where Ni becomes 1.0 for all locations;
                    only for Poisson models

    sigma2_v1     : boolean
                    specify form of corrected denominator of sigma squared to use for
                    model diagnostics; Acceptable options are:

                    'True':       n-tr(S) (defualt)
                    'False':     n-2(tr(S)+tr(S'S))

    kernel        : string
                    type of kernel function used to weight observations;
                    available options:
                    'gaussian'
                    'bisquare'
                    'exponential'

    fixed         : boolean
                    True for distance based kernel function and  False for
                    adaptive (nearest neighbor) kernel function (default)

    constant      : boolean
                    True to include intercept (default) in model and False to exclude
                    intercept.

    dmat          : array
                    n*n, distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    sorted_dmat   : array
                    n*n, sorted distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    spherical     : boolean
                    True for shperical coordinates (long-lat),
                    False for projected coordinates (defalut).

    Attributes
    ----------
    coords        : array-like
                    n*2, collection of n sets of (x,y) coordinates used for
                    calibration locations

    y             : array
                    n*1, dependent variable

    X             : array
                    n*k, independent variable, exlcuding the constant

    bw            : scalar
                    bandwidth value consisting of either a distance or N
                    nearest neighbors; user specified or obtained using
                    Sel_BW

    family        : family object
                    underlying probability model; provides
                    distribution-specific calculations

    offset        : array
                    n*1, the offset variable at the ith location. For Poisson model
                    this term is often the size of the population at risk or
                    the expected size of the outcome in spatial epidemiology
                    Default is None where Ni becomes 1.0 for all locations

    sigma2_v1     : boolean
                    specify form of corrected denominator of sigma squared to use for
                    model diagnostics; Acceptable options are:

                    'True':       n-tr(S) (defualt)
                    'False':     n-2(tr(S)+tr(S'S))

    kernel        : string
                    type of kernel function used to weight observations;
                    available options:
                    'gaussian'
                    'bisquare'
                    'exponential'

    fixed         : boolean
                    True for distance based kernel function and  False for
                    adaptive (nearest neighbor) kernel function (default)

    constant      : boolean
                    True to include intercept (default) in model and False to exclude
                    intercept

    dmat          : array
                    n*n, distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    sorted_dmat   : array
                    n*n, sorted distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    spherical     : boolean
                    True for shperical coordinates (long-lat),
                    False for projected coordinates (defalut).

    n             : integer
                    number of observations

    k             : integer
                    number of independent variables

    mean_y        : float
                    mean of y

    std_y         : float
                    standard deviation of y

    fit_params    : dict
                    parameters passed into fit method to define estimation
                    routine

    W             : array
                    n*n, spatial weights matrix for weighting all
                    observations from each calibration point
    points        : array-like
                    n*2, collection of n sets of (x,y) coordinates used for
                    calibration locations instead of all observations;
                    defaults to None unles specified in predict method

    P             : array
                    n*k, independent variables used to make prediction;
                    exlcuding the constant; default to None unless specified
                    in predict method

    exog_scale    : scalar
                    estimated scale using sampled locations; defualt is None
                    unless specified in predict method

    exog_resid    : array-like
                    estimated residuals using sampled locations; defualt is None
                    unless specified in predict method

    Examples
    --------
    #basic model calibration

    >>> import libpysal as ps
    >>> from mgwr.gwr import GWR
    >>> data = ps.io.open(ps.examples.get_path('GData_utm.csv'))
    >>> coords = list(zip(data.by_col('X'), data.by_col('Y')))
    >>> y = np.array(data.by_col('PctBach')).reshape((-1,1))
    >>> rural = np.array(data.by_col('PctRural')).reshape((-1,1))
    >>> pov = np.array(data.by_col('PctPov')).reshape((-1,1))
    >>> african_amer = np.array(data.by_col('PctBlack')).reshape((-1,1))
    >>> X = np.hstack([rural, pov, african_amer])
    >>> model = GWR(coords, y, X, bw=90.000, fixed=False, kernel='bisquare')
    >>> results = model.fit()
    >>> print(results.params.shape)
    (159, 4)

    #predict at unsampled locations

    >>> index = np.arange(len(y))
    >>> test = index[-10:]
    >>> X_test = X[test]
    >>> coords_test = np.array(coords)[test]
    >>> model = GWR(coords, y, X, bw=94, fixed=False, kernel='bisquare')
    >>> results = model.predict(coords_test, X_test)
    >>> print(results.params.shape)
    (10, 4)

    """

    def __init__(self, coords, y, X, bw, family=Gaussian(), offset=None,
                 sigma2_v1=True, kernel='bisquare', fixed=False, constant=True,
                 dmat=None, sorted_dmat=None, spherical=False):
        """
        Initialize class
        """
        GLM.__init__(self, y, X, family, constant=constant)
        self.constant = constant
        self.sigma2_v1 = sigma2_v1
        self.coords = coords
        self.bw = bw
        self.kernel = kernel
        self.fixed = fixed
        if offset is None:
            self.offset = np.ones((self.n, 1))
        else:
            self.offset = offset * 1.0
        self.fit_params = {}

        self.points = None
        self.exog_scale = None
        self.exog_resid = None
        self.P = None
        self.dmat = dmat
        self.sorted_dmat = sorted_dmat
        self.spherical = spherical
        self.W = self._build_W(fixed, kernel, coords, bw)

    def _build_W(self, fixed, kernel, coords, bw, points=None):
        if fixed:
            try:
                W = fk[kernel](coords, bw, points, self.dmat,
                               self.sorted_dmat,
                               spherical=self.spherical)
            except BaseException:
                raise  # TypeError('Unsupported kernel function  ', kernel)
        else:
            try:
                W = ak[kernel](coords, bw, points, self.dmat,
                               self.sorted_dmat,
                               spherical=self.spherical)
            except BaseException:
                raise  # TypeError('Unsupported kernel function  ', kernel)

        return W

    def fit(self, ini_params=None, tol=1.0e-5, max_iter=20,
            solve='iwls',searching = False):
        """
        Method that fits a model with a particular estimation routine.

        Parameters
        ----------

        ini_betas     : array, optional
                        k*1, initial coefficient values, including constant.
                        Default is None, which calculates initial values during
                        estimation.
        tol:            float, optional
                        Tolerence for estimation convergence.
                        Default is 1.0e-5.
        max_iter      : integer, optional
                        Maximum number of iterations if convergence not
                        achieved. Default is 20.
        solve         : string, optional
                        Technique to solve MLE equations.
                        Default is 'iwls', meaning iteratively (
                        re)weighted least squares.
        searching     : bool, optional
                        Whether to estimate a lightweight GWR that
                        computes the minimum diagnostics needed for
                        bandwidth selection (could speed up
                        bandwidth selection for GWR) or to estimate
                        a full GWR. Default is False.

        Returns
        -------
                      :
                        If searching=True, return a GWRResult
                        instance; otherwise, return a GWRResultLite
                        instance.

        """
        self.fit_params['ini_params'] = ini_params
        self.fit_params['tol'] = tol
        self.fit_params['max_iter'] = max_iter
        self.fit_params['solve'] = solve
        if solve.lower() == 'iwls':
            m = self.W.shape[0]
            # In bandwidth selection, return GWRResultsLite
            if searching:
                resid = np.zeros((m, 1))
                influ = np.zeros((m, 1))
                for i in range(m):
                    wi = self.W[i].reshape((-1, 1))
                    if isinstance(self.family, Gaussian):
                        betas, inv_xtx_xt = _compute_betas_gwr(
                            self.y, self.X, wi)
                        influ[i] = np.dot(self.X[i], inv_xtx_xt[:, i])
                        predy = np.dot(self.X[i], betas)[0]
                        resid[i] = self.y[i] - predy
                    elif isinstance(self.family, (Poisson, Binomial)):
                        rslt = iwls(self.y, self.X, self.family,
                                    self.offset, None, ini_params, tol,
                                    max_iter, wi=wi)
                        inv_xtx_xt = rslt[5]
                        influ[i] = np.dot(self.X[i], inv_xtx_xt[:, i]) * \
                                   rslt[3][i][0]
                        predy = rslt[1][i]
                        resid[i] = self.y[i] - predy
                return GWRResultsLite(self, resid, influ)

            else:
                params = np.zeros((m, self.k))
                predy = np.zeros((m, 1))
                w = np.zeros((m, 1))
                S = np.zeros((m, self.n))
                CCT = np.zeros((m, self.k))
                for i in range(m):               
                    wi = self.W[i].reshape((-1, 1))
                    rslt = iwls(self.y, self.X, self.family,
                                self.offset, None, ini_params, tol,
                                max_iter, wi=wi)
                    params[i, :] = rslt[0].T
                    predy[i] = rslt[1][i]
                    w[i] = rslt[3][i]
                    S[i] = np.dot(self.X[i], rslt[5])
                    # dont need unless f is explicitly passed for
                    # prediction of non-sampled points
                    #cf = rslt[5] - np.dot(rslt[5], f)
                    #CCT[i] = np.diag(np.dot(cf, cf.T/rslt[3]))
                    CCT[i] = np.diag(np.dot(rslt[5], rslt[5].T))
                return GWRResults(self, params, predy, S, CCT, w)

    def predict(self, points, P, exog_scale=None, exog_resid=None,
                fit_params={}):
        """
        Method that predicts values of the dependent variable at un-sampled
        locations

        Parameters
        ----------
        points        : array-like
                        n*2, collection of n sets of (x,y) coordinates used for
                        calibration prediction locations
        P             : array
                        n*k, independent variables used to make prediction;
                        exlcuding the constant
        exog_scale    : scalar
                        estimated scale using sampled locations; defualt is None
                        which estimates a model using points from "coords"
        exog_resid    : array-like
                        estimated residuals using sampled locations; defualt is None
                        which estimates a model using points from "coords"; if
                        given it must be n*1 where n is the length of coords
        fit_params    : dict
                        key-value pairs of parameters that will be passed into fit
                        method to define estimation routine; see fit method for more details

        """
        if (exog_scale is None) & (exog_resid is None):
            train_gwr = self.fit(**fit_params)
            self.exog_scale = train_gwr.scale
            self.exog_resid = train_gwr.resid_response
        elif (exog_scale is not None) & (exog_resid is not None):
            self.exog_scale = exog_scale
            self.exog_resid = exog_resid
        else:
            raise InputError('exog_scale and exog_resid must both either be'
                             'None or specified')
        self.points = points
        if self.constant:
            P = np.hstack([np.ones((len(P), 1)), P])
            self.P = P
        else:
            self.P = P
        self.W = self._build_W(
            self.fixed,
            self.kernel,
            self.coords,
            self.bw,
            points)
        gwr = self.fit(**fit_params)

        return gwr

    @cache_readonly
    def df_model(self):
        return None

    @cache_readonly
    def df_resid(self):
        return None


class GWRResults(GLMResults):
    """
    Basic class including common properties for all GWR regression models

    Parameters
    ----------
    model               : GWR object
                        pointer to GWR object with estimation parameters

    params              : array
                          n*k, estimated coefficients

    predy               : array
                          n*1, predicted y values

    S                   : array
                          n*n, hat matrix

    CCT                 : array
                          n*k, scaled variance-covariance matrix

    w                   : array
                          n*1, final weight used for iteratively re-weighted least
                          sqaures; default is None

    Attributes
    ----------
    model               : GWR Object
                          points to GWR object for which parameters have been
                          estimated

    params              : array
                          n*k, parameter estimates

    predy               : array
                          n*1, predicted value of y

    y                   : array
                          n*1, dependent variable

    X                   : array
                          n*k, independent variable, including constant

    family              : family object
                          underlying probability model; provides
                          distribution-specific calculations

    n                   : integer
                          number of observations

    k                   : integer
                          number of independent variables

    df_model            : integer
                          model degrees of freedom

    df_resid            : integer
                          residual degrees of freedom

    offset              : array
                          n*1, the offset variable at the ith location.
                          For Poisson model this term is often the size of
                          the population at risk or the expected size of
                          the outcome in spatial epidemiology; Default is
                          None where Ni becomes 1.0 for all locations

    scale               : float
                          sigma squared used for subsequent computations

    w                   : array
                          n*1, final weights from iteratively re-weighted least
                          sqaures routine

    resid_response      : array
                          n*1, residuals of the repsonse

    resid_ss            : scalar
                          residual sum of sqaures

    W                   : array
                          n*n; spatial weights for each observation from each
                          calibration point

    S                   : array
                          n*n, hat matrix

    CCT                 : array
                          n*k, scaled variance-covariance matrix

    ENP                 : scalar
                          effective number of paramters, which depends on
                          sigma2

    tr_S                : float
                          trace of S (hat) matrix

    tr_STS              : float
                          trace of STS matrix

    y_bar               : array
                          n*1, weighted mean value of y

    TSS                 : array
                          n*1, geographically weighted total sum of squares

    RSS                 : array
                          n*1, geographically weighted residual sum of squares

    R2                  : float
                          R-squared for the entire model (1- RSS/TSS)

    aic                 : float
                          Akaike information criterion

    aicc                : float
                          corrected Akaike information criterion to account
                          to account for model complexity (smaller
                          bandwidths)

    bic                 : float
                          Bayesian information criterio

    localR2             : array
                          n*1, local R square

    sigma2              : float
                          sigma squared (residual variance) that has been
                          corrected to account for the ENP

    std_res             : array
                          n*1, standardised residuals

    bse                 : array
                          n*k, standard errors of parameters (betas)

    influ               : array
                          n*1, leading diagonal of S matrix

    CooksD              : array
                          n*1, Cook's D

    tvalues             : array
                          n*k, local t-statistics

    adj_alpha           : array
                          3*1, corrected alpha values to account for multiple
                          hypothesis testing for the 90%, 95%, and 99% confidence
                          levels; tvalues with an absolute value larger than the
                          corrected alpha are considered statistically
                          significant.

    deviance            : array
                          n*1, local model deviance for each calibration point

    resid_deviance      : array
                          n*1, local sum of residual deviance for each
                          calibration point

    llf                 : scalar
                          log-likelihood of the full model; see
                          pysal.contrib.glm.family for damily-sepcific
                          log-likelihoods

    pDev                : float
                          local percent of deviation accounted for; analogous to
                          r-squared for GLM's

    mu                  : array
                          n*, flat one dimensional array of predicted mean
                          response value from estimator

    fit_params          : dict
                          parameters passed into fit method to define estimation
                          routine

    predictions         : array
                          p*1, predicted values generated by calling the GWR
                          predict method to predict dependent variable at
                          unsampled points ()
    """

    def __init__(self, model, params, predy, S, CCT, w=None):
        GLMResults.__init__(self, model, params, predy, w)
        self.W = model.W
        self.offset = model.offset
        if w is not None:
            self.w = w
        self.predy = predy
        self.S = S
        self.CCT = self.cov_params(CCT, model.exog_scale)
        self._cache = {}

    @cache_readonly
    def resid_ss(self):
        if self.model.points is not None:
            raise NotImplementedError('Not available for GWR prediction')
        else:
            u = self.resid_response.flatten()
        return np.dot(u, u.T)

    @cache_readonly
    def scale(self, scale=None):
        if isinstance(self.family, Gaussian):
            scale = self.sigma2
        else:
            scale = 1.0
        return scale

    def cov_params(self, cov, exog_scale=None):
        """
        Returns scaled covariance parameters

        Parameters
        ----------
        cov         : array
                      estimated covariance parameters

        Returns
        -------
        Scaled covariance parameters

        """
        if exog_scale is not None:
            return cov * exog_scale
        else:
            return cov * self.scale

    @cache_readonly
    def tr_S(self):
        """
        trace of S (hat) matrix
        """
        return np.trace(self.S * self.w)

    @cache_readonly
    def tr_STS(self):
        """
        trace of STS matrix
        """
        return np.trace(np.dot(self.S.T * self.w, self.S * self.w))

    @cache_readonly
    def ENP(self):
        """
        effective number of parameters

        Defualts to tr(s) as defined in yu et. al (2018) Inference in
        Multiscale GWR

        but can alternatively be based on 2tr(s) - tr(STS)

        and the form depends on the specification of sigma2
        """
        if self.model.sigma2_v1:
            return self.tr_S
        else:
            return 2 * self.tr_S - self.tr_STS

    @cache_readonly
    def y_bar(self):
        """
        weighted mean of y
        """
        if self.model.points is not None:
            n = len(self.model.points)
        else:
            n = self.n
        off = self.offset.reshape((-1, 1))
        arr_ybar = np.zeros(shape=(self.n, 1))
        for i in range(n):
            w_i = np.reshape(np.array(self.W[i]), (-1, 1))
            sum_yw = np.sum(self.y.reshape((-1, 1)) * w_i)
            arr_ybar[i] = 1.0 * sum_yw / np.sum(w_i * off)
        return arr_ybar

    @cache_readonly
    def TSS(self):
        """
        geographically weighted total sum of squares

        Methods: p215, (9.9)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.

        """
        if self.model.points is not None:
            n = len(self.model.points)
        else:
            n = self.n
        TSS = np.zeros(shape=(n, 1))
        for i in range(n):
            TSS[i] = np.sum(np.reshape(np.array(self.W[i]), (-1, 1)) *
                            (self.y.reshape((-1, 1)) - self.y_bar[i])**2)
        return TSS

    @cache_readonly
    def RSS(self):
        """
        geographically weighted residual sum of squares

        Methods: p215, (9.10)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        if self.model.points is not None:
            n = len(self.model.points)
            resid = self.model.exog_resid.reshape((-1, 1))
        else:
            n = self.n
            resid = self.resid_response.reshape((-1, 1))
        RSS = np.zeros(shape=(n, 1))
        for i in range(n):
            RSS[i] = np.sum(np.reshape(np.array(self.W[i]), (-1, 1))
                            * resid**2)
        return RSS

    @cache_readonly
    def localR2(self):
        """
        local R square

        Methods: p215, (9.8)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        if isinstance(self.family, Gaussian):
            return (self.TSS - self.RSS) / self.TSS
        else:
            raise NotImplementedError('Only applicable to Gaussian')

    @cache_readonly
    def sigma2(self):
        """
        residual variance

        if sigma2_v1 is True: only use n-tr(S) in denominator

        Methods: p214, (9.6),
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.

        and as defined  in Yu et. al. (2018) Inference in Multiscale GWR

        if sigma2_v1 is False (v1v2): use n-2(tr(S)+tr(S'S)) in denominator

        Methods: p55 (2.16)-(2.18)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.

        """
        if self.model.sigma2_v1:
            return (self.resid_ss / (self.n - self.tr_S))
        else:
            # could be changed to SWSTW - nothing to test against
            return self.resid_ss / (self.n - 2.0 * self.tr_S + self.tr_STS)

    @cache_readonly
    def std_res(self):
        """
        standardized residuals

        Methods:  p215, (9.7)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        return self.resid_response.reshape(
            (-1, 1)) / (np.sqrt(self.scale * (1.0 - self.influ)))

    @cache_readonly
    def bse(self):
        """
        standard errors of Betas

        Methods:  p215, (2.15) and (2.21)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        return np.sqrt(self.CCT)

    @cache_readonly
    def influ(self):
        """
        Influence: leading diagonal of S Matrix
        """
        return np.reshape(np.diag(self.S), (-1, 1))

    @cache_readonly
    def cooksD(self):
        """
        Influence: leading diagonal of S Matrix

        Methods: p216, (9.11),
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        Note: in (9.11), p should be tr(S), that is, the effective number of parameters
        """
        return self.std_res**2 * self.influ / (self.tr_S * (1.0 - self.influ))

    @cache_readonly
    def deviance(self):
        off = self.offset.reshape((-1, 1)).T
        y = self.y
        ybar = self.y_bar
        if isinstance(self.family, Gaussian):
            raise NotImplementedError(
                'deviance not currently used for Gaussian')
        elif isinstance(self.family, Poisson):
            dev = np.sum(
                2.0 * self.W * (y * np.log(y / (ybar * off)) - (y - ybar * off)), axis=1)
        elif isinstance(self.family, Binomial):
            dev = self.family.deviance(self.y, self.y_bar, self.W, axis=1)
        return dev.reshape((-1, 1))

    @cache_readonly
    def resid_deviance(self):
        if isinstance(self.family, Gaussian):
            raise NotImplementedError(
                'deviance not currently used for Gaussian')
        else:
            off = self.offset.reshape((-1, 1)).T
            y = self.y
            ybar = self.y_bar
            global_dev_res = ((self.family.resid_dev(self.y, self.mu))**2)
            dev_res = np.repeat(global_dev_res.flatten(), self.n)
            dev_res = dev_res.reshape((self.n, self.n))
            dev_res = np.sum(dev_res * self.W.T, axis=0)
            return dev_res.reshape((-1, 1))

    @cache_readonly
    def pDev(self):
        """
        Local percentage of deviance accounted for. Described in the GWR4
        manual. Equivalent to 1 - (deviance/null deviance)
        """
        if isinstance(self.family, Gaussian):
            raise NotImplementedError('Not implemented for Gaussian')
        else:
            return 1.0 - (self.resid_deviance / self.deviance)

    @cache_readonly
    def adj_alpha(self):
        """
        Corrected alpha (critical) values to account for multiple testing during hypothesis
        testing. Includes corrected value for 90% (.1), 95% (.05), and 99%
        (.01) confidence levels. Correction comes from:

        da Silva, A. R., & Fotheringham, A. S. (2015). The Multiple Testing Issue in
        Geographically Weighted Regression. Geographical Analysis.

        """
        alpha = np.array([.1, .05, .001])
        pe = self.ENP
        p = self.k
        return (alpha * p) / pe

    def critical_tval(self, alpha=None):
        """
        Utility function to derive the critial t-value based on given alpha
        that are needed for hypothesis testing

        Parameters
        ----------
        alpha           : scalar
                          critical value to determine which tvalues are
                          associated with statistically significant parameter
                          estimates. Default to None in which case the adjusted
                          alpha value at the 95 percent CI is automatically
                          used.

        Returns
        -------
        critical        : scalar
                          critical t-val based on alpha
        """
        n = self.n
        if alpha is not None:
            alpha = np.abs(alpha) / 2.0
            critical = t.ppf(1 - alpha, n - 1)
        else:
            alpha = np.abs(self.adj_alpha[1]) / 2.0
            critical = t.ppf(1 - alpha, n - 1)
        return critical

    def filter_tvals(self, critical_t=None, alpha=None):
        """
        Utility function to set tvalues with an absolute value smaller than the
        absolute value of the alpha (critical) value to 0. If critical_t
        is supplied than it is used directly to filter. If alpha is provided
        than the critical t value will be derived and used to filter. If neither
        are critical_t nor alpha are provided, an adjusted alpha at the 95
        percent CI will automatically be used to define the critical t-value and
        used to filter. If both critical_t and alpha are supplied then the alpha
        value will be ignored.

        Parameters
        ----------
        critical        : scalar
                          critical t-value to determine whether parameters are
                          statistically significant

        alpha           : scalar
                          alpha value to determine which tvalues are
                          associated with statistically significant parameter
                          estimates

        Returns
        -------
        filtered       : array
                          n*k; new set of n tvalues for each of k variables
                          where absolute tvalues less than the absolute value of
                          alpha have been set to 0.
        """
        n = self.n
        if critical_t is not None:
            critical = critical_t
        else:
            critical = self.critical_tval(alpha=alpha)

        subset = (self.tvalues < critical) & (self.tvalues > -1.0 * critical)
        tvalues = self.tvalues.copy()
        tvalues[subset] = 0
        return tvalues

    @cache_readonly
    def df_model(self):
        return self.n - self.tr_S

    @cache_readonly
    def df_resid(self):
        return self.n - 2.0 * self.tr_S + self.tr_STS

    @cache_readonly
    def normalized_cov_params(self):
        return None

    @cache_readonly
    def resid_pearson(self):
        return None

    @cache_readonly
    def resid_working(self):
        return None

    @cache_readonly
    def resid_anscombe(self):
        return None

    @cache_readonly
    def pearson_chi2(self):
        return None

    @cache_readonly
    def null(self):
        return None

    @cache_readonly
    def llnull(self):
        return None

    @cache_readonly
    def null_deviance(self):
        return None

    @cache_readonly
    def R2(self):
        if isinstance(self.family, Gaussian):
            TSS = np.sum((self.y.reshape((-1, 1)) -
                          np.mean(self.y.reshape((-1, 1))))**2)
            RSS = np.sum((self.y.reshape((-1, 1)) -
                          self.predy.reshape((-1, 1)))**2)
            return 1 - (RSS / TSS)
        else:
            raise NotImplementedError('Only available for Gaussian GWR')

    @cache_readonly
    def aic(self):
        return get_AIC(self)

    @cache_readonly
    def aicc(self):
        return get_AICc(self)

    @cache_readonly
    def bic(self):
        return get_BIC(self)

    @cache_readonly
    def D2(self):
        return None

    @cache_readonly
    def adj_D2(self):
        return None

    @cache_readonly
    def pseudoR2(self):
        return None

    @cache_readonly
    def adj_pseudoR2(self):
        return None

    @cache_readonly
    def pvalues(self):
        return None

    @cache_readonly
    def conf_int(self):
        return None

    @cache_readonly
    def use_t(self):
        return None

    def local_collinearity(self):
        """
        Computes several indicators of multicollinearity within a geographically
        weighted design matrix, including:

        local correlation coefficients (n, ((p**2) + p) / 2)
        local variance inflation factors (VIF) (n, p-1)
        local condition number (n, 1)
        local variance-decomposition proportions (n, p)

        Returns four arrays with the order and dimensions listed above where n
        is the number of locations used as calibrations points and p is the
        nubmer of explanatory variables. Local correlation coefficient and local
        VIF are not calculated for constant term.

        """
        x = self.X
        w = self.W
        nvar = x.shape[1]
        nrow = len(w)
        if self.model.constant:
            ncor = (((nvar - 1)**2 + (nvar - 1)) / 2) - (nvar - 1)
            jk = list(combo(range(1, nvar), 2))
        else:
            ncor = (((nvar)**2 + (nvar)) / 2) - nvar
            jk = list(combo(range(nvar), 2))
        corr_mat = np.ndarray((nrow, int(ncor)))
        if self.model.constant:
            vifs_mat = np.ndarray((nrow, nvar - 1))
        else:
            vifs_mat = np.ndarray((nrow, nvar))
        vdp_idx = np.ndarray((nrow, nvar))
        vdp_pi = np.ndarray((nrow, nvar, nvar))

        for i in range(nrow):
            wi = w[i]
            sw = np.sum(wi)
            wi = wi / sw
            tag = 0

            for j, k in jk:
                corr_mat[i, tag] = corr(
                    np.cov(x[:, j], x[:, k], aweights=wi))[0][1]
                tag = tag + 1

            if self.model.constant:
                corr_mati = corr(np.cov(x[:, 1:].T, aweights=wi))
                vifs_mat[i, ] = np.diag(np.linalg.solve(
                    corr_mati, np.identity((nvar - 1))))

            else:
                corr_mati = corr(np.cov(x.T, aweights=wi))
                vifs_mat[i, ] = np.diag(np.linalg.solve(
                    corr_mati, np.identity((nvar))))

            xw = x * wi.reshape((nrow, 1))
            sxw = np.sqrt(np.sum(xw**2, axis=0))
            sxw = np.transpose(xw.T / sxw.reshape((nvar, 1)))
            svdx = np.linalg.svd(sxw)
            vdp_idx[i, ] = svdx[1][0] / svdx[1]
            phi = np.dot(svdx[2].T, np.diag(1 / svdx[1]))
            phi = np.transpose(phi**2)
            pi_ij = phi / np.sum(phi, axis=0)
            vdp_pi[i, :, :] = pi_ij

        local_CN = vdp_idx[:, nvar - 1].reshape((-1, 1))
        VDP = vdp_pi[:, nvar - 1, :]

        return corr_mat, vifs_mat, local_CN, VDP

    def spatial_variability(self, selector, n_iters=1000, seed=None):
        """
        Method to compute a Monte Carlo test of spatial variability for each
        estimated coefficient surface.

        WARNING: This test is very computationally demanding!

        Parameters
        ----------
        selector        : sel_bw object
                          should be the sel_bw object used to select a bandwidth
                          for the gwr model that produced the surfaces that are
                          being tested for spatial variation

        n_iters         : int
                          the number of Monte Carlo iterations to include for
                          the tests of spatial variability.

        seed            : int
                          optional parameter to select a custom seed to ensure
                          stochastic results are replicable. Default is none
                          which automatically sets the seed to 5536

        Returns
        -------

        p values        : list
                          a list of psuedo p-values that correspond to the model
                          parameter surfaces. Allows us to assess the
                          probability of obtaining the observed spatial
                          variation of a given surface by random chance.


        """
        temp_sel = copy.deepcopy(selector)
        temp_gwr = copy.deepcopy(self.model)

        if seed is None:
            np.random.seed(5536)
        else:
            np.random.seed(seed)

        fit_params = temp_gwr.fit_params
        search_params = temp_sel.search_params
        kernel = temp_gwr.kernel
        fixed = temp_gwr.fixed

        if self.model.constant:
            X = self.X[:, 1:]
        else:
            X = self.X

        init_sd = np.std(self.params, axis=0)
        SDs = []

        for x in range(n_iters):
            temp_coords = np.random.permutation(self.model.coords)
            temp_sel.coords = temp_coords
            temp_sel._build_dMat()
            temp_bw = temp_sel.search(**search_params)

            temp_gwr.W = temp_gwr._build_W(fixed, kernel, temp_coords, temp_bw)
            temp_params = temp_gwr.fit(**fit_params).params

            temp_sd = np.std(temp_params, axis=0)
            SDs.append(temp_sd)

        p_vals = (np.sum(np.array(SDs) > init_sd, axis=0) / float(n_iters))
        return p_vals

    @cache_readonly
    def predictions(self):
        P = self.model.P
        if P is None:
            raise TypeError('predictions only avaialble if predict'
                            'method is previously called on GWR model')
        else:
            predictions = np.sum(P * self.params, axis=1).reshape((-1, 1))
        return predictions

    def summary(self):
        """
        Print out GWR summary
        """
        summary = summaryModel(self) + summaryGLM(self) + summaryGWR(self)
        print(summary)
        return summary


class GWRResultsLite(object):
    """
    Lightweight GWR that computes the minimum diagnostics needed for bandwidth
    selection

    Parameters
    ----------
    model               : GWR object
                        pointer to GWR object with estimation parameters

    resid               : array
                        n*1, residuals of the repsonse

    influ               : array
                        n*1, leading diagonal of S matrix

    Attributes
    ----------
    tr_S                : float
                        trace of S (hat) matrix

    llf                 : scalar
                        log-likelihood of the full model; see
                        pysal.contrib.glm.family for damily-sepcific
                        log-likelihoods

    mu                  : array
                        n*, flat one dimensional array of predicted mean
                        response value from estimator

    resid_ss            : scalar
                          residual sum of sqaures

    """

    def __init__(self, model, resid, influ):
        self.y = model.y
        self.family = model.family
        self.n = model.n
        self.influ = influ
        self.resid_response = resid
        self.model = model

    @cache_readonly
    def tr_S(self):
        return np.sum(self.influ)

    @cache_readonly
    def llf(self):
        return self.family.loglike(self.y, self.mu)

    @cache_readonly
    def mu(self):
        return self.y - self.resid_response

    @cache_readonly
    def resid_ss(self):
        u = self.resid_response.flatten()
        return np.dot(u, u.T)


class MGWR(GWR):
    """
    Multiscale GWR estimation and inference.

    Parameters
    ----------
    coords        : array-like
                    n*2, collection of n sets of (x,y) coordinates of
                    observatons; also used as calibration locations is
                    'points' is set to None

    y             : array
                    n*1, dependent variable

    X             : array
                    n*k, independent variable, exlcuding the constant

    selector      : sel_bw object
                    valid sel_bw object that has successfully called
                    the "search" method. This parameter passes on
                    information from GAM model estimation including optimal
                    bandwidths.

    family        : family object
                    underlying probability model; provides
                    distribution-specific calculations

    sigma2_v1     : boolean
                    specify form of corrected denominator of sigma squared to use for
                    model diagnostics; Acceptable options are:

                    'True':       n-tr(S) (defualt)
                    'False':     n-2(tr(S)+tr(S'S))

    kernel        : string
                    type of kernel function used to weight observations;
                    available options:
                    'gaussian'
                    'bisquare'
                    'exponential'

    fixed         : boolean
                    True for distance based kernel function and  False for
                    adaptive (nearest neighbor) kernel function (default)

    constant      : boolean
                    True to include intercept (default) in model and False to exclude
                    intercept.

    dmat          : array
                    n*n, distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    sorted_dmat   : array
                    n*n, sorted distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.
    spherical     : boolean
                    True for shperical coordinates (long-lat),
                    False for projected coordinates (defalut).

    Attributes
    ----------
    coords        : array-like
                    n*2, collection of n sets of (x,y) coordinates of
                    observatons; also used as calibration locations is
                    'points' is set to None

    y             : array
                    n*1, dependent variable

    X             : array
                    n*k, independent variable, exlcuding the constant

    selector      : sel_bw object
                    valid sel_bw object that has successfully called
                    the "search" method. This parameter passes on
                    information from GAM model estimation including optimal
                    bandwidths.

    bw            : array-like
                    collection of bandwidth values consisting of either a distance or N
                    nearest neighbors; user specified or obtained using
                    Sel_BW with fb=True. Order of values should the same as
                    the order of columns associated with X

    family        : family object
                    underlying probability model; provides
                    distribution-specific calculations

    sigma2_v1     : boolean
                    specify form of corrected denominator of sigma squared to use for
                    model diagnostics; Acceptable options are:

                    'True':       n-tr(S) (defualt)
                    'False':     n-2(tr(S)+tr(S'S))

    kernel        : string
                    type of kernel function used to weight observations;
                    available options:
                    'gaussian'
                    'bisquare'
                    'exponential'

    fixed         : boolean
                    True for distance based kernel function and  False for
                    adaptive (nearest neighbor) kernel function (default)

    constant      : boolean
                    True to include intercept (default) in model and False to exclude
                    intercept.

    dmat          : array
                    n*n, distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    sorted_dmat   : array
                    n*n, sorted distance matrix between calibration locations used
                    to compute weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.

    spherical     : boolean
                    True for shperical coordinates (long-lat),
                    False for projected coordinates (defalut).

    n             : integer
                    number of observations

    k             : integer
                    number of independent variables

    mean_y        : float
                    mean of y

    std_y         : float
                    standard deviation of y

    fit_params    : dict
                    parameters passed into fit method to define estimation
                    routine

    W             : array-like
                    list of n*n arrays, spatial weights matrices for weighting all
                    observations from each calibration point: one for each
                    covariate (k)

    Examples
    --------

    #basic model calibration

    >>> import libpysal as ps
    >>> from mgwr.gwr import MGWR
    >>> from mgwr.sel_bw import Sel_BW
    >>> data = ps.io.open(ps.examples.get_path('GData_utm.csv'))
    >>> coords = list(zip(data.by_col('X'), data.by_col('Y')))
    >>> y = np.array(data.by_col('PctBach')).reshape((-1,1))
    >>> rural = np.array(data.by_col('PctRural')).reshape((-1,1))
    >>> fb = np.array(data.by_col('PctFB')).reshape((-1,1))
    >>> african_amer = np.array(data.by_col('PctBlack')).reshape((-1,1))
    >>> X = np.hstack([fb, african_amer, rural])
    >>> X = (X - X.mean(axis=0)) / X.std(axis=0)
    >>> y = (y - y.mean(axis=0)) / y.std(axis=0)
    >>> selector = Sel_BW(coords, y, X, multi=True)
    >>> selector.search(multi_bw_min=[2])
    [92.0, 101.0, 136.0, 158.0]
    >>> model = MGWR(coords, y, X, selector, fixed=False, kernel='bisquare', sigma2_v1=True)
    >>> results = model.fit()
    >>> print(results.params.shape)
    (159, 4)

    """

    def __init__(self, coords, y, X, selector, sigma2_v1=True,
                 kernel='bisquare',
                 fixed=False, constant=True, dmat=None,
                 sorted_dmat=None, spherical=False):
        """
        Initialize class
        """
        self.selector = selector
        self.bw = self.selector.bw[0]
        self.family = Gaussian()  # manually set since we only support Gassian MGWR for now
        GWR.__init__(self, coords, y, X, self.bw, family=self.family,
                     sigma2_v1=sigma2_v1, kernel=kernel, fixed=fixed,
                     constant=constant, dmat=dmat, sorted_dmat=sorted_dmat,
                     spherical=spherical)
        self.selector = selector
        self.sigma2_v1 = sigma2_v1
        self.points = None
        self.P = None
        self.offset = None
        self.exog_resid = None
        self.exog_scale = None
        self_fit_params = None

    # overwrite GWR method to handle multiple BW's
    def _build_W(self, fixed, kernel, coords, bw, points=None):
        Ws = []
        for bw_i in bw:
            if fixed:
                try:
                    W = fk[kernel](coords, bw_i, points, self.dmat,
                                   self.sorted_dmat,
                                   spherical=self.spherical)
                except BaseException:
                    raise  # TypeError('Unsupported kernel function  ', kernel)
            else:
                try:
                    W = ak[kernel](coords, bw_i, points, self.dmat,
                                   self.sorted_dmat,
                                   spherical=self.spherical)
                except BaseException:
                    raise  # TypeError('Unsupported kernel function  ', kernel)
            Ws.append(W)
        return Ws

    def fit(self):
        """
        Method that extracts information from Sel_BW (selector) object and
        prepares GAM estimation results for MGWRResults object.

        """
        S = self.selector.S
        R = self.selector.R
        params = self.selector.params
        predy = np.dot(S, self.y)
        CCT = np.zeros((self.n, self.k))
        for j in range(self.k):
            C = np.dot(np.linalg.inv(np.diag(self.X[:, j])), R[:, :, j])
            CCT[:, j] = np.diag(np.dot(C, C.T))
        # manually set since we onlly support Gaussian MGWR for now
        w = np.ones(self.n)
        return MGWRResults(self, params, predy, S, CCT, R, w)

    def predict(self):
        '''
        Not implemented.
        '''
        raise NotImplementedError('N/A')


class MGWRResults(GWRResults):
    """
    Class including common properties for a MGWR model.

    Parameters
    ----------
    model               : MGWR object
                          pointer to MGWR object with estimation parameters

    params              : array
                          n*k, estimated coefficients

    predy               : array
                          n*1, predicted y values

    S                   : array
                          n*n, hat matrix

    R                   : array
                          n*n*k, partial hat matrices for each covariate

    CCT                 : array
                          n*k, scaled variance-covariance matrix

    w                   : array
                          n*1, final weight used for iteratively re-weighted least
                          sqaures; default is None

    Attributes
    ----------
    model               : GWR Object
                          points to GWR object for which parameters have been
                          estimated

    params              : array
                          n*k, parameter estimates

    predy               : array
                          n*1, predicted value of y

    y                   : array
                          n*1, dependent variable

    X                   : array
                          n*k, independent variable, including constant

    family              : family object
                          underlying probability model; provides
                          distribution-specific calculations

    n                   : integer
                          number of observations

    k                   : integer
                          number of independent variables

    df_model            : integer
                          model degrees of freedom

    df_resid            : integer
                          residual degrees of freedom

    scale               : float
                          sigma squared used for subsequent computations

    w                   : array
                          n*1, final weights from iteratively re-weighted least
                          sqaures routine

    resid_response      : array
                          n*1, residuals of the repsonse

    resid_ss            : scalar
                          residual sum of sqaures

    W                   : array-like
                          list of n*n arrays, spatial weights matrices for weighting all
                          observations from each calibration point: one for each
                          covariate (k)

    S                   : array
                          n*n, hat matrix

    R                   : array
                          n*n*k, partial hat matrices for each covariate

    CCT                 : array
                          n*k, scaled variance-covariance matrix

    ENP                 : scalar
                          effective number of paramters, which depends on
                          sigma2, for the entire model

    ENP_j               : array-like
                          effective number of paramters, which depends on
                          sigma2, for each covariate in the model

    adj_alpha           : array
                          3*1, corrected alpha values to account for multiple
                          hypothesis testing for the 90%, 95%, and 99% confidence
                          levels; tvalues with an absolute value larger than the
                          corrected alpha are considered statistically
                          significant.

    adj_alpha_j         : array
                          k*3, corrected alpha values to account for multiple
                          hypothesis testing for the 90%, 95%, and 99% confidence
                          levels; tvalues with an absolute value larger than the
                          corrected alpha are considered statistically
                          significant. A set of alpha calues is computed for
                          each covariate in the model.

    tr_S                : float
                          trace of S (hat) matrix

    tr_STS              : float
                          trace of STS matrix

    R2                  : float
                          R-squared for the entire model (1- RSS/TSS)

    aic                 : float
                          Akaike information criterion

    aicc                : float
                          corrected Akaike information criterion to account
                          to account for model complexity (smaller
                          bandwidths)

    bic                 : float
                          Bayesian information criterio

    sigma2              : float
                          sigma squared (residual variance) that has been
                          corrected to account for the ENP

    std_res             : array
                          n*1, standardised residuals

    bse                 : array
                          n*k, standard errors of parameters (betas)

    influ               : array
                          n*1, leading diagonal of S matrix

    CooksD              : array
                          n*1, Cook's D

    tvalues             : array
                          n*k, local t-statistics

    llf                 : scalar
                          log-likelihood of the full model; see
                          pysal.contrib.glm.family for damily-sepcific
                          log-likelihoods

    mu                  : array
                          n*, flat one dimensional array of predicted mean
                          response value from estimator

    """

    def __init__(self, model, params, predy, S, CCT, R, w):
        """
        Initialize class
        """
        GWRResults.__init__(self, model, params, predy, S, CCT, w)
        self.R = R

    @cache_readonly
    def ENP_j(self):
        return [np.trace(self.R[:, :, j]) for j in range(self.R.shape[2])]

    @cache_readonly
    def adj_alpha_j(self):
        """
        Corrected alpha (critical) values to account for multiple testing during hypothesis
        testing. Includes corrected value for 90% (.1), 95% (.05), and 99%
        (.01) confidence levels. Correction comes from:

        da Silva, A. R., & Fotheringham, A. S. (2015). The Multiple Testing Issue in
        Geographically Weighted Regression. Geographical Analysis.

        """
        alpha = np.array([.1, .05, .001])
        pe = np.array(self.ENP_j).reshape((-1, 1))
        p = 1.
        return (alpha * p) / pe

    def critical_tval(self, alpha=None):
        """
        Utility function to derive the critial t-value based on given alpha
        that are needed for hypothesis testing

        Parameters
        ----------
        alpha           : scalar
                          critical value to determine which tvalues are
                          associated with statistically significant parameter
                          estimates. Default to None in which case the adjusted
                          alpha value at the 95 percent CI is automatically
                          used.

        Returns
        -------
        critical        : scalar
                          critical t-val based on alpha
        """
        n = self.n
        if alpha is not None:
            alpha = np.abs(alpha) / 2.0
            critical = t.ppf(1 - alpha, n - 1)
        else:
            alpha = np.abs(self.adj_alpha_j[:, 1]) / 2.0
            critical = t.ppf(1 - alpha, n - 1)
        return critical

    def filter_tvals(self, critical_t=None, alpha=None):
        """
        Utility function to set tvalues with an absolute value smaller than the
        absolute value of the alpha (critical) value to 0. If critical_t
        is supplied than it is used directly to filter. If alpha is provided
        than the critical t value will be derived and used to filter. If neither
        are critical_t nor alpha are provided, an adjusted alpha at the 95
        percent CI will automatically be used to define the critical t-value and
        used to filter. If both critical_t and alpha are supplied then the alpha
        value will be ignored.

        Parameters
        ----------
        critical        : scalar
                          critical t-value to determine whether parameters are
                          statistically significant

        alpha           : scalar
                          alpha value to determine which tvalues are
                          associated with statistically significant parameter
                          estimates

        Returns
        -------
        filtered       : array
                          n*k; new set of n tvalues for each of k variables
                          where absolute tvalues less than the absolute value of
                          alpha have been set to 0.
        """
        n = self.n
        if critical_t is not None:
            critical = np.array(critical_t)
        elif alpha is not None and critical_t is None:
            critical = self.critical_tval(alpha=alpha)
        elif alpha is None and critical_t is None:
            critical = self.critical_tval()

        subset = (self.tvalues < critical) & (self.tvalues > -1.0 * critical)
        tvalues = self.tvalues.copy()
        tvalues[subset] = 0
        return tvalues

    @cache_readonly
    def RSS(self):
        raise NotImplementedError(
            'Not yet implemented for multiple bandwidths')

    @cache_readonly
    def TSS(self):
        raise NotImplementedError(
            'Not yet implemented for multiple bandwidths')

    @cache_readonly
    def localR2(self):
        raise NotImplementedError(
            'Not yet implemented for multiple bandwidths')

    @cache_readonly
    def y_bar(self):
        raise NotImplementedError(
            'Not yet implemented for multiple bandwidths')

    @cache_readonly
    def predictions(self):
        raise NotImplementedError('Not yet implemented for MGWR')

    def local_collinearity(self):
        """
        Computes several indicators of multicollinearity within a geographically
        weighted design matrix, including:

        local condition number (n, 1)
        local variance-decomposition proportions (n, p)

        Returns four arrays with the order and dimensions listed above where n
        is the number of locations used as calibrations points and p is the
        nubmer of explanatory variables

        """
        x = self.X
        w = self.W
        nvar = x.shape[1]
        nrow = self.n
        vdp_idx = np.ndarray((nrow, nvar))
        vdp_pi = np.ndarray((nrow, nvar, nvar))

        for i in range(nrow):
            xw = np.zeros((x.shape))
            for j in range(nvar):
                wi = w[j][i]
                sw = np.sum(wi)
                wi = wi / sw
                xw[:, j] = x[:, j] * wi

            sxw = np.sqrt(np.sum(xw**2, axis=0))
            sxw = np.transpose(xw.T / sxw.reshape((nvar, 1)))
            svdx = np.linalg.svd(sxw)
            vdp_idx[i, ] = svdx[1][0] / svdx[1]

            phi = np.dot(svdx[2].T, np.diag(1 / svdx[1]))
            phi = np.transpose(phi**2)
            pi_ij = phi / np.sum(phi, axis=0)
            vdp_pi[i, :, :] = pi_ij

        local_CN = vdp_idx[:, nvar - 1].reshape((-1, 1))
        VDP = vdp_pi[:, nvar - 1, :]

        return local_CN, VDP

    def spatial_variability(self, selector, n_iters=1000, seed=None):
        """
        Method to compute a Monte Carlo test of spatial variability for each
        estimated coefficient surface.

        WARNING: This test is very computationally demanding!

        Parameters
        ----------
        selector        : sel_bw object
                          should be the sel_bw object used to select a bandwidth
                          for the gwr model that produced the surfaces that are
                          being tested for spatial variation

        n_iters         : int
                          the number of Monte Carlo iterations to include for
                          the tests of spatial variability.

        seed            : int
                          optional parameter to select a custom seed to ensure
                          stochastic results are replicable. Default is none
                          which automatically sets the seed to 5536

        Returns
        -------

        p values        : list
                          a list of psuedo p-values that correspond to the model
                          parameter surfaces. Allows us to assess the
                          probability of obtaining the observed spatial
                          variation of a given surface by random chance.


        """
        temp_sel = copy.deepcopy(selector)

        if seed is None:
            np.random.seed(5536)
        else:
            np.random.seed(seed)

        search_params = temp_sel.search_params

        if self.model.constant:
            X = self.X[:, 1:]
        else:
            X = self.X

        init_sd = np.std(self.params, axis=0)
        SDs = []

        for x in range(n_iters):
            temp_coords = np.random.permutation(self.model.coords)
            temp_sel.coords = temp_coords
            temp_sel._build_dMat()
            temp_sel.search(**search_params)
            temp_params = temp_sel.params
            temp_sd = np.std(temp_params, axis=0)
            SDs.append(temp_sd)

        p_vals = (np.sum(np.array(SDs) > init_sd, axis=0) / float(n_iters))
        return p_vals

    def summary(self):
        """
        Print out MGWR summary
        """
        summary = summaryModel(self) + summaryGLM(self) + summaryMGWR(self)
        print(summary)
        return



        
class STWR(GLM):
    """
    Spatiotemporal weighted regression is an extention of GWR in temporal dimention.
    This model can borrow value of points from past observed stages and improve 
    the good-of-fitness of the latest observed (current) stages.
    Current STWR can calculate weights by two type of spatiotemporal kernels 
    (based on Gaussian or bi-square) and improved sigmond form of temporal kernel. (It is built on a GLM framework). 
    STWR object prepares model input.
    Fit method performs estimation and returns a STWRResults object.

    Parameters
    ----------
    coords_list   : a list of array represent observed coordinates from different time stages.
                    the array is n*2, collection of n sets of (x,y) coordinates of
                    observatons; also used as calibration locations is
                    'points' is set to None

    y_list        : a list of array represent observed dependent variables from different time stages.
                    the array is n*1, dependent variable

    X_list        : a list of array represent observed independent variables from different time stages.
                    n*k, independent variable, exlcuding the constant

    tick_times_intervel : a list of scalars recorded all the time intervals during the observed time stages. 
                          The order is form the first(oledest) time stage to the latest time stage
                          Each scalar record a time interval between two time stages. 
                          To keep the length consistent, we defined the first element of the list is zero.  
    
    sita         :  a scalar represent a slope of linear relation of spatial bandwidth change over time.
                    defalut is zero represent that the spatial bandwidth is kept the same size during the observed time stages.
                    The spatial bandwidth may become narrower with the time intervals increasing.
    gwr_bw0      : a scalar represent the initial spatial bandwidth. The actural spatial bandwidth distance value for each regression point
                   is obtained by the maximun distance to its gwr_bw0 th most nearest neighbor.
                   
    tick_nums     : a scalar represet the number of time stages that current STWR model will used for calibatrition.
    
    dspal_mat_list: a list of spatial distance matrixes.
                     Each row of the matrix is the spatial distance from each points in the latest time stage
                     to all observed points in every time stages.
                     every matrix in the list depends on its latest time stage and the tick_nums used.
    sorted_dspal_list: a list of sorted spatial distance matrixs 
                    used for turncing by spatial bandwidth and compute the weight matrix. Defaults to None and is
                    primarily for avoiding duplicate computation during
                    bandwidth selection.
    d_tmp_list: a list of temporal distance matrixes
                Each row of the matrix is the temporal distance from each points in the latest time stage
                to all observed points in every time stages.
                every matrix in the list depends on its latest time stage and the tick_nums used.
    dspmat:   a big matrix of spatial distance
              Spatial distance matrix that combined all matrixes of dspal_mat_list horizontally. 
              Defaults to None and is primarily used for calculating the combined spatialtemporal weight matrix.
    dtpmat:   a big matrix of temporal distance
              Temporal distance matrix that combined all matrixes of tspal_mat_list horizontally. 
              Defaults to None and is primarily used for calculating the combined spatialtemporal weight matrix.  
    alpha:    a scalar which is used for adjust the spatial effect and temporal effect. It ranges from 0 to 1. 
    
    family:   family object
              underlying probability model; provides
              distribution-specific calculations
    offset:   array
            n*1, the offset variable at the ith location. For Poisson model
            this term is often the size of the population at risk or
            the expected size of the outcome in spatial epidemiology
            Default is None where Ni becomes 1.0 for all locations  
    sigma2_v1:      boolean
                    specify form of corrected denominator of sigma squared to use for
                    model diagnostics; Acceptable options are:
                    'True':       n-tr(S) (defualt)
                    'False':     n-2(tr(S)+tr(S'S))

    kernel:        string
                    type of spatiotemporal kernel function used to weight observations;
                    available options:
                    'spt_gaussian'
                    'spt_bisquare'
                    'spt_exponential'
                        
    spherical:    boolean
                    True for shperical coordinates (long-lat),
                    False for projected coordinates (defalut).
                    
    compress:     boolean, used for summary results
                  whether used for                
                       
    recorded     an interger number used for identifying whether need to store the calculated temporal matrixs for model predition.
                 Defalult is zero, and we need to manual set the value to 1 before we shall use the fitted model for predition,               



    Examples
    --------
    #basic model calibration

    >>> import libpysal as ps
    >>> from mgwr.gwr import GWR
    >>> cal_coords_list =[]
    >>> cal_y_list =[]
    >>> cal_X_list =[]
    >>> delt_stwr_intervel =[0.0]
    >>> csvFile = open("C:/Users/65532/Desktop/datav2/city_tol_cal_all.csv", "r")
    >>> df = pd.read_csv(csvFile,header = 0,names=['cal_coordsX','cal_coordsY','cal_x1','cal_x2','cal_x3','cal_x4','cal_x5','cal_y','timestamp'],
                 dtype = {"cal_coordsX" : "float64","cal_coordsY":"float64",
                          "cal_x1":"float64","cal_x2":"float64","cal_x3":"float64","cal_x4":"float64","cal_x5":"float64",
                          "cal_y" : "float64",
                          "timestamp":"float64"},
                 skip_blank_lines = True,
                 keep_default_na = False)
    >>> df = df.sort_values(by=['timestamp'])  
    >>> all_data = df.values
    >>> tick_time = all_data[0,-1]
    >>> cal_coord_tick = []
    >>> cal_X_tick =[]
    >>> cal_y_tick =[]
    >>> time_tol = 1.0e-7
    >>> lensdata = len(all_data)
    >>> for row in range(lensdata):
            cur_time = all_data[row,-1]
            if(abs(cur_time-tick_time)>time_tol):
                cal_coords_list.append(np.asarray(cal_coord_tick))
                cal_X_list.append(np.asarray(cal_X_tick))
                cal_y_list.append(np.asarray(cal_y_tick))
                delt_t = cur_time - tick_time
                delt_stwr_intervel.append(delt_t) 
                tick_time =cur_time
                cal_coord_tick = []
                cal_X_tick =[]
                cal_y_tick =[]
            coords_tick = np.array([all_data[row,0],all_data[row,1]])
            cal_coord_tick.append(coords_tick)
            x_tick = np.array([all_data[row,2],all_data[row,3],all_data[row,4],all_data[row,5],all_data[row,6]])
            cal_X_tick.append(x_tick)
            y_tick = np.array([all_data[row,7]])
            cal_y_tick.append(y_tick)

     >>> cal_cord_gwr = np.asarray(cal_coord_tick)
     >>> cal_X_gwr  = np.asarray(cal_X_tick)
     >>> cal_y_gwr = np.asarray(cal_y_tick)  
     >>> cal_coords_list.append(np.asarray(cal_coord_tick))
     >>> cal_X_list.append(np.asarray(cal_X_tick))
     >>> cal_y_list.append(np.asarray(cal_y_tick))
     >>> stwr_selector_ = Sel_Spt_BW(cal_coords_list, cal_y_list, cal_X_list,#gwr_bw0,
                                     delt_stwr_intervel,spherical = True)
     >>> optalpha,optsita,opt_btticks,opt_gwr_bw0 = stwr_selector_.search() 
     >>> stwr_model = STWR(cal_coords_list,cal_y_list,cal_X_list,delt_stwr_intervel,
                           optsita,opt_gwr_bw0,tick_nums=opt_btticks,alpha =optalpha,spherical = True,recorded = 1)
     >>> stwr_results = stwr_model.fit()
     >>> print(stwr_results.summary())   
    """
    def __init__(self, coords_list,y_list, X_list,
                 tick_times_intervel =None,sita = None,gwr_bw0 = None,
                 tick_nums = 1,dspal_mat_list = None,sorted_dspal_list = None,
                 d_tmp_list = None,dspmat = None,dtmat=None,alpha =0.3,
                 family=Gaussian(), offset=None,
                 sigma2_v1=True, kernel='spt_bisquare',
                 fixed=False, constant=True,spherical=False,compress = True,recorded = 0):
        self.tick_nums = tick_nums
        self.y_list = y_list
        self.X_list = X_list
        self.coords_list = coords_list
        self.compress = compress #self.mbpred
        self.recorded = recorded        
        y_arr = np.asarray(self.y_list[-1]).reshape((-1,1))
        X_arr = self.X_list[-1]
        for i in range(self.tick_nums-1):
             X_arr = np.vstack((X_arr,self.X_list[-(2+i)]))
             y_arr_tick =np.asarray(self.y_list[-(2+i)]).reshape((-1,1))
             y_arr = np.vstack((y_arr,y_arr_tick))                   
        GLM.__init__(self, y_arr, X_arr, family, constant=constant)        
        self.y_arr = y_arr
        self.X_arr = X_arr
        self.constant = constant
        self.sigma2_v1 = sigma2_v1
        self.gwr_bw0 = gwr_bw0
        self.kernel = kernel
        self.fixed = fixed
        self.tick_times_intervel = tick_times_intervel  
        self.sita = sita  
        if offset is None:
            self.offset = np.ones((self.n, 1))
        else:
            self.offset = offset * 1.0        
        self.fit_params = {}
        self.points_list = None
        self.exog_scale = None
        self.exog_resid = None
        self.P = None
        self.alpha = alpha
        
        self.dspal_mat_list = dspal_mat_list
        self.sorted_dspal_list = sorted_dspal_list
        self.d_tmp_list = d_tmp_list
        self.dspmat = dspmat
        self.dtmat = dtmat
        self.spherical = spherical        
        self.W = self._build_spt_W(fixed, kernel,coords_list,self.y_list,tick_times_intervel,sita,tick_nums,self.points_list,self.alpha,gwr_bw0 = self.gwr_bw0)    
    def _build_spt_W(self, fixed, kernel, coords_list,y_list,tick_times_intervel,sita,tick_nums,points_list=None,alpha=0.3,gwr_bw0=None,pred = False):
        if self.recorded == 1:
             W,self.dtmat,self.d_tmp_list = ak[kernel](coords_list,y_list,tick_times_intervel,sita,tick_nums,
                                           gwr_bw0,self.dspal_mat_list,
                                           self.sorted_dspal_list,
                                           self.d_tmp_list,
                                           self.dspmat,self.dtmat,points_list=points_list,alpha=alpha,
                                           spherical=self.spherical,prediction = pred,rcdtype=self.recorded)
             return W
        else:  
            if self.compress:
                if fixed:
                    try:
                        W = fk[kernel](coords_list,y_list,tick_times_intervel,sita,tick_nums,
                                       gwr_bw0,self.dspal_mat_list,
                                       self.sorted_dspal_list,
                                       self.d_tmp_list,
                                       self.dspmat,self.dtmat,points_list =points_list ,alpha=alpha,
                                       spherical=self.spherical,prediction = pred)
                    except BaseException:
                        raise  # TypeError('Unsupported kernel function  ', kernel)
                else:
                    try:
                        W = ak[kernel](coords_list,y_list,tick_times_intervel,sita,tick_nums,
                                       gwr_bw0,self.dspal_mat_list,
                                       self.sorted_dspal_list,
                                       self.d_tmp_list,
                                       self.dspmat,self.dtmat,points_list =points_list,alpha=alpha,
                                       spherical=self.spherical,prediction = pred)
                    except BaseException:
                        raise  # TypeError('Unsupported kernel function  ', kernel)
            else:
                if fixed:
                    try:
                        W = fk[kernel](coords_list,y_list,tick_times_intervel,sita,tick_nums,
                                       gwr_bw0,self.dspal_mat_list,
                                       self.sorted_dspal_list,
                                       self.d_tmp_list,
                                       self.dspmat,self.dtmat,points_list =points_list ,alpha=alpha,mbpred=True,
                                       spherical=self.spherical,prediction = pred)
                    except BaseException:
                        raise  # TypeError('Unsupported kernel function  ', kernel)
                else:
                    try:
                        W = ak[kernel](coords_list,y_list,tick_times_intervel,sita,tick_nums,
                                       gwr_bw0,self.dspal_mat_list,
                                       self.sorted_dspal_list,
                                       self.d_tmp_list,
                                       self.dspmat,self.dtmat,points_list =points_list,alpha=alpha,mbpred=True,
                                       spherical=self.spherical,prediction = pred)
                    except BaseException:
                        raise  # TypeError('Unsupported kernel function  ', kernel)
            return W
    def fit(self, ini_params=None, tol=1.0e-5, max_iter=20,
            solve='iwls',searching = False):      
        self.fit_params['ini_params'] = ini_params
        self.fit_params['tol'] = tol
        self.fit_params['max_iter'] = max_iter
        self.fit_params['solve'] = solve
        if solve.lower() == 'iwls':
            m = self.W.shape[0]
            if searching:
                resid = np.zeros((m, 1))
                influ = np.zeros((m, 1))
                for i in range(m):
                    wi = self.W[i].reshape((-1, 1))
                    if isinstance(self.family, Gaussian): 
                        betas, inv_xtx_xt = _compute_betas_gwr(
                                 self.y, self.X, wi)
                        influ[i] = np.dot(self.X[i], inv_xtx_xt[:, i])
                        predy = np.dot(self.X[i], betas)[0]
                        resid[i] = self.y[i] - predy
                    elif isinstance(self.family, (Poisson, Binomial)):
                        rslt = iwls(self.y, self.X, self.family,
                                    self.offset, None, ini_params, tol,
                                    max_iter, wi=wi)
                        inv_xtx_xt = rslt[5]
                        influ[i] = np.dot(self.X[i], inv_xtx_xt[:, i]) * \
                                   rslt[3][i][0]
                        predy = rslt[1][i]
                        resid[i] = self.y[i] - predy        
                return STWRResultsLite(self, resid, influ,m)
            else:
                params = np.zeros((m, self.k))
                predy = np.zeros((m, 1))
                w = np.zeros((m, 1))
                S = np.zeros((m, self.n))
                CCT = np.zeros((m, self.k))
                for i in range(m):
                    wi = self.W[i].reshape((-1, 1))#[:m,]
                    rslt = iwls(self.y, self.X, self.family,
                                self.offset, None, ini_params, tol,
                                max_iter, wi=wi)
                    params[i, :] = rslt[0].T
                    predy[i] = rslt[1][i]
                    w[i] = rslt[3][i]
                    S[i] = np.dot(self.X[i], rslt[5])
                    CCT[i] = np.diag(np.dot(rslt[5], rslt[5].T))
                return STWRResults(self, params, predy, S, CCT,w,compress = self.compress)

    def predict(self, points_list, P,  exog_scale=None, exog_resid=None,
                fit_params={}):
        if (exog_scale is None) & (exog_resid is None):
            train_gwr = self.fit(**fit_params)
            self.exog_scale = train_gwr.scale
            self.exog_resid = train_gwr.resid_response
        elif (exog_scale is not None) & (exog_resid is not None):
            self.exog_scale = exog_scale
            self.exog_resid = exog_resid
        else:
            raise InputError('exog_scale and exog_resid must both either be'
                             'None or specified')
        self.points_list = points_list
        pointslist_nums = len(self.points_list)
        if (pointslist_nums!=1):
              raise InputError('Current unsupported to predit multi times datasets')                    
        if self.constant:
                    P[0] = np.hstack([np.ones((len(P[0]), 1)), P[0]])
                    self.P = P[0]
        else:
            self.P = P[0]
        # No recorded when predict
        self.recorded = 0
   
        # Current model can only use for predict value at points at the same time with the latest obversed time stage
        # We can further modify this model and consider the ratio of variation, and even predict the temporal weight according to the ratio.          
        self.W = self._build_spt_W(
            self.fixed,
            self.kernel,
            self.coords_list,
            self.y_list,
            tick_times_intervel = self.tick_times_intervel,
            sita = self.sita,
            tick_nums = self.tick_nums,gwr_bw0=self.gwr_bw0,
            points_list = self.points_list,
            alpha = self.alpha,pred =True)    
        stwr = self.fit(**fit_params)                    
        return stwr          
    @cache_readonly
    def df_model(self):
        return None

    @cache_readonly
    def df_resid(self):
        return None

class STWRResultsLite(object):
    def __init__(self, model, resid, influ,m):
        self.m = m
        self.y = model.y[:m] 
        self.family = model.family
        self.n = m
        self.influ = influ
        self.resid_response = resid
        self.model = model
    @cache_readonly
    def tr_S(self):
        return np.sum(self.influ)

    @cache_readonly
    def llf(self):
        return self.family.loglike(self.y, self.mu)

    @cache_readonly
    def mu(self):
        return self.y - self.resid_response

    @cache_readonly
    def resid_ss(self):
        u = self.resid_response.flatten()
        return np.dot(u, u.T)


class STWRResults(GLMResults):
    def __init__(self, model, params, predy, S, CCT,w=None,compress = False):        
        self.model_copy = None  
        if(compress):
            self.model_copy =copy.deepcopy(model) 
            m = self.model_copy.W.shape[0]
            self.y = self.model_copy.y[:m]
            self.n = m
            self.y_ful = self.model_copy.y
            self.X_ful = self.model_copy.X
            self.model_copy.y = self.model_copy.y[:m]
            self.model_copy.X = self.model_copy.X[:m] 
        else:
           self.model_copy = model 
        GLMResults.__init__(self, self.model_copy, params, predy, w)
        self.W = self.model_copy.W       
        self.offset = self.model_copy.offset
        if w is not None:
            self.w = w
        self.predy = predy
        self.S = S
        self.CCT = self.cov_params(CCT, self.model_copy.exog_scale)
        self._cache = {}

    @cache_readonly
    def resid_ss(self):
        if self.model_copy.points_list is not None:
            raise NotImplementedError('Not available for STWR prediction')
        else:
            u = self.resid_response.flatten()
        return np.dot(u, u.T)

    @cache_readonly
    def scale(self, scale=None):
        if isinstance(self.family, Gaussian):
            scale = self.sigma2
        else:
            scale = 1.0
        return scale

    def cov_params(self, cov, exog_scale=None):
        """
        Returns scaled covariance parameters

        Parameters
        ----------
        cov         : array
                      estimated covariance parameters

        Returns
        -------
        Scaled covariance parameters

        """
        if exog_scale is not None:
            return cov * exog_scale
        else:
            return cov * self.scale

    @cache_readonly
    def tr_S(self):
        """
        trace of S (hat) matrix
        """
        return np.trace(self.S * self.w)

    @cache_readonly
    def tr_STS(self):
        """
        trace of STS matrix
        """
        return np.trace(np.dot(self.S.T * self.w, self.S * self.w))

    @cache_readonly
    def ENP(self):
        """
        effective number of parameters

        Defualts to tr(s) as defined in yu et. al (2018) Inference in
        Multiscale GWR

        but can alternatively be based on 2tr(s) - tr(STS)

        and the form depends on the specification of sigma2
        """
        if self.model_copy.sigma2_v1:
            return self.tr_S
        else:
            return 2 * self.tr_S - self.tr_STS

    @cache_readonly
    def y_bar(self):
        """
        weighted mean of y
        """
#        if self.model_copy.points is not None:
#            n = len(self.model_copy.points)
#        else:
#            n = self.n
#        off = self.offset.reshape((-1, 1))
#        arr_ybar = np.zeros(shape=(self.n, 1))
#        for i in range(n):
#            w_i = np.reshape(np.array(self.W[i]), (-1, 1))
#            sum_yw = np.sum(self.y.reshape((-1, 1)) * w_i)
#            arr_ybar[i] = 1.0 * sum_yw / np.sum(w_i * off)
#        return arr_ybar
        if self.model_copy.points_list is not None:
            n = len(self.model_copy.points_list[-1])
        else:
            n =self.W.shape[0] 
        off = self.offset.reshape((-1, 1))
        arr_ybar = np.zeros(shape=(self.n, 1))
        for i in range(n):         
            w_i = self.W[i].reshape((-1, 1))
            sum_yw = np.sum(self.y_ful.reshape((-1, 1)) * w_i)
            arr_ybar[i] = 1.0 * sum_yw / np.sum(w_i * off)
        return arr_ybar[:n]

    @cache_readonly
    def TSS(self):
        """
        geographically weighted total sum of squares

        Methods: p215, (9.9)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.

        """
        #        if self.model_copy.points is not None:
#            n = len(self.model_copy.points)  
#        else:
#                    n = self.n         
        if  self.model_copy.points_list is not None:
            n = len(self.model_copy.points_list[-1])
        else:
            n = self.W.shape[0]  
            
        TSS = np.zeros(shape=(n, 1))
        for i in range(n):
            TSS[i] = np.sum(np.reshape(np.array(self.W[i]), (-1, 1)) *
                            (self.y_ful.reshape((-1, 1)) - self.y_bar[i])**2)
        return TSS

    @cache_readonly
    def RSS(self):
        """
        geographically weighted residual sum of squares

        Methods: p215, (9.10)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        #        if self.model_copy.points is not None:
#            n = len(self.model_copy.points)
#            resid = self.model_copy.exog_resid.reshape((-1, 1))
#        else:
#            n = self.n
#            resid = self.resid_response.reshape((-1, 1))
        if self.model_copy.points_list is not None:
            n = len(self.model_copy.points_list[-1])
            resid = self.model_copy.exog_resid.reshape((-1, 1))
        else:
            n = self.W.shape[0]
            resid = self.resid_response.reshape((-1, 1))
        
        RSS = np.zeros(shape=(n, 1))      
        for i in range(n):      
            RSS[i] = np.sum(self.W[i].reshape((-1, 1))[:n]
                            * resid**2)
        return RSS

    @cache_readonly
    def localR2(self):
        """
        local R square

        Methods: p215, (9.8)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        if isinstance(self.family, Gaussian):
            return (self.TSS - self.RSS) / self.TSS
        else:
            raise NotImplementedError('Only applicable to Gaussian')

    @cache_readonly
    def sigma2(self):
        """
        residual variance

        if sigma2_v1 is True: only use n-tr(S) in denominator

        Methods: p214, (9.6),
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.

        and as defined  in Yu et. al. (2018) Inference in Multiscale GWR

        if sigma2_v1 is False (v1v2): use n-2(tr(S)+tr(S'S)) in denominator

        Methods: p55 (2.16)-(2.18)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.

        """
        if self.model_copy.sigma2_v1:
            return (self.resid_ss / (self.n - self.tr_S))
        else:
            # could be changed to SWSTW - nothing to test against
            return self.resid_ss / (self.n - 2.0 * self.tr_S + self.tr_STS)

    @cache_readonly
    def std_res(self):
        """
        standardized residuals

        Methods:  p215, (9.7)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        return self.resid_response.reshape(
            (-1, 1)) / (np.sqrt(self.scale * (1.0 - self.influ)))

    @cache_readonly
    def bse(self):
        """
        standard errors of Betas

        Methods:  p215, (2.15) and (2.21)
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        """
        return np.sqrt(self.CCT)

    @cache_readonly
    def influ(self):
        """
        Influence: leading diagonal of S Matrix
        """
        return np.reshape(np.diag(self.S), (-1, 1))

    @cache_readonly
    def cooksD(self):
        """
        Influence: leading diagonal of S Matrix

        Methods: p216, (9.11),
        Fotheringham, A. S., Brunsdon, C., & Charlton, M. (2002).
        Geographically weighted regression: the analysis of spatially varying
        relationships.
        Note: in (9.11), p should be tr(S), that is, the effective number of parameters
        """
        return self.std_res**2 * self.influ / (self.tr_S * (1.0 - self.influ))

    @cache_readonly
    def deviance(self):
        off = self.offset.reshape((-1, 1)).T
        y = self.y
        ybar = self.y_bar
        if isinstance(self.family, Gaussian):
            raise NotImplementedError(
                'deviance not currently used for Gaussian')
        elif isinstance(self.family, Poisson):
            dev = np.sum(
                2.0 * self.W * (y * np.log(y / (ybar * off)) - (y - ybar * off)), axis=1)
        elif isinstance(self.family, Binomial):
            dev = self.family.deviance(self.y, self.y_bar, self.W, axis=1)
        return dev.reshape((-1, 1))

    @cache_readonly
    def resid_deviance(self):
        if isinstance(self.family, Gaussian):
            raise NotImplementedError(
                'deviance not currently used for Gaussian')
        else:
            off = self.offset.reshape((-1, 1)).T
            y = self.y
            ybar = self.y_bar
            global_dev_res = ((self.family.resid_dev(self.y, self.mu))**2)
            dev_res = np.repeat(global_dev_res.flatten(), self.n)
            dev_res = dev_res.reshape((self.n, self.n))
            dev_res = np.sum(dev_res * self.W.T, axis=0)
            return dev_res.reshape((-1, 1))

    @cache_readonly
    def pDev(self):
        """
        Local percentage of deviance accounted for. Described in the GWR4
        manual. Equivalent to 1 - (deviance/null deviance)
        """
        if isinstance(self.family, Gaussian):
            raise NotImplementedError('Not implemented for Gaussian')
        else:
            return 1.0 - (self.resid_deviance / self.deviance)

    @cache_readonly
    def adj_alpha(self):
        """
        Corrected alpha (critical) values to account for multiple testing during hypothesis
        testing. Includes corrected value for 90% (.1), 95% (.05), and 99%
        (.01) confidence levels. Correction comes from:

        da Silva, A. R., & Fotheringham, A. S. (2015). The Multiple Testing Issue in
        Geographically Weighted Regression. Geographical Analysis.

        """
        alpha = np.array([.1, .05, .001])
        pe = self.ENP
        p = self.k
        return (alpha * p) / pe

    def critical_tval(self, alpha=None):
        """
        Utility function to derive the critial t-value based on given alpha
        that are needed for hypothesis testing

        Parameters
        ----------
        alpha           : scalar
                          critical value to determine which tvalues are
                          associated with statistically significant parameter
                          estimates. Default to None in which case the adjusted
                          alpha value at the 95 percent CI is automatically
                          used.

        Returns
        -------
        critical        : scalar
                          critical t-val based on alpha
        """
        n = self.n
        if alpha is not None:
            alpha = np.abs(alpha) / 2.0
            critical = t.ppf(1 - alpha, n - 1)
        else:
            alpha = np.abs(self.adj_alpha[1]) / 2.0
            critical = t.ppf(1 - alpha, n - 1)
        return critical

    def filter_tvals(self, critical_t=None, alpha=None):
        """
        Utility function to set tvalues with an absolute value smaller than the
        absolute value of the alpha (critical) value to 0. If critical_t
        is supplied than it is used directly to filter. If alpha is provided
        than the critical t value will be derived and used to filter. If neither
        are critical_t nor alpha are provided, an adjusted alpha at the 95
        percent CI will automatically be used to define the critical t-value and
        used to filter. If both critical_t and alpha are supplied then the alpha
        value will be ignored.

        Parameters
        ----------
        critical        : scalar
                          critical t-value to determine whether parameters are
                          statistically significant

        alpha           : scalar
                          alpha value to determine which tvalues are
                          associated with statistically significant parameter
                          estimates

        Returns
        -------
        filtered       : array
                          n*k; new set of n tvalues for each of k variables
                          where absolute tvalues less than the absolute value of
                          alpha have been set to 0.
        """
        n = self.n
        if critical_t is not None:
            critical = critical_t
        else:
            critical = self.critical_tval(alpha=alpha)

        subset = (self.tvalues < critical) & (self.tvalues > -1.0 * critical)
        tvalues = self.tvalues.copy()
        tvalues[subset] = 0
        return tvalues

    @cache_readonly
    def df_model(self):
        return self.n - self.tr_S

    @cache_readonly
    def df_resid(self):
        return self.n - 2.0 * self.tr_S + self.tr_STS

    @cache_readonly
    def normalized_cov_params(self):
        return None

    @cache_readonly
    def resid_pearson(self):
        return None

    @cache_readonly
    def resid_working(self):
        return None

    @cache_readonly
    def resid_anscombe(self):
        return None

    @cache_readonly
    def pearson_chi2(self):
        return None

    @cache_readonly
    def null(self):
        return None

    @cache_readonly
    def llnull(self):
        return None

    @cache_readonly
    def null_deviance(self):
        return None

    @cache_readonly
    def R2(self):
        if isinstance(self.family, Gaussian):
            TSS = np.sum((self.y.reshape((-1, 1)) -
                          np.mean(self.y.reshape((-1, 1))))**2)
            RSS = np.sum((self.y.reshape((-1, 1)) -
                          self.predy.reshape((-1, 1)))**2)
            return 1 - (RSS / TSS)
        else:
            raise NotImplementedError('Only available for Gaussian GWR')

    @cache_readonly
    def aic(self):
        return get_AIC(self)

    @cache_readonly
    def aicc(self):
        return get_AICc(self)

    @cache_readonly
    def bic(self):
        return get_BIC(self)

    @cache_readonly
    def D2(self):
        return None

    @cache_readonly
    def adj_D2(self):
        return None

    @cache_readonly
    def pseudoR2(self):
        return None

    @cache_readonly
    def adj_pseudoR2(self):
        return None

    @cache_readonly
    def pvalues(self):
        return None

    @cache_readonly
    def conf_int(self):
        return None

    @cache_readonly
    def use_t(self):
        return None

    def local_collinearity(self):
        """
        Computes several indicators of multicollinearity within a geographically
        weighted design matrix, including:

        local correlation coefficients (n, ((p**2) + p) / 2)
        local variance inflation factors (VIF) (n, p-1)
        local condition number (n, 1)
        local variance-decomposition proportions (n, p)

        Returns four arrays with the order and dimensions listed above where n
        is the number of locations used as calibrations points and p is the
        nubmer of explanatory variables. Local correlation coefficient and local
        VIF are not calculated for constant term.

        """
        x = self.X
        w = self.W
        nvar = x.shape[1]
        nrow = len(w)
        if self.model_copy.constant:
            ncor = (((nvar - 1)**2 + (nvar - 1)) / 2) - (nvar - 1)
            jk = list(combo(range(1, nvar), 2))
        else:
            ncor = (((nvar)**2 + (nvar)) / 2) - nvar
            jk = list(combo(range(nvar), 2))
        corr_mat = np.ndarray((nrow, int(ncor)))
        if self.model_copy.constant:
            vifs_mat = np.ndarray((nrow, nvar - 1))
        else:
            vifs_mat = np.ndarray((nrow, nvar))
        vdp_idx = np.ndarray((nrow, nvar))
        vdp_pi = np.ndarray((nrow, nvar, nvar))

        for i in range(nrow):
            wi = w[i]
            sw = np.sum(wi)
            wi = wi / sw
            tag = 0

            for j, k in jk:
                corr_mat[i, tag] = corr(
                    np.cov(x[:, j], x[:, k], aweights=wi))[0][1]
                tag = tag + 1

            if self.model_copy.constant:
                corr_mati = corr(np.cov(x[:, 1:].T, aweights=wi))
                vifs_mat[i, ] = np.diag(np.linalg.solve(
                    corr_mati, np.identity((nvar - 1))))

            else:
                corr_mati = corr(np.cov(x.T, aweights=wi))
                vifs_mat[i, ] = np.diag(np.linalg.solve(
                    corr_mati, np.identity((nvar))))

            xw = x * wi.reshape((nrow, 1))
            sxw = np.sqrt(np.sum(xw**2, axis=0))
            sxw = np.transpose(xw.T / sxw.reshape((nvar, 1)))
            svdx = np.linalg.svd(sxw)
            vdp_idx[i, ] = svdx[1][0] / svdx[1]
            phi = np.dot(svdx[2].T, np.diag(1 / svdx[1]))
            phi = np.transpose(phi**2)
            pi_ij = phi / np.sum(phi, axis=0)
            vdp_pi[i, :, :] = pi_ij

        local_CN = vdp_idx[:, nvar - 1].reshape((-1, 1))
        VDP = vdp_pi[:, nvar - 1, :]

        return corr_mat, vifs_mat, local_CN, VDP

    def spatial_variability(self, selector, n_iters=1000, seed=None):
        """
        Method to compute a Monte Carlo test of spatial variability for each
        estimated coefficient surface.

        WARNING: This test is very computationally demanding!

        Parameters
        ----------
        selector        : sel_bw object
                          should be the sel_bw object used to select a bandwidth
                          for the gwr model that produced the surfaces that are
                          being tested for spatial variation

        n_iters         : int
                          the number of Monte Carlo iterations to include for
                          the tests of spatial variability.

        seed            : int
                          optional parameter to select a custom seed to ensure
                          stochastic results are replicable. Default is none
                          which automatically sets the seed to 5536

        Returns
        -------

        p values        : list
                          a list of psuedo p-values that correspond to the model
                          parameter surfaces. Allows us to assess the
                          probability of obtaining the observed spatial
                          variation of a given surface by random chance.


        """
        temp_sel = copy.deepcopy(selector)
        temp_gwr = copy.deepcopy(self.model_copy)

        if seed is None:
            np.random.seed(5536)
        else:
            np.random.seed(seed)

        fit_params = temp_gwr.fit_params
        search_params = temp_sel.search_params
        kernel = temp_gwr.kernel
        fixed = temp_gwr.fixed

        if self.model_copy.constant:
            X = self.X[:, 1:]
        else:
            X = self.X

        init_sd = np.std(self.params, axis=0)
        SDs = []

        for x in range(n_iters):
            temp_coords = np.random.permutation(self.model_copy.coords)
            temp_sel.coords = temp_coords
            temp_sel._build_dMat()
            temp_bw = temp_sel.search(**search_params)

            temp_gwr.W = temp_gwr._build_W(fixed, kernel, temp_coords, temp_bw)
            temp_params = temp_gwr.fit(**fit_params).params

            temp_sd = np.std(temp_params, axis=0)
            SDs.append(temp_sd)

        p_vals = (np.sum(np.array(SDs) > init_sd, axis=0) / float(n_iters))
        return p_vals

    @cache_readonly
    def predictions(self):
        P = self.model_copy.P
        if P is None:
            raise TypeError('predictions only avaialble if predict'
                            'method is previously called on GWR model')
        else:
            predictions = np.sum(P * self.params, axis=1).reshape((-1, 1))
        return predictions

    def summary(self):
        """
        Print out STWR summary
        """
        summary = summaryModel(self) + summaryGLM(self) + summarySTWR(self)
        print(summary)
        return summary