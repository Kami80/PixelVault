let petState={emotion:'idle',frame:0,x:180};
function setPetEmotion(e){petState.emotion=e; const el=document.querySelector('#pet-emotion'); if(el) el.textContent=e;}
function animatePet(){const p=document.querySelector('#pet-sprite');if(!p)return; petState.frame=(petState.frame+1)%4;p.style.backgroundPosition=`-${petState.frame*64}px 0`; if(petState.emotion==='walk'){petState.x=(petState.x+2)%260;p.style.transform=`translateX(${petState.x}px)`;} requestAnimationFrame(animatePet)}
async function sendPet(){let m=document.querySelector('#msg').value;let r=await fetch('/pet/api/chat/',{method:'POST',headers:{'X-CSRFToken':getCookie('csrftoken'),'Content-Type':'application/json'},body:JSON.stringify({message:m})});let j=await r.json();document.querySelector('#chat').innerHTML+=`<p>🐾 ${j.message}</p>`;setPetEmotion(j.emotion||'thinking');}
function getCookie(n){return document.cookie.split('; ').find(x=>x.startsWith(n+'='))?.split('=')[1]||''}
window.onload=()=>{animatePet();setPetEmotion('idle')}
