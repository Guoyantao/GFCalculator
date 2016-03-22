#!/usr/bin/python

# Global Forest Change calculator for provided species' distributions maps

import csv
import logging
import time
import ee
import collections
from datetime import datetime

assets_filename = 'assets_eoo.csv' # File with IDs of species' range maps (uploaded through Google Maps Engine)
altitude_filename = 'altitude_range_all.csv' # File with species' altitude limits

scale = 2000        # Scale for running the calculations (2000 is recommended by IUCN)
maxPixels = 1e13    # Maximal number of pixels in image before rescaling is done
bestEffort = True   # If number of pixels exceeds 'maxPixels' then rescale image

# Parameters for exponential backoff - a method for repeating a function call after
# an exception has happened. A workaround to a time-out issue in the Earth Engine
tries = 5
delay = 10
backoff = 2

# The logging module
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='raster.log',
                    filemode='w')
                    
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)-8s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

ee.Initialize()  # Initialise the EE

startTime = datetime.now() # Start measuring the time

gfcImage = ee.Image('UMD/hansen/global_forest_change_2013') # The GFC map
gtopo30 = ee.Image('USGS/GTOPO30') # GTOPO30 Digital Elevation Map

# Concession areas
woodlogging = ee.Image('GME/images/12170611901221780154-14850889436297602760');
woodfibre = ee.Image('GME/images/12170611901221780154-03384629936081429678');
oilpalm = ee.Image('GME/images/12170611901221780154-00658915758003517223');
concessions = ee.ImageCollection([woodlogging, woodfibre, oilpalm]).mosaic();

# Read altitude limits
Altitude = collections.namedtuple('Altitude', 'min max')
with open(altitude_filename, 'rb') as f:
    reader = csv.reader(f)
    reader.next()
    alt_info = {species: Altitude(min=float(min_alt), max=float(max_alt)) for species, min_alt, max_alt in reader}

# Select specific bands from GFC map
forest2000 = gfcImage.select(['treecover2000']).divide(100)
lossImage = gfcImage.select(['loss'])
lossYear = gfcImage.select(['lossyear'])
gainImage = gfcImage.select(['gain'])

# Remove concession areas from GFC bands
forest2000 = forest2000.where(concessions, 0);
lossImage = lossImage.where(concessions, 0);
lossYear = lossYear.where(concessions, 0);
gainImage = gainImage.where(concessions, 0);

# Find pixels in which only gain occurred
gainAndLoss = gainImage.And(lossImage)
gainOnly = gainImage.And(gainAndLoss.Not())

#tree30 = forest2000.gte(0.3);
#forest2000 = forest2000.mask(tree30)

# Multiply all bands by pixel area to get metres^2
hansen = []
hansen += [forest2000.multiply(ee.Image.pixelArea()).set('forest', 'Tree_area_2000', 'gee_returns', 'treecover2000'),
           forest2000.mask(lossImage).multiply(ee.Image.pixelArea()).set('forest', 'Forest_loss_2001_2012', 'gee_returns', 'treecover2000'),
           lossImage.multiply(ee.Image.pixelArea()).set('forest', 'Forest_loss_2001_2012_worstcase', 'gee_returns', 'loss'),
           gainOnly.multiply(ee.Image.pixelArea()).set('forest', 'Gain_forest', 'gee_returns', 'gain')]
hansen +=  [forest2000.mask(lossYear.eq(year)).multiply(ee.Image.pixelArea()).set('forest', 'Loss_20{0:0=2d}'.format(year), 'gee_returns', 'treecover2000') for year in range(1,13)]

ic = ee.ImageCollection.fromImages(hansen); # Form a collection from all Hansen images


class Species(object):
  
    def __init__(self, asset_id, image_filename):
        """
        Parameters
        --------------
        asset_id : string
            An asset id provided by the Google Maps Engine. User uploads images (e.g. range maps) through the 
            Maps Engine and in return gets an ID of the uploaded image. That is the "asset id"
        image_filename : string
            Name of the image. The asset id is associated with the image name (e.g. species id). We are using
            this relation to report information to the user and to retrieve the altitude info.
            
        Returns
        --------------
        None
        """          
        self._asset_id = asset_id
        self._min_alt = alt_info[image_filename].min
        self._max_alt = alt_info[image_filename].max
        
    def __call__(self, image):
        """
        This is the algorithm that will do the forest area calculations. It takes species' range map,
        Global Forest Change map and elevation map to calculate forest area for the given species
        
        Parameters
        --------------
        image : EE image
            A tree cover image. For instance, it can be "forest loss" or "forest gain".

        Returns
        --------------
        area : a number
            Forest cover area
        """             
        # Retrieve the species' range map image from GME
        species = ee.Image('GME/images/' + self._asset_id) 
        # Clip elevation map with species-specific altitude limits
        alt_range = gtopo30.gte(self._min_alt).And(gtopo30.lte(self._max_alt))
        # Clip species' range map with altitude information. The operation removes all pixels that
        # do not fall within the altitude limits 
        area_of_occupancy = alt_range.And(species)
        # Multiply Hansen image by the species' area of occupancy. Every pixel will contain forest cover
        # area for a given species
        forest_area_of_occupancy = image.multiply(area_of_occupancy)
        # Sum all pixels in an image to get total forest area for a given species
        total_area = forest_area_of_occupancy.reduceRegion(
            reducer = ee.Reducer.sum(),
            geometry = area_of_occupancy.geometry(),
            scale = scale,
            maxPixels = maxPixels,
            bestEffort = bestEffort)
        # Copy over the properties of the original image.
        area = forest_area_of_occupancy.copyProperties(image);
        # Store the calcuated area as a property of the image.
        gee_returns = image.get('gee_returns');
        area = area.set(ee.String('area'), total_area.get(gee_returns))
        return area

# Names of fields that will be returned on an output
fields = ['species', 'Tree_area_2000', 'Gain_forest', 'Forest_loss_2001_2012', 'Forest_loss_2001_2012_worstcase',
          'Loss_2001', 'Loss_2002', 'Loss_2003', 'Loss_2004', 'Loss_2005', 'Loss_2006', 'Loss_2007',
          'Loss_2008', 'Loss_2009', 'Loss_2010', 'Loss_2011', 'Loss_2012']

# Read assets IDs
with open(assets_filename, 'rb') as f:
    reader = csv.reader(f)
    assets = collections.OrderedDict(asset for asset in reader)

# Open result file for writing    
fout = open('results_' + assets_filename, 'wb', buffering=0)
dw = csv.DictWriter(fout, fieldnames=fields)
dw.writeheader()

# Log file that stores names of all species for which we were unable to calculate forest cover.
# The reason can be for instance a problem with a range map
ferr = open(assets_filename + '_failed.txt', 'ab+', buffering=0)

# The function will be run on server-side to calculate the forest cover for a given species
def run(asset_id, image_filename):
    species = Species(asset_id, image_filename)
    pixel_areas_masked = ic.map(species)
    # Use exponential backoff to handle timeout errors
    mtries, mdelay = tries, delay
    # If time-out occurs it means the calculations did not finish in the prescribed time. However,
    # the calculations are still running. That's why we query for results again after certain time, e.g. 10s.
    # If situation repeats, this time we try after longer period, e.g. 20s. We do a number of retries (e.g. 5),
    # after which we give up. It's called exponential backoff.
    while True:
        try:
            return pixel_areas_masked.getInfo()['features']
        except ee.EEException, e:
            if '500' in str(e): # internal error ocurred
                raise # no point in re-trying
            mtries -= 1
            if mtries == 0:
                raise Exception('Number of retries exceeded. I give up!')
            msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
            logging.warning(msg)
            time.sleep(mdelay)
            mdelay *= backoff                 

# Iterate through all species and calculate for them forest cover. By forest cover we understand all
# GFC-derived quantities, e.g. forest cover in 2000, forest loss, forest gain.
for image_filename, asset_id in assets.items():
    print 'Calculating: ', image_filename
    try:
        # Run computations
        results = run(asset_id, image_filename)
        # Get results
        d = {result['properties']['forest']: result['properties']['area'] for result in results }
        d['species'] = image_filename
        # Write results
        dw.writerow(d)
    except Exception, e:
        # Write errors
        logging.error('Failed: %s %s with message: %s', image_filename, asset_id, str(e))
        logging.exception(e)
        ferr.write(image_filename + ',' + asset_id + '\n')

fout.close()
ferr.close()

print datetime.now()-startTime
