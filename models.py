from database import db
from datetime import datetime

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    projects = db.relationship('Project', backref='client', lazy=True)

class CatalogItem(db.Model):
    """Catálogo mestre de peças e requisitos"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50)) # Iluminação, Áudio, Rede
    description_commercial = db.Column(db.Text) # Texto para o Cliente
    tech_requirement = db.Column(db.Text) # Texto para o Eletricista

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    # Relacionamento para pegar os itens do projeto
    items = db.relationship('ProjectItem', backref='project', lazy=True, cascade="all, delete-orphan")

class ProjectItem(db.Model):
    """Item específico instalado na casa do cliente"""
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    catalog_item_id = db.Column(db.Integer, db.ForeignKey('catalog_item.id'), nullable=False)
    
    room_name = db.Column(db.String(50), nullable=False) # Sala, Quarto, etc.
    quantity = db.Column(db.Integer, default=1)
    obs = db.Column(db.String(200)) # Observação local
    
    # Atalho para acessar os dados do catálogo
    catalog_item = db.relationship('CatalogItem')