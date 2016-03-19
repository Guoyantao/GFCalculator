# -*- coding: utf-8 -*-
"""
Created on Sun Nov  9 13:27:04 2014

@author: Lukasz Tracewski
"""

import time
import logging
import ee # Earth Engine
import csv
import collections
from datetime import datetime

assets_filename = 'assets_eoo.csv'
altitude_filename = 'altitude_range_all.csv'

startTime = datetime.now()
# Initialize Earth Engine.
ee.Initialize()

scale = 2000
maxPixels = 1e13
bestEffort = False

tries = 6
delay = 10
backoff = 2

# Configuration of logging module
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

gtopo30 = ee.Image('USGS/GTOPO30')

# Read altitude limits
Altitude = collections.namedtuple('Altitude', 'min max')
with open(altitude_filename, 'rb') as f:
    reader = csv.reader(f)
    reader.next()
    alt_info = {species: Altitude(min=float(min_alt), max=float(max_alt)) for species, min_alt, max_alt in reader}

# ESA landcover
# esaImage = ee.Image('GME/images/12170611901221780154-17538638850927780878')
esaImage = ee.Image('ESA/GLOBCOVER_L4_200901_200912_V2_3').select(['landcover'])

woodlogging = ee.Image('GME/images/12170611901221780154-14850889436297602760');
woodfibre = ee.Image('GME/images/12170611901221780154-03384629936081429678');
oilpalm = ee.Image('GME/images/12170611901221780154-00658915758003517223');
concessions = ee.ImageCollection([woodlogging, woodfibre, oilpalm]).mosaic();

esaImage = esaImage.where(concessions, 0);

with open('GlobCoverLegend.csv', 'rb') as legend_file:
    reader = csv.reader(legend_file, delimiter=';')
    classes = [ dict(class_no=key, description=value) for (key, value) in reader ]

legend = [row['description'] for row in classes]
legend.insert(0, 'species')

# Construct an image collection, where each image corresponds to a landcover class.
def CreatLandcoverClassImage(landcover_class_dict):
    class_no = landcover_class_dict['class_no']
    # Create an binary image for a single landcover class
    binImage = esaImage.eq(ee.Image(ee.Number(int(class_no))))
    # Rename the band to the class name.
    binImage = binImage.select([0], [class_no])
    # Add an image property with the landcover class name.
    binImage = binImage.set(landcover_class_dict);
    return binImage;
    
class_image_list = map(CreatLandcoverClassImage, classes)
ic = ee.ImageCollection.fromImages(class_image_list);


class Runner(object):
    def __init__(self, asset_id, image_filename):
        self._asset_id = asset_id
        self._min_alt = alt_info[image_filename].min
        self._max_alt = alt_info[image_filename].max
        
    def __call__(self, image):
        species = ee.Image('GME/images/' + self._asset_id) 
        mask = image.And(species);
        alt_range = gtopo30.gte(self._min_alt).And(gtopo30.lte(self._max_alt))
        mask = alt_range.And(mask)
        # Use the mask to create an image with pixel areas [m^2]
        area = ee.Image.pixelArea().mask(mask);
        # Calculate the total area of the overlapping area.
        total_area = area.reduceRegion(
            reducer = ee.Reducer.sum(),
            geometry = species.geometry(),
            scale = scale,
            maxPixels = maxPixels,
            bestEffort = bestEffort)
        # Copy over the properties of the original image.
        area = area.copyProperties(image);
        # Store the calcuated area as a property of the image.
        area = area.set(ee.String('area'), total_area.get('area'))
        return area        
    
def run(image_filename, asset_id):
    runner = Runner(asset_id, image_filename)
    pixel_areas_masked = ic.map(runner)
    
    mtries, mdelay = tries, delay 
    while True:
        try:
            return pixel_areas_masked.getInfo()['features']
        except ee.EEException, e:
            if '500' in str(e):
                raise
            mtries -= 1
            if mtries == 0:
                raise Exception('Number of retries exceeded. I give up!')
            msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
            logging.warning(msg)
            time.sleep(mdelay)
            mdelay *= backoff 


# Read file with assets and put them into a dictionary
with open(assets_filename, 'rb') as f:
    reader = csv.reader(f)
    assets = collections.OrderedDict(asset for asset in reader)

fout = open('globcover.csv', 'wb', buffering=0)
dw = csv.DictWriter(fout, fieldnames=legend)
dw.writeheader()

ferr = open('failed.txt', 'ab+', buffering=0)

# Iterate through all provided assets
for image_filename, asset_id in assets.items():
#    logging.info('Processing %s %s', image_filename, asset_id)
    print image_filename
    try:
        results = run(image_filename, asset_id)
        d = {result['properties']['description']: result['properties']['area'] for result in results }
        d['species'] = image_filename
        dw.writerow(d)
    except Exception, e:
        logging.error('Failed: %s %s with message: %s', image_filename, asset_id, str(e))
        ferr.write(image_filename + ' ' + asset_id + '\n')

fout.close()
ferr.close()

print datetime.now()-startTime
