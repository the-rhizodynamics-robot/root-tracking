library(ggplot2)
library(splines)
library(here)
library(tools)


##plot of many roots roots, amplitude pos and neg plus loess, trying shading. NO POINTS
amplidute_by_time <- function(root_path_vector, xmax, ymin, ymax, fillcol = fillcol){
  #root_path_vector is a vector of all the roots to be plotted
  
  #adjust alpha to number of observations to promote consistency
  alpha = 1/length(root_path_vector)
  
  #create blank object
  p = ggplot()
  
  total = data.frame()
  
  for (r in root_path_vector) {
    #amplitude over time
    root = read.csv(r)
    total = rbind(total, root)
    maxs = data.frame(root[root$max,c("time", "amplitude")])
    mins = data.frame(root[root$min,c("time", "amplitude")])
    p =p + geom_smooth(data = maxs, aes(time, amplitude), method = "loess", se = FALSE, color = "gray",  size=.5) +
      geom_ribbon(data = maxs, aes(x = time, y = amplitude, xmin = 0, xmax = xmax, ymin= 0, ymax = predict(loess(amplitude ~ time))), alpha = alpha, fill = fillcol) +
      geom_smooth(data=mins, aes(time, amplitude), method = "loess", se = FALSE, color = "gray", size=.5) +
      geom_ribbon(data=mins, aes(x = time, y = amplitude, xmin = 0, xmax = xmax, ymin= predict(loess(amplitude ~ time)), ymax = 0), alpha = alpha, fill = fillcol) +
      ylim(ymin= ymin, ymax=ymax) +
      xlim(xmin = 0, xmax = xmax) +
      theme(axis.line = element_line(colour = "black"),
            panel.grid.major = element_blank(),
            panel.grid.minor = element_blank(),
            panel.border = element_blank(),
            panel.background = element_blank()) 
  }
  
  maxs = data.frame(total[total$max,c("time", "amplitude")])
  mins = data.frame(total[total$min,c("time", "amplitude")])
  
  p = p + geom_smooth(data = maxs, aes(time, amplitude), method = "loess", se = FALSE) +
    geom_smooth(data = mins, aes(time, amplitude), method = "loess", se = FALSE)
  
  #collect all termination_frames and put red points at end of loess plots
  #terminated_roots = total[!is.na(total$termination_frame),]
  #View(terminated_roots)
  #p = p + geom_point(data = terminated_roots, aes(x = arc_length, y = amplitude, col = "red"))
  
  print(p)
}


#plot of arc_length over time
del_arclength_by_time1 <- function(root_path_vector, xmax, ymax){
  #root_path_vector is a vector of all the roots to be plotted
  
  #create blank object
  p = ggplot()
  
  total = data.frame()
  
  for (r in root_path_vector) {
    #amplitude over arc_length
    root = read.csv(r)
    del_arc_length = data.frame(root[,c("time", "del_arc_length")])
   
    n = 4
    del_arc_length = aggregate(del_arc_length, list(rep(1:(nrow(del_arc_length) %/% n + 1), each = n, len = nrow(del_arc_length))), mean)[-1]
    del_arc_length$del_arc_length = del_arc_length$del_arc_length * 4
    
    total = rbind(total, del_arc_length)
    
    p =p + geom_smooth(data = del_arc_length, aes(time, del_arc_length), method = "loess", se = FALSE, color = "gray",  size=.5) +
      ylim(ymin=0, ymax=ymax) +
      xlim(xmin = 0, xmax = xmax) 
  }
  
  p = p +
    theme(axis.line = element_line(colour = "black"),
          panel.grid.major = element_blank(),
          panel.grid.minor = element_blank(),
          panel.border = element_blank(),
          panel.background = element_blank()) 
  
  del_arc_length = data.frame(total[,c("time", "del_arc_length")])

  p = p + geom_smooth(data = del_arc_length, aes(time, del_arc_length), method = "loess", se = TRUE) 
  
  print(p)
}


#plot of period
period_by_time1 <- function(root_path_vector, xmax, ymax){
  #create blank object
  p = ggplot()
  
  total = data.frame()
  
  for (r in root_path_vector) {
    #amplitude over arc_length
    root = read.csv(r)
    total = rbind(total, root)
    period = data.frame(root[root$max | root$min,c("time", "period")])
    p =p + geom_smooth(data = period, aes(time, period), method = "loess", se = FALSE, color = "gray",  size=.5) +
      ylim(ymin=0, ymax=ymax) +
      xlim(xmin = 0, xmax = xmax) 
  }
  
  p = p +
    theme(axis.line = element_line(colour = "black"),
          panel.grid.major = element_blank(),
          panel.grid.minor = element_blank(),
          panel.border = element_blank(),
          panel.background = element_blank()) 
  
  period= data.frame(total[total$max | total$min,c("time", "period")])
  
  p = p + geom_smooth(data = period, aes(time, period), method = "loess", se = TRUE) 
  
  print(p)
}

#plot of arc_length over time
arclength_by_time1 <- function(root_path_vector, xmax, ymax){
  #root_path_vector is a vector of all the roots to be plotted
  
  #create blank object
  p = ggplot()
  
  total = data.frame()
  
  for (r in root_path_vector) {
    #amplitude over arc_length
    root = read.csv(r)
    total = rbind(total, root)
    arc_length = data.frame(root[,c("time", "arc_length")])
    p =p + geom_smooth(data = arc_length, aes(time, arc_length), method = "loess", se = FALSE, color = "gray",  size=.5) +
      ylim(ymin=0, ymax=ymax) +
      xlim(xmin = 0, xmax = xmax) 
  }
  
  p = p +
    theme(axis.line = element_line(colour = "black"),
          panel.grid.major = element_blank(),
          panel.grid.minor = element_blank(),
          panel.border = element_blank(),
          panel.background = element_blank()) 
  
  arc_length = data.frame(total[,c("time", "arc_length")])

  p = p + geom_smooth(data = arc_length, aes(time, arc_length), method = "loess", se = TRUE) 
  
  print(p)
}


##plot of many roots roots, amplitude pos and neg plus loess, trying shading. NO POINTS
amplidute_by_arclength3 <- function(root_path_vector, ymin, ymax, fillcol = fillcol){
  #root_path_vector is a vector of all the roots to be plotted
  
  #adjust alpha to number of observations to promote consistency
  alpha = 1/length(root_path_vector)
  
  #create blank object
  p = ggplot()
  
  total = data.frame()
  
  for (r in root_path_vector) {
    #amplitude over arc_length
    root = read.csv(r)
    total = rbind(total, root)
    maxs = data.frame(root[root$max,c("arc_length", "amplitude")])
    mins = data.frame(root[root$min,c("arc_length", "amplitude")])
    p =p + geom_smooth(data = maxs, aes(arc_length, amplitude), method = "loess", se = FALSE, color = "gray",  size=.5) +
      geom_ribbon(data = maxs, aes(x = arc_length, y = amplitude, xmin = 0, xmax = 50, ymin= 0, ymax = predict(loess(amplitude ~ arc_length))), alpha = alpha, fill = fillcol) +
      geom_smooth(data=mins, aes(arc_length, amplitude), method = "loess", se = FALSE, color = "gray", size=.5) +
      geom_ribbon(data=mins, aes(x = arc_length, y = amplitude, xmin = 0, xmax = 50, ymin= predict(loess(amplitude ~ arc_length)), ymax = 0), alpha = alpha, fill = fillcol) +
      ylim(ymin= ymin, ymax=ymax) +
      xlim(xmin = 0, xmax = 50) +
      theme(axis.line = element_line(colour = "black"),
            panel.grid.major = element_blank(),
            panel.grid.minor = element_blank(),
            panel.border = element_blank(),
            panel.background = element_blank()) 
  }
  
  maxs = data.frame(total[total$max,c("arc_length", "amplitude")])
  mins = data.frame(total[total$min,c("arc_length", "amplitude")])
  
  p = p + geom_smooth(data = maxs, aes(arc_length, amplitude), method = "loess", se = FALSE) +
    geom_smooth(data = mins, aes(arc_length, amplitude), method = "loess", se = FALSE)
  
  #collect all termination_frames and put red points at end of loess plots
  #terminated_roots = total[!is.na(total$termination_frame),]
  #View(terminated_roots)
  #p = p + geom_point(data = terminated_roots, aes(x = arc_length, y = amplitude, col = "red"))
  
  print(p)
}
