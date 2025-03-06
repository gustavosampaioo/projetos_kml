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

# Função para extrair estilos do KML (LineStyle e IconStyle)
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
        # Extrai cor do IconStyle
        iconstyle = estilo.find(".//{http://www.opengis.net/kml/2.2}IconStyle")
        if iconstyle is not None:
            color_tag = iconstyle.find(".//{http://www.opengis.net/kml/2.2}color")
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
        
        # Processa pasta CIDADES
        elif nome_folder.upper() == "CIDADES":
            for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
                nome = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
                point = placemark.find(".//{http://www.opengis.net/kml/2.2}Point")
                if point is not None:
                    coords = point.coordinates.text.strip().split(',')
                    lon = float(coords[0])
                    lat = float(coords[1])
                    color = "blue"
                    
                    style_url = placemark.find(".//{http://www.opengis.net/kml/2.2}styleUrl")
                    if style_url is not None:
                        style_id = style_url.text.strip().lstrip("#")
                        if style_id in estilos:
                            color = estilos[style_id]
                    
                    cidades_coords.append((nome, (lat, lon), color))
    
    return distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords

# Configuração do aplicativo Streamlit
st.title("Calculadora de Distância de Arquivos KML")
st.write("Este aplicativo calcula a distância total das LineStrings dentro de Folders contendo 'LINK' no nome e exibe os dados organizados por pasta.")

uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords = processar_kml("temp.kml")

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
    
    # Adiciona marcadores para CIDADES
    for nome, coord, color in cidades_coords:
        folium.CircleMarker(
            location=coord,
            radius=5,
            fill=True,
            color=color,
            fill_color=color,
            fill_opacity=1,
            popup=nome
        ).add_to(mapa)
    
    folium_static(mapa)
    
    st.success(f"Distância total das Folders 'LINK': {distancia_total:.2f} metros")
