# MCMV-RS — Sitemap automático

Arquivos novos: `.github/workflows/atualizar-sitemap.yml` e `scripts/generate_sitemap.py`.
O sitemap **existente** `sitemap.xml` só é alterado quando o workflow roda com sucesso.
Não modifica o layout, JavaScript ou funcionamento da vitrine.

## Instalação
1. Copie o conteúdo deste ZIP para **a raiz do repositório** do portal (`index.html`, `config.js` e `sitemap.xml` na mesma pasta). Preserve a pasta oculta `.github`.
2. No GitHub, acesse o repositório → **Settings → Actions → General → Workflow permissions** e escolha **Read and write permissions**, se a opção estiver disponível. Caso a organização tenha políticas diferentes, autorize o token a escrever no repositório.
3. Confirme que o GitHub Pages publica a branch padrão (por exemplo `main`) e a pasta raiz. Se publica a pasta `docs/` ou usa artifact de deploy, adapte o destino do XML.
4. Vá em **Actions → Atualizar sitemap MCMV-RS → Run workflow** para a primeira execução. Depois ele roda diariamente às 03:17 UTC (00:17 em Brasília, podendo atrasar). 
5. Confira `https://mcmv-rs.com.br/sitemap.xml` após a publicação. O `robots.txt` já aponta para esse endereço.
6. Envie o sitemap no Search Console. Para **cross-site sitemap**, com URLs externas como `varandas-canoas.com.br`, verifique as propriedades de TODOS os sites listados na mesma conta do Search Console antes de submeter o sitemap centralizado. Consulte: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap#cross-submit-sitemaps

## Fonte de dados
O Python lê a URL existente do `config.js` e requisita a API do Motor A por JSONP, usando o campo `items[].url` já empregado nos links 'Conhecer' da vitrine. Mantém sempre a homepage, remove duplicatas, URLs não HTTPS e parâmetros de rastreamento. Usa o campo `canonicalUrl` quando disponível.

Se quiser controlar a indexação em uma futura versão do Apps Script, inclua `indexar: false`, `index: false` ou `noindex: true` no item correspondente. O Motor A atual pode não fornecer esses campos; neste caso, os itens com URLs válidas serão incluídos automaticamente, sem filtro por status, já que 'em obras' e 'entregue' podem ser indexáveis.

Se a API falhar, retornar login/HTML, lista vazia ou nenhuma URL válida, o job falha **sem apagar o sitemap anterior**. O workflow faz commit apenas quando detectar alterações.

## Limitações importantes
- O GitHub Pages hospeda XML **estático gerado automaticamente**, não executa o gerador em cada visita.
- O GitHub pode atrasar execuções agendadas e desativar schedules em repositórios públicos inativos.
- Isso não garante indexação, não altera o canonical das landing pages e não cria URLs de imóveis no domínio do portal.
- Se o repositório exigir PR ou possuir proteção na branch, o `git push` pode ser bloqueado. Ajuste as permissões ou adote fluxo de PR.
- Caso você não tenha controle/verificação de algum domínio externo, o Google pode não aceitar suas URLs por esse sitemap central. Melhor utilizar sitemap do domínio correspondente.
