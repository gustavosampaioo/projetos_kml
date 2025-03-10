import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from pykml import parser
from geopy.distance import geodesic
import plotly.express as px
from folium.features import CustomIcon
from folium import Icon

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


def processar_folder_link(folder, estilos):
    distancia_folder = 0.0
    dados = []
    coordenadas_folder = []
    dados_em_andamento = []
    dados_concluido = []
    
    # Verifica se o nome da pasta contém "LINK PARCEIROS"
    nome_folder = folder.name.text if hasattr(folder, 'name') else "Desconhecido"
    is_link_parceiros = "LINK PARCEIROS" in nome_folder.upper()
    
    # Define a cor com base no nome da pasta
    if is_link_parceiros:
        color = "red"  # Cor vermelha para "LINK PARCEIROS"
    elif "AMARELO" in nome_folder.upper():
        color = "yellow"
    elif "VERDE" in nome_folder.upper():
        color = "green"
    else:
        color = "blue"  # Cor padrão para "LINK"
    
    # Se for "LINK PARCEIROS", processa diretamente as LineString
    if is_link_parceiros:
        for placemark in folder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
            nome_placemark = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
            
            for line_string in placemark.findall(".//{http://www.opengis.net/kml/2.2}LineString"):
                coordinates = line_string.coordinates.text.strip().split()
                coordinates = [tuple(map(float, coord.split(',')[:2][::-1])) for coord in coordinates]
                
                distancia = calcular_distancia_linestring(coordinates)
                distancia_folder += distancia
                
                # Adiciona as informações às listas correspondentes
                dados.append([nome_folder, nome_placemark, distancia])  # Inclui o nome da pasta
                coordenadas_folder.append((nome_placemark, coordinates, color, "solid"))  # Sólido para "LINK PARCEIROS"
        
        return distancia_folder, dados, coordenadas_folder, [], [], is_link_parceiros
    
    # Caso contrário, processa como pasta "LINK" normal
    for subfolder in folder.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        subfolder_name = subfolder.name.text if hasattr(subfolder, 'name') else "Subpasta Desconhecida"
        
        # Verifica se a subpasta é "EM ANDAMENTO" ou "CONCLUÍDO"
        is_em_andamento = "EM ANDAMENTO" in subfolder_name.upper()
        is_concluido = "CONCLUÍDO" in subfolder_name.upper()
        
        # Processa as LineString dentro da subpasta
        for placemark in subfolder.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
            nome_placemark = placemark.name.text if hasattr(placemark, 'name') else "Sem Nome"
            
            # Usa a cor definida no estilo
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
                
                # Adiciona as informações às listas correspondentes
                if is_em_andamento:
                    dados_em_andamento.append([nome_folder, nome_placemark, distancia])
                    coordenadas_folder.append((nome_placemark, coordinates, color, "dashed"))  # Tracejado para "EM ANDAMENTO"
                elif is_concluido:
                    dados_concluido.append([nome_folder, nome_placemark, distancia])
                    coordenadas_folder.append((nome_placemark, coordinates, color, "solid"))  # Sólido para "CONCLUÍDO"
                else:
                    dados.append([nome_folder, nome_placemark, distancia])
                    coordenadas_folder.append((nome_placemark, coordinates, color, "solid"))  # Sólido para outras pastas
    
    return distancia_folder, dados, coordenadas_folder, dados_em_andamento, dados_concluido, is_link_parceiros



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
    dados_em_andamento = []
    dados_concluido = []
    dados_link_parceiros = []  # Lista para armazenar dados dos LINK PARCEIROS
    dados_gpon = {}
    
    for folder in root.findall(".//{http://www.opengis.net/kml/2.2}Folder"):
        nome_folder = folder.name.text if hasattr(folder, 'name') else "Desconhecido"
        
        # Processa pastas LINK e LINK PARCEIROS
        if "LINK" in nome_folder.upper():
            distancia_folder, dados, coordenadas_folder, em_andamento, concluido, is_link_parceiros = processar_folder_link(folder, estilos)
            distancia_total += distancia_folder
            
            # Separa os dados dos "LINK PARCEIROS" dos dados da pasta "LINK"
            if is_link_parceiros:
                dados_link_parceiros.extend(dados)
                coordenadas_por_pasta[nome_folder] = coordenadas_folder
            else:
                dados_por_pasta[nome_folder] = (distancia_folder, dados)
                coordenadas_por_pasta[nome_folder] = coordenadas_folder
                dados_em_andamento.extend(em_andamento)
                dados_concluido.extend(concluido)
        
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
    
    return distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords, dados_gpon, dados_em_andamento, dados_concluido, dados_link_parceiros

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
    opcoes_primeiro_nivel = ["TODAS"]  # Adiciona a opção "TODAS" no início da lista
    for nome_gpon, dados in dados_gpon.items():
        if "primeiro_nivel" in dados:
            for subpasta in dados["primeiro_nivel"]:
                opcoes_primeiro_nivel.append(subpasta["nome"])
    
    # Adiciona um selectbox para selecionar o primeiro nível
    selecionado = st.selectbox("Selecione o POP para análise:", opcoes_primeiro_nivel)
    
    # Verifica se a opção selecionada é "TODAS"
    if selecionado == "TODAS":
        st.write("### Informações de TODOS os POPs")
        
        # Inicializa listas para armazenar dados das tabelas
        dados_tabela_rotas = []  # Tabela de Rotas e CTO's
        dados_tabela_quantidade_rotas = []  # Tabela de Quantidade de Rotas por CTO
        
        # Itera sobre todas as GPONs e suas subpastas
        for nome_gpon, dados in dados_gpon.items():
            if "primeiro_nivel" in dados:
                for subpasta in dados["primeiro_nivel"]:
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
    
    else:
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

#verificar codigo
def calcular_porcentagem_concluida(dados_por_pasta, dados_concluido):
    porcentagens = {}
    
    # Verificação dos dados
    print("Dados por pasta:", dados_por_pasta)
    print("Dados concluídos:", dados_concluido)
   
    # Itera sobre as pastas e calcula a porcentagem concluída
    for nome_folder, (distancia_total, _) in dados_por_pasta.items():
        # Filtra os dados concluídos para a pasta atual
        distancia_concluida = sum(linha[2] for linha in dados_concluido if linha[0] == nome_folder)
        
        # Verifica se a distância total é maior que zero para evitar divisão por zero
        if distancia_total > 0:
            porcentagem = (distancia_concluida / distancia_total) * 100
        else:
            porcentagem = 0.0
        
        # Armazena a porcentagem no dicionário
        porcentagens[nome_folder] = porcentagem
    
    return porcentagens

# Função para criar o gráfico de porcentagem concluída
def criar_grafico_porcentagem_concluida(porcentagens):
    # Cria um DataFrame a partir do dicionário de porcentagens
    df_porcentagens = pd.DataFrame(list(porcentagens.items()), columns=["Pasta", "Porcentagem Concluída"])
    
    # Cria o gráfico de barras
    fig = px.bar(
        df_porcentagens,
        x="Pasta",
        y="Porcentagem Concluída",
        title="Porcentagem Concluída por Pasta",
        labels={"Porcentagem Concluída": "Porcentagem Concluída (%)"},
        text_auto=True  # Exibe os valores nas barras
    )
    
    # Ajusta o layout do gráfico
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis_title="Pasta",
        yaxis_title="Porcentagem Concluída (%)",
        yaxis_range=[0, 100]  # Define o limite do eixo Y de 0% a 100%
    )
    
    return fig


# Configuração do aplicativo Streamlit
st.title("Analisador de Projetos")
st.write("Este aplicativo analisa um arquivo no formato .kml e imprime informações bem dinâmicas e interativas sobre o projetos de fibra ótica")

# Upload do arquivo KML
uploaded_file = st.file_uploader("Carregue um arquivo KML", type=["kml"])

if uploaded_file is not None:
    # Salva o arquivo temporariamente
    with open("temp.kml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Processa o KML (desempacota todos os 8 valores retornados)
    distancia_total, dados_por_pasta, coordenadas_por_pasta, cidades_coords, dados_gpon, dados_em_andamento, dados_concluido, dados_link_parceiros = processar_kml("temp.kml")
    
    # Exibe o mapa e outras informações
    st.subheader("Mapa do Link entre Cidades")
    
    # Cria o mapa Folium
    mapa = folium.Map(location=[-5.0892, -42.8016], zoom_start=5, tiles="Esri WorldImagery")
    
    # Adiciona LineStrings e marcadores ao mapa
    for nome_folder, coordenadas_folder in coordenadas_por_pasta.items():
        for nome_placemark, coordinates, color, line_style in coordenadas_folder:
            # Calcula a distância da LineString
            distancia = calcular_distancia_linestring(coordinates)
            
            # Define o estilo da linha
            if line_style == "dashed":
                dash_array = "10, 10"  # Tracejado mais perceptível
                weight = 4  # Espessura maior para destacar
                opacity = 1.0  # Opacidade total (sem linha de fundo)
            else:
                dash_array = None  # Linha sólida
                weight = 3  # Espessura padrão
                opacity = 0.7  # Opacidade padrão
            
            # Adiciona a LineString ao mapa
            folium.PolyLine(
                coordinates,
                color=color,  # Cor da linha
                weight=weight,  # Espessura da linha
                opacity=opacity,  # Opacidade da linha
                dash_array=dash_array,  # Aplica o tracejado apenas para "EM ANDAMENTO"
                tooltip=f"{nome_folder} - {nome_placemark} | Distância: {distancia} metros"
            ).add_to(mapa)
    
    # Adiciona marcadores das cidades ao mapa com ícone azul padrão redimensionado
    for nome_cidade, coords in cidades_coords:
        casa_icon = CustomIcon(
            icon_image="https://fontetelecom.com.br/infraestrutura/assets/img/logo/logo-1.png",  # URL de um ícone de casa
            icon_size=(40, 20)  # Tamanho do ícone (largura, altura)
        )
        
        folium.Marker(
            location=coords,
            tooltip=nome_cidade,
            icon=casa_icon  # Usa o ícone personalizado
        ).add_to(mapa)
    
    # Exibe o mapa no Streamlit
    folium_static(mapa)
    
    # Exibe tabela para "LINK PARCEIROS"
    if dados_link_parceiros:
        st.subheader("ROTAS LINK PARCEIROS")
        
        # Cria o DataFrame para a tabela dos "LINK PARCEIROS"
        df_link_parceiros = pd.DataFrame(
            dados_link_parceiros,
            columns=["Pasta", "Rota", "Distância (m)"]
        )
        
        # Adiciona a coluna ID
        df_link_parceiros.insert(0, "ID", range(1, len(df_link_parceiros) + 1))
        
        # Calcula o subtotal por pasta
        subtotal_por_pasta = df_link_parceiros.groupby("Pasta")["Distância (m)"].sum().reset_index()
        subtotal_por_pasta.columns = ["Pasta", "Subtotal"]
        
        # Cria uma lista para armazenar as linhas da tabela
        dados_tabela_link_parceiros = []
        
        # Adiciona todas as rotas primeiro
        for _, rota in df_link_parceiros.iterrows():
            dados_tabela_link_parceiros.append([rota["ID"], rota["Pasta"], rota["Rota"], rota["Distância (m)"]])
        
        # Adiciona os subtotais no final
        for _, subtotal in subtotal_por_pasta.iterrows():
            dados_tabela_link_parceiros.append(["", subtotal["Pasta"], "Subtotal", subtotal["Subtotal"]])
        
        # Calcula o total geral
        total_geral = df_link_parceiros["Distância (m)"].sum()
        
        # Adiciona a linha de total geral
        dados_tabela_link_parceiros.append(["", "Total", "", total_geral])
        
        # Cria o DataFrame final
        df_tabela_final = pd.DataFrame(
            dados_tabela_link_parceiros,
            columns=["ID", "Pasta", "Rota", "Distância (m)"]
        )
        
        # Define a coluna ID como índice do DataFrame
        df_tabela_final.set_index("ID", inplace=True)
        
        # Exibe a tabela
        st.dataframe(df_tabela_final)
    
    # Exibe tabelas para pastas LINK
    st.subheader("Quantidade de Fibra Ótica projetada - LINK")
    dados_tabela_pastas = []
    
    # Dicionário para armazenar subtotais por pasta
    subtotais_pastas = {}
    
    for nome_folder, (distancia_folder, dados) in dados_por_pasta.items():
        subtotal_pasta = 0.0
        for linha in dados:
            dados_tabela_pastas.append([nome_folder, linha[1], linha[2]])
            subtotal_pasta += linha[2]
        
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


    #verificar codigo
    # Adiciona a funcionalidade ao Streamlit
    if uploaded_file is not None:

        # Calcula a porcentagem concluída por pasta
        porcentagens_concluidas = calcular_porcentagem_concluida(dados_por_pasta, dados_concluido)
    
        # Cria o gráfico de porcentagem concluída
        grafico_porcentagem = criar_grafico_porcentagem_concluida(porcentagens_concluidas)
    
        # Exibe o gráfico no Streamlit
        st.subheader("Porcentagem Concluída por Pasta")
        st.plotly_chart(grafico_porcentagem)
    #até aqui

    # Exibe tabelas para pastas "EM ANDAMENTO" e "CONCLUÍDO"
    if dados_em_andamento or dados_concluido:
        st.subheader("Status das Rotas - LINK")
        
        # Tabela para "EM ANDAMENTO"
        if dados_em_andamento:
            st.write("#### Rotas em Andamento")
            df_em_andamento = pd.DataFrame(
                dados_em_andamento,
                columns=["Pasta", "Rota", "Distância (m)"]
            )
            df_em_andamento.insert(0, "ID", range(1, len(df_em_andamento) + 1))
            
            # Calcula o subtotal por pasta
            subtotal_em_andamento = df_em_andamento.groupby("Pasta")["Distância (m)"].sum().reset_index()
            subtotal_em_andamento.columns = ["Pasta", "Subtotal"]
            
            # Cria uma lista para armazenar as linhas da tabela
            dados_tabela_em_andamento = []
            
            # Adiciona todas as rotas primeiro
            for _, rota in df_em_andamento.iterrows():
                dados_tabela_em_andamento.append([rota["ID"], rota["Pasta"], rota["Rota"], rota["Distância (m)"]])
            
            # Adiciona os subtotais no final
            for _, subtotal in subtotal_em_andamento.iterrows():
                dados_tabela_em_andamento.append(["", subtotal["Pasta"], "Subtotal", subtotal["Subtotal"]])
            
            # Calcula o total geral
            total_em_andamento = df_em_andamento["Distância (m)"].sum()
            
            # Adiciona a linha de total geral
            dados_tabela_em_andamento.append(["", "Total", "", total_em_andamento])
            
            # Cria o DataFrame final
            df_tabela_final_em_andamento = pd.DataFrame(
                dados_tabela_em_andamento,
                columns=["ID", "Pasta", "Rota", "Distância (m)"]
            )
            
            # Define a coluna ID como índice do DataFrame
            df_tabela_final_em_andamento.set_index("ID", inplace=True)
            
            # Exibe a tabela
            st.dataframe(df_tabela_final_em_andamento)
        
        # Tabela para "CONCLUÍDO"
        if dados_concluido:
            st.write("#### Rotas Concluídas")
            df_concluido = pd.DataFrame(
                dados_concluido,
                columns=["Pasta", "Rota", "Distância (m)"]
            )
            df_concluido.insert(0, "ID", range(1, len(df_concluido) + 1))
            
            # Calcula o subtotal por pasta
            subtotal_concluido = df_concluido.groupby("Pasta")["Distância (m)"].sum().reset_index()
            subtotal_concluido.columns = ["Pasta", "Subtotal"]
            
            # Cria uma lista para armazenar as linhas da tabela
            dados_tabela_concluido = []
            
            # Adiciona todas as rotas primeiro
            for _, rota in df_concluido.iterrows():
                dados_tabela_concluido.append([rota["ID"], rota["Pasta"], rota["Rota"], rota["Distância (m)"]])
            
            # Adiciona os subtotais no final
            for _, subtotal in subtotal_concluido.iterrows():
                dados_tabela_concluido.append(["", subtotal["Pasta"], "Subtotal", subtotal["Subtotal"]])
            
            # Calcula o total geral
            total_concluido = df_concluido["Distância (m)"].sum()
            
            # Adiciona a linha de total geral
            dados_tabela_concluido.append(["", "Total", "", total_concluido])
            
            # Cria o DataFrame final
            df_tabela_final_concluido = pd.DataFrame(
                dados_tabela_concluido,
                columns=["ID", "Pasta", "Rota", "Distância (m)"]
            )
            
            # Define a coluna ID como índice do DataFrame
            df_tabela_final_concluido.set_index("ID", inplace=True)
            
            # Exibe a tabela
            st.dataframe(df_tabela_final_concluido)
    
    # Exibe o dashboard GPON
    criar_dashboard_gpon(dados_gpon)
    
    # Exibe a tabela interativa
    criar_tabela_interativa_gpon(dados_gpon)
