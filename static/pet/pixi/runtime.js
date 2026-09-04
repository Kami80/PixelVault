(function(){

class PetEngine {

    constructor(){
        this.state = "idle";
        this.emotion = "happy";
        this.init();
    }

    init(){

        const container =
            document.getElementById("pixelvault-pet");

        if(!container || !window.PIXI){
            return;
        }

        this.app = new PIXI.Application({
            width:240,
            height:240,
            backgroundAlpha:0
        });

        container.appendChild(this.app.view);

        this.pet = PIXI.Sprite.from(
            "/static/pet/assets/pet_idle_00.webp"
        );

        this.pet.anchor.set(.5);
        this.pet.x=120;
        this.pet.y=120;
        this.pet.scale.set(.8);

        this.app.stage.addChild(this.pet);

        this.loop();
    }


    setState(state){
        this.state = state;
        console.log("Pet state:",state);
    }


    loop(){

        this.app.ticker.add(()=>{
            this.pet.y =
              120 + Math.sin(Date.now()/300)*5;
        });

    }
}


window.PixelVaultPet = new PetEngine();

})();