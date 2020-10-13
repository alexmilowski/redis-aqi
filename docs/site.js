// jQuery free!
function setup() {
   if (document.readyState=="loading") {
      setTimeout(setup,10);
      return
   }
   if (document.location.pathname.endsWith("/")) {
      let classes = document.body.getAttribute("class");
      if (classes==null) {
         classes = "";
      }
      classes += " main";
      document.body.setAttribute("class",classes)
   }
   secondary = document.getElementById("secondary")
   for (let section of document.getElementsByClassName("tile")) {
      if (section.tagName!="SECTION") {
         continue;
      }
      let a = section.getElementsByTagName('a')[0]
      section.addEventListener("click", () => {
         document.location = a.href;
      });
      // let title = section.getElementsByClassName("tile")[0];
      // let container = document.createElement("span");
      // container.setAttribute("class","item");
      // let link = document.createElement("a");
      // link.setAttribute("href",a.getAttribute("href"));
      // link.appendChild(document.createTextNode(title.textContent));
      // container.appendChild(link);
      // secondary.appendChild(container);
   }
}

setup();
