
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
      let center = [37.7749, -122.4194]
      this.map = L.map('map').setView(center, 14);
      this.heatmap = L.layerGroup().addTo(this.map);

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
            app.fetchPartitions(last.split('T')[0]);
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
