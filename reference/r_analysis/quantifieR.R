#To do:
#Verify arc_length calculations are reasonable. I think they are noisy between adjacent timepoints but smooth over time.

#For plotting amplitude, use ggplot to make several overlaid spline fits/loess graphs in light color (for each root), then a dark average over all roots. Also highlight 
#mean elongation region or something to show difference in length?

#consider returning ggplot objects to allow for more complex combinging of plots? 

#Try tweakin xmax (perhaps making it average of the individual root xmax's)

#Try similar graphs of period and elongation rate

#Figure out a way to filter roots who just don't have as much data as other roots, but keep one that don't have as much data due to curling

#simple point plot of root depth

#generally handle data. IE, maybe have a way to make experimental folders. Perhaps pass list of experiments numbers and then all of those raw tip coordinates go there.

#Make experiment class

library(here)
source(here("circumnutation_quantification/","functions", "quantification_functions.R"))
source(here("circumnutation_quantification/","functions", "plotting_functions.R"))

#UTILITY FUNCTIONS AND CONSTANTS
mpp1=10/83.435  #mm per pixel conversion for camera 1
mpp2=10/250  #mm per pixel conversion for camera 2

#testing
#quant_looper("/home/rstudio/data/test_tip_coordinates/", 1, 200, mpp2, 100)

plot_looper("/home/rstudio/data/current_exp/tip_coordinates/", "2859_2908_", 1, 220, mpp2, .3)

quant_looper("/home/rstudio/data/current_exp/tip_coordinates/", 1, 240, mpp2, 100)

#grapher = read.csv(paste("/home/rstudio/data/outputs/", "2461_1", ".csv", sep = ""))


#amplitude by time.
#no points, no confidence band, overall trend
#20 dC
amplidute_by_time(files[c(1:7)], 72, -1.1, 1.1, fillcol = "black") #dark
amplidute_by_time(files[c(8:16)], 72, -1.1, 1.1, fillcol = "red") #red
amplidute_by_time(files[c(17:24)], 72, -1.1, 1.1, fillcol = "gray") #white

#24.5 dC
amplidute_by_time(files[c(25:36)], 72, -1.1, 1.1, fillcol = "black") #dark
amplidute_by_time(files[c(37:43)], 72, -1.1, 1.1, fillcol = "gray") #white


#amplitude by archlength
#no points, no confidence band, overall trend
#20 dC
amplidute_by_arclength3(files[c(1:7)], -1.1, 1.1, fillcol = "black") #dark
amplidute_by_arclength3(files[c(8:16)], -1.1, 1.1, fillcol = "red") #red
amplidute_by_arclength3(files[c(17:24)], -1.1, 1.1, fillcol = "gray") #white

#24.5 dC
amplidute_by_arclength3(files[c(25:36)], -1.1, 1.1, fillcol = "black") #dark
amplidute_by_arclength3(files[c(37:43)], -1.1, 1.1, fillcol = "gray") #white


#arc_length over time
#20 dC
arclength_by_time1(files[c(1:7)], 70, 50) #dark
arclength_by_time1(files[c(8:16)], 70, 50) #red
arclength_by_time1(files[c(17:24)], 70, 50) #white

#del_arc_length over time
#20 dC 
del_arclength_by_time1(files[c(1:7)], 70, .75) #dark
del_arclength_by_time1(files[c(8:16)], 70, .75) #red
del_arclength_by_time1(files[c(17:24)], 70, .75) #white

#24.5
del_arclength_by_time1(files[c(25:36)], 70, .75) #dark
del_arclength_by_time1(files[c(37:43)], 70, .75) #WHITE

#period over time
#24.5 dC
period_by_time1(files[c(1:7)], 70, 5) #dark
period_by_time1(files[c(8:16)], 70, 5) #red
period_by_time1(files[c(17:24)], 70, 5) #white


#amplitude by time.
#no points, no confidence band, overall trend
#24.5 dC white P.C.R. 
#amplidute_by_time(files[c(1:7)], 72, -1.1, 1.1, fillcol = "black")
#amplidute_by_time(files[c(8:13)], 72, -1.1, 1.1, fillcol = "black")
#amplidute_by_time(files[c(14:20)], 72, -1.1, 1.1, fillcol = "black")


#add box number and seed number to output of quantification function
#then for graphing give a list of boxes, then vectors of variable lengths with condition information, then append csvs into tidy format


