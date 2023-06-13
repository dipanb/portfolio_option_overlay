# -*- coding: utf-8 -*-
"""Option_Overlay_Strategy.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1kVE77drVcQGLfjPkpTuQ0wzNEKXctBCZ
"""

import yfinance as yf

import pandas as pd
import numpy as np

import scipy.stats as sci
import scipy.optimize as optim
import math
from tabulate import tabulate

Contra_Fund = yf.download('FCNTX', start="2015-01-01")['Adj Close'].pct_change(1).tail(-1)
SP500 = yf.download('^GSPC', start="2015-01-01")['Adj Close'].pct_change(1).tail(-1)

sci.pearsonr(Contra_Fund,SP500)[0]

Beta = np.cov(Contra_Fund,SP500)[0,1]/np.var(SP500)
print(Beta)

def d1(S,K,T,r,sigma):
    return(math.log(S/K)+(r+sigma**2/2.)*T)/(sigma*math.sqrt(T))
def d2(S,K,T,r,sigma):
    return d1(S,K,T,r,sigma)-sigma*math.sqrt(T)

def bs_call(S,K,sigma,T=1,r=.04):
    return S*sci.norm.cdf(d1(S,K,T,r,sigma))-K*math.exp(-r*T)*sci.norm.cdf(d2(S,K,T,r,sigma))

def bs_put(S,K,sigma,T=1,r=0.04):
    return -S*sci.norm.cdf(-d1(S,K,T,r,sigma)) + K*math.exp(-r*T)*sci.norm.cdf(-d2(S,K,T,r,sigma))

def option_premium(Put_M,Call_M,Put_Units,Call_Units,S,sigma):
  option_premium = 0
  if len(Put_M)>0:
    for i in range(len(Put_M)):
      option_premium = option_premium + Put_Units[i]*(int(Put_M[i]>0)*2-1)*bs_put(S,np.abs(S*Put_M[i]),sigma)
  if len(Call_M)>0:
    for i in range(len(Call_M)):
      option_premium = option_premium + Call_Units[i]*(int(Put_M[i]>0)*2-1)*bs_call(S,np.abs(S/Call_M[i]),sigma)
  return option_premium


def option_payoff(S,K,type,l_s):
  put_call = 1 if type == 'call' else -1
  l_s = 1 if l_s == 'long' else -1
  payoff = [l_s*max(put_call*(x - K),0) for x in S]
  return payoff

def option_premium_from_delta(Put_Delta,Call_Delta,Put_Units,Call_Units,S,sigma,r=0.04):
  option_premium = 0
  Put_K_list = []
  Call_K_list = []
  if len(Put_Delta)>0:
    for i in range(len(Put_Delta)):
      D1 = -sci.norm.ppf((-1 if Put_Delta[i]<0 else 1)*Put_Delta[i])
      D2 = D1 - sigma
      K = S/np.exp(D1*sigma - r - sigma**2/2) 

      Put_K_list.append(K)
      option_premium = option_premium + Put_Units[i]*(-1 if Put_Delta[i]<0 else 1) * (K*np.exp(-r)*sci.norm.cdf(-D2) - sci.norm.cdf(-D1)*S)

  if len(Call_Delta)>0:
    for i in range(len(Call_Delta)):
      D1 = sci.norm.ppf((-1 if Call_Delta[i]<0 else 1)*Call_Delta[i])
      D2 = D1 - sigma
      K = S/np.exp(D1*sigma - r - sigma**2/2) 

      Call_K_list.append(K)
      option_premium = option_premium + Call_Units[i]*(-1 if Call_Delta[i]<0 else 1) * (-K*np.exp(-r)*sci.norm.cdf(D2) + sci.norm.cdf(D1)*S)

    return {'option premium':option_premium,'Call K List':Call_K_list,'Put K List':Put_K_list}

def Strategy_Evaluator(Sims,SP500_Today,Contra_Fund_Today,Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,Hedge_Per,Strategy_Type):

  #Without Hedge
  CVaR_Contra = Sims[Sims[:,0] <= np.quantile(Sims[:,0],0.05),0].mean()
  Returns_Contra = np.mean(Sims[:,0])
  St_Dev_Contra = np.std(Sims[:,0])
  Sharpe_Ratio_Contra = (Returns_Contra - 0.04)/St_Dev_Contra
  Calmar_Ratio_Contra = (Returns_Contra - 0.04)/np.abs(np.min(Returns_Contra))

  #Hedging
  if Strategy_Type == 'Moneyness':
    #moneyness Strategy
    Option_Premium = option_premium(Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,SP500_Today,np.std(Sims[:,1]))
    Hedge_Cost = Option_Premium*Contra_Fund_Today/SP500_Today*Hedge_Per*Beta

    print(Option_Premium,Hedge_Cost/(Hedge_Cost+Contra_Fund_Today))
    SP500_Sim_Prices_from_Beta_and_Fund_Prices = (1+Sims[:,0])*SP500_Today/Beta

    PayOff = np.zeros(len(SP500_Sim_Prices_from_Beta_and_Fund_Prices)) 
    if len(Put_Moneyness)>0:
      for i in range(len(Put_Moneyness)):
        PayOff = PayOff + np.dot(Put_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,abs(Put_Moneyness[i])*SP500_Today,"put","long" if Put_Moneyness[i]>0 else "short"))
    if len(Call_Moneyness)>0:
      for i in range(len(Call_Moneyness)):
        PayOff = PayOff + np.dot(Call_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,SP500_Today/abs(Call_Moneyness[i]),"call","long" if Call_Moneyness[i]>0 else "short"))

    PayOff_Contra = PayOff * Contra_Fund_Today/SP500_Today * Hedge_Per
    Hedged_Returns = ((1+Sims[:,0])*Contra_Fund_Today+PayOff_Contra)/(Contra_Fund_Today + Hedge_Cost) - 1
  else:
    #Delta Strategy
    temp_dict = option_premium_from_delta(Put_Moneyness,Call_Moneyness,Put_Units, Call_Units, SP500_Today,np.std(Sims[:,1]),r=0.04)
    Put_K = temp_dict['Put K List']
    Call_K = temp_dict['Call K List'] 
    Option_Premium = temp_dict['option premium']
    Hedge_Cost = Option_Premium*Contra_Fund_Today/SP500_Today*Hedge_Per*Beta

    SP500_Sim_Prices_from_Beta_and_Fund_Prices = (1+Sims[:,0])*SP500_Today/Beta

    PayOff = np.zeros(len(SP500_Sim_Prices_from_Beta_and_Fund_Prices)) 
    if len(Put_Moneyness)>0:
      for i in range(len(Put_Moneyness)):
        PayOff = PayOff + np.dot(Put_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,Put_K[i],"put","long" if Put_Moneyness[i]>0 else "short"))
    if len(Call_Moneyness)>0:
      for i in range(len(Call_Moneyness)):
        PayOff = PayOff + np.dot(Call_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,Call_K[i],"call","long" if Call_Moneyness[i]>0 else "short"))

    PayOff_Contra = PayOff * Contra_Fund_Today/SP500_Today * Hedge_Per
    Hedged_Returns = ((1+Sims[:,0])*Contra_Fund_Today+PayOff_Contra)/(Contra_Fund_Today + Hedge_Cost) - 1

  CVaR_Hedge = Hedged_Returns[Hedged_Returns <= np.quantile(Hedged_Returns,0.05)].mean()
  Returns_Hedge = np.mean(Hedged_Returns)
  St_Dev_Hedge = np.std(Hedged_Returns)
  Sharpe_Ratio_Hedge = (Returns_Hedge - 0.04)/St_Dev_Hedge
  Calmar_Ratio_Hedge = (Returns_Hedge - 0.04)/abs(min(Hedged_Returns))

  return {'No hedge Returns':Returns_Contra,'No hedge St Dev':St_Dev_Contra,'No hedge Sharpe Ratio':Sharpe_Ratio_Contra,'No hedge CVaR':CVaR_Contra, 'No Hedge Calmar Ratio':Calmar_Ratio_Contra,
          'Hedge Returns':Returns_Hedge,'Hedge St Dev':St_Dev_Hedge,'Hedge Sharpe Ratio':Sharpe_Ratio_Hedge,'Hedge CVaR':CVaR_Hedge,'Hedge Calmar Ratio':Calmar_Ratio_Hedge, 
          'Fund Percentage Used in Hedge':Hedge_Cost/(Contra_Fund_Today + Hedge_Cost)}

Sims = np.random.multivariate_normal([((1 + Contra_Fund).resample('Y').prod() - 1).mean(),((1 + SP500).resample('Y').prod() - 1).mean()], np.cov(Contra_Fund,SP500)*252, size=10000)

#Day of hedge inputs
SP500_Today = 4298.86
Contra_Fund_Today = 14.4

#Pecentage of Portfolio Hedged
Hedge_Per = 1

#Moneyness Strategy
Put_Moneyness = [0.95,-0.9]
Call_Moneyness = []

#Delta Strategy
Put_Delta = [0.3,-0.2]
Call_Delta = [-.1]

#Units
Put_Units = [1,1]
Call_Units = []

Strategy_Evaluator(Sims,SP500_Today,Contra_Fund_Today,Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,Hedge_Per,"Moneyness")
# Strategy_Evaluator(Sims,SP500_Today,Contra_Fund_Today,Put_Delta,Call_Delta,Hedge_Per,"Delta")

#Optimizer
def objective_fn(x, Num_Legs,Strategy_Type,Sims,SP500_Today,Contra_Fund_Today,Return_Type):

  Put_Moneyness = []
  Call_Moneyness = []
  Put_Units = []
  Call_Units = []

  for i in range(Num_Legs):
    if x[(i+1)*2-1]<0:
      Put_Units.append(np.abs(x[(i+1)*2-2]))
      Put_Moneyness.append((2*int(x[(i+1)*2-2]<0)-1)*x[(i+1)*2-1])
    else :
      Call_Units.append(np.abs(x[(i+1)*2-2]))
      Call_Moneyness.append((2*int(x[(i+1)*2-2]>0)-1)*x[(i+1)*2-1])

  Hedge_Per = x[-1]

  if Strategy_Type == 'Moneyness':
    #moneyness Strategy
    Option_Premium = option_premium(Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,SP500_Today,np.std(Sims[:,1]))
    Hedge_Cost = Option_Premium*Contra_Fund_Today/SP500_Today*Hedge_Per*Beta

    if Return_Type=='Premium Cost':
      return Hedge_Cost

    SP500_Sim_Prices_from_Beta_and_Fund_Prices = (1+Sims[:,0])*SP500_Today/Beta

    PayOff = np.zeros(len(SP500_Sim_Prices_from_Beta_and_Fund_Prices)) 
    if len(Put_Moneyness)>0:
      for i in range(len(Put_Moneyness)):
        PayOff = PayOff + np.dot(Put_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,abs(Put_Moneyness[i])*SP500_Today,"put","long" if Put_Moneyness[i]>0 else "short"))
    if len(Call_Moneyness)>0:
      for i in range(len(Call_Moneyness)):
        PayOff = PayOff + np.dot(Call_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,SP500_Today/abs(Call_Moneyness[i]),"call","long" if Call_Moneyness[i]>0 else "short"))

    PayOff_Contra = PayOff * Contra_Fund_Today/SP500_Today * Hedge_Per
    Hedged_Returns = ((1+Sims[:,0])*Contra_Fund_Today+PayOff_Contra)/(Contra_Fund_Today + Hedge_Cost) - 1
  else:
    #Delta Strategy
    temp_dict = option_premium_from_delta(Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,SP500_Today,np.std(Sims[:,1]),r=0.04)
    Put_K = temp_dict['Put K List']
    Call_K = temp_dict['Call K List'] 
    Option_Premium = temp_dict['option premium']
    Hedge_Cost = Option_Premium*Contra_Fund_Today/SP500_Today*Hedge_Per*Beta

    if Return_Type=='Premium Cost':
      return Hedge_Cost

    SP500_Sim_Prices_from_Beta_and_Fund_Prices = (1+Sims[:,0])*SP500_Today/Beta

    PayOff = np.zeros(len(SP500_Sim_Prices_from_Beta_and_Fund_Prices)) 
    if len(Put_Moneyness)>0:
      for i in range(len(Put_Moneyness)):
        PayOff = PayOff + np.dot(Put_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,Put_K[i],"put","long" if Put_Moneyness[i]>0 else "short"))
    if len(Call_Moneyness)>0:
      for i in range(len(Call_Moneyness)):
        PayOff = PayOff + np.dot(Call_Units[i],option_payoff(SP500_Sim_Prices_from_Beta_and_Fund_Prices,Call_K[i],"call","long" if Call_Moneyness[i]>0 else "short"))

    PayOff_Contra = PayOff * Contra_Fund_Today/SP500_Today * Hedge_Per
    Hedged_Returns = ((1+Sims[:,0])*Contra_Fund_Today+PayOff_Contra)/(Contra_Fund_Today + Hedge_Cost) - 1

  if Return_Type=='Hedged Returns':
    return Hedged_Returns.mean()

  return -Hedged_Returns[Hedged_Returns <= np.quantile(Hedged_Returns,0.05)].mean()

#####Inputs to optimizer#########
# Num_Legs = 2
# Strategy_Type = "Moneyness"
# Hedge_Per = 1
# #Units negative - Short 
# #Moneyness Negative - Put
# x = [2,-0.95,-1,-0.9,Hedge_Per]

Num_Legs = 1
Strategy_Type = "Moneyness"
Hedge_Per = 1
#Units negative - Short 
#Moneyness Negative - Put
x = [1,-0.95,Hedge_Per]

# bnds = ((-10,10),(-2,2),(-10,10),(-2,2),(0,1))
bnds = ((-10,10),(-2,2),(0,1))

price_cons = ({'type':'ineq', 'fun':lambda x: 0.05 - objective_fn(x, Num_Legs,Strategy_Type,Sims,SP500_Today,Contra_Fund_Today,'Premium Cost')/Contra_Fund_Today}) 
return_cons = ({'type':'ineq', 'fun':lambda x: objective_fn(x, Num_Legs,Strategy_Type,Sims,SP500_Today,Contra_Fund_Today,'Hedged Returns')/np.mean(Sims[:,0]) - 0.9})

moneyness_cons_1_low =  ({'type':'ineq', 'fun':lambda x: np.abs(x[1])-0.8})
# moneyness_cons_2_low =  ({'type':'ineq', 'fun':lambda x: np.abs(x[3])-0.8})

moneyness_cons_1_up =  ({'type':'ineq', 'fun':lambda x: 1.05-np.abs(x[1])})
# moneyness_cons_2_up =  ({'type':'ineq', 'fun':lambda x: 1.05-np.abs(x[3])})

# cons = [price_cons,return_cons,moneyness_cons_1_low,moneyness_cons_2_low,moneyness_cons_1_up,moneyness_cons_2_up]
cons = [price_cons,return_cons,moneyness_cons_1_low,moneyness_cons_1_up]

res= optim.minimize(objective_fn,x,
                    method='SLSQP',
                    bounds=bnds,
                    constraints = cons,
                    args = (Num_Legs,Strategy_Type,Sims,SP500_Today,Contra_Fund_Today,"CVaR"),
                    options = {'maxiter':1000,'disp':True})
print("x: ",res['x'])
print("CVaR: ",-res['fun'])

x = res['x']
Put_Moneyness = []
Call_Moneyness = []
Put_Units = []
Call_Units = []

for i in range(Num_Legs):
  if x[(i+1)*2-1]<0:
    Put_Units.append(np.abs(x[(i+1)*2-2]))
    Put_Moneyness.append((2*int(x[(i+1)*2-2]<0)-1)*x[(i+1)*2-1])
  else :
    Call_Units.append(np.abs(x[(i+1)*2-2]))
    Call_Moneyness.append((2*int(x[(i+1)*2-2]>0)-1)*x[(i+1)*2-1])

Hedge_Per = x[-1]

print('Naked vs Optimized Strategy')
print(Strategy_Evaluator(Sims,SP500_Today,Contra_Fund_Today,Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,Hedge_Per,"Moneyness"))
print(Put_Moneyness,Call_Moneyness,Put_Units,Call_Units,Hedge_Per)

Contra_Fund_Today/SP500_Today*Beta * 1000 * 1.028

