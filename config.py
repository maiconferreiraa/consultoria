import os

class Config:
    # Chave secreta para segurança de formulários (pode ser qualquer texto aleatório)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-muito-secreta-automacao'
    
    # Caminho do banco de dados SQLite
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'automacao.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False