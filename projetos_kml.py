import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from pykml import parser
from geopy.distance import geodesic
import plotly.express as px

# Função para calcular a distância total de uma LineString em metros
def calcular_distancia_linestring(coordinates):
    distancia_total = 0.0
    for i in range(len(coordinates) - 1):
        ponto_atual = coordinates[i]
        proximo_ponto = coordinates[i + 1]
        distancia_total += geodesic(ponto_atual, proximo_ponto).meters
    return round(distancia_total, 0)  # Arredonda para 0 casas decimais

# Função para extrair estilos do KML (LineStyle)
def extrair_estilos(root):
    estilos = {}
    for estilo in root.findall(".//{http://www.opengis.net/kml/2.2}Style"):
        style_id = estilo.get("id")
        # Extrai cor do LineStyle
        linestyle = estilo.find(".//{http://www.opengis.net/kml/2.2}LineStyle")
        if linestyle is not None:
            color_tag = linestyle.find(".//{http://www.opengis.net/kml/2.2}color")
            if color_tag is not None:
                kml_color = color_tag.text.strip()
                color = f"#{kml_color[6:8]}{kml_color[4:6]}{kml_color[2:4]}"
                estilos[style_id] = color
    return estilos

# Função para processar folders que contenham "LINK" no nome
def processar_folder_link(folder, estilos):
    distancia_folder = 0.0
    dados = []
    coordenadas_folder = []
    
    for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
        nome_placemark = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
        color = "blue"
        
        style_url = placemark.find(".//{http://www.opengis.net/kml/2.2}styleUrl")
        if style_url is not None:
            style_id = style_url.text.strip().lstrip("#")
            if style_id in estilos:
                color = estilos[style_id]
        
        for line_string in placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString"):
            coordinates = line_string.coordinates.text.strip().split()
            coordinates = [tuple(map(float, coord.split(',')[:2][::-1])) for coord in coordinates]
            
            distancia = calcular_distancia_linestring(coordinates)
            distancia_folder += distancia
            dados.append([nome_placemark, distancia])
            coordenadas_folder.append((nome_placemark, coordinates, color))
    
    return distancia_folder, dados, coordenadas_folder

# Função para buscar recursivamente por pastas "CTO'S"
def buscar_ctos(folder, ctos_processados=None):
    if ctos_processados is None:
        ctos_processados = set()  # Conjunto para rastrear pastas "CTO'S" já processadas
    
    ctos = []
    
    for subpasta in folder.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        nome_subpasta = subpasta.name.text if hasattr(subpasta, 'name') else "Subpasta Desconhecida"
        
        # Se a subpasta contiver "CTO'S" no nome e ainda não foi processada
        if "CTO'S" in nome_subpasta.upper() and nome_subpasta not in ctos_processados:
            ctos_processados.add(nome_subpasta)  # Marca a pasta como processada
            dados_cto = {"nome": nome_subpasta, "rotas": []}
            
            # Processa as rotas dentro da subpasta CTO'S
            rotas = subpasta.findall(".//{http://www.opengis.net/kml/2.2}Folder")
            for rota in rotas:
                nome_rota = rota.name.text if hasattr(rota, 'name') else "Rota Desconhecida"
                placemarks = rota.findall(".//{http://www.opengis.net/kml/2.2}Placemark")
                dados_cto["rotas"].append({
                    "nome_rota": nome_rota,
                    "quantidade_placemarks": len(placemarks)
                })
            
            ctos.append(dados_cto)
        
        # Busca recursivamente por mais pastas "CTO'S" dentro da subpasta atual
        ctos.extend(buscar_ctos(subpasta, ctos_processados))
    
    return ctos

# Função para processar pastas GPON e suas subpastas
def processar_gpon(root):
    dados_gpon = {}
    
    for folder in root.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        nome_folder = folder.name.text if hasattr(folder, 'name') else "Desconhecido"
        
        # Verifica se o nome da pasta contém "GPON"
        if "GPON" in nome_folder.upper():
            dados_gpon[nome_folder] = {"primeiro_nivel": []}
            
            # Coleta todas as subpastas do primeiro nível após a pasta GPON
            for subpasta in folder.findall("{http://www.opengis.net/kml/2.2}Folder"):
                nome_subpasta = subpasta.name.text if hasattr(subpasta, 'name') else "Subpasta Desconhecida"
                
                # Dados da subpasta do primeiro nível
                dados_subpasta = {"nome": nome_subpasta, "ctos": buscar_ctos(subpasta), "linestrings": []}
                
                # Processa as LineStrings dentro da subpasta
                for placemark in subpasta.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
                    for line_string in placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString"):
                        coordinates = line_string.coordinates.text.strip().split()
                        coordinates = [tuple(map(float, coord.split(',')[:2][::-1])) for coord in coordinates]
                        distancia = calcular_distancia_linestring(coordinates)
                        dados_subpasta["linestrings"].append((placemark.name.text if hasattr(placemark, 'name') else "Sem Nome", distancia))
                
                # Adiciona a subpasta do primeiro nível aos dados da pasta GPON
                dados_gpon[nome_folder]["primeiro_nivel"].append(dados_subpasta)
    
    return dados_gpon

# Função para processar o KML e calcular distâncias
def processar_kml(caminho_arquivo):
    with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
        root = parser.parse(arquivo).getroot()
    
    estilos = extrair_estilos(root)
    distancia_total = 0.0
    dados_por_pasta = {}
    coordenadas_por_pasta = {}
    cidades_coords = []
    
    for folder in root.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        nome_folder = folder.name.text if hasattr(folder, 'name') else "Desconhecido"
        
        # Processa pastas LINK
        if "LINK" in nome_folder.upper():
            distancia_folder, dados, coordenadas_folder = processar_folder_link(folder, estilos)
            distancia_total += distancia_folder
            if dados:
                dados_por_pasta[nome_folder] = (distancia_folder, dados)
                coordenadas_por_pasta[nome_folder] = coordenadas_folder
        
        # Processa pastas que contenham "CIDADES" no nome
        if "CIDADES" in nome_folder.upper():
            for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
                nome = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
                point = placemark.find(".//{http://www.opengis.net/kml/2.2}Point")
                if point is not None:
                    coords = point.coordinates.text.strip().split(',')
                    lon = float(coords[0])
                    lat = float(coords[1])
                    cidades_coords.append((nome, (lat, lon)))
    
    # Processa pastas GPON
    dados_gpon = processar_gpon(root)
    
    return distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords, dados_gpon

# Função para criar o dashboard GPON
def criar_dashboard_gpon(dados_gpon):
    
    # Inicializa listas para armazenar dados da tabela
    dados_tabela = []
    
    # Itera sobre todas as GPONs e suas subpastas
    for nome_gpon, dados in dados_gpon.items():
        if "primeiro_nivel" in dados:
            for subpasta in dados["primeiro_nivel"]:
                # Inicializa os totais para a subpasta atual
                total_rotas = 0
                total_placemarks = 0
                soma_distancia = 0.0
                
                # Coleta dados de Rotas e Placemarks
                if "ctos" in subpasta:
                    for cto in subpasta["ctos"]:
                        if "rotas" in cto:
                            total_rotas += len(cto["rotas"])
                            for rota in cto["rotas"]:
                                total_placemarks += rota["quantidade_placemarks"]
                
                # Calcula a soma das distâncias das LineStrings
                if "linestrings" in subpasta:
                    soma_distancia = sum(distancia for _, distancia in subpasta["linestrings"])
                
                # Adiciona os dados da subpasta à lista
                dados_tabela.append([
                    subpasta["nome"],  # Nome da subpasta
                    total_rotas,       # Quantidade de rotas
                    total_placemarks,  # Quantidade de placemarks
                    soma_distancia     # Soma das distâncias das LineStrings
                ])
    
    # Cria o DataFrame para a tabela
    df_tabela = pd.DataFrame(
        dados_tabela,
        columns=["POP", "Rotas", "CTO'S", "Fibra Ótica (metros)"]
    )
    
    # Adiciona a coluna ID
    df_tabela.insert(0, "ID", range(1, len(df_tabela) + 1))
    
    # Adiciona uma linha de total
    df_tabela.loc["Total"] = [
        "",  # ID (vazio para a linha de total)
        "Total",  # Subpasta
        df_tabela["Rotas"].sum(),
        df_tabela["CTO'S"].sum(),
        df_tabela["Fibra Ótica (metros)"].sum()
    ]
    
    # Define a coluna ID como índice do DataFrame
    df_tabela.set_index("ID", inplace=True)
    
    # Exibe a tabela
    st.write("### GPON - Análise Rotas, CTO'S, Fibra Ótica")
    st.dataframe(df_tabela)

# Função para criar uma tabela interativa com seleção de primeiro nível
def criar_tabela_interativa_gpon(dados_gpon):
    # Cria uma lista de opções para o selectbox (primeiro nível)
    opcoes_primeiro_nivel = []
    for nome_gpon, dados in dados_gpon.items():
        if "primeiro_nivel" in dados:
            for subpasta in dados["primeiro_nivel"]:
                opcoes_primeiro_nivel.append(subpasta["nome"])
    
    # Adiciona um selectbox para selecionar o primeiro nível
    selecionado = st.selectbox("Selecione o POP para análise:", opcoes_primeiro_nivel)
    
    # Encontra os dados correspondentes ao primeiro nível selecionado
    for nome_gpon, dados in dados_gpon.items():
        if "primeiro_nivel" in dados:
            for subpasta in dados["primeiro_nivel"]:
                if subpasta["nome"] == selecionado:
                    st.write(f"### Informações de: {selecionado}")
                    
                    # Inicializa listas para armazenar dados das tabelas
                    dados_tabela_rotas = []  # Tabela de Rotas e CTO's
                    dados_tabela_quantidade_rotas = []  # Tabela de Quantidade de Rotas por CTO
                    
                    # Coleta dados de Rotas e CTO's
                    if "ctos" in subpasta:
                        for cto in subpasta["ctos"]:
                            quantidade_rotas = 0
                            if "rotas" in cto:
                                for rota in cto["rotas"]:
                                    dados_tabela_rotas.append([
                                        cto["nome"],  # Nome do CTO
                                        rota["nome_rota"],  # Nome da Rota
                                        rota["quantidade_placemarks"]  # Quantidade de Placemarks
                                    ])
                                    quantidade_rotas += 1
                            
                            # Adiciona a quantidade de rotas por CTO
                            dados_tabela_quantidade_rotas.append([
                                cto["nome"],  # Nome do CTO
                                quantidade_rotas  # Quantidade de Rotas
                            ])
                    
                    # Cria o DataFrame para a tabela de Quantidade de Rotas por CTO
                    df_tabela_quantidade_rotas = pd.DataFrame(
                        dados_tabela_quantidade_rotas,
                        columns=["Projeto", "Rotas"]
                    )
                    
                    # Adiciona a coluna ID
                    df_tabela_quantidade_rotas.insert(0, "ID", range(1, len(df_tabela_quantidade_rotas) + 1))
                    
                    # Adiciona uma linha de total
                    total_rotas = df_tabela_quantidade_rotas["Rotas"].sum()
                    df_tabela_quantidade_rotas.loc["Total"] = ["", "Total", total_rotas]
                    
                    # Define a coluna ID como índice do DataFrame
                    df_tabela_quantidade_rotas.set_index("ID", inplace=True)
                    
                    # Exibe a tabela de Quantidade de Rotas por CTO
                    st.write("#### Quantidade de Rotas por projeto")
                    st.dataframe(df_tabela_quantidade_rotas)
                    
                    # Cria o DataFrame para a tabela de Rotas e CTO's
                    df_tabela_rotas = pd.DataFrame(
                        dados_tabela_rotas,
                        columns=["Projeto", "Rota", "CTO'S"]
                    )
                    
                    # Adiciona a coluna ID
                    df_tabela_rotas.insert(0, "ID", range(1, len(df_tabela_rotas) + 1))
                    
                    # Adiciona uma linha de total
                    total_placemarks = df_tabela_rotas["CTO'S"].sum()
                    df_tabela_rotas.loc["Total"] = ["", "Total", "", total_placemarks]
                    
                    # Define a coluna ID como índice do DataFrame
                    df_tabela_rotas.set_index("ID", inplace=True)
                    
                    # Exibe a tabela de Rotas e CTO's
                    st.write("#### Rotas e CTO's")
                    st.dataframe(df_tabela_rotas)


# Configuração do aplicativo Streamlit
st.title("Analisador de Projetos")
st.write("Este aplicativo analisa um arquivo no formato .kml e imprime informações bem dinâmicas e interativas sobre o projetos de fibra ótica")

# Upload do arquivo KML
uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    # Salva o arquivo temporariamente
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Processa o KML
    distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords, dados_gpon = processar_kml("temp.kml")
    
    # Adiciona LineStrings e marcadores ao mapa
    for nome_folder, coordenadas_folder in coordenadas_por_pasta.items():
        for nome_placemark, coordinates, color in coordenadas_folder:
            folium.PolyLine(
                coordinates,
                color=color,
                weight=3,
                opacity=0.7,
                tooltip=f"{nome_folder} - {nome_placemark}"
            ).add_to(mapa)
    
    for nome, coord in cidades_coords:
        folium.Marker(
            location=coord,
            icon=folium.Icon(icon="home", color="green"),
            popup=nome
        ).add_to(mapa)
    
    folium_static(mapa)
    
    # Exibe tabelas para pastas LINK
    st.subheader("Quantidade de Fibra Ótica projetada - LINK")
    dados_tabela_pastas = []
    
    # Dicionário para armazenar subtotais por pasta
    subtotais_pastas = {}
    
    for nome_folder, (distancia_folder, dados) in dados_por_pasta.items():
        subtotal_pasta = 0.0
        for linha in dados:
            dados_tabela_pastas.append([nome_folder, linha[0], linha[1]])
            subtotal_pasta += linha[1]
        
        # Armazena o subtotal da pasta
        subtotais_pastas[nome_folder] = subtotal_pasta
    
    # Adiciona as linhas de subtotal por pasta
    for nome_folder, subtotal in subtotais_pastas.items():
        dados_tabela_pastas.append([nome_folder, "Subtotal", subtotal])
    
    # Cria o DataFrame
    df_tabela_pastas = pd.DataFrame(
        dados_tabela_pastas,
        columns=["Pasta", "ROTAS LINK", "Distância (m)"]
    )
    
    # Adiciona a coluna ID
    df_tabela_pastas.insert(0, "ID", range(1, len(df_tabela_pastas) + 1))
    
    # Calcula o total geral
    total_distancia = df_tabela_pastas[df_tabela_pastas["ROTAS LINK"] != "Subtotal"]["Distância (m)"].sum()
    
    # Adiciona a linha de total geral
    df_tabela_pastas.loc["Total"] = ["", "Total", "", total_distancia]
    
    # Define a coluna ID como índice do DataFrame
    df_tabela_pastas.set_index("ID", inplace=True)
    
    # Exibe a tabela
    st.dataframe(df_tabela_pastas)
    
    # Exibe o dashboard GPON
    criar_dashboard_gpon(dados_gpon)
    
    # Exibe a tabela interativa
    criar_tabela_interativa_gpon(dados_gpon)  # Certifique-se de que dados_gpon está definido
