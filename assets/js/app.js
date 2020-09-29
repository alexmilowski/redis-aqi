
function sequenceNumber(size,p) {
   let [λ, ϕ] = p;
   let [λ_s, φ_s] = Array.isArray(size) ? size : [size,size];
   let [λ_p, φ_p] = [90 - λ, ϕ < 0 ? 360 + ϕ : ϕ];
   let s = Math.floor(λ_p / λ_s) * Math.floor(360.0 / φ_s) + Math.floor(φ_p / φ_s) + 1;
   return s;
}

function sequencePartitions(size) {
   let [λ_s, φ_s] = Array.isArray(size) ? size : [size,size];
   let N_λ = Math.floor(180 / λ_s);
   let N_φ = Math.floor(360 / φ_s);
   return [N_λ, N_φ];
}

function quadrangleForSequenceNumber(size,s) {
   let [λ_s, φ_s] = Array.isArray(size) ? size : [size,size];

   let [N_λ, N_φ] = sequencePartitions(size);

   let z = (s - 1) % (N_λ * N_φ);
   let φ_p = (z % N_φ) * φ_s;
   let nw = [90 - Math.floor(z / N_φ) * λ_s,  φ_p > 180 ? φ_p - 360 : φ_p];
   let se = [nw[0] - λ_s, nw[1] + φ_s];
   return [nw,se];
}


function* sequenceNumbersForBounds(size,...args) {
   let nw = null, sw = null;
   if (args.length==1) {
      nw = args[0][0];
      se = args[0][1];
   } else if (args.length==2) {
      nw = args[0];
      se = args[1];
   } else {
      throw "Too many arguments after size: "+args.length;
   }
   let p = 0.00000000001;
   let s_nw = sequenceNumber(size,nw);
   let s_ne = sequenceNumber(size,[nw[0],se[1]-p]);
   if (s_ne < s_nw) {
      for (let s of sequenceNumbersForBounds(size,nw,[se[0],-p])) {
         yield s;
      }
      for (let s in sequenceNumbersForBounds(size,[nw[0],p],se)) {
         yield s;
      }
   }
   let width = s_ne - s_nw + 1;
   let [N_λ, N_φ] = sequencePartitions(size);

   let s_se = sequenceNumber(size,[se[0]-p,se[1]-p]);
   let current = s_nw;
   while (current <= s_se) {
      let row_start = current;
      for (let i=0; i<width; i++) {
         yield current;
         current += 1;
      }
      current = row_start + N_φ;
   }
}

function calculateAQI(Cp, Ih, Il, BPh, BPl) {
   a = Ih - Il
   b = BPh - BPl
   c = Cp - BPl
   return Math.round((a/b) * c + Il)
}


function aqiFromPM(pm) {

   if (pm < 0) {
      throw `pm must be > 0: ${pm}`
   }

   // # Good                              0 - 50         0.0 - 15.0         0.0 – 12.0
   // # Moderate                         51 - 100           >15.0 - 40        12.1 – 35.4
   // # Unhealthy for Sensitive Groups  101 – 150     >40 – 65          35.5 – 55.4
   // # Unhealthy                       151 – 200         > 65 – 150       55.5 – 150.4
   // # Very Unhealthy                  201 – 300 > 150 – 250     150.5 – 250.4
   // # Hazardous                       301 – 400         > 250 – 350     250.5 – 350.4
   // # Hazardous                       401 – 500         > 350 – 500     350.5 – 500
   if (pm > 350.5) {
      return calculateAQI(pm, 500, 401, 500, 350.5);
   } else if (pm > 250.5) {
      return calculateAQI(pm, 400, 301, 350.4, 250.5);
   } else if (pm > 150.5) {
      return calculateAQI(pm, 300, 201, 250.4, 150.5);
   } else if (pm > 55.5) {
      return calculateAQI(pm, 200, 151, 150.4, 55.5);
   } else if (pm > 35.5) {
      return calculateAQI(pm, 150, 101, 55.4, 35.5);
   } else if (pm > 12.1) {
      return calculateAQI(pm, 100, 51, 35.4, 12.1);
   } else {
      return calculateAQI(pm, 50, 0, 12, 0);
   }
}

class AQIInterpolator {

   constructor() {
      this.methods =  ['linear','cubic','nearest','krige-linear', 'krige-power', 'krige-gaussian', 'krige-spherical', 'krige-exponential', 'krige-hole-effect'];
      this.resolutions = [0.1,0.05,0.025,0.02,0.015,0.01,0.005];
      this.stop = false;
      this.maxColor = "#000000";
      this.colorMap = {
         50 : "#adff2f",
         100 : "#ff8c00",
         150 : "#ff4500",
         200 : "#ff4500",
         250 : "#b22222",
         300 : "#8b0000",
         350 : "#800080",
         400 : "#4b0082"
      }
      this.colorPartitions = Object.keys(this.colorMap).map((v) => parseInt(v)).sort((a,b) => a-b);

   }

   init() {
      this.loadedSequenceNumbers = {}
      let center = [37.7749, -122.4194]
      this.map = L.map('map').setView(center, 14);
      this.heatmap = L.layerGroup().addTo(this.map);
      this.sensors = L.layerGroup().addTo(this.map);

      let mapLink = '<a href="http://openstreetmap.org">OpenStreetMap</a>';
      L.tileLayer(
         'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
         attribution: '&copy; ' + mapLink + ' Contributors',
         maxZoom: 18,
      }).addTo(this.map);

      this.metadata = L.control({position: 'topright'});

      this.metadata.onAdd = function (map) {

         let div = L.DomUtil.create('div', 'info metadata');

         return div;
      };

      this.metadata.addTo(this.map);

      this.colorlegend = L.control({position: 'bottomright'});

      this.colorlegend.onAdd = function (map) {

         let div = L.DomUtil.create('div', 'info colors');

         return div;
      };
      this.colorlegend.addTo(this.map);
      app.colorPartitions.forEach((value) => {
         let color = this.colorMap[value];
         $(".colors").append(`<span class='color' style='background-color: ${color}'>${value}</span>`);
      });
      $(".colors").append(`<span class='color' style='background-color: ${this.maxColor}'>>${this.colorPartitions[this.colorPartitions.length-1]}</span>`);

      this.map.on('moveend', (e) => {
         setTimeout(() => {
            let partition = $("#partition").val();
            app.loadSensorsForMap(partition);
         },1);
      });
      this.map.on('zoomend', (e) => {
         setTimeout(() => {
            app.resizeSensors();
         },1);
      });
   }

   fetchPartitions(day,oncomplete) {
      fetch(`/api/partitions?start=${day}&end=${day}`)
         .then(response => response.json())
         .then(data => {
            $("#partition").empty();
            $("#extent").empty().text(`${data.first.at} to ${data.last.at}`);
            let [from_date, from_time] = data.first.at.split('T');
            let [to_date, to_time] = data.last.at.split('T');
            $("#from_date").val(from_date);
            $("#from_time").val(from_time);
            $("#to_date").val(to_date);
            $("#to_time").val(to_time);
            data.partitions.forEach((item) => {
               $("#partition").append(`<option>${item}</option>`)
            });
            if (oncomplete!=undefined) {
               setTimeout(
                  () => {
                     oncomplete(data.first.at,data.last.at,day,data.partitions.length);
                  },
                  1
               )
            }
         })
         .catch((error) => {
            console.error('Cannot load partitions.',error);
         });

   }

   aqiColor(value) {
      for (let pos=0; pos<this.colorPartitions.length; pos++) {
         if (value < this.colorPartitions[pos]) {
            return this.colorMap[this.colorPartitions[pos]];
         }
      }
      return this.maxColor
   }

   addOverlay(data,fit) {
      if (fit) {
         this.map.fitBounds([data.bounds.slice(0,2),data.bounds.slice(2,4)]);
      }
      let lat_size = data.grid.length;
      let lon_size = data.grid[0].length;

      this.heatmap.clearLayers();

      for (let lat_pos=0; lat_pos < lat_size; lat_pos++) {
         for (let lon_pos=0; lon_pos < lon_size; lon_pos++) {
            let bounds = [
               [data.bounds[0] - lat_pos * data.resolution, data.bounds[1] + lon_pos * data.resolution],
               [data.bounds[0] - (lat_pos + 1) * data.resolution, data.bounds[1] + (lon_pos + 1) * data.resolution]];
            let value = data.grid[lat_pos][lon_pos]
            let opacity = value / 200
            if (opacity > 1) {
               opacity = 1
            }
            opacity = opacity * 0.75;
            let color = this.aqiColor(value);
            L.rectangle(bounds,{weight: 0, color: color, fillOpacity: opacity}).addTo(this.heatmap)
         }
      }
   }

   interpolatePartition(partition,method,resolution,onload,onshow) {
      $(".metadata").empty().text(partition);
      let bounds = app.map.getBounds()
      let nw = bounds.getNorthWest()
      let se = bounds.getSouthEast()
      let start = new Date();
      let url = `/api/partition/${partition}/interpolate?nwlat=${nw.lat}&nwlon=${nw.lng}&selat=${se.lat}&selon=${se.lng}&method=${method}&resolution=${resolution}`;
      fetch(url)
         .then(response => response.json())
         .then(data => {
            let dataLoaded = new Date();
            let diff = (dataLoaded - start) / 1000.0;
            console.log(`Interpolation: ${diff}s`);
            if (onload!=undefined) {
               setTimeout(onload,1);
            }
            //console.log(data);
            this.addOverlay(data,false);
            let overlayLoaded = new Date();
            diff = (overlayLoaded - dataLoaded) / 1000.0;
            console.log(`Overlay: ${diff}s`);
            if (onshow!=undefined) {
               setTimeout(onshow,1);
            }
         })
         .catch((error) => {
            console.error('Cannot load data.',error);
         });
   }

   sequencePartitions(partitions,method,resolution) {
      this.stop = false
      let current = 0
      let show = () => {
         if (!this.stop && current<partitions.length) {
            this.interpolatePartition(partitions[current],method,resolution,show);
            current += 1;
         }
      }
      show();
   }

   clearSensors() {
      this.sensors.clearLayers();
      this.loadedSequenceNumbers = {}
   }

   loadSensorsForMap(partition) {
      if (partition==undefined || partition.length==0) {
         return;
      }
      let datetime = partition.split('PT')[0];
      let bounds = app.map.getBounds();
      let nw = bounds.getNorthWest();
      let se = bounds.getSouthEast();
      let size = 0.5;
      for (let seqno of sequenceNumbersForBounds(size,[nw.lat,nw.lng],[se.lat,se.lng])) {
         if (seqno in this.loadedSequenceNumbers)  {
            continue;
         }
         let url = `/api/q/${size}/n/${seqno}/${datetime}`;
         console.log(url);
         fetch(url)
            .then(response => response.json())
            .then(data => {
               this.loadedSequenceNumbers[seqno] = true;
               setTimeout(() => {
                  this.showSensors(data);
               },1);
            })
            .catch((error) => {
               console.error(`Cannot load sequence number ${seqno} for ${url}`,error);
            });
      }
   }

   resizeSensors() {
      let zoom = this.map.getZoom();
      let scale = zoom/20.0;
      let radius = 10*scale;
      let opacity = 0.5*scale*scale;
      console.log(`Radius ${radius}, scale ${scale}`);
      this.sensors.eachLayer((layer) => {
         layer.setRadius(radius);
         layer.setStyle({opacity:opacity});
      });
   }
   showSensors(data) {
      let zoom = this.map.getZoom();
      let scale = zoom/15.0;
      let radius = 8*scale;
      let opacity = 0.5*scale;
      console.log(`Radius ${radius}, scale ${scale}`);
      for (let sensor of data) {
         let [id, offset, lat, lon, pm] = sensor;
         let aqi = aqiFromPM(pm);
         let color = this.aqiColor(aqi);
         L.circleMarker([lat,lon],{radius: radius, weight: 0, color: color, opacity: opacity}).bindTooltip(`${aqi}`,{permanant:true,direction: 'center',offset: [0, 15], opacity: 0.65}).addTo(this.sensors);
      }
   }



}

let app = new AQIInterpolator();

$(document).ready(() => {

   app.init();

   $("#load").on("click",() => {
      var url = $("#url").val();
      console.log(`Loading ${url}`);

      let start = new Date();
      fetch(`/api/load?url=${url}`)
         .then(response => response.json())
         .then(data => {
            let diff = (new Date() - start) / 1000.0;
            console.log(`Elapsed: ${diff}s`);
            //console.log(data);
            app.addOverlay(data,true);
         })
         .catch((error) => {
            console.error('Cannot load data.',error);
         });
      return false;
   })

   $("#aqi").on("click",() => {

      let partition = $("#partition").val();
      let method = $("#method").val();
      let resolution = parseFloat($("#resolution").val());
      app.interpolatePartition(partition,method,resolution);

   });

   $("#stop").on("click",() => {
      app.stop = true;
   });

   $("#partition").on("change", () => {
      app.clearSensors();
      let partition = $("#partition").val();
      app.loadSensorsForMap(partition);
   });


   $("#sequence").on("click", () => {
      let from_date = $("#from_date").val();
      let from_time = $("#from_time").val();
      let to_date = $("#to_date").val();
      let to_time = $("#to_time").val();
      let method = $("#method").val();
      let resolution = parseFloat($("#resolution").val());
      fetch(`/api/partitions?start=${from_date}T${from_time}&end=${to_date}T${to_time}`)
         .then(response => response.json())
         .then(data => {
            if (data.partitions.length > 0) {
               app.sequencePartitions(data.partitions,method,resolution);
            } else {
               console.log("No partitions returned for date/time range.");
            }
         })
         .catch((error) => {
            console.error('Cannot load partitions.',error);
         });

   });

   let now = new Date()
   let end = now.toISOString().split('T')[0]

   app.fetchPartitions(
      end,
      (first,last,day,total) => {
         if (total==0) {
            app.fetchPartitions(
               last.split('T')[0],
               (first,last,day,totle) => {
                  setTimeout(() => {
                     let partition = $("#partition").val();
                     app.loadSensorsForMap(partition);
                  },1);
               }
            );
         } else {
            setTimeout(() => {
               let partition = $("#partition").val();
               app.loadSensorsForMap(partition);
            },1);
         }
      }
   );

   app.methods.forEach((method) => {
      $("#method").append(`<option${method=='linear' ? ' selected' : ''}>${method}</option>`);
   });
   app.resolutions.forEach((resolution) => {
      $("#resolution").append(`<option${resolution==0.025 ? ' selected' : ''}>${resolution}</option>`);
   });

})
