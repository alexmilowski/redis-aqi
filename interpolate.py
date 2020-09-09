import sys
import argparse
import requests
import json
import numpy as np
from math import floor, ceil
import scipy.interpolate

import pykrige



# data format
# ['timestamp', 'ID', 'age', 'pm_0', 'pm_1', 'pm_2', 'pm_3', 'pm_4', 'pm_5', 'pm_6', 'conf', 'Type', 'Label', 'Lat', 'Lon', 'isOwner', 'Flags', 'CH']

def aqiFromPM(pm):

   if pm < 0:
      raise ValueError('pm must be > 0: '+str(pm))
   if pm > 1200:
      raise ValueError('pm must be < 1200: '+str(pm))
   # Good                              0 - 50         0.0 - 15.0         0.0 – 12.0
   # Moderate                         51 - 100           >15.0 - 40        12.1 – 35.4
   # Unhealthy for Sensitive Groups  101 – 150     >40 – 65          35.5 – 55.4
   # Unhealthy                       151 – 200         > 65 – 150       55.5 – 150.4
   # Very Unhealthy                  201 – 300 > 150 – 250     150.5 – 250.4
   # Hazardous                       301 – 400         > 250 – 350     250.5 – 350.4
   # Hazardous                       401 – 500         > 350 – 500     350.5 – 500
   if pm > 350.5:
      return calculateAQI(pm, 500, 401, 500, 350.5)
   elif pm > 250.5:
      return calculateAQI(pm, 400, 301, 350.4, 250.5)
   elif pm > 150.5:
      return calculateAQI(pm, 300, 201, 250.4, 150.5)
   elif pm > 55.5:
      return calculateAQI(pm, 200, 151, 150.4, 55.5)
   elif pm > 35.5:
      return calculateAQI(pm, 150, 101, 55.4, 35.5)
   elif pm > 12.1:
      return calculateAQI(pm, 100, 51, 35.4, 12.1)
   else:
      return calculateAQI(pm, 50, 0, 12, 0)

def calculateAQI(Cp, Ih, Il, BPh, BPl):

   a = Ih - Il
   b = BPh - BPl
   c = Cp - BPl
   return round((a/b) * c + Il)

class AQIInterpolator():
   def __init__(self,box,mesh_size=100,resolution=None):
      self.box = box
      self.values = {}
      self.mesh_size = mesh_size
      self.resolution = resolution

      # TODO: only for northern / western hemisphere?

      self.lat_size = abs(box[0]-box[2])
      self.lon_size = abs(box[1]-box[3])

      # calculate the resolution from the mesh size
      if self.resolution is  None:
         # compute the resolution based on the largest dimension of the box
         max = self.lat_size if self.lat_size > self.lon_size else self.lon_size
         self.resolution = max / self.mesh_size

      self.lat_grid_size = ceil( self.lat_size / self.resolution )
      self.lon_grid_size = ceil( self.lon_size / self.resolution )


   def add(self,lat,lon,aqi):
      if lat > self.box[0] or lat < self.box[2] or lon < self.box[1] or lon > self.box[3]:
         return False

      lat_pos = int(floor(abs((self.box[0] - lat) / self.resolution)))
      lon_pos = int(floor(abs((self.box[1] - lon) / self.resolution)))

      pos = (lat_pos,lon_pos)

      if pos in self.values:
         N, current_aqi = self.values[pos]

         factor = float(N)/float(N+1)

         current_aqi = list(map(lambda v : int(round(v[0]*factor + v[1]/float(N+1))), zip(current_aqi, aqi) ))

         self.values[pos] = (N+1,current_aqi)
      else:
         self.values[pos] = (1,aqi)

      return True

   def aqi_estimator(self,index=2,method='nearest'):
      points = list(self.values.keys())
      values = [self.values[p][1][index] for p in points]

      def f(x,y):
         return scipy.interpolate.griddata(points,values,(x,y), method=method, fill_value=0)

      return f

   def generate_grid(self,index=2,method='nearest'):

      if method.startswith('krige-'):
         return self.generate_krige_grid(index=index,method=method[6:])

      f = self.aqi_estimator(index=index,method=method)

      grid = np.fromfunction(f,(self.lat_grid_size,self.lon_grid_size),dtype=int)

      return grid

   def generate_krige_grid(self,index=2,method='linear'):
      x = [p[0] for p in self.values.keys()]
      y = [p[1] for p in self.values.keys()]
      z = [self.values[(x[pos],y[pos])][1][index] for pos in range(len(x))]
      krige = pykrige.ok.OrdinaryKriging(x,y,z,variogram_model=method)
      mesh_x = [float(pos) for pos in range(self.lat_grid_size)]
      mesh_y = [float(pos) for pos in range(self.lon_grid_size)]
      grid, sigmasq = krige.execute('grid',mesh_x,mesh_y)
      return grid.data.T


def plot_grid(grid,colormap=None):
   import matplotlib.pyplot as plt
   plt.imshow(grid,cmap=plt.get_cmap(colormap) if colormap is not None else None)
   plt.show()

def loader(box,urls,mesh_size=100,resolution=None,verbose=False):
   interpolator = AQIInterpolator(box,mesh_size=mesh_size,resolution=resolution)

   for url in urls:
      resp = requests.get(url)
      if resp.status_code==200:
         data = resp.json()
         headers = data[0]
         count = 0
         for row in data[1:]:
            if row[2]<30 and row[11]==0:
               aqi = list(map(lambda v : aqiFromPM(float(v)) if v is not None else 0,row[3:7]))
               if row[13] is None or row[14] is None:
                  if verbose:
                     print('Ignoring: '+(','.join(map(str,[row[1],row[11],row[12],row[13],row[14]]))))
                  continue
               if interpolator.add(float(row[13]),float(row[14]),aqi):
                  count += 1
         if verbose:
            print('Count: '+str(count))
      else:
         raise ValueError('Cannot load {}, status {}'.format(url,str(resp.status_code)))

   return interpolator


_box_tests = {
   # Bay Area: 38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817
   'bayarea' : [38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817],
   # San Francisco: 37.80888750820881,-122.57097888976305,37.719593811785046,-122.32739139586647
   'sf' : [37.80888750820881,-122.57097888976305,37.719593811785046,-122.32739139586647]
}
if __name__ == '__main__':

   argparser = argparse.ArgumentParser(description='interpolate-aq')
   argparser.add_argument('--verbose',help='Verbose output',action='store_true',default=False)
   argparser.add_argument('--size',help='The grid mesh size (integer)',type=int,default=100)
   argparser.add_argument('--resolution',help='The grid resolution (float)',type=float)
   argparser.add_argument('--index',help='The pm measurement to use',type=int,default=2)
   argparser.add_argument('--method',help='The interpolation method',choices=['linear','cubic','nearest','krige-linear', 'krige-power', 'krige-gaussian', 'krige-spherical', 'krige-exponential', 'krige-hole-effect'],default='linear')
   argparser.add_argument('--bounding-box',help='The bounding box (nwlat,nwlon,selat,selon)',default='37.80888750820881,-122.57097888976305,37.719593811785046,-122.32739139586647')
   argparser.add_argument('urls',help='The urls',nargs='+')

   args = argparser.parse_args()

   box = list(map(float,args.bounding_box.split(',')))

   if args.verbose:
      print('Bounding box: '+(','.join(map(str,box))))

   interpolator = loader(box,args.urls,mesh_size=args.size,resolution=args.resolution)

   grid = interpolator.generate_grid(method=args.method,index=args.index)

   for lat_pos in range(len(grid)):
      for lon_pos in range(len(grid[lat_pos])):
         sys.stdout.write(' ')
         sys.stdout.write(str(round(grid[lat_pos][lon_pos])))
      sys.stdout.write('\n')
