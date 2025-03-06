import streamlit as st
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
    
    # Obtém o nome da pasta
    nome_folder = folder.name.text if hasattr(folder, 'name') else ""
    if "LINK" in nome_folder.upper():
        st.subheader(f"Processando Folder: {nome_folder}")
        
        # Processa todas as LineStrings dentro da pasta
        for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
            for line_string in placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString"):
                coordinates = line_string.coordinates.text.strip().split()
                # Converter coordenadas para (latitude, longitude) e inverter a ordem
                coordinates = [tuple(map(float, coord.split(',')[:2][::-1])) for coord in coordinates]
                
                distancia = calcular_distancia_linestring(coordinates)
                distancia_folder += distancia
                st.write(f"Distância da LineString: {distancia:.2f} metros")
    
    return distancia_folder

# Função para processar o KML e calcular a distância das pastas "LINK"
def processar_kml(caminho_arquivo):
    with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
        root = parser.parse(arquivo).getroot()
    
    distancia_total = 0.0
    
    # Processa todas as pastas do KML
    for folder in root.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        distancia_total += processar_folder_link(folder)
    
    return distancia_total

# Configuração do aplicativo Streamlit
st.title("Calculadora de Distância de Arquivos KML")
st.write("Este aplicativo calcula a distância total das LineStrings dentro de Folders contendo 'LINK' no nome.")

# Upload do arquivo KML
uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    # Salva o arquivo temporariamente para processamento
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Processa o arquivo KML
    distancia_total = processar_kml("temp.kml")
    
    # Exibe a distância total
    st.success(f"Distância total das Folders 'LINK': {distancia_total:.2f} metros")
