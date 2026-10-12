library(ggplot2)
library(splines)
library(tools)

#PLOT GENERATOR HELPER FUNCTION
plot_looper <- function(exp_dir, timestamp, start, stop, mpp, spn){
    plants = list.files(exp_dir, pattern="*.csv", full.names=TRUE)
    
    for (p in plants) {
        count = 0
        xs = vector()
        ys = vector()
        coords = colnames(read.csv(p))
        for (t in coords) {
            count = count + 1
            a = gsub("[^0-9.-]", "", t)
            a = gsub(".", " ", a, fixed = T)
            a = scan(text = a, what = "", quiet = T)
            xs[count] = as.integer(a[1])
            ys[count] = as.integer(a[2])
          }
        
        plant = file_path_sans_ext(basename(p))
        dat = data.frame(xs, ys)
        colnames(dat) = c("BX", "BY")
        #colnames(dat) = c("BX", "BY")
        plot_curve(timestamp, plant, dat, start, stop, mpp, spn)

    }
}


#Quant GENERATOR HELPER FUNCTION
quant_looper <- function(exp_dir, start, stop, mpp, dfspline) {
    timestamp = exp_dir
    plants = list.files(exp_dir, pattern="*.csv", full.names=TRUE)
    for (p in plants) {
      count = 0
      xs = vector()
      ys = vector()
      coords = colnames(read.csv(p))
      for (t in coords) {
        count = count + 1
        a = gsub("[^0-9.-]", "", t)
        a = gsub(".", " ", a, fixed = T)
        a = scan(text = a, what = "", quiet = T)
        xs[count] = as.integer(a[1])
        ys[count] = as.integer(a[2])
      }
      plant = file_path_sans_ext(basename(p))
      dat = data.frame(xs, ys)
      colnames(dat) = c("BX", "BY")
      dat_trimmed = root_curl_trim(dat, plant)
      root_quant(timestamp, plant, dat_trimmed, start, stop, mpp, dfspline)
    }
}


#ORIGINAL PLOT GENERATOR FUNCTIONS
#function to plot curves and calculate amplitudes. coords is the dataframe of coordinates. start and stop are datapoints being plotted.
#mpp is the pixel conversion. spn is the span for the loess model. It is increased for the 1-NAA experiment because root growth was
#extremely slow.

plot_curve <- function(timestamp, plant, coords, start, stop, mpp, spn) {
    tryCatch(
    expr = {
    offset = which(coords[,1] != 10000)[[1]]
    start = offset
    xy_df=coords[start:stop,] #columns 2 and 3 are the coordinates, only take rows we're interested in plotting
    #print(xy_df)
    #loess regression to estimate center line of root. span = .2 for almost everything, .6 for 1-NAA treated
    loessMod10 <- loess(BX~BY, data=xy_df, span=spn) #use Loess to estimate centerline. Span can be tuned. BX and BY are from imageJ
    jpeg(file=paste("/home/rstudio/data/current_exp/outputs/plots/", timestamp, plant, "_xy_plot.jpeg", sep = ""))
    plot(BX~BY, data=xy_df, main = plant)
    lines(xy_df$BY, predict(loessMod10, data.frame(BY = xy_df$BY)))
    dev.off()

    #correct for drift
    BX_corrected=0 #will be the BX adjusted to the point along the loess prediction surface nearest to the observed point
    BX_min=0 #keeps track of shortest distance
    dist=0 #placeholder variable for distance

    #count is a counter variable
    count=0
    for (obs in xy_df$BY){
      count=count+1 #track which observation is being analyzed
      BX_min=xy_df[count,1]-predict(loessMod10, xy_df[count,])
      for (offset in c(-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6)) { #the pixel offset range we're scanning over. Can tune.
        if(!is.na(predict(loessMod10, obs + offset))) #deal with predicting at the ends where offsets will produce NAs
          dist=euc.dist(xy_df[count,],c(predict(loessMod10, obs+offset),obs+offset)) #calculate distance of each point to point along curve with offset
        #print(dist)
        if(dist<abs(BX_min)) {
          BX_min=BX_min/abs(BX_min)*dist #save offset to minimum if it's smaller than the previously found minimum. Preserve sign.
      }
    }
    BX_corrected[count]=BX_min
    }

    #plot individual points
    jpeg(file=paste("/home/rstudio/data/current_exp/outputs/plots/", timestamp, plant, "_spline_plot.jpeg", sep = ""))
    plot(BX_corrected*mpp~c(seq((start-1)/4,(stop-1)/4,.25)), ylim=c(-1.25,1.25), xlab = "hours",ylab = "distance from center line (millimeters)", main = plant)
    #plot a spline over the corrected values
    spline.lm <- lm((BX_corrected*mpp) ~ ns(seq((start-1)/4,(stop-1)/4,.25), df=100), data=xy_df)
    lines(seq((start-1)/4,(stop-1)/4,.25), predict(spline.lm), lwd=2, col='red')
    dev.off()
    }, 
    error = function(e){ 
        message(paste("could not complete plot curve for root: ", plant))
        print(e)
    }
    )
    }



#IDENTIFY MAXS AND MINS, CALCULATE PERIODS, ASSIGN Y VALUES, CALCULATE ARC_LENGTH
#FOR FIRST AND LAST TIMEPOINTS, ONLY GO FROM SECOND TO SECOND-TO-LAST?
#FIRST LINE/LAST LINE: "time","max","min","amplitdue","period","y","arc_length"
# 0, 0, 0, CALC, 0, 0, 0

#ORIGINAL AMPLITUDE CALCULATION FUNCTIONS
root_quant <- function (timestamp, plant, coords, start, stop, mpp, dfspline) {
  tryCatch(
    expr = {
    print(plant)
    offset = which(coords[,1] != 10000)[[1]]
    start = offset
    end_frame = stop
    col_names = c("time","max","min","amplitude","period","x", "y","arc_length", "del_arc_length", "box","seed","termination_frame")
    data = data.frame(matrix(ncol = length(col_names), nrow = stop - start + 1))  
    colnames(data) = col_names

    data[,1] = seq(start, (stop))*.25 - .25

    xy_df=coords[start:stop,] #columns 2 and 3 are the coordinates, only take rows we're interested in analyzing

    #loess regression to estimate center line of root
    loessMod10 <- loess(BX~BY, data=xy_df, span=.2) #use Loess to estimate centerline. Span can be tuned. BX and BY are from imageJ
    #   plot(BX~BY, data=xy_df)
    #   lines(xy_df$BY, predict(loessMod10, data.frame(BY = xy_df$BY)))


    #correct for drift
    BX_corrected = 0 #will be the BX adjusted to the point along the loess prediction surface nearest to the observed point
    BX_min = 0 #keeps track of shortest distance
    dist = 0 #placeholder variable for distance

    #count is a counter variable
    count = 0
    
    #continue is boolean to indicate if root appears to have stopped growing (curled, etc)
    cont = TRUE
    
    for (obs in xy_df$BY){
      if (end_frame == stop) {
        count = count + 1 #track which observation is being analyzed
        BX_min=xy_df[count,1]-predict(loessMod10, xy_df[count,])
        for (offset in c(-4,-3,-2,-1,0,1,2,3,4)) { #the pixel offset range we're scanning over. Might want to make larger.
          if (end_frame != stop) {
            break
          } 
          if(!is.na(predict(loessMod10, obs+offset))) #deal with predicting at the ends where offsets will produce NAs  
            dist=euc.dist(xy_df[count,],c(predict(loessMod10, obs+offset),obs+offset)) #calculate distance of each point to point along curve with offset
            #print(dist)
            tryCatch(
              expr = {
    
              if(dist<abs(BX_min)) {
                  BX_min=BX_min/abs(BX_min)*dist #save offset to minimum if it's smaller than the previously found minimum. Preserve sign.
              }
            },
            error = function(e){ 
              message(paste("Root growth appeared to terminate at frame:", count, " for plant:", plant))
              print(e)
              end_frame <<- count
            }
          )
      }
      BX_corrected[count] = BX_min
      }
    }
    
    BX_corrected = BX_corrected[1:end_frame]
    
    #find indices of local maxima. add noise term in case of ties.
    loc_max=find_peaks(BX_corrected+rnorm(end_frame-start+1, mean=0, sd= .0001))

    #find indices of local minima. add noise term in case of ties.
    loc_min=find_peaks(-BX_corrected+rnorm(end_frame-start+1, mean=0, sd= .0001))
    
    #reduce dataframe to size of experiment prior to root termination
    data = data[1:end_frame, ]
    
    #save  
    data[,4] = BX_corrected*mpp
         
    #save boolean max and mins
    data[,2] = FALSE
    data[loc_max,2] = TRUE
    data[,3] = FALSE
    data[loc_min,3] = TRUE
    
    #calculate periods
    max_bool = FALSE
    min_bool = FALSE
    max_tracker = 0
    min_tracker = 0
    len_tracker = 0
    x_prior = xy_df[1,1]
    y_prior = xy_df[1,2]
    
    for (r in 1:dim(data)[1]) {
        #mins and maxes
        if (data[r,2]) {
            if (max_bool) {
                data[r,5] = data[r,1] - data[max_tracker,1]
                max_tracker = r
                
            }
            else {
                max_bool = TRUE
                max_tracker = r
            }
        }
      
        if (data[r,3]) {
            if (min_bool) {
                data[r,5] = data[r,1] - data[min_tracker,1]
                min_tracker = r
            }
            else {
                min_bool = TRUE
                min_tracker = r
            }
        }
        
        #x 
        data[r,6] = (xy_df[r,1] - xy_df[1,1]) * mpp
        
        #y, ie depth
        data[r,7] = (xy_df[r,2] - xy_df[1,2]) * mpp
        
        #arc_length
        if (r > 1) {
          inc = euc.dist(x_prior - predict(loessMod10, xy_df[r,2]), y_prior - xy_df[r,2]) * mpp
          data[r,8] = data[r-1,8] + inc
        }
          else {
            data[r,8] = 0
        }
      
    
        #del_arclength
        if (r > 1) {
            data[r,9] = euc.dist(x_prior - predict(loessMod10, xy_df[r,2]), y_prior - xy_df[r,2]) * mpp
            x_prior = predict(loessMod10, xy_df[r,2])
            y_prior = xy_df[r,2]
        }
        else {
          data[r,9] = 0
        }
    }
    
    #get box and seed number in 9th and 10th columns
    data[,10] = as.integer(substr(plant, 1, gregexpr("_", "2461_1")[[1]][1] - 1))
    data[,11] = as.integer(substr(plant, gregexpr("_", "2461_1")[[1]][1] + 1, nchar(plant)))
    data = data[1:(end_frame - 1),]
    data[end_frame - 1 , 12] = TRUE #set end_frame

    
    #change to: ~/buckets/processed_bucket/showcase/$box_num
    write.csv(data, paste("/home/rstudio/data/current_exp/outputs/quantification/", plant, ".csv", sep = ""), row.names=FALSE)
    },
    error = function(e){ 
      message(paste("could not complete quanificiation for root: ", plant))
      print(e)
      #traceback(1, max.lines = 1)
    }
    )
    
}

#return x,y coordinates of growth prior to curling 
root_curl_trim <- function(dat, plant) {
  #centered = dat - dat[1,]
  distances = apply(dat, 1, euc.dist, x2 = unlist(dat[1,]))
  distances_sliding_window = slideFunct(distances, 10,1)
  max_dist_window = max(distances_sliding_window) 
  max_index = which(distances_sliding_window == max_dist_window)
  return(dat[1:(max_index - 5), ])
}

#euclidean distance function. 
euc.dist <- function(x1, x2) sqrt(sum((x1 - x2) ^ 2))


#local maximum function. From user stas g. https://stackoverflow.com/questions/34205515/finding-local-maxima-and-minima-in-r
find_peaks <- function (x, m = 3){
  shape <- diff(sign(diff(x, na.pad = FALSE)))
  pks <- sapply(which(shape < 0), FUN = function(i){
    z <- i - m + 1
    z <- ifelse(z > 0, z, 1)
    w <- i + m + 1
    w <- ifelse(w < length(x), w, length(x))
    if(all(x[c(z : i, (i + 2) : w)] <= x[i + 1])) return(i + 1) else return(numeric(0))
  })
  pks <- unlist(pks)
  pks
}

slideFunct <- function(data, window, step){
  total <- length(data)
  spots <- seq(from=1, to=(total-window), by=step)
  result <- vector(length = length(spots))
  for(i in 1:length(spots)){
    result[i] <- mean(data[spots[i]:(spots[i]+window)])
  }
  return(result)
}

