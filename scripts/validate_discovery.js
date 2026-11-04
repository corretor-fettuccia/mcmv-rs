#!/usr/bin/env node
// Compatibilidade com workflows antigos. Valida SOMENTE o contrato V4.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const c = JSON.parse(fs.readFileSync(path.join(__dirname,'..','catalogo.json'),'utf8'));
if(c.schemaVersion!==4 || c.sourceContract!=='core-imobiliario-v4') throw Error('Catálogo V3 sobrescreveu o Core V4');
if(!Array.isArray(c.items) || !Array.isArray(c.empreendimentos)) throw Error('Dados V4 ausentes');
const attrs = [...new Set(c.items.flatMap(x=>x.attributes||[]))].sort((a,b)=>a.toLowerCase().localeCompare(b.toLowerCase(),'pt-BR'));
const listed = c.filtros?.atributos || [];
if(attrs.length!==listed.length || attrs.some(x=>!listed.includes(x))) throw Error('Filtros de atributos inconsistentes');
for(const item of c.items) {
  const old = c.empreendimentos.find(x=>x.id===item.id);
  if(!old || JSON.stringify(old.atributos)!==JSON.stringify(item.attributes)) throw Error('Atributos faltam em empreendimentos[].atributos: '+item.id);
}
console.log('OK: '+c.items.length+' imóveis, '+attrs.length+' filtros, projeções V4 e legada válidas');
