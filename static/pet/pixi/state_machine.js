export const PetStates = {
 IDLE:"idle",
 WORKING:"working",
 THINKING:"thinking",
 HAPPY:"happy",
 SLEEPING:"sleeping",
 CELEBRATING:"celebrating"
};

export class StateMachine {

 constructor(){
  this.state=PetStates.IDLE;
 }

 change(state){
  this.state=state;
 }

}