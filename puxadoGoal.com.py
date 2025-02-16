import sys
import subprocess
import pkg_resources
import json
from datetime import datetime
import pytz
import unicodedata
import re

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", package])

def check_and_install_dependencies():
    required = {'playwright', 'pytz'}
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = required - installed

    if missing:
        print("Instalando dependências faltantes...")
        for package in missing:
            install(package)
    else:
        print("Atualizando dependências...")
        for package in required:
            install(package)

    print("Instalação/atualização de dependências concluída.")

def normalizar_nome(nome):
    nome = re.sub(r'[^\w\s-]', '', nome.lower())
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def ler_nao_inclusos():
    try:
        with open('NaoInclusos.txt', 'r', encoding='utf-8') as f:
            return [linha.strip().lower() for linha in f if linha.strip()]
    except FileNotFoundError:
        print("Arquivo NaoInclusos.txt não encontrado. Todos os jogos serão incluídos.")
        return []

def traduzir_dia_semana(dia_semana):
    dias = {
        "Monday": "SEGUNDA-FEIRA",
        "Tuesday": "TERÇA-FEIRA",
        "Wednesday": "QUARTA-FEIRA",
        "Thursday": "QUINTA-FEIRA",
        "Friday": "SEXTA-FEIRA",
        "Saturday": "SÁBADO",
        "Sunday": "DOMINGO"
    }
    return dias.get(dia_semana, dia_semana)

def extrair_jogos(max_retries=3, timeout=60000):
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

    for attempt in range(max_retries):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                page = context.new_page()
                print(f"Tentativa {attempt + 1} de {max_retries}: Iniciando a extração...")
                
                page.goto("https://www.goal.com/br/listas/futebol-programacao-jogos-tv-aberta-fechada-onde-assistir-online-app/bltc0a7361374657315", timeout=timeout)
                
                # Espera explícita pelo conteúdo
                page.wait_for_selector('.standard-slide_slide__NTl4f', timeout=timeout)
                
                # Aguarda um pouco mais para garantir que todo o conteúdo seja carregado
                page.wait_for_timeout(5000)

                jogos_do_dia = []
                tz = pytz.timezone('America/Recife')
                now = datetime.now(tz)
                dia_atual = now.strftime('%d/%m/%Y')
                dia_semana = traduzir_dia_semana(now.strftime('%A'))
                titulo_json = f"JOGOS DO DIA - {dia_atual} ({dia_semana})"
                jogos_do_dia.append({"titulo_json": titulo_json})
                
                slides = page.query_selector_all('.standard-slide_slide__NTl4f')
                for slide in slides:
                    data = slide.query_selector('.headline_headline__IQpss').inner_text().strip()
                    rows = slide.query_selector_all('table tr:not(:first-child)')
                    for row in rows:
                        cols = row.query_selector_all('td')
                        if len(cols) >= 5:
                            jogo = cols[0].inner_text().strip()
                            campeonato = cols[1].inner_text().strip()
                            horario = cols[2].inner_text().strip()
                            onde_passa = cols[3].inner_text().strip()
                            times = jogo.split('x')
                            time1 = times[0].strip() if len(times) > 0 else 'N/A'
                            time2 = times[1].strip() if len(times) > 1 else 'N/A'
                            jogos_do_dia.append({
                                "data": data,
                                "hora": horario,
                                "campeonato": campeonato,
                                "time1": time1,
                                "time2": time2,
                                "onde_passa": onde_passa
                            })
                
                browser.close()
                
                with open('jogos.json', 'w', encoding='utf-8') as f:
                    json.dump(jogos_do_dia, f, ensure_ascii=False, indent=4)
                
                print("Extração concluída com sucesso.")
                return jogos_do_dia

        except PlaywrightTimeoutError:
            print(f"Timeout na tentativa {attempt + 1}. Tentando novamente...")
            time.sleep(5)  # Espera 5 segundos antes de tentar novamente
        except Exception as e:
            print(f"Erro durante a extração na tentativa {attempt + 1}: {e}")
            time.sleep(5)  # Espera 5 segundos antes de tentar novamente

    print("Todas as tentativas falharam. Não foi possível extrair os jogos.")
    return None

def organizar_jogos(jogos_originais):
    jogos_por_data = {}
    for jogo in jogos_originais[1:]:
        data = jogo['data']
        jogo_simplificado = {
            "hora": jogo['hora'],
            "campeonato": jogo['campeonato'],
            "time1": jogo['time1'],
            "time2": jogo['time2'],
            "onde_passa": jogo['onde_passa']
        }
        if data not in jogos_por_data:
            jogos_por_data[data] = []
        jogos_por_data[data].append(jogo_simplificado)
    jogos_organizados = {
        "titulo": jogos_originais[0]['titulo_json'],
        "jogos": jogos_por_data
    }
    with open('jogos_organizados.json', 'w', encoding='utf-8') as f:
        json.dump(jogos_organizados, f, ensure_ascii=False, indent=4)
    print("Arquivo 'jogos_organizados.json' criado com sucesso.")
    return jogos_organizados

def formatar_json_para_txt(dados):
    nao_inclusos = ler_nao_inclusos()
    texto_saida = [dados['titulo']]
    for data, jogos in dados['jogos'].items():
        texto_saida.append(f"\n{data}")
        for jogo in jogos:
            if jogo['campeonato'].lower() not in nao_inclusos and jogo['onde_passa'].lower() not in nao_inclusos:
                linha = f"{jogo['time1']} x {jogo['time2']} {jogo['campeonato']} {jogo['hora']} {jogo['onde_passa']}"
                texto_saida.append(linha)
    
    with open('jogos_do_dia.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(texto_saida))
    print("Arquivo 'jogos_do_dia.txt' criado com sucesso.")
    
def main():
    check_and_install_dependencies()
    jogos_extraidos = extrair_jogos()
    if jogos_extraidos:
        jogos_organizados = organizar_jogos(jogos_extraidos)
        formatar_json_para_txt(jogos_organizados)

if __name__ == "__main__":
    main()
