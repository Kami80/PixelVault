export class PixelPet {
 constructor(app){this.app=app;this.state='idle';}
 setState(state){this.state=state;}
 walk(x,y){this.setState('walking');}
 celebrate(){this.setState('celebrate');}
}
