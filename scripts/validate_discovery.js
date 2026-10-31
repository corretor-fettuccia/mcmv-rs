#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const site = 'https://mcmv-rs.com.br/';
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const assert = (condition, message) => { if (!condition) throw new Error(message); };
try {
  const catalog = JSON.parse(read('catalogo.json'));
  assert(catalog.url_principal === site && catalog.url_pesquisa === site, 'Destino da busca incorreto');
  assert(Array.isArray(catalog.empreendimentos) && catalog.empreendimentos.length > 0, 'Catálogo vazio');
  assert(catalog.total_empreendimentos === catalog.empreendimentos.length, 'Contagem divergente');
  const itemUrls = catalog.empreendimentos.map(item => {
    assert(item.nome && item.url_busca === site, 'Registro incompleto');
    assert(/^https:\/\/[^\s]+$/.test(item.imagem), `Imagem ausente/inválida: ${item.nome}`);
    assert(/^https:\/\/[^\s]+$/.test(item.url_empreendimento), 'URL inválida');
    return item.url_empreendimento;
  });
  const xml = read('sitemap.xml');
  assert(xml.includes('<urlset'), 'Sitemap inválido');
  const actual = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);
  const expected = [...new Set([site, ...itemUrls])];
  assert(actual.length === new Set(actual).size, 'URLs duplicadas no sitemap');
  assert(JSON.stringify([...actual].sort()) === JSON.stringify(expected.sort()), 'Sitemap divergente da API');
  const ads = read('google-ads-imoveis.csv');
  assert(ads.includes('Listing ID') && ads.includes('Image URL'), 'CSV Ads sem cabeçalho');
  for (const item of catalog.empreendimentos) {
    assert(ads.includes(item.imagem), `Imagem não encontrada no feed Ads: ${item.nome}`);
  }
  const merchant = read('merchant-produtos.xml');
  if (merchant.includes('<item>')) assert(merchant.includes('<g:image_link>'), 'XML sem image_link');
  if (merchant.includes('<item>')) assert(merchant.includes('<g:brand>'), 'XML sem marca verdadeira — publicar MD válidos');
  assert(!merchant.includes('<g:link>https://mcmv-rs.com.br/</g:link>'), 'XML aponta para página inicial');
  const llms = read('llms.txt');
  assert(llms.startsWith('# MCMV-RS'), 'llms.txt sem título');
  assert(llms.includes(site), 'llms.txt sem homepage');
  assert(llms.includes('não é site oficial'), 'Falta aviso institucional');
  for (const item of catalog.empreendimentos) {
    assert(llms.includes(item.url_empreendimento), `Landing ausente em llms.txt: ${item.nome}`);
  }
  assert(read('robots.txt').includes('Sitemap: https://mcmv-rs.com.br/sitemap.xml'), 'robots.txt sem sitemap');
  console.log(`OK: ${actual.length} URLs no sitemap (${catalog.empreendimentos.length} empreendimentos + raiz).`);
} catch (error) {
  console.error('ERRO:', error.message);
  process.exit(1);
}
