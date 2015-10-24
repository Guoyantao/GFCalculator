# Global Forest Change calculator
## Overview
The script uses Hansen et al. (2013) Global Forest Change map in conjunction with Google Earth Engine to calculate forest cover in years 2000 - 2012 for a given set of species' distribution maps within provided altitude limits. 

## Global Forest Change map
Quantification of tree cover area and deforestation events from satellite imagery in a sistematic way across the globe is a considerable challenge, which has been undertaken by group of prof. Hansen from Maryland University, in cooperation with Google team. The result, Global Forest Change (GFC) map, is a map product that provides estimates on forest cover in year 2000, as well as gain and loss events that happened until 2014 (as of version 1.2 of the map). The map has resolution 1296001 x 493200 pixels and a pixel size 30 metres. Since pixels are squares, a single pixel represents 30mx30m = 900m^2 area. 

## Basics
GFC map is composed of several bands (layers). Each layer is a separate image that represents a different piece of information. Here we will focus on four of them:
* **treecover2000**: percentage of tree cover in the pixel. In other words, each pixel has value from 0 till 100, with 0 meaning no forest at all and 100 full forest cover
* **loss**: pixel has value 1 if loss ever occurred during the study period.
* **gain**: pixel has value 1 if gain ever occurred during the study period.
* **lossyear**: value of a pixel denotes in which year loss occurred, starting with 2000. Ino other words, if pixel has value 5, then it means that the deforestation event occurred in 2005. 
It should be noted that Hansen et al. in their work used Food and Agriculture Organisation (UN) definition of a tree: any vegetation taller than 5 metres. In consequence, the GFC map captures as tree also any sort of plantations that happen to be taller than 5 metres. Although here we are using "trees" and "forest" interchangeably

## Usage
The species' distribution maps are stored on Google Maps Engine (GME) server. Unfortunately GME does provide an option to share rasters publically and therefore running the script as-in will not succeed. Aim of sharing this code is to demonstrate how the calculations can be performed.

## Input
Required input:
* assets_filename: file with IDs of species' range maps (uploaded through GME)
* altitude_filename: comma-delimeted file in format species, min. altitude, max. altitude

## Algorithm
The algorithm of calculating tree cover in 2000 and forest loss is straightforward, since all the hard labour has already been done for us by Hanen et al., i.e. identifying trees and deforestation events from Landsat imagery. The Global Forest Change map 

![diagram](algorithm.png?token=AFPv1fVwT39JenrwQi6h3yTRPbfXMdiQks5WE5piwA%3D%3D)
