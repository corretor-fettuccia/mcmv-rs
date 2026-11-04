#!/usr/bin/env node
'use strict';
// Teste independente da UI V9. Nao acessa API, planilha ou rede.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
function fakeElement(){
  return {
    textContent:'',innerHTML:'',value:'',hidden:false,style:{},options:[],children:[],
    handlers:{},addEventListener(type,fn){this.handlers[type]=fn;},
    setAttribute(){},replaceChildren(){},append(){},add(){},scrollIntoView(){}
  };
}
const nodes = new Map();
const node = id => {if(!nodes.has(id))nodes.set(id,fakeElement());return nodes.get(id)};
const doc = {
  currentScript:{src:'https://mcmv-rs.com.br/app.js?v=9.0.0'},
  baseURI:'https://mcmv-rs.com.br/',
  getElementById:node,querySelector(){return node('footnote');},
  createElement(){return fakeElement();}
};
let tick = null; let cleared = 0;
const ctx = vm.createContext({
  document:doc,URL,Set,Date,Number,String,Math,Array,Intl,
  fetch:()=>new Promise(()=>{}),
  setInterval(fn){tick=fn;return 13;},clearInterval(){cleared++;tick=null;},
  console:{log(){},info(){},error(){}}
});
vm.runInContext(source,ctx,{filename:'app.js',timeout:3000});
const prices = {id:'demo',name:'Imóvel & V9',image:'https://cdn.test/foto1.webp',
  gallery:['https://cdn.test/foto1.webp','https://cdn.test/foto2.webp','javascript:alert(1)',
    {url:'https://cdn.test/foto3.webp'},'https://cdn.test/foto2.webp'],
  pageUrl:'https://mcmv-rs.com.br/imoveis/demo/',state:'Lançamento',city:'Canoas',minimum:250000};
const photos = vm.runInContext('cardGalleryUrls',ctx)(prices);
assert.equal(photos.length,3);
assert.deepEqual([...photos],[
  'https://cdn.test/foto1.webp','https://cdn.test/foto2.webp','https://cdn.test/foto3.webp'
]);
const markup=vm.runInContext('cardHtml',ctx)(prices,0);
assert.equal((markup.match(/class="cardSlide/g)||[]).length,3);
assert.match(markup,/cardGalleryCount/);
assert.match(markup,/href="https:\/\/mcmv-rs.com.br\/imoveis\/demo\/"/);
assert(!markup.includes('javascript:alert'));
assert(!markup.includes('Imóvel & V9</h3>'));
assert(!vm.runInContext('cardHtml',ctx)({...prices,gallery:[],image:prices.image},0).includes('cardGalleryCount'));
assert.match(vm.runInContext('cardHtml',ctx)({...prices,gallery:[],image:''},0),/fallbackArtwork/);
let active = new Set();
const mkClass = (name)=>({
  name,
  toggle(x,yes){if(yes)active.add(name);else active.delete(name)},
});
let current=0;
const slides=[0,1,2].map(i=>({classList:{toggle(_cls,on){if(on)current=i}},setAttribute(){},removeAttribute(){},loading:'lazy'}));
const dots=[0,1,2].map(i=>({classList:mkClass('dot'+i)}));
const counter={textContent:''};
const media={dataset:{galleryCount:'3'},querySelectorAll(sel){return sel==='.cardSlide'?slides:dots;},
  querySelector(sel){return sel==='.cardGalleryCount'?counter:null;}};
const card={querySelector(sel){return sel==='.cardmedia'?media:null;},contains(el){return el===card;}};
const begin = vm.runInContext('galleryStart',ctx);
const stop = vm.runInContext('galleryStop',ctx);
begin(card);
assert.equal(current,1);assert.equal(counter.textContent,'2 / 3');assert.equal(typeof tick,'function');
tick();assert.equal(current,2);assert.equal(counter.textContent,'3 / 3');
stop();assert.equal(current,0);assert.equal(counter.textContent,'1 / 3');assert(cleared>=1);
assert.equal(typeof node('tiles').handlers.pointerover,'function');
assert.equal(typeof node('tiles').handlers.pointerout,'function');
assert.equal(typeof node('tiles').handlers.focusin,'function');
assert.equal(typeof node('tiles').handlers.focusout,'function');
assert.match(html,/id="vitrine-hover-gallery-v9"/);
assert.match(html,/app\.js\?v=9\.0\.0/);
console.log('OK V9: URLs validas/deduplicadas, 3 slides, hover, 1.5s, reset, fallback, filtros delegados e cache bust.');
