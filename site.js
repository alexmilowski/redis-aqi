// jQuery free!
function setup() {
   if (document.readyState=="loading") {
      setTimeout(setup,10);
      return
   }
   for (let section of document.getElementsByClassName("tile")) {
      if (section.tagName!="SECTION") {
         continue;
      }
      section.addEventListener("click", () => {
         let a = section.getElementsByTagName('a')[0]
         document.location = a.href;
      });
   }
}

setup();
