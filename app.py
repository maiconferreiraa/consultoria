import os
import re
import base64
import io
import json
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, make_response, session, jsonify
)

import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
from weasyprint import HTML

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
UPLOAD_FOLDER = 'static/logos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.environ.get('SECRET_KEY', 'CHAVE_MESTRA_CONSULTORIA_AUTOMACAO_2025')
USER_SESSION_KEY = 'user_id'

# --- LIGAÇÃO AO FIREBASE ---
try:
    if os.path.exists("firebase_key.json"):
        cred = credentials.Certificate("firebase_key.json")
    elif os.path.exists("/etc/secrets/firebase_key.json"):
        cred = credentials.Certificate("/etc/secrets/firebase_key.json")
    else:
        cred = None

    if cred and not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client() if cred else None
except Exception as e:
    print(f"ERRO FIREBASE: {e}")
    db = None

# --- CLASSES E HELPERS ---
class DictObj:
    """Permite aceder a dicionários usando a notação de ponto."""
    def __init__(self, data, id=None):
        self.id = id
        if data:
            for key, value in data.items():
                setattr(self, key, value)
    
    def get(self, key, default=None):
        return getattr(self, key, default)

# --- FILTRO DE MOEDA ---
@app.template_filter('format_currency')
def format_currency(value):
    try:
        if value is None: return "R$ 0,00"
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

# --- CONFIGURAÇÃO DE CORES ---
SUVINIL_CORAL_COLORS = {
    "Branco Neve Suvinil": "#F0F0F0", "Gelo Suvinil": "#F4F4F4", "Papiro Suvinil": "#F0EDE6",
    "Off White Suvinil": "#F5F5F5", "Creme Suvinil": "#FFFDD0", "Algodão Egípcio Suvinil": "#EBEAE3",
    "Palha Suvinil": "#FAF0C9", "Broto de Feijão Suvinil": "#C2B8A3", "Cinza Elefante Suvinil": "#B0B0B0",
    "Crômio Suvinil": "#A9A9A9", "Prata Suvinil": "#CCD1D1", "Névoa Intensa Suvinil": "#D3D7D2",
    "Cinza Urbano Suvinil": "#5E5E5E", "Nanquim Suvinil": "#262626", "Cinza Asfalto Suvinil": "#4C5357",
    "Preto Absoluto Suvinil": "#0A0A0A", "Amarelo Sol Suvinil": "#FFD700", "Luz de Inverno Suvinil": "#F5E6B5",
    "Amarelo Real Suvinil": "#FAD32B", "Laranja Outonal Suvinil": "#F0A300", "Terra Roxa Suvinil": "#A0522D",
    "Bege Areia Suvinil": "#D8C5A5", "Valentino Suvinil": "#DC143C", "Verde Piscina Suvinil": "#00A99D",
    "Azul Profundo Suvinil": "#000080", "Azul Celeste Suvinil": "#56A0C5", "Céu Sereno Suvinil": "#87CEEB",
    "Rosa Açaí Suvinil": "#E0B0FF", "Rosa Pastel Suvinil": "#FFB6C1", "Chá de Rosas Suvinil": "#D8BFD8",
}

# --- SEGURANÇA ---
def get_current_user_id():
    return session.get(USER_SESSION_KEY)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if db is None: return "Erro Firestore.", 500
        if USER_SESSION_KEY not in session: return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user_settings():
    user_id = get_current_user_id()
    app_title_custom = "Home Automation Technology" 
    app_logo_url = None
    if user_id and db:
        doc = db.collection('user_settings').document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            app_title_custom = data.get('app_title', app_title_custom)
            b64, mime = data.get('logo_base64'), data.get('logo_mime_type')
            if b64 and mime: app_logo_url = f"data:{mime};base64,{b64}"
    return dict(app_title_custom=app_title_custom, app_logo_url=app_logo_url, now=datetime.now()) 

# --- GERAÇÃO DE NARRATIVA AUTOMÁTICA ---
def gerar_narrativa_ambiente(itens):
    circuitos_luz = 0
    integracoes = []
    for item in itens:
        nome = item.item_name.lower()
        qtd = int(item.quantity or 0)
        if "tecla" in nome:
            match = re.search(r'(\d+)\s*tecla', nome)
            circuitos_luz += (int(match.group(1)) if match else 1) * qtd
        if "ar condicionado" in nome: integracoes.append("climatização")
        if "tv" in nome or "cinema" in nome: integracoes.append("audiovisual")
    frases = []
    if circuitos_luz > 0: frases.append(f"O ambiente conta com {circuitos_luz} pontos de iluminação inteligente.")
    if integracoes: frases.append(f"Inclui integração de {', '.join(set(integracoes))}.")
    return " ".join(frases)

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_token = request.form.get('id_token')
        try:
            decoded = firebase_auth.verify_id_token(id_token)
            session[USER_SESSION_KEY] = decoded['uid']
            return redirect(url_for('index'))
        except: return "Erro Auth", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop(USER_SESSION_KEY, None)
    return redirect(url_for('login'))

@app.route('/editar_titulo', methods=['POST'])
@login_required
def editar_titulo():
    user_id = get_current_user_id()
    new_title = request.form.get('app_title_new')
    logo_file = request.files.get('logo_file')
    update_data = {}
    if logo_file and logo_file.filename:
        file_bytes = logo_file.read()
        update_data['logo_base64'] = base64.b64encode(file_bytes).decode('utf-8')
        update_data['logo_mime_type'] = logo_file.mimetype 
    if new_title: update_data['app_title'] = new_title
    if update_data: db.collection('user_settings').document(user_id).set(update_data, merge=True)
    return redirect(request.referrer or url_for('index'))

# --- ROTAS DE PROJETOS ---
@app.route('/')
@login_required 
def index():
    user_id = get_current_user_id()
    projects_ref = db.collection('projects').where('user_id', '==', user_id).stream()
    projects = []
    MIN_DT_AWARE = datetime(1, 1, 1, tzinfo=timezone.utc)
    for doc in projects_ref:
        data = doc.to_dict()
        p = DictObj(data, id=doc.id)
        p.client = DictObj({"name": data.get('client_name'), "address": data.get('client_address')})
        projects.append(p)
    projects.sort(key=lambda x: x.get('created_at', MIN_DT_AWARE), reverse=True)
    return render_template('index.html', projects=projects)

@app.route('/novo_projeto', methods=['GET', 'POST'])
@login_required
def novo_projeto():
    if request.method == 'POST':
        data = {
            "client_name": request.form['cliente'], 
            "client_address": request.form['endereco'],
            "client_phone": request.form['telefone'], 
            "created_at": datetime.now(timezone.utc),
            "user_id": get_current_user_id()
        }
        _, ref = db.collection('projects').add(data)
        session['success_message'] = "Projeto criado com sucesso!"
        return redirect(url_for('gerenciar_projeto', project_id=ref.id))
    return render_template('nova_consultoria.html')

@app.route('/editar_projeto/<project_id>', methods=['GET', 'POST'])
@login_required
def editar_projeto(project_id):
    ref = db.collection('projects').document(project_id)
    if request.method == 'POST':
        ref.update({
            "client_name": request.form['cliente'], 
            "client_address": request.form['endereco'], 
            "client_phone": request.form['telefone']
        })
        session['success_message'] = "Dados do cliente atualizados!"
        return redirect(url_for('gerenciar_projeto', project_id=project_id))
    p_data = ref.get().to_dict()
    p = DictObj(p_data, id=project_id)
    return render_template('editar_projeto.html', project=p)

@app.route('/apagar_projeto/<project_id>')
@login_required
def apagar_projeto(project_id):
    db.collection('projects').document(project_id).delete()
    session['success_message'] = "Projeto excluído com sucesso!"
    return redirect(url_for('index'))

# --- GESTÃO DO PROJETO ---
@app.route('/projeto/<project_id>', methods=['GET', 'POST'])
@login_required 
def gerenciar_projeto(project_id):
    user_id = get_current_user_id()
    proj_ref = db.collection('projects').document(project_id)
    proj_doc = proj_ref.get()
    if not proj_doc.exists or proj_doc.to_dict().get('user_id') != user_id: return redirect(url_for('index'))

    if request.method == 'POST':
        if 'delete_item_id' in request.form:
            proj_ref.collection('items').document(request.form['delete_item_id']).delete()
            session['success_message'] = "Item removido do projeto."
        else:
            cat_id = request.form['catalog_item_id']
            cat_doc = db.collection('catalogo').document(cat_id).get().to_dict()
            item_data = {
                "room_name": request.form['room_name'].strip(), 
                "quantity": int(request.form['quantity']),
                "obs": request.form['obs'].strip(),
                "catalog_item_id": cat_id, 
                "item_name": cat_doc['name'].strip(),
                "item_color": request.form.get('item_color', '').strip(),
                "description_commercial": cat_doc.get('description_commercial', ''),
                "tech_requirement": cat_doc.get('tech_requirement', ''),
                "model_touch": request.form.get('model_touch_override', cat_doc.get('model_touch', 'quadrado')),
                "logo_inserir": request.form.get('logo_inserir') == 'SIM',
                "unit_price": 0.0, 
                "created_at": datetime.now(timezone.utc)
            }
            proj_ref.collection('items').add(item_data)
            session['success_message'] = f"Item '{cat_doc['name']}' adicionado!"
        return redirect(url_for('gerenciar_projeto', project_id=project_id))

    def get_list(coll):
        items_stream = db.collection(coll).stream()
        res = []
        for d in items_stream:
            data = d.to_dict()
            if not data.get('user_id') or data.get('user_id') == user_id: res.append(DictObj(data, id=d.id))
        return sorted(res, key=lambda x: x.name)

    catalogo, ambientes = get_list('catalogo'), get_list('ambientes')
    items_ref = proj_ref.collection('items').stream()
    project_items = []
    resumo_consolidado = {}
    
    for doc in items_ref:
        d = doc.to_dict()
        it = DictObj(d, id=doc.id)
        
        it.item_name = str(d.get('item_name', 'Sem Nome')).strip()
        it.room_name = str(d.get('room_name', 'Indefinido')).strip()
        it.quantity = int(d.get('quantity', 1))
        it.unit_price = float(d.get('unit_price', 0))
        it.obs = str(d.get('obs', '')).strip()
        it.total_price = it.unit_price * it.quantity
        it.item_color = str(d.get('item_color', '')).strip()
        
        project_items.append(it)
        
        # Consolidação para Orçamento e Resumo
        key = f"{it.item_name}:::{it.item_color}"
        if key not in resumo_consolidado:
            resumo_consolidado[key] = {
                'item_name': it.item_name, 'item_color': it.item_color, 'quantity': 0, 'unit_price': it.unit_price, 
                'rooms': set(), 'obs_list': set(), 'group_id': key
            }
        resumo_consolidado[key]['quantity'] += it.quantity
        resumo_consolidado[key]['rooms'].add(it.room_name)
        if it.unit_price > resumo_consolidado[key]['unit_price']: resumo_consolidado[key]['unit_price'] = it.unit_price
        if it.obs and it.obs != 'N/A': resumo_consolidado[key]['obs_list'].add(it.obs)

    consolidated_items = []
    total_orcamento_calculado = 0
    for k, v in resumo_consolidado.items():
        v['room_name'] = ", ".join(sorted(list(v['rooms'])))
        v['obs'] = " | ".join(sorted(list(v['obs_list'])))
        v['total_price'] = v['quantity'] * v['unit_price']
        total_orcamento_calculado += v['total_price']
        consolidated_items.append(DictObj(v))

    proj_data = proj_doc.to_dict()
    project_obj = DictObj(proj_data, id=proj_doc.id)
    project_obj.client = DictObj({"name": proj_data.get('client_name'), "address": proj_data.get('client_address'), "phone": proj_data.get('client_phone')})
    
    msg = session.pop('success_message', None)
    return render_template('gerenciar_projeto.html', project=project_obj, items=project_items, consolidated_items=consolidated_items, total_orcamento=total_orcamento_calculado, catalogo=catalogo, ambientes=ambientes, cores=SUVINIL_CORAL_COLORS, success_message=msg)

# --- ROTAS DE AMBIENTES E CATÁLOGO ---
@app.route('/adicionar_ambiente', methods=['POST'])
@login_required
def adicionar_ambiente():
    db.collection('ambientes').add({"name": request.form['name'].strip(), "user_id": get_current_user_id()})
    session['success_message'] = f"Cômodo '{request.form['name']}' adicionado com sucesso!"
    return redirect(request.referrer)

@app.route('/editar_ambiente', methods=['POST'])
@login_required
def editar_ambiente():
    db.collection('ambientes').document(request.form.get('room_id')).update({"name": request.form['name'].strip()})
    session['success_message'] = "Nome do cômodo atualizado!"
    return redirect(request.referrer)

@app.route('/excluir_ambiente/<room_id>')
@login_required
def excluir_ambiente(room_id):
    db.collection('ambientes').document(room_id).delete()
    session['success_message'] = "Cômodo removido com sucesso!"
    return redirect(request.referrer)

@app.route('/adicionar_item_catalogo', methods=['POST'])
@login_required
def adicionar_item_catalogo():
    db.collection('catalogo').add({
        "name": request.form['name'], "category": request.form['category'], 
        "description_commercial": request.form['description_commercial'], 
        "tech_requirement": request.form['tech_requirement'], 
        "model_touch": request.form.get('model_touch_new', 'quadrado'),
        "user_id": get_current_user_id()
    })
    session['success_message'] = "Item adicionado ao catálogo!"
    return redirect(request.referrer)

@app.route('/excluir_item_catalogo/<item_id>')
@login_required
def excluir_item_catalogo(item_id):
    db.collection('catalogo').document(item_id).delete()
    session['success_message'] = "Item removido do catálogo."
    return redirect(request.referrer)

# --- ROTAS DE SALVAMENTO DE PREÇOS ---
@app.route('/salvar_precos_projeto/<project_id>', methods=['POST'])
@login_required
def salvar_precos_projeto(project_id):
    proj_ref = db.collection('projects').document(project_id)
    items_ref = proj_ref.collection('items').stream()
    novos_precos = {}
    for key, value in request.form.items():
        if key.startswith('price_group_'):
            group_key = key.replace('price_group_', '')
            try: novos_precos[group_key] = float(value.replace(',', '.'))
            except: continue

    for doc in items_ref:
        d = doc.to_dict()
        item_key = f"{str(d.get('item_name', '')).strip()}:::{str(d.get('item_color', '')).strip()}"
        if item_key in novos_precos:
            proj_ref.collection('items').document(doc.id).update({"unit_price": novos_precos[item_key]})
            
    session['success_message'] = "Preços do orçamento atualizados!"
    return redirect(url_for('gerenciar_projeto', project_id=project_id))

@app.route('/editar_item_projeto', methods=['POST'])
@login_required
def editar_item_projeto():
    proj_id = request.form.get('project_id')
    db.collection('projects').document(proj_id).collection('items').document(request.form.get('item_id')).update({
        "quantity": int(request.form['quantity']), 
        "obs": request.form['obs'].strip(),
        "room_name": request.form.get('room_name').strip(), 
        "item_color": request.form.get('item_color').strip(),
        "logo_inserir": request.form.get('logo_inserir') == 'SIM'
    })
    session['success_message'] = "Item do projeto atualizado!"
    return redirect(url_for('gerenciar_projeto', project_id=proj_id))

# --- GERAÇÃO DE PDFS ---
@app.route('/projeto/<project_id>/pdf/<tipo>')
@login_required 
def gerar_pdf(project_id, tipo):
    proj_ref = db.collection('projects').document(project_id)
    proj_data = proj_ref.get().to_dict()
    items_ref = proj_ref.collection('items').stream()
    itens_para_template, itens_por_ambiente, total_geral = [], {}, 0

    if tipo == 'orcamento':
        resumo = {}
        for doc in items_ref:
            d = doc.to_dict()
            name, color = str(d.get('item_name', '')).strip(), str(d.get('item_color', '')).strip()
            key = f"{name}:::{color}"
            p, q = float(d.get('unit_price', 0)), int(d.get('quantity', 1))
            if key not in resumo:
                resumo[key] = {'item_name': name, 'item_color': color, 'color_hex': SUVINIL_CORAL_COLORS.get(color, '#F0F0F0'), 'quantity': 0, 'unit_price': p, 'rooms': set()}
            resumo[key]['quantity'] += q
            resumo[key]['rooms'].add(d.get('room_name', '').strip())
        for v in resumo.values():
            v['room_name'] = ", ".join(sorted(list(v['rooms'])))
            v['total_price'] = v['quantity'] * v['unit_price']
            total_geral += v['total_price']
            itens_para_template.append(DictObj(v))
    else:
        for doc in items_ref:
            d = doc.to_dict()
            it = DictObj(d, id=doc.id)
            it.unit_price, it.quantity = float(d.get('unit_price', 0)), int(d.get('quantity', 1))
            it.total_price = it.unit_price * it.quantity
            it.color_hex = SUVINIL_CORAL_COLORS.get(it.item_color, '#F0F0F0')
            it.catalog_item = DictObj({"name": it.item_name, "description_commercial": d.get('description_commercial', ''), "tech_requirement": d.get('tech_requirement', '')})
            total_geral += it.total_price
            itens_para_template.append(it)
            room = str(d.get('room_name', 'Sem Ambiente')).strip()
            if room not in itens_por_ambiente: itens_por_ambiente[room] = []
            itens_por_ambiente[room].append(it)

    p_obj = DictObj(proj_data, id=project_id)
    p_obj.client = DictObj({"name": proj_data.get('client_name'), "address": proj_data.get('client_address'), "phone": proj_data.get('client_phone')})
    html = render_template(f'relatorios/{tipo}.html', project=p_obj, items=itens_para_template, itens_por_ambiente=itens_por_ambiente, narrativas={r: gerar_narrativa_ambiente(its) for r, its in itens_por_ambiente.items()} if tipo != 'orcamento' else {}, total_geral=total_geral, data_hoje=datetime.now(timezone.utc).strftime("%d/%m/%Y"), cores=SUVINIL_CORAL_COLORS)
    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    return response

@app.route('/projeto/<project_id>/pdf/levantamento')
@login_required
def gerar_levantamento(project_id):
    proj_ref = db.collection('projects').document(project_id)
    proj_data = proj_ref.get().to_dict()
    items_ref = proj_ref.collection('items').stream()
    resumo = {}
    for doc in items_ref:
        d = doc.to_dict()
        key = f"{str(d.get('item_name', '')).strip()}:::{str(d.get('item_color', '')).strip()}"
        if key not in resumo: resumo[key] = {'nome': d.get('item_name'), 'total': 0, 'locais': set(), 'color_name': d.get('item_color'), 'color_hex': SUVINIL_CORAL_COLORS.get(d.get('item_color'), '#F0F0F0'), 'logo_inserir': d.get('logo_inserir', False), 'model_touch': d.get('model_touch', 'quadrado'), 'obs_list': set()}
        resumo[key]['total'] += int(d.get('quantity', 1))
        resumo[key]['locais'].add(d.get('room_name', 'Indefinido'))
    resumo_final = []
    for v in resumo.values():
        v['locais_str'] = ", ".join(sorted(list(v['locais'])))
        resumo_final.append(v)
    p_obj = DictObj(proj_data, id=project_id)
    p_obj.client = DictObj({"name": proj_data.get('client_name'), "address": proj_data.get('client_address'), "phone": proj_data.get('client_phone')})
    html = render_template('relatorios/levantamento.html', project=p_obj, itens_resumidos=resumo_final, data_hoje=datetime.now(timezone.utc).strftime("%d/%m/%Y"), cores=SUVINIL_CORAL_COLORS)
    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001)