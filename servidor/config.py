"""Preferências do servidor salvas em %APPDATA%\\SegundaTela\\config.json."""
import json
import os


def _arquivo():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    pasta = os.path.join(base, "SegundaTela")
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, "config.json")


def ler(chave, padrao=None):
    try:
        with open(_arquivo(), encoding="utf-8") as f:
            return json.load(f).get(chave, padrao)
    except (OSError, ValueError):
        return padrao


def gravar(chave, valor):
    try:
        with open(_arquivo(), encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        dados = {}
    dados[chave] = valor
    try:
        with open(_arquivo(), "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2)
    except OSError:
        pass
