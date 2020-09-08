let app = {
   methods: ['linear','cubic','nearest','krige-linear', 'krige-power', 'krige-gaussian', 'krige-spherical', 'krige-exponential', 'krige-hole-effect']
}

$(document).ready(() => {

   let center = [37.7749, -122.4194]
   app.map = L.map('map').setView(center, 14);
   app.heatmap = L.layerGroup().addTo(app.map);

   let mapLink = '<a href="http://openstreetmap.org">OpenStreetMap</a>';
   L.tileLayer(
      'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; ' + mapLink + ' Contributors',
      maxZoom: 18,
      }).addTo(app.map);

   function addOverlay(data,fit) {
      if (fit) {
         app.map.fitBounds([data.bounds.slice(0,2),data.bounds.slice(2,4)]);
      }
      lat_size = data.grid.length;
      lon_size = data.grid[0].length;

      app.heatmap.clearLayers();

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
            let color = "#8b0000";
            if (value < 50 ) {
               // good
               color = "#adff2f";
            } else if (value < 100) {
               // moderate
               color = "#ffff00"
            } else if (value < 150 ) {
               // unhealthy for sensitive groups
               color = "#ff4500";
            } else if (value < 200) {
               // unhealthy
               color = "#dc143c";
            } else if (value < 300) {
               // very unhealthy
               color = "#b20000";
            }
            // if (lat_pos%10 == 0) {
            //    console.log(`${lat_pos},${lon_pos} = ${data.grid[lat_pos][lon_pos]} -> ${opacity}, ${color}`);
            // }
            L.rectangle(bounds,{weight: 0, color: color, fillOpacity: opacity}).addTo(app.heatmap)
         }
      }
   }

   $("#load").on("click",() => {
      var url = $("#url").val();
      console.log(`Loading ${url}`);

      let start = new Date();
      fetch(`/api/load?url=${url}`)
         .then(response => response.json())
         .then(data => {
            let diff = (new Date() - start) / 1000.0;
            console.log(`Elapsed: ${diff}s`);
            console.log(data);
            addOverlay(data,true);
         })
         .catch((error) => {
            console.error('Cannot load data.',error);
         });
      return false;
   })

   $("#aqi").on("click",() => {
      let bounds = app.map.getBounds()
      let nw = bounds.getNorthWest()
      let se = bounds.getSouthEast()
      let mapWidth = Math.abs(nw.lng - se.lng)
      console.log(mapWidth);
      var partition = $("#partition").val();
      var method = $("#method").val();
      let start = new Date();
      url = `/api/partition/${partition}/interpolate?nwlat=${nw.lat}&nwlon=${nw.lng}&selat=${se.lat}&selon=${se.lng}&method=${method}`
      fetch(url)
         .then(response => response.json())
         .then(data => {
            let diff = (new Date() - start) / 1000.0;
            console.log(`Elapsed: ${diff}s`);
            console.log(data);
            addOverlay(data,false);
         })
         .catch((error) => {
            console.error('Cannot load data.',error);
         });

   });

   fetch('/api/partitions')
      .then(response => response.json())
      .then(data => {
         $("#partition").empty();
         data.forEach((item) => {
            $("#partition").append(`<option>${item}</option>`)
         });
      })
      .catch((error) => {
         console.error('Cannot load partitions.',error);
      });

   app.methods.forEach((method) => {
      $("#method").append(`<option${method=='linear' ? ' selected' : ''}>${method}</option>`);
   });

})
