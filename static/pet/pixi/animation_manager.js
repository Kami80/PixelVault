export class AnimationManager {

 constructor(){
   this.animations={
    idle:[],
    walk:[],
    work:[],
    think:[],
    celebrate:[]
   };
 }

 play(name){
   console.log("Playing animation:",name);
 }

}