from haversine import haversine, Unit
from math import floor

def sequence_number(size,p):
   λ, ϕ = p
   λ_s, φ_s = size if type(size)==tuple else (size,size)

   λ_p, φ_p = (90 - λ, 360 + ϕ if ϕ < 0 else ϕ)

   s = floor(λ_p / λ_s) * floor(360.0 / φ_s) + floor(φ_p / φ_s) + 1

   return s

def sequence_partitions(size):
   λ_s, φ_s = size if type(size)==tuple else (size,size)
   N_λ = floor(180 / λ_s)
   N_φ = floor(360 / φ_s)
   return N_λ, N_φ

def quadrangle_for_sequence_number(size,s):
   λ_s, φ_s = size if type(size)==tuple else (size,size)

   N_λ, N_φ = sequence_partitions(size)

   z = (s - 1) % (N_λ * N_φ)
   φ_p = (z % N_φ) * φ_s
   nw = (90 - floor(z / N_φ) * λ_s, φ_p - 360 if φ_p > 180 else φ_p)
   se = (nw[0] - λ_s, nw[1] + φ_s)
   return [nw,se]

def is_valid_datetime_partition(partition,t):
   if t.second!=0 or \
      t.microsecond!=0 or \
      t.second % partition != 0:
      return False
   return True

def sequence_numbers_for_bounds(size,*args):
   if len(args)==1:
      nw = args[0][0]
      se = args[0][1]
   elif len(args)==2:
      nw = args[0]
      se = args[1]
   else:
      raise ValueError('Too many arguments after client and key: '+str(len(args)))
   p = 0.00000000001
   s_nw = sequence_number(size,nw)
   s_ne = sequence_number(size,(nw[0],se[1]-p))
   if s_ne < s_nw:
      for s in sequence_numbers_for_bounds(size,nw,(se[0],-p)):
         yield s
      for s in sequence_numbers_for_bounds(size,(nw[0],p),se):
         yield s
   width = s_ne - s_nw + 1
   N_λ, N_φ = sequence_partitions(size)

   s_se = sequence_number(size,(se[0]-p,se[1]-p))
   current = s_nw
   while current <= s_se:
      row_start = current
      for _ in range(width):
         yield current
         current += 1
      current = row_start + N_φ

def quadrangles_for_bounds(size,*args):
   λ_s, φ_s = size if type(size)==tuple else (size,size)
   if len(args)==1:
      nw = args[0][0]
      se = args[0][1]
   elif len(args)==2:
      nw = args[0]
      se = args[1]
   else:
      raise ValueError('Too many arguments after client and key: '+str(len(args)))

   # TODO: does not handle crossing lon=0
   p = 0.00000000001
   nw_quadrangle = quadrangle_for_sequence_number(size,sequence_number(size,nw))
   se_quadrangle = quadrangle_for_sequence_number(size,sequence_number(size,(se[0]-p,se[1]-p)))

   current = [nw_quadrangle[0],nw_quadrangle[1]]

   while current[0][0] > se_quadrangle[1][0]:
      yield current

      if current[0][1] + φ_s >= se_quadrangle[1][1]:
         current[0] = (current[0][0] - λ_s, nw_quadrangle[0][1])
         current[1] = (current[1][0] - λ_s, current[0][1] + φ_s)
      else:
         current[0] = (current[0][0], current[0][1] + φ_s)
         current[1] = (current[1][0], current[1][1] + φ_s)

def query_circle(client, partition_key, center, radius, unit='km', bounds=None):
   """
   Iterates the values that fail within the defined circle
   for the geospatial key.

   Arguments:
   client - the Redis client instance
   partition_key - the geospatial set key
   center - the center of the circle as a tuple/list (lat,lon)
   radius - the radius of the circle
   unit - the unit of measure for the radius (defaults to km)
   bounds - A bounding box to trip the results (defaults to None)
   """
   # note: query is lon,lat
   result = client.georadius(partition_key,center[1],center[0],radius,unit=unit,withcoord=True)

   nw = bounds[0] if bounds is not None else None
   se = bounds[1] if bounds is not None else None

   for key, pos in result:

      # Note: pos is lon, lat

      lat = pos[1]
      lon = pos[0]

      # check boundary
      if bounds is not None and lat >= nw[0] or lat <= se[0] or lon <= nw[1] or lon >= se[1]:
         continue

      yield key, (lat,lon)

def query_quadrangle(client, partition_key, *args):
   """
   Iterates the values that fail within the defined quadrangle
   for the geospatial key.

   Arguments:
   client - the Redis client instance
   partition_key - the geospatial set key
   bounds - the bounds as an array of [nw,se]
   - or -
   nw - the north west corner of the quadrangle as a tuple/list (lat,lon)
   se - the south east corner of the quadrangle as a tuple/list (lat,lon)
   """

   if len(args)==1:
      nw = args[0][0]
      se = args[0][1]
   elif len(args)==2:
      nw = args[0]
      se = args[1]
   else:
      raise ValueError('Too many arguments after client and key: '+str(len(args)))

   lat_size = abs(nw[0] - se[0])
   lon_size = abs(nw[1] - se[1])

   # inscribe the quadrangle onto a circle with radius from center to
   center = (nw[0] - lat_size/2, nw[1] + lon_size/2)
   radius = haversine(center,nw,unit=Unit.KILOMETERS)

   return query_circle(client,partition_key,center,radius,bounds=[nw,se])

def query_region(client,partition_key,*args,size=0.5,by_quadrangles=False):
   if len(args)==1:
      nw = args[0][0]
      se = args[0][1]
   elif len(args)==2:
      nw = args[0]
      se = args[1]
   else:
      raise ValueError('Too many arguments after client and key: '+str(len(args)))

   if by_quadrangles:
      for quadrangle in quadrangles_for_bounds(size,nw,se):
         for key, pos in query_quadrangle(client,partition_key,quadrangle):

            lat = pos[0]
            lon = pos[1]

            # check boundary
            if lat >= nw[0] or lat <= se[0] or lon <= nw[1] or lon >= se[1]:
               #print(pos)
               continue

            yield key, pos
   else:
      for sequence_number in sequence_numbers_for_bounds(size,nw,se):

         q_nw, q_se = quadrangle_for_sequence_number(size,sequence_number)

         for key, pos in query_quadrangle(client,partition_key,q_nw,q_se):

            lat = pos[0]
            lon = pos[1]

            # check boundary
            if lat >= nw[0] or lat <= se[0] or lon <= nw[1] or lon >= se[1]:
               #print(pos)
               continue

            yield key, pos
