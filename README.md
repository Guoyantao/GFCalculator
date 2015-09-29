# GFCalculator
Global Forest Change calculator - uses Hansen et a. (2013) Global Forest Change map to calculate forest cover in years 2000 - 2012 for a given set of species' distribution maps within provided altitude limits. 

## Usage
The species' distribution maps are stored on Google Maps Engine (GME) server. Unfortunately GME does provide an option to share rasters publically and therefore running the script as-in will not succeed. Aim of sharing this code is to demonstrate how the calculations can be performed.

## Input
Required input:
* assets_filename: file with IDs of species' range maps (uploaded through GME)
* altitude_filename: comma-delimeted file in format species, min. altitude, max. altitude

## Algorithm
![diagram](algorithm.png?token=AFPv1fVwT39JenrwQi6h3yTRPbfXMdiQks5WE5piwA%3D%3D)
