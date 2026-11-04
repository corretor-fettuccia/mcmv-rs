#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'app.js'),'utf8');
const v4={schemaVersion:4,config:{titulo:'Teste',simuladorAtivo:false,faixasRenda:[],fatorRenda:0.3,prazoMeses:420,jurosAno:0.08},items:[{
  id:'imovel-002',name:'Apartamento V4 com Sacada',url:'https://example.com/v4',
  pageUrl:'https://example.com/imoveis/imovel-002/',highlight:'Sacada',description:'Descrição completa',
  image:'https://example.com/foto.webp',region:'Metropolitana',city:'Canoas',neighborhood:'Centro',
  state:'Pronto para morar',minimum:360000,maximum:360000,attributes:['Sacada']
}]};
const v3={nome:'Portal legado',empreendimentos:[{
  id:'imovel-001',nome:'Apartamento com Jacuzzi',descricao:'Sacada e Jacuzzi',
  cidade:'Canoas',bairro:'Centro',regiao:'Metropolitana RS',uf:'RS',situacao:'Pronto para morar',
  valor_minimo:320000,valor_maximo:330000,imagem:'https://example.com/img.webp',
  url_empreendimento:'https://example.com/imovel',atributos:'Jacuzzi, Sacada'
}]};
function fakeElement(){
  return {value:'',innerHTML:'',textContent:'',hidden:false,style:{},className:'',children:[],options:[],childElementCount:0,
    addEventListener(){},appendChild(child){this.children.push(child);this.childElementCount++;return child},
    append(...children){this.children.push(...children);this.childElementCount+=children.length},
    setAttribute(){},replaceChildren(...kids){this.children=[...kids];this.options=[...kids];this.childElementCount=kids.length},
    add(option){this.options.push(option)},scrollIntoView(){}};
}
async function run(data,status=200){
  const els=new Map();const get=id=>{if(!els.has(id))els.set(id,fakeElement());return els.get(id)};
  let requested='';let consoleLines=[];
  const doc={getElementById:get,querySelector(){return get('footnote')},
    currentScript:{src:'https://mcmv-rs.com.br/app.js?v=4.1.3'},
    baseURI:'https://mcmv-rs.com.br/',createElement(){return fakeElement()},
    createTextNode(text){return {textContent:text}}};
  const context={document:doc,URL,Option:function(label,value){return {label,value}},
    fetch:async function(url){requested=url;return {ok:status===200,status,headers:{get(){return 'application/json'}},json:async()=>data}},
    console:{error(...args){consoleLines.push(args.join(' '))},info(...args){consoleLines.push(args.join(' '))}},
    setTimeout,clearTimeout,Date,Set,Array,Math,Number,String,Intl};
  vm.runInNewContext(source,context,{filename:'app.js',timeout:2000});
  for(let i=0;i<12;i++)await Promise.resolve();
  return {get,requested,consoleLines};
}
(async()=>{
  const a=await run(v4);
  assert.equal(a.requested,'https://mcmv-rs.com.br/catalogo.json');
  assert.match(a.get('resultsCount').textContent,/empreendimentos encontrados|empreendimento encontrado/);
  assert.match(a.get('tiles').innerHTML,/class="card"/);
  assert(!a.consoleLines.some(x=>x.includes('Falha')));
  const b=await run(v3);
  assert.match(b.get('resultsCount').textContent,/1 empreendimento encontrado/);
  assert.match(b.get('tiles').innerHTML,/Apartamento com Jacuzzi/);
  assert.match(b.get('tiles').innerHTML,/href="https:\/\/example\.com\/imovel"/);
  assert(!b.get('attributeArea').hidden,'atributos da versão legada precisam aparecer');
  const labels=b.get('attributeFilters').children.map(x=>x.children.find(y=>y&&y.textContent)?.textContent).filter(Boolean);
  assert.deepEqual(labels,['Jacuzzi','Sacada']);
  const c=await run({},404);
  assert.match(c.get('tiles').children[0].textContent,/HTTP 404/);
  const atual=JSON.parse(fs.readFileSync(path.join(root,'catalogo.json'),'utf8'));
  const d=await run(atual);
  assert(!d.consoleLines.some(x=>x.includes('Falha')),'catálogo existente não pode quebrar a vitrine');
  console.log('OK V4.1.3: JSON público, V4, legado V3, catálogo instalado, filtros dinâmicos e erro HTTP.');
})().catch(e=>{console.error(e);process.exitCode=1});
