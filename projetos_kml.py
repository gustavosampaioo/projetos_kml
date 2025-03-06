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

# Função para processar folders que contenham "LINK" no nome
def processar_folder_link(folder):
    distancia_folder = 0.0
    dados = []
    coordenadas_folder = []
    
    # Obtém o nome da pasta
    nome_folder = folder.name.text if hasattr(folder, 'name') else "Desconhecido"
    if "LINK" in nome_folder.upper():
        
        # Processa todas as LineStrings dentro da pasta
        for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
            nome_placemark = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
            color = "blue"  # Cor padrão
            
            # Verifica se há cor definida no estilo do Placemark
            style = placemark.findall(".//{http://www.opengis.net/kml/2.2}Style")
            if style:
                for s in style:
                    linestyle = s.find(".//{http://www.opengis.net/kml/2.2}LineStyle")
                    if linestyle is not None:
                        color_tag = linestyle.find(".//{http://www.opengis.net/kml/2.2}color")
                        if color_tag is not None:
                            kml_color = color_tag.text.strip()
                            color = f"#{kml_color[6:8]}{kml_color[4:6]}{kml_color[2:4]}"  # Converte de ABGR para RGB
            
            for line_string in placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString"):
                coordinates = line_string.coordinates.text.strip().split()
                # Converter coordenadas para (latitude, longitude) e inverter a ordem
                coordinates = [tuple(map(float, coord.split(',')[:2][::-1])) for coord in coordinates]
                
                distancia = calcular_distancia_linestring(coordinates)
                distancia_folder += distancia
                dados.append([nome_placemark, distancia])
                coordenadas_folder.append((nome_placemark, coordinates, color))
    
    return nome_folder, distancia_folder, dados, coordenadas_folder

# Função para processar o KML e calcular a distância das pastas "LINK"
def processar_kml(caminho_arquivo):
    with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
        root = parser.parse(arquivo).getroot()
    
    distancia_total = 0.0
    dados_por_pasta = {}
    coordenadas_por_pasta = {}
    
    # Processa todas as pastas do KML
    for folder in root.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        nome_folder, distancia_folder, dados, coordenadas_folder = processar_folder_link(folder)
        distancia_total += distancia_folder
        if dados:
            dados_por_pasta[nome_folder] = (distancia_folder, dados)
            coordenadas_por_pasta[nome_folder] = coordenadas_folder
    
    return distancia_total, dados_por_pasta, coordenadas_por_pasta

# Configuração do aplicativo Streamlit
st.title("Calculadora de Distância de Arquivos KML")
st.write("Este aplicativo calcula a distância total das LineStrings dentro de Folders contendo 'LINK' no nome e exibe os dados organizados por pasta.")

# Upload do arquivo KML
uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    # Salva o arquivo temporariamente para processamento
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Processa o arquivo KML
    distancia_total, dados_por_pasta, coordenadas_por_pasta = processar_kml("temp.kml")
    
    # Exibe tabelas individuais para cada folder
    for nome_folder, (distancia_folder, dados) in dados_por_pasta.items():
        st.subheader(f"Folder: {nome_folder}")
        df = pd.DataFrame(dados, columns=["LineString", "Distância (m)"])
        st.dataframe(df)
        st.write(f"**Soma da distância no folder '{nome_folder}': {distancia_folder:.2f} metros**")
        st.markdown("---")
    
    # Criar um mapa com Folium
    st.subheader("Mapa das LineStrings")
    mapa = folium.Map(location=[-15.7801, -47.9292], zoom_start=5, tiles="Esri WorldImagery")
    
    for nome_folder, coordenadas_folder in coordenadas_por_pasta.items():
        for nome_placemark, coordinates, color in coordenadas_folder:
            folium.PolyLine(
                coordinates,
                color=color,
                weight=3,
                opacity=0.7,
                tooltip=f"{nome_folder} - {nome_placemark}"
            ).add_to(mapa)
    
    # Exibir o mapa no Streamlit
    folium_static(mapa)
    
    # Exibe a distância total
    st.success(f"Distância total das Folders 'LINK': {distancia_total:.2f} metros")
