export class PetWorld {
 constructor(app){
   this.app=app;
   this.camera={x:0,y:0,zoom:1};
   this.objects=[];
 }
 addObject(obj){this.objects.push(obj);}
 movePetTo(target){
   window.dispatchEvent(new CustomEvent("pet:navigate",{detail:target}));
 }
}