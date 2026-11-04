#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'app.js'),'utf8');
const item1={
  id:'imovel-002',name:'Apartamento com Sacada e Jacuzzi',url:'https://imovel.example.com/',
  pageUrl:'https://mcmv-rs.com.br/imoveis/imovel-002/',highlight:'Apartamento novo',description:'Descrição completa',
  image:'https://imovel.example.com/foto.webp',region:'Metropolitana',city:'Canoas',neighborhood:'Centro',
  state:'Pronto para morar',minimum:360000,maximum:360000,attributes:['Sacada','Jacuzzi']
};
const item2={...item1,id:'imovel-003',name:'Apartamento com Sacada',pageUrl:'https://mcmv-rs.com.br/imoveis/imovel-003/',attributes:['Sacada']};
const cfg={titulo:'Teste',simuladorAtivo:false,faixasRenda:[],fatorRenda:0.3,prazoMeses:420,jurosAno:0.08};
const v4={schemaVersion:4,config:cfg,items:[item1,item2]};
const v3={nome:'Portal legado',empreendimentos:[{
  id:'imovel-001',nome:'Apartamento com Jacuzzi',descricao:'Sacada e Jacuzzi',
  cidade:'Canoas',bairro:'Centro',regiao:'Metropolitana RS',uf:'RS',situacao:'Pronto para morar',
  valor_minimo:320000,valor_maximo:330000,imagem:'https://example.com/img.webp',
  url_empreendimento:'https://external.example.com/imovel',atributos:'Jacuzzi, Sacada'
}]};
function fakeElement(){
  return {value:'',innerHTML:'',textContent:'',hidden:false,style:{},className:'',children:[],options:[],childElementCount:0,checked:false,
    handlers:{},addEventListener(type,cb){this.handlers[type]=cb},
    appendChild(child){this.children.push(child);this.childElementCount++;return child},
    append(...children){this.children.push(...children);this.childElementCount+=children.length},
    setAttribute(){},replaceChildren(...kids){this.children=[...kids];this.options=[...kids];this.childElementCount=kids.length},
    add(option){this.options.push(option)},scrollIntoView(){}};
}
async function run(data,status=200){
  const els=new Map();const get=id=>{if(!els.has(id))els.set(id,fakeElement());return els.get(id)};
  let requested='';const errors=[];
  const doc={getElementById:get,querySelector(){return get('footnote')},
    currentScript:{src:'https://mcmv-rs.com.br/app.js?v=4.1.7'},
    baseURI:'https://mcmv-rs.com.br/',createElement(){return fakeElement()},
    createTextNode(text){return {textContent:text}}};
  const context={document:doc,URL,Option:function(label,value){return {label,value}},
    fetch:async function(url){requested=url;return {ok:status===200,status,headers:{get(){return 'application/json'}},json:async()=>data}},
    console:{error(...args){errors.push(args.join(' '))},info(){}},
    setTimeout,clearTimeout,Date,Set,Array,Math,Number,String,Intl};
  vm.runInNewContext(source,context,{filename:'app.js',timeout:2000});
  doc.currentScript=null; // Comportamento real depois que o script termina de executar.
  for(let i=0;i<15;i++)await Promise.resolve();
  return {get,requested,errors};
}
(async()=>{
  const a=await run(v4);
  assert.equal(a.requested,'https://mcmv-rs.com.br/catalogo.json');
  assert.match(a.get('resultsCount').textContent,/2 empreendimentos encontrados/);
  const html=a.get('tiles').innerHTML;
  assert.match(html,/Ver detalhes/);
  assert.match(html,/href="https:\/\/mcmv-rs\.com\.br\/imoveis\/imovel-002\/"/);
  assert(!html.includes('Landing page'),'Jamais mostrar CTA externa em card');
  assert(!html.includes('href="https://imovel.example.com/"'),'Não deve expor o link comercial no card');
  assert.equal(a.get('attributeArea').hidden,false);
  const labels=a.get('attributeFilters').children;
  assert.equal(labels.length,2);
  assert.deepEqual(labels.map(x=>x.children[1].textContent),['Jacuzzi','Sacada']);
  assert.deepEqual(labels.map(x=>x.children[2].textContent),['1','2']);
  labels[0].children[0].checked=true;
  labels[0].children[0].handlers.change();
  assert.match(a.get('resultsCount').textContent,/1 empreendimento encontrado/);
  assert.match(a.get('tiles').innerHTML,/Apartamento com Sacada e Jacuzzi/);
  assert(!a.get('tiles').innerHTML.includes('imovel-003'));
  labels[1].children[0].checked=true;
  labels[1].children[0].handlers.change();
  assert.match(a.get('resultsCount').textContent,/1 empreendimento encontrado/);
  labels[0].children[0].checked=false;
  labels[0].children[0].handlers.change();
  assert.match(a.get('resultsCount').textContent,/2 empreendimentos encontrados/);
  assert.equal(a.errors.length,0);

  const b=await run(v3);
  assert.equal(b.get('attributeArea').hidden,false);
  assert.deepEqual(b.get('attributeFilters').children.map(x=>x.children[1].textContent),['Jacuzzi','Sacada']);
  assert.match(b.get('tiles').innerHTML,/href="https:\/\/mcmv-rs\.com\.br\/imoveis\/imovel-001\/"/);
  assert(!b.get('tiles').innerHTML.includes('href="https://external.example.com/imovel"'));

  // O catálogo real só existe depois da etapa 1 do Core; sem ele, esta parte é pulada.
  const catalogFile=path.join(root,'catalogo.json');
  if(fs.existsSync(catalogFile)){
    const actual=JSON.parse(fs.readFileSync(path.join(root,'catalogo.json'),'utf8'));
    const c=await run(actual);
    assert.equal(c.get('attributeArea').hidden,false);
    // Compare as MESMAS chaves da vitrine (sem acentos/maiúsculas).
    // A contagem literal do JSON pode ser maior por grafias equivalentes.
    const attributeKey = value => String(value??'').trim().normalize('NFD')
      .replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
    const present=new Set((actual.items||[])
      .flatMap(x=>Array.isArray(x.attributes)?x.attributes:[])
      .map(attributeKey).filter(Boolean));
    const available=new Set((actual.atributos_disponiveis||[])
      .map(attributeKey).filter(Boolean));
    assert.deepEqual([...available].sort(),[...present].sort(),
      'Lista pública de atributos deve corresponder aos filtros do catálogo');
    if(present.size) {
      assert.equal(c.get('attributeFilters').children.length,present.size);
    } else {
      assert.match(c.get('attributeFilters').children[0].textContent,/0 atributos no catálogo publicado/);
    }
    assert(!c.get('tiles').innerHTML.includes('Landing page'));

  }

  // Regressão: variantes de acentuação/caixa não podem duplicar filtros.
  const variants={schemaVersion:4,config:cfg,items:[
    {...item1,attributes:['Água quente','Sacada']},
    {...item2,attributes:['agua quente','SACADA']}
  ]};
  const e=await run(variants);
  const variantFilters=e.get('attributeFilters').children;
  assert.equal(variantFilters.length,2);
  assert.deepEqual(variantFilters.map(x=>x.children[2].textContent),['2','2']);

  const d=await run({},404);
  assert.match(d.get('tiles').children[0].textContent,/HTTP 404/);
  console.log('OK: CTAs internos, filtros e contagens normalizados, grafias equivalentes, catálogo, HTTP 404.');
})().catch(e=>{console.error(e);process.exitCode=1});
