import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from pykml import parser
from geopy.distance import geodesic

# Função para calcular a distância total de uma LineString em metros
def calcular_distancia_linestring(coordinates):
    distancia_total = 0.0
    for i in range(len(coordinates) - 1):
        ponto_atual = coordinates[i]
        proximo_ponto = coordinates[i + 1]
        distancia_total += geodesic(ponto_atual, proximo_ponto).meters
    return distancia_total

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
                dados_subpasta = {"nome": nome_subpasta, "ctos": buscar_ctos(subpasta)}
                
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

# Configuração do aplicativo Streamlit
st.title("Calculadora de Distância de Arquivos KML")
st.write("Este aplicativo calcula a distância total das LineStrings dentro de Folders contendo 'LINK' no nome e exibe os dados organizados por pasta.")

uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords, dados_gpon = processar_kml("temp.kml")

    # Exibe tabelas para pastas LINK
    for nome_folder, (distancia_folder, dados) in dados_por_pasta.items():
        st.subheader(f"Folder: {nome_folder}")
        df = pd.DataFrame(dados, columns=["LineString", "Distância (m)"])
        st.dataframe(df)
        st.write(f"**Soma da distância no folder '{nome_folder}': {distancia_folder:.2f} metros**")
        st.markdown("---")
    
    # Cria o mapa
    st.subheader("Mapa das LineStrings e Cidades")
    mapa = folium.Map(location=[-15.7801, -47.9292], zoom_start=5, tiles="Esri WorldImagery")
    
    # Adiciona LineStrings
    for nome_folder, coordenadas_folder in coordenadas_por_pasta.items():
        for nome_placemark, coordinates, color in coordenadas_folder:
            folium.PolyLine(
                coordinates,
                color=color,
                weight=3,
                opacity=0.7,
                tooltip=f"{nome_folder} - {nome_placemark}"
            ).add_to(mapa)
    
    # Adiciona marcadores para CIDADES (com ícone de casa)
    for nome, coord in cidades_coords:
        folium.Marker(
            location=coord,
            icon=folium.Icon(icon="home", color="green"),  # Ícone de casa
            popup=nome
        ).add_to(mapa)
    
    folium_static(mapa)
    
    st.success(f"Distância total das Folders 'LINK': {distancia_total:.2f} metros")
    
    # Exibe o dashboard para pastas GPON
    st.subheader("Dashboard GPON")
    for nome_gpon, dados in dados_gpon.items():
        st.write(f"### {nome_gpon}")
        
        # Verifica se a chave "primeiro_nivel" existe nos dados
        if "primeiro_nivel" in dados:
            for subpasta in dados["primeiro_nivel"]:
                st.write(f"**Subpasta do Primeiro Nível:** {subpasta['nome']}")
                
                # Verifica se a chave "ctos" existe na subpasta
                if "ctos" in subpasta:
                    for cto in subpasta["ctos"]:
                        st.write(f"**CTO'S:** {cto['nome']}")
                        
                        # Verifica se a chave "rotas" existe no CTO
                        if "rotas" in cto:
                            for rota in cto["rotas"]:
                                st.write(f"- Rota: {rota['nome_rota']}")
                                st.write(f"  - Placemarks: {rota['quantidade_placemarks']}")
