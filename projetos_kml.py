import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from pykml import parser
from geopy.distance import geodesic

def calcular_distancia_linestring(coordinates):
    distancia_total = 0.0
    for i in range(len(coordinates) - 1):
        ponto_atual = coordinates[i]
        proximo_ponto = coordinates[i + 1]
        distancia_total += geodesic(ponto_atual, proximo_ponto).meters
    return distancia_total

def extrair_estilos(root):
    estilos = {}
    for estilo in root.findall(".//{http://www.opengis.net/kml/2.2}Style"):
        style_id = estilo.get("id")
        linestyle = estilo.find(".//{http://www.opengis.net/kml/2.2}LineStyle")
        if linestyle is not None:
            color_tag = linestyle.find(".//{http://www.opengis.net/kml/2.2}color")
            if color_tag is not None:
                kml_color = color_tag.text.strip()
                # Converte ABGR para RRGGBB e extrai alpha
                if len(kml_color) == 8:
                    alpha = kml_color[0:2]
                    rr = kml_color[6:8]
                    gg = kml_color[4:6]
                    bb = kml_color[2:4]
                    color = f"#{rr}{gg}{bb}"
                    estilos[style_id] = color
                    st.write(f"Estilo encontrado: ID={style_id}, Cor KML={kml_color}, Cor convertida={color}")  # Log para depuração
                else:
                    st.error(f"Formato de cor inválido para o estilo {style_id}: {kml_color}")
    return estilos

def processar_folder_link(folder, estilos):
    distancia_folder = 0.0
    dados = []
    coordenadas_folder = []
    
    nome_folder = folder.name.text if hasattr(folder, 'name') else "Desconhecido"
    if "LINK" in nome_folder.upper():
        for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
            nome_placemark = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
            color = "blue"  # Cor padrão se não encontrar o estilo
            style_url = placemark.find(".//{http://www.opengis.net/kml/2.2}styleUrl")
            if style_url is not None:
                style_id = style_url.text.strip().lstrip("#")
                if style_id in estilos:
                    color = estilos[style_id]
                else:
                    st.warning(f"Estilo {style_id} não encontrado para o Placemark {nome_placemark}.")
            
            for line_string in placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString"):
                coordinates = line_string.coordinates.text.strip().split()
                coordinates = [tuple(map(float, coord.split(',')[:2][::-1])) for coord in coordinates]
                distancia = calcular_distancia_linestring(coordinates)
                distancia_folder += distancia
                dados.append([nome_placemark, distancia])
                coordenadas_folder.append((nome_placemark, coordinates, color))
    
    return nome_folder, distancia_folder, dados, coordenadas_folder

def processar_kml(caminho_arquivo):
    with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
        root = parser.parse(arquivo).getroot()
    
    estilos = extrair_estilos(root)
    distancia_total = 0.0
    dados_por_pasta = {}
    coordenadas_por_pasta = {}
    
    for folder in root.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        nome_folder, distancia_folder, dados, coordenadas_folder = processar_folder_link(folder, estilos)
        distancia_total += distancia_folder
        if dados:
            dados_por_pasta[nome_folder] = (distancia_folder, dados)
            coordenadas_por_pasta[nome_folder] = coordenadas_folder
    
    return distancia_total, dados_por_pasta, coordenadas_por_pasta

st.title("Calculadora de Distância de Arquivos KML")
st.write("Este aplicativo calcula a distância total das LineStrings dentro de Folders contendo 'LINK' no nome e exibe os dados organizados por pasta.")

uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    distancia_total, dados_por_pasta, coordenadas_por_pasta = processar_kml("temp.kml")
    
    for nome_folder, (distancia_folder, dados) in dados_por_pasta.items():
        st.subheader(f"Folder: {nome_folder}")
        df = pd.DataFrame(dados, columns=["LineString", "Distância (m)"])
        st.dataframe(df)
        st.write(f"**Soma da distância no folder '{nome_folder}': {distancia_folder:.2f} metros**")
        st.markdown("---")
    
    st.subheader("Mapa das LineStrings")
    mapa = folium.Map(location=[-15.7801, -47.9292], zoom_start=5, tiles="Esri WorldImagery")
    
    for nome_folder, coordenadas_folder in coordenadas_por_pasta.items():
        for nome_placemark, coordinates, color in coordenadas_folder:
            folium.PolyLine(
                coordinates,
                color=color,
                weight=3,
                opacity=0.7,  # Opacidade fixa, mas pode ser ajustada com alpha do KML se necessário
                tooltip=f"{nome_folder} - {nome_placemark}"
            ).add_to(mapa)
    
    folium_static(mapa)
    
    st.success(f"Distância total das Folders 'LINK': {distancia_total:.2f} metros")
