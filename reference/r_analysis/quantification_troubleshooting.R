library(here)
library(stringr)

plot_looper_2("/home/rstudio/data/tip_coordinates/", "2460_2471_", 1, 196, mpp2, .3)


#PLOT GENERATOR HELPER FUNCTION
plot_looper_2 <- function(exp_dir, timestamp, start, stop, mpp, spn){
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
    print(dat)
    print(which(dat[,1] != 10000)[[1]])
    #colnames(dat) = c("BX", "BY")
    #plot_curve(timestamp, plant, dat, start, stop, mpp, spn)
    
  }
}