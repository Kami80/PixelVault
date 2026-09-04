export class PixelPet {
  constructor(app) {
    this.app = app;
    this.state = "idle";
  }

  setState(state) {
    this.state = state;
    console.log("Pet state:", state);
  }

  moveTo(x, y) {
    console.log("Moving pet:", x, y);
  }
}