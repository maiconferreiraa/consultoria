import os
from flask import Flask, render_template, request, redirect, url_for, make_response, session
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
# from weasyprint import HTML  # COMENTADO: Causa falha no Vercel
from datetime import datetime
from functools import wraps
import re
import requests  # NOVO: Necessário para chamar a API de PDF
import json # Adicionado para manipulação de JSON

# --- CONFIGURAÇÃO INICIAL E SECRET KEY ---
app = Flask(__name__)
# CHAVE SECRETA É OBRIGATÓRIA PARA USAR SESSÕES (necessário para o login)
app.secret_key = os.environ.get('SECRET_KEY', 'SUA_CHAVE_SECRETA_MUITO_LONGA_E_COMPLEXA')
USER_SESSION_KEY = 'user_id'

# --- CONFIGURAÇÃO DA API DE PDF (NOVO SERVIÇO: pdfgeneratorapi.com) ---
PDF_API_URL = os.environ.get('PDF_API_URL', 'https://us1.pdfgeneratorapi.com/api/v4/documents/generate') 
# IMPORTANTE: Este é o token Bearer, diferente da chave anterior.
PDF_API_TOKEN = os.environ.get('PDF_API_TOKEN', 'SEU_TOKEN_BEARER_AQUI') 

# Variáveis para os IDs dos templates que você vai carregar no painel da API:
MEMORIAL_TEMPLATE_ID = os.environ.get('MEMORIAL_TEMPLATE_ID', 'memorial_id_exemplo')
TECNICO_TEMPLATE_ID = os.environ.get('TECNICO_TEMPLATE_ID', 'tecnico_id_exemplo')
LEVANTAMENTO_TEMPLATE_ID = os.environ.get('LEVANTAMENTO_TEMPLATE_ID', 'levantamento_id_exemplo')

# Certifique-se de que o arquivo firebase_key.json está na mesma pasta
if os.path.exists("firebase_key.json"):
    cred = credentials.Certificate("firebase_key.json")
else:
    # Fallback para o Render (caso use Secret Files)
    cred = credentials.Certificate("/etc/secrets/firebase_key.json")

firebase_admin.initialize_app(cred)
db = firestore.client()

class DictObj:
    def __init__(self, data, id=None):
        self.id = id
        if data:
            for key, value in data.items():
                setattr(self, key, value)

# --- CONFIGURAÇÃO DE CORES SUVINIL & CORAL (PALETA AMPLIADA E ESSENCIAL) ---
# LISTA EXPANDIDA COM OS NOMES E CÓDIGOS HEX MAIS POPULARES E ESSENCIAIS.
# HEX codes são aproximados e baseados em referências populares da indústria.
SUVINIL_CORAL_COLORS = {
    # Cores Neutras / Clássicas Suvinil (EXPANDIDO)
    "Branco Neve Suvinil": "#F0F0F0",
    "Gelo Suvinil": "#F4F4F4",
    "Papiro Suvinil": "#F0EDE6",
    "Off White Suvinil": "#F5F5F5",
    "Creme Suvinil": "#FFFDD0",
    "Algodão Egípcio Suvinil": "#EBEAE3",
    "Palha Suvinil": "#FAF0C9",
    "Broto de Feijão Suvinil": "#C2B8A3",
    
    # Tons de Cinza Suvinil (EXPANDIDO)
    "Cinza Elefante Suvinil": "#B0B0B0",
    "Crômio Suvinil": "#A9A9A9",
    "Prata Suvinil": "#CCD1D1",
    "Névoa Intensa Suvinil": "#D3D7D2",
    "Cinza Urbano Suvinil": "#5E5E5E",
    "Nanquim Suvinil": "#262626",
    "Cinza Asfalto Suvinil": "#4C5357",
    "Preto Absoluto Suvinil": "#0A0A0A",
    
    # Cores Quentes Suvinil
    "Amarelo Sol Suvinil": "#FFD700",
    "Luz de Inverno Suvinil": "#F5E6B5",
    "Amarelo Real Suvinil": "#FAD32B",
    "Laranja Outonal Suvinil": "#F0A300",
    "Terra Roxa Suvinil": "#A0522D",
    "Bege Areia Suvinil": "#D8C5A5",
    "Valentino Suvinil": "#DC143C", # Vermelho/Rosa Vibrante
    
    # Cores Frias Suvinil
    "Verde Piscina Suvinil": "#00A99D",
    "Azul Profundo Suvinil": "#000080",
    "Azul Celeste Suvinil": "#56A0C5",
    "Céu Sereno Suvinil": "#87CEEB",
    "Rosa Açaí Suvinil": "#E0B0FF",
    "Rosa Pastel Suvinil": "#FFB6C1",
    "Chá de Rosas Suvinil": "#D8BFD8",
    
    # Cores Coral (EXPANDIDO)
    "Branco Coton Coral": "#F8F8FF",
    "Ovelha Coral": "#F9F6F0",
    "Toque de Seda Coral": "#EBE7DB",
    "Lagoa Gélida Coral": "#E7EAE6",
    "Dia De Inverno Coral": "#E6E9E6",
    "Marfim Coral": "#FFFFF0",
    "Fendi Coral": "#BCB8B1",
    
    # Tons de Cinza/Escuros Coral
    "Crômo Fosco Coral": "#BDBDBD",
    "Chuva de Granizo Coral": "#A8A8A8",
    "Elefante Branco Coral": "#888888",
    "Preto Total Coral": "#1C1C1C",
    "Tubarão Branco Coral": "#DCDCDC",
    
    # Cores Vivas Coral
    "Amarelo Gema Coral": "#FFC000",
    "Laranja Caliente Coral": "#FF6700",
    "Verde Amazonas Coral": "#008880",
    "Azul Náutico Coral": "#00003A",
    "Azul Piscina Coral": "#00BFFF",
    "Rosa Choque Coral": "#FF69B4",
    "Marrom Tabaco Coral": "#4D3900",
    "Areia do Deserto Coral": "#D2B48C",
    "Vermelho Rubi Coral": "#E0115F",
    "Amarelo Trator Coral": "#FFB84C",

    # Tons de Madeira / Metálicos (EXPANDIDO)
    "Madeira Carvalho": "#964B00",
    "Madeira Nogueira": "#582900",
    "Madeira Mogno": "#C04000",
    "Aço Escovado": "#A9A9A9",
    "Alumínio Fosco": "#BDBDBD",
    "Prata Metálico": "#C0C0C0", # Adicionado (C0C0C0 é um prata padrão)
    "Ouro Metálico": "#D4AF37",  # Adicionado
    "Dourado Brilhante": "#FFD700", # Adicionado
}

# --- FUNÇÃO DE REVERSE LOOKUP (NOVA) ---

def get_color_name_from_hex(hex_code, color_palette):
    """Tenta encontrar o nome da cor na paleta dado um código HEX. Ignora maiúsculas/minúsculas."""
    # Garante que o HEX code esteja em maiúsculas para comparação consistente
    hex_code = hex_code.upper()
    for name, hex_value in color_palette.items():
        if hex_value.upper() == hex_code:
            return name
    return None

# --- DECORADOR DE SEGURANÇA ---

def get_current_user_id():
    """Retorna o UID do usuário atualmente logado."""
    return session.get(USER_SESSION_KEY)

def login_required(f):
    """Protege as rotas, verifica a sessão e redireciona para o login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if USER_SESSION_KEY not in session:
            # Redireciona para a tela de login se não houver ID na sessão
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- CONTEXT PROCESSOR: Injeta configurações do usuário em todos os templates ---
@app.context_processor
def inject_user_settings():
    """Busca o título personalizado do usuário ou usa o padrão."""
    user_id = get_current_user_id()
    
    # Título padrão
    app_title_custom = "Home Automation Technology"
    
    if user_id:
        # Tenta buscar a configuração do Firestore
        settings_doc = db.collection('user_settings').document(user_id).get()
        if settings_doc.exists:
            custom_title = settings_doc.to_dict().get('app_title')
            if custom_title:
                app_title_custom = custom_title
                
    # Retorna as variáveis que estarão disponíveis em todos os templates
    return dict(app_title_custom=app_title_custom)

# --- ROTAS DE CONFIGURAÇÃO (Título Personalizado) ---
@app.route('/editar_titulo', methods=['POST'])
@login_required
def editar_titulo():
    user_id = get_current_user_id()
    new_title = request.form.get('app_title_new')
    
    if new_title:
        # Salva o novo título na coleção user_settings
        db.collection('user_settings').document(user_id).set({'app_title': new_title}, merge=True)
        
    # Redireciona para a página anterior (ou index se não houver)
    return redirect(request.referrer or url_for('index'))


# --- LISTAS MESTRES (MANTIDAS IGUAIS) ---
def get_master_rooms():
    return [
        {"name": "Sala de Estar"}, {"name": "Sala de Jantar"}, {"name": "Cozinha"},
        {"name": "Área Gourmet"}, {"name": "Quarto Master (Suíte)"}, {"name": "Quarto Hóspedes"},
        {"name": "Quarto Filhos"}, {"name": "Banheiro Social"}, {"name": "Banheiro Suíte"},
        {"name": "Lavabo"}, {"name": "Escritório / Home Office"}, {"name": "Home Cinema"},
        {"name": "Corredor / Circulação"}, {"name": "Hall de Entrada"}, {"name": "Garagem"},
        {"name": "Lavanderia / Área de Serviço"}, {"name": "Área Externa / Piscina"}, {"name": "Jardim"}
    ]

def get_master_list():
    desc_zigbee = "Interruptor inteligente 4x2. Acabamento Acrílico (Touch). Comando de Voz e App."
    desc_zigbee_4x4 = "Painel Inteligente 4x4. Acabamento Acrílico (Touch). Comando de Voz e App."
    desc_tomada_red = "Tomada 20A Vermelha (Pino Grosso) 220V. Acabamento Acrílico."
    desc_tomada_white = "Tomada Branca Padrão. Acabamento Acrílico."
    desc_infra = "Módulo de infraestrutura. Acabamento Acrílico."

    desc_ar = "Climatização Inteligente. Controle total da temperatura pelo App ou Voz. Garanta o conforto térmico ideal antes mesmo de chegar em casa, com máxima eficiência energética e agendamentos automáticos."
    desc_tv = "Entretenimento Centralizado. Adeus aos múltiplos controles remotos. Comande sua TV, troque canais e acesse streamings via comando de voz ou através de uma interface única no celular."
    desc_som = "Experiência Sonora Imersiva. Som ambiente de alta fidelidade controlado por zonas. Crie playlists para festas ou relaxamento e integre a música ao cenário de iluminação."
    desc_cinema = "Cinema em Casa (Home Theater). Com um único toque no 'Modo Cinema', as luzes se apagam, as cortinas se fecham e o sistema de áudio e vídeo se ajusta para a performance máxima."
    desc_piscina = "Gestão de Lazer Outdoor. Controle de filtragem, aquecimento e iluminação RGB da piscina na palma da mão. Sua área de lazer sempre pronta para o uso, sem idas manuais à casa de máquinas."
    desc_jacuzzi = "Spa & Relaxamento. Prepare seu momento de descanso remotamente. Ative a hidromassagem e ajuste a temperatura ideal para que sua Jacuzzi esteja perfeita à sua espera ao chegar."

    return [
        {"name": "Automação de Ar Condicionado", "category": "Integração", "description_commercial": desc_ar, "tech_requirement": "Ponto de energia para Módulo IR ou Wi-Fi Integrado."},
        {"name": "Automação de TV / Vídeo", "category": "Integração", "description_commercial": desc_tv, "tech_requirement": "Ponto de energia para Central de Automação/IR Próximo à TV."},
        {"name": "Sonorização Ambiente (Zoneamento)", "category": "Integração", "description_commercial": desc_som, "tech_requirement": "Previsão de caixas no forro e cabeamento até o Amplificador."},
        {"name": "Home Cinema (Cena Integrada)", "category": "Integração", "description_commercial": desc_cinema, "tech_requirement": "Integração Lógica (Requer TV + Som + Iluminação conectados)."},
        {"name": "Automação de Piscina (Bomba/Luz)", "category": "Integração", "description_commercial": desc_piscina, "tech_requirement": "Módulo Relé na casa de máquinas (Wi-Fi/Zigbee) + Contatora se necessário."},
        {"name": "Automação de Jacuzzi/Spa", "category": "Integração", "description_commercial": desc_jacuzzi, "tech_requirement": "Módulo de Alta Potência ou Contatora na alimentação da Jacuzzi."},

        {"name": "Zigbee 1 Tecla (4x2)", "category": "Iluminação", "description_commercial": desc_zigbee, "tech_requirement": "Caixa 4x2. F+N+1 Retorno."},
        {"name": "Zigbee 2 Teclas (4x2)", "category": "Iluminação", "description_commercial": desc_zigbee, "tech_requirement": "Caixa 4x2. F+N+2 Retornos."},
        {"name": "Zigbee 3 Teclas (4x2)", "category": "Iluminação", "description_commercial": desc_zigbee, "tech_requirement": "Caixa 4x2. F+N+3 Retornos."},
        {"name": "Zigbee 4 Teclas (4x2)", "category": "Iluminação", "description_commercial": desc_zigbee, "tech_requirement": "Caixa 4x2. F+N+4 Retornos. (Alta Densidade)."},

        {"name": "Zigbee 1 Tecla (4x4)", "category": "Iluminação", "description_commercial": desc_zigbee_4x4, "tech_requirement": "Caixa 4x4. F+N+1 Retorno."},
        {"name": "Zigbee 2 Teclas (4x4)", "category": "Iluminação", "description_commercial": desc_zigbee_4x4, "tech_requirement": "Caixa 4x4. F+N+2 Retornos."},
        {"name": "Zigbee 3 Teclas (4x4)", "category": "Iluminação", "description_commercial": desc_zigbee_4x4, "tech_requirement": "Caixa 4x4. F+N+3 Retornos."},
        {"name": "Zigbee 4 Teclas (4x4)", "category": "Iluminação", "description_commercial": desc_zigbee_4x4, "tech_requirement": "Caixa 4x4. F+N+4 Retornos."},
        {"name": "Zigbee 5 Teclas (4x4)", "category": "Iluminação", "description_commercial": desc_zigbee_4x4, "tech_requirement": "Caixa 4x4. F+N+5 Retornos."},
        {"name": "Zigbee 6 Teclas (4x4)", "category": "Iluminação", "description_commercial": desc_zigbee_4x4, "tech_requirement": "Caixa 4x4. F+N+6 Retornos."},
        {"name": "Zigbee 8 Teclas (4x4)", "category": "Iluminação", "description_commercial": "Painel Master 4x4 8 Zonas. Acrílico.", "tech_requirement": "Caixa 4x4. F+N+8 Retornos."},

        {"name": "Tomada 20A Vermelha - 1 Módulo (4x2)", "category": "Energia", "description_commercial": desc_tomada_red, "tech_requirement": "Caixa 4x2. Fio 4mm. Circuito Específico."},
        {"name": "Tomada 20A Vermelha - 2 Módulos (4x2)", "category": "Energia", "description_commercial": "Dupla 20A Vermelha.", "tech_requirement": "Caixa 4x2. Fio 4mm."},
        {"name": "Tomada 20A Vermelha - 3 Módulos (4x2)", "category": "Energia", "description_commercial": "Tripla 20A Vermelha.", "tech_requirement": "Caixa 4x2."},
        {"name": "Conjunto: 1 Tom 20A Vermelha + 1 Tom 10A (4x2)", "category": "Energia", "description_commercial": "Misto: 1 Vermelha (20A) + 1 Branca (10A).", "tech_requirement": "Caixa 4x2."},

        {"name": "Tomada 20A Branca - 1 Módulo (4x2)", "category": "Energia", "description_commercial": "20A Branca Pino Grosso.", "tech_requirement": "Caixa 4x2. Fio 4mm."},
        {"name": "Tomada 20A Branca - 2 Módulos (4x2)", "category": "Energia", "description_commercial": "Dupla 20A Branca.", "tech_requirement": "Caixa 4x2. Fio 4mm."},
        {"name": "Tomada 20A Branca - 3 Módulos (4x2)", "category": "Energia", "description_commercial": "Tripla 20A Branca.", "tech_requirement": "Caixa 4x2."},

        {"name": "Tomada 10A Branca - 1 Módulo (4x2)", "category": "Energia", "description_commercial": desc_tomada_white, "tech_requirement": "Caixa 4x2. Fio 2.5mm."},
        {"name": "Tomada 10A Branca - 2 Módulos (4x2)", "category": "Energia", "description_commercial": "Dupla 10A Branca.", "tech_requirement": "Caixa 4x2."},
        {"name": "Tomada 10A Branca - 3 Módulos (4x2)", "category": "Energia", "description_commercial": "Tripla 10A Branca.", "tech_requirement": "Caixa 4x2."},

        {"name": "Tomadas 4x4 - 4 Módulos (10A)", "category": "Energia", "description_commercial": "Painel 4 Tomadas 10A.", "tech_requirement": "Caixa 4x4."},
        {"name": "Tomadas 4x4 - 6 Módulos (10A)", "category": "Energia", "description_commercial": "Painel 6 Tomadas 10A.", "tech_requirement": "Caixa 4x4."},
        {"name": "Tomadas 4x4 - 4 Módulos (20A)", "category": "Energia", "description_commercial": "Painel 4 Tomadas 20A.", "tech_requirement": "Caixa 4x4."},
        
        {"name": "Misto 4x2: 1 Tom + 1 Tecla", "category": "Misto", "description_commercial": "Híbrido Acrílico.", "tech_requirement": "Caixa 4x2. Separar Circuitos."},
        {"name": "Misto 4x2: 1 Tom + 2 Teclas", "category": "Misto", "description_commercial": "Híbrido Acrílico.", "tech_requirement": "Caixa 4x2. Separar Circuitos."},
        {"name": "Misto 4x4: 1 Tom / 1 Tecla", "category": "Misto", "description_commercial": "Painel Misto 4x4.", "tech_requirement": "Caixa 4x4."},
        {"name": "Misto 4x4: 1 Tom / 5 Teclas", "category": "Misto", "description_commercial": "Painel Alta Densidade (1 Tom + 5 Luz).", "tech_requirement": "Caixa 4x4."},
        
        {"name": "TV + Internet (4x2)", "category": "Dados", "description_commercial": "RJ45 + Coaxial.", "tech_requirement": "Tubulação Dados."},
        {"name": "Ponto Internet RJ45 (4x2)", "category": "Dados", "description_commercial": "Rede CAT6.", "tech_requirement": "Cabo CAT6."},
        {"name": "Tampa Cega 4x2", "category": "Infra", "description_commercial": desc_infra, "tech_requirement": "Caixa 4x2."},
        {"name": "Tampa Cega 4x4", "category": "Infra", "description_commercial": desc_infra, "tech_requirement": "Caixa 4x4."},
        {"name": "Saída de Fio (Furo)", "category": "Infra", "description_commercial": "Conector Wago."},
    ]

# --- POPULAÇÃO INICIAL (SEED) ---
def seed_database():
    # 1. Catálogo de Dispositivos (Global)
    docs = db.collection('catalogo').limit(1).stream()
    if not any(docs):
        print("Populando catálogo...")
        items = get_master_list()
        batch = db.batch()
        for item in items:
            doc_ref = db.collection('catalogo').document()
            batch.set(doc_ref, item)
        batch.commit()
    
    # 2. Lista de Ambientes (Global)
    rooms = db.collection('ambientes').limit(1).stream()
    if not any(rooms):
        print("Populando ambientes...")
        padrao = get_master_rooms()
        batch_r = db.batch()
        for r in padrao:
            doc_ref = db.collection('ambientes').document()
            batch_r.set(doc_ref, r)
        batch_r.commit()

# --- INTELIGÊNCIA DE NARRATIVA ---
def gerar_narrativa_ambiente(itens):
    circuitos_luz = 0
    tomadas_comuns = 0
    tomadas_especificas = 0
    integracoes = []
    tem_automacao = False
    
    for item in itens:
        # Verifica se 'catalog_item' existe no objeto do item
        if not hasattr(item, 'catalog_item') or not item.catalog_item:
            continue

        nome = item.catalog_item.name.lower()
        # Garante que a quantidade seja tratada como int
        try:
            qtd = int(item.quantity)
        except (TypeError, ValueError):
            qtd = 0
        
        if "zigbee" in nome and "tecla" in nome:
            tem_automacao = True
            match = re.search(r'(\d+)\s*tecla', nome)
            if match: circuitos_luz += int(match.group(1)) * qtd
            else: circuitos_luz += 1 * qtd
        
        if "tomada" in nome:
            if "vermelha" in nome or "20a" in nome: tomadas_especificas += qtd
            else: tomadas_comuns += qtd
        
        if "ar condicionado" in nome: integracoes.append("climatização")
        if "tv" in nome or "home cinema" in nome or "video" in nome: integracoes.append("audiovisual")
        if "som" in nome or "sonoriza" in nome or "audio" in nome: integracoes.append("sonorização ambiente")
        if "cortina" in nome or "persiana" in nome: integracoes.append("cortinas motorizadas")
        if "piscina" in nome: integracoes.append("área de lazer (piscina)")
        if "jacuzzi" in nome or "spa" in nome: integracoes.append("spa/jacuzzi")
    
    frases = []
    if circuitos_luz > 0:
        texto_luz = f"Neste ambiente, o sistema gerencia **{circuitos_luz} circuitos de iluminação**."
        if tem_automacao: texto_luz += " Todos habilitados para comando de voz e cenas."
        frases.append(texto_luz)
    
    if tomadas_comuns > 0 or tomadas_especificas > 0:
        partes = []
        if tomadas_comuns > 0: partes.append(f"{tomadas_comuns} pontos de uso geral")
        if tomadas_especificas > 0: partes.append(f"{tomadas_especificas} pontos específicos (20A)")
        frases.append(f"Infraestrutura elétrica dimensionada com {', '.join(partes)}.")

    if integracoes:
        integracoes = list(set(integracoes))
        frases.append(f"Destaque para a **automação completa de {', '.join(integracoes)}**, integrando conforto em uma única interface.")
    
    if not frases:
        return ""
        
    return " ".join(frases)

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_token = request.form.get('id_token')
        if not id_token:
            return "Erro: Token de autenticação faltando.", 400

        try:
            # 1. Verifica e decodifica o token (Segurança)
            decoded_token = firebase_auth.verify_id_token(id_token)
            uid = decoded_token['uid']
            
            # 2. Guarda o UID na sessão do Flask
            session[USER_SESSION_KEY] = uid
            
            # 3. CORREÇÃO: Força o redirecionamento para o index (Dashboard)
            return redirect(url_for('index'))

        except Exception as e:
            # Em caso de token expirado ou inválido
            return f"Erro de autenticação: {e}", 401

    if USER_SESSION_KEY in session:
        # Se o usuário já está logado, manda direto para o index
        return redirect(url_for('index'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop(USER_SESSION_KEY, None)
    return redirect(url_for('login'))


# --- ROTAS DE GERENCIAMENTO (PROTEGIDAS E FILTRADAS) ---

@app.route('/')
@login_required 
def index():
    user_id = get_current_user_id()
    
    # FILTRO: Apenas projetos deste usuário, ordenado por data
    projects_ref = db.collection('projects').where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    projects = []
    for doc in projects_ref:
        data = doc.to_dict()
        client_obj = DictObj({"name": data.get('client_name'), "address": data.get('client_address'), "phone": data.get('client_phone')})
        proj_obj = DictObj(data, id=doc.id)
        proj_obj.client = client_obj
        projects.append(proj_obj)
        
    return render_template('index.html', projects=projects, now=datetime.now())

@app.route('/adicionar_ambiente', methods=['POST'])
@login_required 
def adicionar_ambiente():
    project_id = request.form.get('project_id_redirect')
    # Adicionando um ID de usuário (Embora o ambiente deva ser global ou do projeto, no modelo atual, ele está sendo tratado como global/pessoal)
    db.collection('ambientes').add({"name": request.form['name'], "user_id": get_current_user_id()})
    if project_id: return redirect(url_for('gerenciar_projeto', project_id=project_id))
    return redirect(url_for('index'))

@app.route('/editar_ambiente', methods=['POST'])
@login_required 
def editar_ambiente():
    project_id = request.form.get('project_id_redirect')
    room_id = request.form.get('room_id')
    db.collection('ambientes').document(room_id).update({"name": request.form['name']})
    if project_id: return redirect(url_for('gerenciar_projeto', project_id=project_id))
    return redirect(url_for('index'))

@app.route('/excluir_ambiente/<room_id>')
@login_required 
def excluir_ambiente(room_id):
    db.collection('ambientes').document(room_id).delete()
    return redirect(request.referrer or url_for('index'))

@app.route('/adicionar_item_catalogo', methods=['POST'])
@login_required 
def adicionar_item_catalogo():
    project_id = request.form.get('project_id_redirect')
    novo_item = {
        "name": request.form['name'], "category": request.form['category'],
        "description_commercial": request.form['description_commercial'], "tech_requirement": request.form['tech_requirement'],
        "user_id": get_current_user_id()
    }
    db.collection('catalogo').add(novo_item)
    if project_id: return redirect(url_for('gerenciar_projeto', project_id=project_id))
    return redirect(url_for('index'))

@app.route('/editar_item_catalogo', methods=['POST'])
@login_required 
def editar_item_catalogo():
    project_id = request.form.get('project_id_redirect')
    item_id = request.form.get('item_id')
    dados = {
        "name": request.form['name'], "category": request.form['category'],
        "description_commercial": request.form['description_commercial'], "tech_requirement": request.form['tech_requirement']
    }
    db.collection('catalogo').document(item_id).update(dados)
    if project_id: return redirect(url_for('gerenciar_projeto', project_id=project_id))
    return redirect(url_for('index'))

@app.route('/excluir_item_catalogo/<item_id>')
@login_required 
def excluir_item_catalogo(item_id):
    db.collection('catalogo').document(item_id).delete()
    return redirect(request.referrer or url_for('index'))

@app.route('/novo_projeto', methods=['GET', 'POST'])
@login_required 
def novo_projeto():
    if request.method == 'POST':
        project_data = {
            "client_name": request.form['cliente'],
            "client_address": request.form['endereco'],
            "client_phone": request.form['telefone'],
            "created_at": datetime.now(),
            "user_id": get_current_user_id()
        }
        _, project_ref = db.collection('projects').add(project_data)
        return redirect(url_for('gerenciar_projeto', project_id=project_ref.id))
    return render_template('nova_consultoria.html', now=datetime.now())

@app.route('/editar_projeto/<project_id>', methods=['GET', 'POST'])
@login_required 
def editar_projeto(project_id):
    project_ref = db.collection('projects').document(project_id)
    proj_doc = project_ref.get()
    
    # SEGURANÇA: Verifica se o projeto existe e pertence ao usuário
    if not proj_doc.exists or proj_doc.to_dict().get('user_id') != get_current_user_id():
        return redirect(url_for('index'))

    if request.method == 'POST':
        project_ref.update({
            "client_name": request.form['cliente'],
            "client_address": request.form['endereco'],
            "client_phone": request.form['telefone']
        })
        return redirect(url_for('index'))
    
    data = proj_doc.to_dict()
    project = DictObj({"client_name": data.get('client_name'), "client_address": data.get('client_address'), "client_phone": data.get('client_phone')}, id=proj_doc.id)
    return render_template('editar_projeto.html', project=project, now=datetime.now())

@app.route('/apagar_projeto/<project_id>')
@login_required 
def apagar_projeto(project_id):
    proj_doc = db.collection('projects').document(project_id).get()
    
    if proj_doc.exists and proj_doc.to_dict().get('user_id') == get_current_user_id():
        db.collection('projects').document(project_id).delete()
    
    return redirect(url_for('index'))

@app.route('/projeto/<project_id>', methods=['GET', 'POST'])
@login_required 
def gerenciar_projeto(project_id):
    user_id = get_current_user_id()
    proj_doc = db.collection('projects').document(project_id).get()
    
    # SEGURANÇA: Redireciona se o projeto não existir ou não pertencer ao usuário
    if not proj_doc.exists or proj_doc.to_dict().get('user_id') != user_id:
        return redirect(url_for('index'))

    proj_data = proj_doc.to_dict()
    client_obj = DictObj({"name": proj_data.get('client_name'), "address": proj_data.get('client_address'), "phone": proj_data.get('client_phone')})
    project_obj = DictObj(proj_data, id=proj_doc.id)
    project_obj.client = client_obj
    
    # --- 1. Catálogo de Dispositivos: DUAS CONSULTAS ---
    global_cat_ref = db.collection('catalogo').order_by('name').stream()
    global_catalogo = [DictObj(doc.to_dict(), id=doc.id) for doc in global_cat_ref]
    
    user_cat_ref = db.collection('catalogo').where('user_id', '==', user_id).order_by('name').stream()
    user_catalogo = [DictObj(doc.to_dict(), id=doc.id) for doc in user_cat_ref]

    # Mescla as duas listas
    catalogo = global_catalogo + user_catalogo
    
    # --- 2. Lista de Ambientes: DUAS CONSULTAS ---
    global_room_ref = db.collection('ambientes').order_by('name').stream()
    global_ambientes = [DictObj(doc.to_dict(), id=doc.id) for doc in global_room_ref]
    
    user_room_ref = db.collection('ambientes').where('user_id', '==', user_id).order_by('name').stream()
    user_ambientes = [DictObj(doc.to_dict(), id=doc.id) for doc in user_room_ref]
    
    # Mescla as duas listas.
    ambientes = global_ambientes + user_ambientes
    
    # 3. Itens do Projeto
    items_ref = db.collection('projects').document(project_id).collection('items').stream()
    project_items = []
    itens_por_ambiente = {} 
    
    for doc in items_ref:
        i_data = doc.to_dict()
        cat_item_obj = DictObj({
            "name": i_data.get('item_name'), 
            "tech_requirement": i_data.get('tech_requirement'), 
            "description_commercial": i_data.get('description_commercial')
        })
        item_obj = DictObj(i_data, id=doc.id)
        item_obj.catalog_item = cat_item_obj
        project_items.append(item_obj)
        
        # LÓGICA DE AGRUPAMENTO DE ITENS POR AMBIENTE
        room_name = i_data.get('room_name', 'Sem Ambiente')
        if room_name not in itens_por_ambiente:
            itens_por_ambiente[room_name] = []
        itens_por_ambiente[room_name].append(item_obj)
        
    project_obj.items = project_items

    if request.method == 'POST':
        if 'delete_item_id' in request.form:
            db.collection('projects').document(project_id).collection('items').document(request.form['delete_item_id']).delete()
        else:
            cat_id = request.form['catalog_item_id']
            # Obtém o nome/HEX da cor (agora pode ser do select ou do campo de texto livre)
            item_color = request.form.get('item_color')
            
            # NOVO: Se for um código HEX, tenta reverter para o nome do preset
            if item_color and re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', item_color):
                matched_name = get_color_name_from_hex(item_color, SUVINIL_CORAL_COLORS)
                if matched_name:
                    item_color = matched_name # Salva o nome do preset (ex: "Branco Neve Suvinil")
            
            cat_doc = db.collection('catalogo').document(cat_id).get().to_dict()
            item_data = {
                "room_name": request.form['room_name'],
                "quantity": int(request.form['quantity']),
                "obs": request.form['obs'],
                "catalog_item_id": cat_id,
                "item_name": cat_doc['name'],
                "tech_requirement": cat_doc['tech_requirement'],
                "description_commercial": cat_doc['description_commercial'],
                "item_color": item_color # Salva o nome ou o HEX não reconhecido
            }
            db.collection('projects').document(project_id).collection('items').add(item_data)
        return redirect(url_for('gerenciar_projeto', project_id=project_id))

    # Adiciona a lista de cores ao contexto do template
    # REMOVIDO: global SUVINIL_CORAL_COLORS
    return render_template('gerenciar_projeto.html', 
        project=project_obj, 
        catalogo=catalogo, 
        ambientes=ambientes, 
        cores=SUVINIL_CORAL_COLORS, # Passa as cores
        itens_por_ambiente=itens_por_ambiente, 
        now=datetime.now()
    )

# --- ROTA: EDITAR ITEM DO PROJETO ---
@app.route('/editar_item_projeto', methods=['POST'])
@login_required 
def editar_item_projeto():
    project_id = request.form['project_id']
    item_id = request.form['item_id']
    cat_id = request.form['catalog_item_id']
    
    item_color = request.form.get('item_color')
    
    # NOVO: Se for um código HEX, tenta reverter para o nome do preset
    if item_color and re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', item_color):
        matched_name = get_color_name_from_hex(item_color, SUVINIL_CORAL_COLORS)
        if matched_name:
            item_color = matched_name # Salva o nome do preset (ex: "Branco Neve Suvinil")
            
    cat_doc = db.collection('catalogo').document(cat_id).get().to_dict()
    
    db.collection('projects').document(project_id).collection('items').document(item_id).update({
        "room_name": request.form['room_name'],
        "quantity": int(request.form['quantity']),
        "obs": request.form['obs'],
        "catalog_item_id": cat_id,
        "item_name": cat_doc['name'],
        "tech_requirement": cat_doc['tech_requirement'],
        "description_commercial": cat_doc['description_commercial'],
        "item_color": item_color # Atualiza o valor da cor (nome ou HEX)
    })
    
    return redirect(url_for('gerenciar_projeto', project_id=project_id))

# --- FUNÇÃO AUXILIAR PARA A API DE PDF (USANDO O NOVO FORMATO DE DADOS) ---
def generate_pdf_from_data(template_id, data_payload, output_filename):
    """
    Envia os dados estruturados para a API pdfgeneratorapi.com e retorna o PDF binário.
    """
    if not PDF_API_TOKEN or PDF_API_TOKEN == 'SEU_TOKEN_BEARER_AQUI':
        print("ERRO: PDF_API_TOKEN não configurado. A conversão falhará.")
        return None, "PDF_API_TOKEN não configurado. Por favor, adicione o Token Bearer no Vercel."

    headers = {
        'Authorization': f'Bearer {PDF_API_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/pdf'
    }

    # O payload usa o formato exigido pela nova API
    payload = {
        "template": {
            "id": template_id,
            "data": data_payload
        },
        "format": "pdf",
        "output": "download", # Pede o conteúdo PDF binário diretamente
        "name": f"{output_filename}_{datetime.now().strftime('%Y%m%d')}"
    }
    
    # NOVO: Imprime o JSON de dados no console para debug
    print("--- JSON PAYLOAD ENVIADO PARA API ---")
    print(json.dumps(payload, indent=2))
    print("--------------------------------------")


    try:
        response = requests.post(PDF_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            # Se a resposta for 200 e for um PDF, retorna o conteúdo binário
            return response.content, None
        else:
            error_details = response.text[:500]
            print(f"Erro na API de PDF Generator. Status: {response.status_code}. Resposta: {error_details}")
            # Se a API retornar JSON de erro, tenta parsear
            try:
                error_json = response.json()
                # Tenta extrair a mensagem de erro específica
                error_message = error_json.get('message', error_details)
            except json.JSONDecodeError:
                error_message = error_details

            return None, f"Erro {response.status_code} na conversão de PDF. Detalhes: {error_message}"

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão com a API de PDF: {e}")
        return None, f"Erro de conexão: {str(e)}"

# --- PDFS (REIMPLEMENTADOS VIA API DE DADOS E TEMPLATE) ---

@app.route('/projeto/<project_id>/pdf/<tipo>')
@login_required 
def gerar_pdf(project_id, tipo):
    user_id = get_current_user_id()
    proj_doc = db.collection('projects').document(project_id).get()
    
    # (Lógica de segurança e coleta de dados permanece)
    if not proj_doc.exists or proj_doc.to_dict().get('user_id') != user_id:
        return redirect(url_for('index'))

    proj_data = proj_doc.to_dict()
    client_obj = DictObj({"name": proj_data.get('client_name'), "address": proj_data.get('client_address'), "phone": proj_data.get('client_phone')})
    project = DictObj(proj_data, id=proj_doc.id)
    project.client = client_obj
    
    items_ref = db.collection('projects').document(project_id).collection('items').stream()
    itens_por_ambiente = {}
    
    # Prepara a lista de itens e o agrupamento por ambiente
    for doc in items_ref:
        data = doc.to_dict()
        cat_obj = DictObj({
            "name": data['item_name'], 
            "tech_requirement": data['tech_requirement'], 
            "description_commercial": data['description_commercial']
        })
        
        color_name = data.get('item_color', 'Branco Neve Suvinil')
        color_hex = SUVINIL_CORAL_COLORS.get(color_name, '#F0F0F0') 
        if color_hex == '#F0F0F0' and re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', color_name):
            color_hex = color_name
        
        item_obj = DictObj(data)
        item_obj.catalog_item = cat_obj
        item_obj.color_name = color_name
        item_obj.color_hex = color_hex
        
        room = data['room_name']
        if room not in itens_por_ambiente: itens_por_ambiente[room] = []
        itens_por_ambiente[room].append(item_obj)
    
    narrativas = {}
    for ambiente, itens in itens_por_ambiente.items():
        narrativas[ambiente] = gerar_narrativa_ambiente(itens)

    # 1. Decide o ID do Template
    if tipo == 'tecnico':
        template_id = TECNICO_TEMPLATE_ID
        output_filename = "Relatorio_Tecnico"
    else: # Memorial
        template_id = MEMORIAL_TEMPLATE_ID
        output_filename = "Relatorio_Memorial"
        
    # 2. Prepara os Dados Estruturados para a API
    # ATENÇÃO: A estrutura JSON deve ser compatível com o template que você vai subir!
    data_for_api = {
        "ClientName": project.client.name,
        "ClientAddress": project.client.address,
        "ClientPhone": project.client.phone,
        "CurrentDate": datetime.now().strftime("%d/%m/%Y"),
        "Narratives": [{"room": room, "text": narrative} for room, narrative in narrativas.items()],
        "Rooms": [
            {
                "RoomName": room,
                "Narrative": narratives.get(room, ""),
                # Converte os objetos DictObj em dicionários simples
                "Items": [
                    {
                        "Name": item.catalog_item.name,
                        "Quantity": item.quantity,
                        "ColorName": item.color_name,
                        "TechReq": item.catalog_item.tech_requirement,
                        "CommercialDesc": item.catalog_item.description_commercial,
                        "Obs": item.obs
                    } for item in items
                ]
            } for room, items in itens_por_ambiente.items()
        ]
    }
    
    # 3. Chama a API
    pdf_content, error_message = generate_pdf_from_data(template_id, data_for_api, output_filename)

    if pdf_content:
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={output_filename}.pdf'
        return response
    else:
        return f"Erro ao gerar PDF: {error_message}", 500


# ROTA PDF LEVANTAMENTO (Reimplementada via API de Dados e Template)
@app.route('/projeto/<project_id>/pdf/levantamento')
@login_required 
def gerar_levantamento(project_id):
    user_id = get_current_user_id()
    proj_doc = db.collection('projects').document(project_id).get()

    if not proj_doc.exists or proj_doc.to_dict().get('user_id') != user_id:
        return redirect(url_for('index'))

    proj_data = proj_doc.to_dict()
    client_obj = DictObj({"name": proj_data.get('client_name'), "address": proj_data.get('client_address'), "phone": proj_data.get('client_phone')})
    project = DictObj(proj_data, id=proj_doc.id)
    project.client = client_obj
    items_ref = db.collection('projects').document(project_id).collection('items').stream()
    resumo = {}
        
    for doc in items_ref:
        data = doc.to_dict()
        name = data['item_name']
        qtde = int(data['quantity'])
        color_name = data.get('item_color', 'Branco Neve Suvinil')
        
        color_hex = SUVINIL_CORAL_COLORS.get(color_name, '#F0F0F0') 
        if color_hex == '#F0F0F0' and re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', color_name):
            color_hex = color_name
        
        key = f"{name} ({color_name})" 
        
        if key not in resumo: 
            resumo[key] = {
                'nome': name, 
                'total': 0, 
                'locais': [],
                'color_name': color_name,
                'color_hex': color_hex
            }
        resumo[key]['total'] += qtde
        resumo[key]['locais'].append(data['room_name'])
        
    # Prepara a lista de itens resumidos para a API
    summarized_items = [
        {
            "Name": data['nome'],
            "TotalQuantity": data['total'],
            "Color": data['color_name'],
            "Locations": ", ".join(set(data['locais']))
        }
        for key, data in resumo.items()
    ]
    
    # 1. Define o ID do Template
    template_id = LEVANTAMENTO_TEMPLATE_ID
    output_filename = "Levantamento_Compras"

    # 2. Prepara os Dados Estruturados para a API
    data_for_api = {
        "ClientName": project.client.name,
        "CurrentDate": datetime.now().strftime("%d/%m/%Y"),
        "SummarizedItems": summarized_items
    }
                          
    # 3. Chama a API
    pdf_content, error_message = generate_pdf_from_data(template_id, data_for_api, output_filename)

    if pdf_content:
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=Levantamento.pdf'
        return response
    else:
        return f"Erro ao gerar Levantamento PDF: {error_message}", 500


if __name__ == '__main__':
    seed_database()
    app.run(debug=True, port=5001)