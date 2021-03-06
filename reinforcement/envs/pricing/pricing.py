import numpy as np
from scipy.interpolate import interp1d
from numpy import exp, sqrt, log
from scipy.integrate import quad
from numpy.linalg import cholesky

"""Classes for my simulation"""

class Curve:

    def __init__(self, **kwargs):

        raise Exception('do not instantiate this class.')

    def __call__(self, date): #return the value of the curve at a defined time

        return self.curve(date)

class EquityForwardCurve(Curve):

    def __init__(self, spot=None, reference=None, discounting_curve=None,
                repo_rates=None, repo_dates=None, act = "No"):
        self.spot = spot
        self.reference = reference
        self.discounting_curve = discounting_curve
        if act =="360":
            self.T = ACT_360(repo_dates,self.reference)
        elif act == "365":
            self.T = ACT_365(repo_dates,self.reference)
        else:
            self.T = abs(repo_dates - self.reference)
        self.q = np.array([repo_rates[0]])
        for i in range(1,len(self.T)):
            alpha = ((self.T[i])*(repo_rates[i])-(self.T[i-1])*
                     (repo_rates[i-1]))/(self.T[i]-self.T[i-1])
            self.q = np.append(self.q,alpha)
        print("Forward repo time grid",self.T)
        print("Forward repo rate: ", self.q)

    def curve(self, date):
        q = lambda x: piecewise_function(x,self.T,self.q)
        date = np.array(date)
        if date.shape!=():
            return  np.asarray([(self.spot/self.discounting_curve(extreme))*exp(-quad_piecewise(q,self.T,0,extreme)) for extreme in date])
        else:
            return (self.spot/self.discounting_curve(date))*exp(-quad_piecewise(q,self.T,0,date))


class DiscountingCurve(Curve):

    def __init__(self, reference=None, discounts=None, dates=None, act = "No"):
        self.reference = reference
        if act=="360":
            self.T = ACT_360(dates,self.reference)
        elif act == "365":
            self.T = ACT_365(dates,self.reference)
        else:
            self.T = abs(dates - self.reference)
        if self.T[0] ==0:
            r_zero = np.array([0])   #at reference date the discount is 1
            r_zero = np.append(r_zero,(-1./((self.T[1:])))*log(discounts[1:]))
            r_zero[0] = r_zero[1]
        else:
            r_zero = (-1./(self.T))*log(discounts)
        self.r = interp1d(self.T,r_zero) #zero rate from 0 to T1
        print("zero interest rate time grid",self.T)
        print("zero interest rate: ",r_zero)

    def curve(self, date):
        return exp(-self.r(date)*date)


class ForwardVariance(Curve):  #I calculate the variance and not the volatility for convenience of computation

    def __init__(self, reference=None, spot_volatility=None, strikes=None, maturities=None, strike_interp=None, act="No"):
        self.reference = reference #pricing date of the implied volatilities
        if act=="360":
            self.T = ACT_360(maturities,self.reference)
        elif act=="365":
            self.T = ACT_365(maturities,self.reference)
        else:
            self.T = abs(maturities-self.reference)
        if isinstance(strike_interp, EquityForwardCurve):
            """Interpolation with the ATM forward"""
            self.spot_vol = np.array([])
            matrix_interpolated = interp1d(strikes,spot_volatility,axis=1)(strike_interp(self.T))
            for i in range (len(maturities)):
                self.spot_vol = np.append(self.spot_vol,matrix_interpolated[i,i])
        else:
            """Interpolation with the ATM spot"""
            self.spot_vol = interp1d(strikes,spot_volatility,axis=0)(strike_interp)

        self.forward_vol = np.array([self.spot_vol[0]]) #forward volatility from 0 to T1
        for i in range (1,len(self.T)):
            alpha = ((self.T[i])*(self.spot_vol[i]**2)-(self.T[i-1])*
                     (self.spot_vol[i-1]**2))/(self.T[i]-self.T[i-1])
            self.forward_vol = np.append(self.forward_vol, sqrt(alpha))
        print("Forward volatility time grid: ",self.T)
        print("Forward volatility: ",self.forward_vol)

    def curve(self,date):
        return piecewise_function(date,self.T,self.forward_vol**2)


class PricingModel:

    def __init__(self, **kwargs):

      raise Exception('model not implemented.')

    def simulate(self, fixings=None, Nsim=1, seed=14, **kwargs):

      raise Exception('simulate not implemented.')


class Black(PricingModel):
    """Black model"""

    def __init__(self, variance=None, forward_curve=None,**kwargs):
        self.variance = variance
        self.forward_curve = forward_curve

    def simulate(self, fixings=None, random_gen = None, corr = None, Nsim=1,**kwargs):
        fixings = np.array(fixings)
        if fixings.shape==():
            fixings = np.array([fixings])
        Ndim = len(corr)
        Nsim = int(Nsim)
        if corr is None:
            logmartingale = np.zeros((int(Nsim),len(fixings)))
            for i in range (len(fixings)):
                Z = random_gen.randn(Nsim)
                if i ==0:
                    logmartingale.T[i]=-0.5*quad_piecewise(self.variance,self.variance.T,0,fixings[i])+sqrt(quad_piecewise(self.variance,self.variance.T,0,fixings[i]))*Z
                elif i!=0:
                    logmartingale.T[i]=logmartingale.T[i-1]-0.5*quad_piecewise(self.variance,self.variance.T,fixings[i-1],fixings[i])+sqrt(quad_piecewise(self.variance,self.variance.T,fixings[i-1],fixings[i]))*Z
            return exp(logmartingale)*self.forward_curve(fixings)

        else:
            logmartingale = np.zeros((int(Nsim),len(fixings),Ndim))
            R = cholesky(corr)
            for i in range (len(fixings)):
                Z = random_gen.randn(Nsim,Ndim)
                ep = np.dot(R,Z.T)   #matrix of correlated random variables
                for j in range(Ndim):
                    if i ==0:
                        logmartingale[:,i,j]=-0.5*quad_piecewise(self.variance[j],self.variance[j].T,0,fixings[i])+sqrt(quad_piecewise(self.variance[j],self.variance[j].T,0,fixings[i]))*ep[j]
                    elif i!=0:
                        logmartingale[:,i,j]=logmartingale[:,i-1,j]-0.5*quad_piecewise(self.variance[j],self.variance[j].T,fixings[i-1],fixings[i])+sqrt(quad_piecewise(self.variance[j],self.variance[j].T,fixings[i-1],fixings[i]))*ep[j]
            M = exp(logmartingale)
            for i in range(Ndim):
                M[:,:,i] = M[:,:,i]*self.forward_curve[i](fixings)
            return M


"""Payoff Functions"""
def Vanilla_PayOff(St=None,strike=None, typo = 1): #Monte Carlo call payoff
    zero = np.zeros(St.shape)
    if typo ==1:
        """Call option payoff"""
        pay = St-strike
    elif typo ==-1:
        """Put option payoff"""
        pay = strike - St
    return np.maximum(pay,zero)

def ACT_365(date1,date2):
    """Day count convention for a normal year"""
    return abs(date1-date2)/365

def ACT_360(date1,date2):
    """Day count convention for a 360 year"""
    return abs(date1-date2)/360


"""Definition of a piecewise function"""
def piecewise_function(date, interval, value):
    mask = np.array([])
    mask = np.append(mask,(date>=0) & (date<interval[0]))
    for i in range(1,len(interval)):
        mask= np.append(mask,(date>=interval[i-1]) & (date<interval[i]))
    y = 0
    for i in range(len(interval)):
        y = y+ value[i]*mask[i]
    y = y+value[len(value)-1]*(date>=interval[len(value)-1])  #from the last date to infinity I assume as value that one of the last intervall
    return y

def quad_piecewise(f, time_grid, t_in, t_fin):
    """integral of a piecewise constant function"""
    y = np.array([])
    dt = np.array([])
    if t_in == t_fin:
        return 0
    if t_fin in time_grid:
        time_grid = time_grid[np.where(time_grid<=t_fin)[0]]
    if t_in in time_grid:
        time_grid = time_grid[np.where(time_grid>=t_in)[0]]
    if t_in not in time_grid:
        time_grid = time_grid[np.where(time_grid>t_in)[0]]
        time_grid = np.insert(time_grid,0,t_in)
    if t_fin not in time_grid:
        time_grid = time_grid[np.where(time_grid<t_fin)[0]]
        time_grid = np.insert(time_grid,len(time_grid),t_fin)
    for i in range(len(time_grid)-1):
        y = np.append(y,f(time_grid[i]))
    dt = np.diff(time_grid)
    return np.sum(y*dt)
