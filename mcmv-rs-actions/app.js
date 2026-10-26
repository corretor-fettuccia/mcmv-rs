
    'use strict';
    const $ = id => document.getElementById(id);
    let items = [];
    const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const money = n => Number(n).toLocaleString('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0});
    const clean = s => String(s??'').trim();
    const normalize = s => clean(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
    const validUrl = value => {try {const u=new URL(value); return ['http:','https:'].includes(u.protocol)&&!!u.hostname&&!u.username&&!u.password;}catch{return false;}};
    const locationSvg = `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg>`;
    function labelPrice(min,max){const a=Number(min)||0,b=Number(max)||0; if(!a&&!b)return'Consulte valores';if(a&&b)return money(a)+' – '+money(b);return a?'A partir de '+money(a):'Até '+money(b);}
    function locationText(x){const s=[clean(x.neighborhood),clean(x.city)].filter(Boolean);return s.length?s.join(' · '):'Cidade e bairro a informar';}
    let portalConfig = null;
    let financial = null;
    function artSvg(index){const colors=[['#cae7dd','#78aca0','#eff9f4'],['#dde0ed','#7f96b1','#f6f6fc'],['#ecddc9','#be9b7a','#faf3e8'],['#c8e4ee','#76a4bb','#effafd'],['#dfd8d4','#a7968b','#fbf5ef']][index%5];const tall=index%3===0;return `<div class="fallbackArtwork" aria-hidden="true"><svg viewBox="0 0 600 370" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="sky${index}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${colors[0]}"/><stop offset="1" stop-color="${colors[2]}"/></linearGradient><linearGradient id="build${index}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${colors[2]}"/><stop offset="1" stop-color="${colors[1]}"/></linearGradient></defs><rect width="600" height="370" fill="url(#sky${index})"/><circle cx="490" cy="75" r="44" fill="#fff" opacity=".65"/><path d="M0 300Q175 260 325 297T600 290V370H0Z" fill="${colors[1]}" opacity=".23"/><rect x="155" y="${tall?60:105}" width="260" height="250" fill="url(#build${index})" stroke="#809899" stroke-opacity=".23" stroke-width="2"/><rect x="410" y="140" width="95" height="169" fill="${colors[2]}" stroke="#a6c0bd"/><rect x="124" y="149" width="35" height="161" fill="#94bbb0" opacity=".6"/><path d="M144 ${tall?59:104}h275" stroke="#657d84" stroke-width="8"/><g fill="#537f91">${Array.from({length:4},(_,floor)=>Array.from({length:5},(_,col)=>`<rect x="${174+col*45}" y="${(tall?80:125)+floor*51}" width="29" height="33" rx="1" opacity="${(col+floor)%3===0?'.66':'.82'}"/>`).join('')).join('')}</g><g stroke="#d9e9e5" stroke-width="4">${Array.from({length:5},(_,col)=>`<path d="M${174+col*45+14} ${tall?80:125}v185"/>`).join('')}</g><g fill="#618a7e"><path d="M47 305v-90" stroke="#668174" stroke-width="7"/><circle cx="47" cy="220" r="40"/><circle cx="78" cy="248" r="27"/><path d="M551 306v-72" stroke="#668174" stroke-width="6"/><circle cx="551" cy="232" r="42"/></g><rect y="310" width="600" height="60" fill="#e9e5de" opacity=".65"/><path d="M0 315h600" stroke="#fff" stroke-width="3"/></svg></div>`;}

    function mcmvFaixa(income){
      const ranges = portalConfig.faixasRenda || [];
      for(const f of ranges){if(income<=Number(f.ate))return {nome:f.nome,id:f.id};}
      return {nome:'Fora das faixas cadastradas',id:0};
    }
    function financiamentoEstimado(renda){
      const f=mcmvFaixa(renda),parcela=renda*Number(portalConfig.fatorRenda);
      const meses=Number(portalConfig.prazoMeses),taxa=Number(portalConfig.jurosAno)/12;
      const fator=taxa===0?1/meses:taxa/(1-Math.pow(1+taxa,-meses));
      return {...f,renda,parcela,loan:parcela/fator};
    }
    function priceRange(){
      const v=Number(portalConfig.intervaloPercentual||20)/100;
      return [financial.loan*(1-v),financial.loan*(1+v)];
    }
    function compatibility(x){
      if(!financial) return null;
      const [low,high]=priceRange();
      const min=Number(x.minimum)||0,max=Number(x.maximum)||0;
      if(!min&&!max)return {matched:false, text:'Sem preços cadastrados'};
      const a=min||max,b=Math.max(a,max||min);
      return {matched:a<=high && b>=low,text:a<=high && b>=low?'Compatível com a faixa estimada':'Fora da faixa'};
    }
    function campanhaValida(x){
      if(!x.campaign || x.campaign==='NENHUMA') return false;
      const dia=new Date().toISOString().slice(0,10);
      return (!x.campaignStart||x.campaignStart<=dia)&&(!x.campaignEnd||x.campaignEnd>=dia);
    }
    function cardHtml(x,i){
      const campanha=campanhaValida(x);
      const pin=campanha && x.campaign==='SELO'?'<span class="campaignPin">'+esc(x.campaignText||'CONDIÇÃO ESPECIAL')+'</span>':'';
      const banner=campanha && x.campaign==='BANNER'?'<div class="campaignBanner">'+esc(x.campaignText||'Condição especial')+'</div>':'';
      const img=validUrl(x.image)?'<img src="'+esc(x.image)+'" loading="lazy" alt="Empreendimento '+esc(x.name)+'" onerror="this.style.display=\'none\'">':artSvg(i);
      return '<article class="card"><div class="cardmedia">'+img+'<span class="badge">'+esc(x.state)+'</span>'+pin+'</div><div class="cardbody"><h3>'+esc(x.name)+'</h3><div class="location">'+locationSvg+'<span>'+esc([x.neighborhood,x.city].filter(Boolean).join(' · '))+'</span></div>'+banner+'<p class="detail">'+esc(x.highlight)+'</p><div class="divider"><div class="price"><small>FAIXA DE VALORES</small>'+esc(labelPrice(x.minimum,x.maximum))+'</div><a class="cardbtn" href="'+esc(validUrl(x.url)?x.url:'#')+'" target="_blank" rel="noopener noreferrer">Conhecer →</a></div></div></article>';
    }
    function updateSelect(el,values,blank){
      const old=el.value;
      const sorted=[...new Set(values.map(clean).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
      el.replaceChildren(new Option(blank,''));sorted.forEach(v=>el.add(new Option(v,v)));
      el.value=sorted.includes(old)?old:'';
    }
    function refreshOptions(){
      const region=$('regionFilter').value,city=$('cityFilter').value;
      updateSelect($('regionFilter'),items.map(x=>x.region),'Todas as regiões');
      updateSelect($('cityFilter'),items.filter(x=>!region||x.region===region).map(x=>x.city),'Todas as cidades');
      updateSelect($('neighborhoodFilter'),items.filter(x=>(!region||x.region===region)&&(!city||x.city===city)).map(x=>x.neighborhood),'Todos os bairros');
    }
    function refreshTiles(){
      if(!portalConfig)return;
      const all=items;
      const keys=normalize($('search').value).split(/\s+/).filter(Boolean);
      const region=$('regionFilter').value,city=$('cityFilter').value,neigh=$('neighborhoodFilter').value,st=$('stateFilter').value;
      let filtered=all.filter(x=>{
        const words=normalize([x.name,x.region,x.city,x.neighborhood,x.address,x.highlight,x.state].join(' '));
        return (!region||x.region===region)&&(!city||x.city===city)&&(!neigh||x.neighborhood===neigh)&&(!st||x.state===st)&&keys.every(k=>words.includes(k));
      });
      if(financial) filtered=filtered.filter(x=>compatibility(x).matched);
      $('resultsCount').textContent=filtered.length+' '+(filtered.length===1?'empreendimento encontrado':'empreendimentos encontrados');
      $('tiles').innerHTML=filtered.length?filtered.map(cardHtml).join(''):'<div class="empty">Nenhum empreendimento encontrado. Ajuste os filtros de localização ou sua renda.</div>';
    }
    function renderMode(mode){
      financial=null;
      $('incomePanel').hidden=mode!=='income';
      $('placePanel').hidden=mode!=='place';
      $('modeIncome').className=mode==='income'?'':'secondary';
      $('modePlace').className=mode==='place'?'':'secondary';
      refreshTiles();
    }
    function initPortal(payload){
      portalConfig=payload.config;items=payload.items||[];
      // Preserva o titulo SEO e o hero institucional definidos no HTML.
      // Os dados do Motor A alimentam o catalogo e os filtros.
      // Identidade institucional fixa; título do catálogo exibido no hero.
      document.querySelector('.footnote').textContent=portalConfig.simuladorAtivo?'Portal para você conquistar o sonho da casa própria.':'Portal imobiliário. Informações de empreendimentos.';
      if(!portalConfig.simuladorAtivo){
        $('simulator').hidden=true;
        $('modeIncome').hidden=true;
        $('incomePanel').hidden=true;
        financial=null;
      }
      refreshOptions();refreshTiles();
    }
    $('search').addEventListener('input',refreshTiles);
    $('regionFilter').addEventListener('change',()=>{$('cityFilter').value='';$('neighborhoodFilter').value='';refreshOptions();refreshTiles();});
    $('cityFilter').addEventListener('change',()=>{$('neighborhoodFilter').value='';refreshOptions();refreshTiles();});
    $('neighborhoodFilter').addEventListener('change',refreshTiles);
    $('stateFilter').addEventListener('change',refreshTiles);
    $('resetFilters').addEventListener('click',()=>{
      for(const id of ['search','regionFilter','cityFilter','neighborhoodFilter','stateFilter'])$(id).value='';
      financial=null;refreshOptions();refreshTiles();
    });
    $('modeIncome').addEventListener('click',()=>renderMode('income'));
    $('modePlace').addEventListener('click',()=>renderMode('place'));
    $('focusPlace').addEventListener('click',()=>{$('search').focus();$('search').scrollIntoView({behavior:'smooth'});});
    $('runSim').addEventListener('click',()=>{
      const renda=Number($('income').value);
      if(!Number.isFinite(renda)||renda<=0){$('simResult').textContent='Informe uma renda mensal válida.';return;}
      financial=financiamentoEstimado(renda);
      const [low,high]=priceRange();
      $('simResult').innerHTML='<b>'+esc(financial.nome)+'</b> · Financiamento estimado: <b>'+money(financial.loan)+'</b><br>Imóveis pesquisados: <b>'+money(low)+' a '+money(high)+'</b><br><small>Estimativa de triagem: não representa aprovação bancária, subsídio ou cálculo oficial da CAIXA.</small>';
      refreshTiles();$('tiles').scrollIntoView({behavior:'smooth',block:'nearest'});
    });
    $('clearSim').addEventListener('click',()=>{financial=null;$('simResult').textContent='Informe sua renda para filtrar a vitrine.';refreshTiles();});
    $('income').addEventListener('keydown',e=>{if(e.key==='Enter')$('runSim').click();});
    $('tiles').innerHTML='<div class="loader">Carregando empreendimentos cadastrados...</div>';
    /** Carrega o Motor A via JSONP. Apps Script ContentService redireciona para outra
     * origem; JSONP permite consultar o endpoint público pelo GitHub Pages sem CORS.
     * Só usar com API exclusivamente pública e sem dados sensíveis.
     */
    function carregarCatalogo() {
      const url = String(window.VITRINE_API_URL || '').trim();
      if (!/^https:\/\/script\.google\.com\/macros\/s\/[^/]+\/exec(?:\?.*)?$/i.test(url)) {
        exibirFalha('Configure VITRINE_API_URL em config.js com a URL /exec do Motor A.');
        return;
      }
      const callback='__portalVitrine_'+Date.now()+'_'+Math.floor(Math.random()*100000);
      const script=document.createElement('script');
      let concluded=false;
      let timer;
      const concluir=()=>{ if(concluded)return false;concluded=true;
        clearTimeout(timer);delete window[callback];script.remove();return true; };
      window[callback]=(payload)=>{
        if(!concluir())return;
        if(!payload || !payload.ok || !payload.config || !Array.isArray(payload.items)){
          exibirFalha((payload && payload.error) || 'Resposta inesperada do Motor A.');return;
        }
        try { initPortal(payload); } catch(err) {
          console.error('[Vitrine] Falha ao processar dados do Motor A:', err);
          exibirFalha('A API respondeu, mas ocorreu um erro ao processar o catálogo. Consulte o console do navegador.');
        }
      };
      script.onerror=()=>{if(concluir())exibirFalha('Não foi possível carregar a API pública. Verifique a implantação, o acesso e a resposta JSONP do Motor A.');};
      timer=setTimeout(()=>{if(concluir())exibirFalha('A consulta demorou demais. Verifique a conexão ou a URL /exec.');},18000);
      const separator=url.includes('?')?'&':'?';
      script.src=url+separator+'callback='+encodeURIComponent(callback);
      document.head.appendChild(script);
    }
    function exibirFalha(msg){
      $('resultsCount').textContent='Catálogo indisponível';
      $('tiles').replaceChildren();
      const box=document.createElement('div');box.className='empty';box.textContent=msg;
      $('tiles').appendChild(box);
    }
    carregarCatalogo();
