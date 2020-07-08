**S**patiotemporal **W**eighted **R**egression (STWR)
=======================================
News:
1.Welcome to read and comment our article "A Spatiotemporal Weighted Regression Model (STWRv1.0) for Analyzing Local Non-stationarity in Space and Time",which can be accessed via the link below:https://doi.org/10.5194/gmd-2019-292 

Spatiotemporal Weighted Regression

This module provides functionality to calibrate STWR as well as traditional GWR and MGWR 2.0.2 (https://github.com/pysal/mgwr). It is
built upon the sparse generalized linear modeling (spglm) module. 

Features
--------
- STWR model calibration via a new spatiotemporal kernel. And it can use data observed at different past time stages to make the model 
 better fit the latest observation points. A highlight of STWR is a new temporal kernel function, in which the method for temporal weighting 
 is based on the degree of impact from each observed point to a regression point. The degree of impact, in turn, is based on the rate of 
 value variation of the nearby observed point during the time interval. The updated spatiotemporal kernel function is based on a weighted 
 combination of the temporal kernel with a commonly used spatial kernel (Gaussian or bi-square) by specifying a linear function of spatial 
 bandwidth versus time. 

- GWR model calibration via iteratively weighted least squares for Gaussian,
  Poisson, and binomial probability models.
- GWR bandwidth selection via golden section search or equal interval search
- GWR-specific model diagnostics, including a multiple hypothesis test
  correction and local collinearity
- Monte Carlo test for spatial variability of parameter estimate surfaces
- GWR-based spatial prediction
- MGWR model calibration via GAM iterative backfitting for Gaussian model
- MGWR covariate-specific inference, including a multiple hypothesis test
  correction and local collinearity  

