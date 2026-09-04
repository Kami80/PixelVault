export function bindPetEvent(event){
 document.dispatchEvent(new CustomEvent("pixel-pet-event",{detail:event}));
}