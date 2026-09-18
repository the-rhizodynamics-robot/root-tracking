library(methods)

movies <- setRefClass("movies", fields = list(name = "character", 
                                              leadActor = "character", rating = "numeric"), methods = list(
                                                increment_rating = function()
                                                {
                                                  rating <<- rating + 1
                                                },
                                                decrement_rating = function()
                                                {
                                                  rating <<- rating - 1
                                                }
                                              ))