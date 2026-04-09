from flask import Blueprint, request, jsonify
from app.db import get_conn
import os
import requests
import random

entrega_bp = Blueprint("entrega", __name__)

@entrega_bp.post("/entrega/calcular")
def calcular_entrega():
    """
    Calcular tempo estimado de entrega
    ---
    tags:
      - Entrega
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - endereco_id
          properties:
            endereco_id:
              type: string
              example: "0441265c6167f76c683bbdd4d1d345de"
    responses:
      200:
        description: Entrega calculada com sucesso
        schema:
          type: object
          properties:
            eta_minutos:
              type: integer
              example: 42
            distancia_km:
              type: number
              example: 12.6
            fonte:
              type: string
              example: google
      400:
        description: Dados inválidos
      404:
        description: Endereço não encontrado
      500:
        description: Erro no cálculo
    """
    
    data = request.get_json()
    endereco_id = data.get("endereco_id")
    

    if not endereco_id:
        return jsonify({"error": "endereco_id é obrigatório"}), 400

    with get_conn(readonly=True) as conn:
        endereco = conn.execute("""
            SELECT logradouro, numero, bairro, cidade, estado, cep
            FROM enderecos
            WHERE id = ?
        """, (endereco_id,)).fetchone()

    if not endereco:
        return jsonify({"error": "Endereço não encontrado"}), 404

    origem = os.environ.get("ORIGEM_PIZZARIA")
    destino = f"{endereco['logradouro']}, {endereco['numero']}, {endereco['bairro']}, {endereco['cidade']} - {endereco['estado']}"

    params = {
        "origins": origem,
        "destinations": destino,
        "key": os.environ.get("GOOGLE_MAPS_KEY"),
        "units": "metric",
    }

    r = requests.get(
        "https://maps.googleapis.com/maps/api/distancematrix/json",
        params=params,
        timeout=10,
    )

    data = r.json()
    element = data["rows"][0]["elements"][0]

    if element["status"] != "OK":
        return jsonify({"error": "Erro ao calcular rota"}), 500

    distancia_km = element["distance"]["value"] / 1000
    eta_minutos = round(element["duration"]["value"] / 60)

    
    # tempo vindo do Google
    tempo_entrega_min = eta_minutos
    tempo_entrega_max = eta_minutos

    # regra de negócio – preparo
    PREPARO_MIN = 20
    PREPARO_MAX = 25

    # soma final
    total_min = PREPARO_MIN + tempo_entrega_min
    total_max = PREPARO_MAX + tempo_entrega_max

    return jsonify({
        "preparo_min": PREPARO_MIN,
        "preparo_max": PREPARO_MAX,
        "entrega_min": tempo_entrega_min,
        "entrega_max": tempo_entrega_max,
        "total_min": total_min,
        "total_max": total_max,
        "distancia_km": distancia_km,
        "fonte": "google"
    })