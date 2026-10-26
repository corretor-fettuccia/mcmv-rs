#!/usr/bin/env bash
# Instalador CLI - envia o codigo do motor indicado para seu Apps Script exclusivo.
# Nenhum comando aqui publica Web Apps, cria implantacoes ou altera o Google Sheets.
set -euo pipefail

if [[ $# -lt 2 ]]; then echo 'Uso interno: subir_motor.sh A|B DIRETORIO [opcoes]' >&2; exit 2; fi
MOTOR="$1"; PASTA="$2"; shift 2
ROOT="$(cd -- "$PASTA/.." && pwd)"

uso() {
cat <<'TXT'
Opcoes:
  --vincular SCRIPT_ID  Grava .clasp.json (somente se ainda nao existe) e faz push
  --status             Mostra arquivos reconhecidos, nao envia nada
  --dry-run            Valida e mostra os comandos sem chamar a rede
  --ajuda              Exibe estas instrucoes

Exemplo: ./subir.sh --vincular 1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789
Depois: ./subir.sh
TXT
}

VINCULAR=""; STATUS=false; DRY_RUN=false
while (($#)); do
  case "$1" in
    --vincular)
      if (($# < 2)); then echo 'ERRO: --vincular requer o Script ID.' >&2; exit 2; fi
      VINCULAR="$2"; shift 2 ;;
    --status) STATUS=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --ajuda|-h|--help) uso; exit 0 ;;
    *) echo "ERRO: parametro nao reconhecido: $1" >&2; uso; exit 2 ;;
  esac
done

command -v node >/dev/null || { echo 'ERRO: Node.js nao encontrado.' >&2; exit 1; }
if [[ "$DRY_RUN" == false ]]; then
  command -v npx >/dev/null || { echo 'ERRO: npx nao encontrado (instale Node.js/npm).' >&2; exit 1; }
fi

cd "$PASTA"
case "$MOTOR" in
 A)
   NOME='MOTOR A - API PUBLICA / SOMENTE LEITURA'
   ARQUIVOS=('Config.gs' 'API.gs' 'appsscript.json')
   OUTRO="$ROOT/B_ADMIN_PRIVADO/.clasp.json"
   ;;
 B)
   NOME='MOTOR B - ADMIN PRIVADO / ESCRITA'
   ARQUIVOS=('Config.gs' 'Installer.gs' 'Server.gs' 'Index.html' 'appsscript.json')
   OUTRO="$ROOT/A_API_PUBLICA/.clasp.json"
   ;;
 *) echo 'ERRO: motor nao reconhecido' >&2; exit 2 ;;
esac

echo "== $NOME =="
echo "Data: $(date '+%d/%m/%Y %H:%M:%S')"
for arq in "${ARQUIVOS[@]}"; do
  [[ -s "$arq" ]] || { echo "ERRO: falta o arquivo $PASTA/$arq" >&2; exit 1; }
done

# Arquivos de outro motor aqui seriam enviados por engano e violam a isolacao.
if [[ "$MOTOR" == A && ( -e 'Server.gs' || -e 'Installer.gs' || -e 'Index.html' ) ]]; then
  echo 'ERRO: arquivos administrativos detectados no Motor A.' >&2; exit 1
fi
if [[ "$MOTOR" == B && -e 'API.gs' ]]; then
  echo 'ERRO: API publica detectada na pasta do Motor B.' >&2; exit 1
fi

# Script IDs do Google Apps Script (nao o ID do Google Sheets).
verificar_id() {
  node -e '
  const value=process.argv[1];
  if (!/^[A-Za-z0-9_-]{20,200}$/.test(value) || value === "1ljlMUCV4GQgE201tSsh_9-wTK_0_LqZorobDmlM1cS4") {
    console.error("ERRO: Script ID invalido ou parece ser o ID da planilha. Copie o ID em Configuracoes do projeto > ID do script.");
    process.exit(1);
  }' "$1"
}

if [[ -n "$VINCULAR" ]]; then
  verificar_id "$VINCULAR"
  if [[ -f .clasp.json ]]; then
    echo 'ERRO: .clasp.json ja existe. Nao sera substituido automaticamente.' >&2
    echo 'Confira o projeto vinculado antes de alterar manualmente esse arquivo.' >&2
    exit 1
  fi
  # Previne vincular ambos os motores a um unico projeto Apps Script.
  if [[ -f "$OUTRO" ]]; then
    OUTRO_ID="$(node -e 'let o=require(process.argv[1]); process.stdout.write(o.scriptId||"")' "$OUTRO")"
    if [[ "$VINCULAR" == "$OUTRO_ID" ]]; then
      echo 'ERRO: Motor A e Motor B nao podem usar o mesmo Script ID.' >&2; exit 1
    fi
  fi
  printf '{\n  "scriptId": "%s",\n  "rootDir": "."\n}\n' "$VINCULAR" > .clasp.json
  chmod 600 .clasp.json
  echo '.clasp.json criado para este motor.'
fi

if [[ ! -f .clasp.json ]]; then
  echo 'ERRO: .clasp.json nao encontrado neste modulo.' >&2
  echo 'Vincule com: ./subir.sh --vincular SEU_SCRIPT_ID_DO_APPS_SCRIPT' >&2
  exit 1
fi

SCRIPT_ID="$(node -e '
  const fs=require("fs");
  try {
    const c=JSON.parse(fs.readFileSync(".clasp.json", "utf8"));
    if (!c.scriptId || (c.rootDir && c.rootDir !== ".")) throw Error("scriptId ausente ou rootDir diferente de ponto");
    process.stdout.write(c.scriptId);
  } catch (e) {console.error("ERRO: .clasp.json invalido: " + e.message);process.exit(1)}')"
verificar_id "$SCRIPT_ID"
if [[ -f "$OUTRO" ]]; then
  OUTRO_ID="$(node -e 'let o=require(process.argv[1]); process.stdout.write(o.scriptId||"")' "$OUTRO")"
  if [[ "$SCRIPT_ID" == "$OUTRO_ID" ]]; then
    echo 'ERRO: ambos os motores apontam para o MESMO projeto Apps Script. Corrija os IDs.' >&2; exit 1
  fi
fi

echo "Pasta: $PASTA"
echo "Projeto Apps Script: $SCRIPT_ID"
echo "Arquivos previstos: ${ARQUIVOS[*]}"
echo
echo 'ATENCAO: push --force substitui o conteudo remoto do projeto vinculado.'

if [[ "$DRY_RUN" == true ]]; then
  echo 'SIMULACAO: npx @google/clasp show-file-status'
  if [[ "$STATUS" == false ]]; then echo 'SIMULACAO: npx @google/clasp push --force'; fi
  echo 'Nenhum arquivo enviado.'
  exit 0
fi

echo '== Arquivos reconhecidos pelo clasp =='
npx @google/clasp show-file-status

if [[ "$STATUS" == true ]]; then
  echo 'Status concluido; nada foi enviado.'
  exit 0
fi

echo
echo '== Enviando arquivos para o Apps Script =='
npx @google/clasp push --force

echo
echo '== PUSH CONCLUIDO =='
if [[ "$MOTOR" == B ]]; then
  echo '1) No editor do projeto B, execute instalarProjeto() com a conta proprietaria.'
  echo '2) Confira OPERADORES e protecao da planilha.'
  echo '3) Implante/atualize a Web App B: executar como usuario que acessa, acesso autenticado.'
else
  echo '1) No editor do projeto A, execute testarLeitura() (nao grava nada).'
  echo '2) Implante/atualize a Web App A: executar como a conta LEITORA; acesso publico.'
  echo '3) Copie o /exec de A para VITRINE_GITHUB/config.js.'
fi
echo 'O push NAO atualiza automaticamente uma implantacao /exec ja publicada.'
