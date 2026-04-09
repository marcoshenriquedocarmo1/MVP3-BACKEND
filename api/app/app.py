import os
from flask import Flask, app, jsonify, send_from_directory, request, abort
from flasgger import Swagger
from app.db import get_conn
import re
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
from app.entrega import entrega_bp

def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exc(e: HTTPException):
        resp = jsonify({
            "error": e.name,
            "status_code": e.code,
            "message": e.description,
        })
        return resp, e.code

    @app.errorhandler(Exception)
    def handle_exc(e: Exception):
        resp = jsonify({
            "error": "Internal Server Error",
            "status_code": 500,
            "message": str(e),
        })
        return resp, 500


ALLOWED_CATEGORIES = {"entrada", "pizza", "sobremesa", "bebida"}

def validate_menu_payload(data: dict, partial: bool = False):
    """
    Validação simples de payload do menu.
    - Se partial=True (PATCH), todos os campos são opcionais, mas se vier, precisa ser válido.
    - Se partial=False (POST/PUT), campos obrigatórios: id, nome, categoria, preco_cents.
    """
    required = {"id", "nome", "categoria", "preco_cents"}

    if not isinstance(data, dict):
        abort(400, description="JSON inválido")

    if not partial:
        missing = required - set(data.keys())
        if missing:
            abort(400, description=f"Campos obrigatórios ausentes: {', '.join(sorted(missing))}")

    if "id" in data:
        if not isinstance(data["id"], str) or not data["id"].strip():
            abort(400, description="Campo 'id' deve ser string não vazia")

    if "nome" in data:
        if not isinstance(data["nome"], str) or not data["nome"].strip():
            abort(400, description="Campo 'nome' deve ser string não vazia")

    if "categoria" in data:
        cat = data["categoria"]
        if cat not in ALLOWED_CATEGORIES:
            abort(400, description=f"Categoria inválida. Use: {', '.join(sorted(ALLOWED_CATEGORIES))}")

    if "preco_cents" in data:
        try:
            preco = int(data["preco_cents"])
            if preco < 0:
                raise ValueError
        except Exception:
            abort(400, description="Campo 'preco_cents' deve ser inteiro >= 0")

    # campos opcionais (sem validação pesada no MVP)
    for opt in ("descricao", "ingredientes", "imagem"):
        if opt in data and data[opt] is not None and not isinstance(data[opt], str):
            abort(400, description=f"Campo '{opt}' deve ser string")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_cliente_payload(data: dict, partial: bool = False):
    """
    Validação simples do payload de cliente.
    - Se partial=False (POST/PUT): 'nome' é obrigatório.
    - Se partial=True (PATCH): tudo é opcional, mas se vier, precisa ser válido.
    """
    if not isinstance(data, dict):
        abort(400, description="JSON inválido")

    if not partial:
        if "nome" not in data:
            abort(400, description="Campo obrigatório ausente: nome")

    if "nome" in data:
        if not isinstance(data["nome"], str) or not data["nome"].strip():
            abort(400, description="Campo 'nome' deve ser string não vazia")

    if "telefone" in data and data["telefone"] is not None:
        if not isinstance(data["telefone"], str):
            abort(400, description="Campo 'telefone' deve ser string")

    if "email" in data and data["email"] is not None:
        if not isinstance(data["email"], str):
            abort(400, description="Campo 'email' deve ser string")
        email = data["email"].strip()
        if email and not EMAIL_RE.match(email):
            abort(400, description="Campo 'email' inválido")


def validate_endereco_payload(data: dict, partial: bool = False):
    """
    Validação simples do payload de endereço.
    - Se partial=False (POST/PUT): cliente_id, logradouro, cidade, estado são obrigatórios.
    - Se partial=True (PATCH): todos opcionais, mas se vier, precisam ser válidos.
    """
    if not isinstance(data, dict):
        abort(400, description="JSON inválido")

    required = {"cliente_id", "logradouro", "cidade", "estado"}
    if not partial:
        missing = required - set(data.keys())
        if missing:
            abort(400, description=f"Campos obrigatórios ausentes: {', '.join(sorted(missing))}")

    # Tipos básicos (sem validação pesada no MVP)
    str_fields = [
        "cliente_id", "apelido", "logradouro", "numero", "complemento",
        "bairro", "cidade", "estado", "cep"
    ]
    for f in str_fields:
        if f in data and data[f] is not None and not isinstance(data[f], str):
            abort(400, description=f"Campo '{f}' deve ser string")

    # latitude/longitude se vierem, devem ser numéricos
    for f in ("latitude", "longitude"):
        if f in data and data[f] is not None:
            try:
                float(data[f])
            except Exception:
                abort(400, description=f"Campo '{f}' deve ser numérico (float)")


ALLOWED_STATUS = {"criado", "preparando", "a_caminho", "entregue", "cancelado"}

def validate_pedido_payload(data: dict):
    """
    POST /pedidos
    Obrigatórios:
      - cliente_id (string)
      - endereco_entrega_id (string)
      - itens: lista de { item_menu_id (string), quantidade (int > 0) }
    Opcionais:
      - observacoes (string)
      - taxa_entrega_cents (int >= 0)
    """
    if not isinstance(data, dict):
        abort(400, description="JSON inválido")

    required = {"cliente_id", "endereco_entrega_id", "itens"}
    missing = required - set(data.keys())
    if missing:
        abort(400, description=f"Campos obrigatórios ausentes: {', '.join(sorted(missing))}")

    if not isinstance(data["cliente_id"], str) or not data["cliente_id"].strip():
        abort(400, description="cliente_id inválido")

    if not isinstance(data["endereco_entrega_id"], str) or not data["endereco_entrega_id"].strip():
        abort(400, description="endereco_entrega_id inválido")

    itens = data["itens"]
    if not isinstance(itens, list) or len(itens) == 0:
        abort(400, description="itens deve ser uma lista não vazia")

    for idx, it in enumerate(itens):
        if not isinstance(it, dict):
            abort(400, description=f"Item {idx} inválido")
        if "item_menu_id" not in it or not isinstance(it["item_menu_id"], str) or not it["item_menu_id"].strip():
            abort(400, description=f"Item {idx}: 'item_menu_id' obrigatório")
        if "quantidade" not in it:
            abort(400, description=f"Item {idx}: 'quantidade' obrigatório")
        try:
            q = int(it["quantidade"])
            if q <= 0:
                raise ValueError
        except Exception:
            abort(400, description=f"Item {idx}: 'quantidade' deve ser inteiro > 0")

    if "taxa_entrega_cents" in data:
        try:
            t = int(data["taxa_entrega_cents"])
            if t < 0:
                raise ValueError
        except Exception:
            abort(400, description="'taxa_entrega_cents' deve ser inteiro >= 0")

def validate_status_payload(data: dict):
    """
    PATCH /pedidos/{id}/status
    Obrigatório:
      - status (um dos ALLOWED_STATUS)
    """
    if not isinstance(data, dict) or "status" not in data:
        abort(400, description="Campo obrigatório: status")
    st = data["status"]
    if st not in ALLOWED_STATUS:
        abort(400, description=f"Status inválido. Use: {', '.join(sorted(ALLOWED_STATUS))}")



def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    # Swagger básico
    app.config["SWAGGER"] = {
        "title": "Pizzaria API (MVP)",
        "uiversion": 3
    }
    swagger_template = {
        "info": {
            "title": "Pizzaria API (MVP)",
            "description": "API para catálogo (menu) e pedidos. MVP com Flask + SQLite + Swagger.",
            "version": "0.1.0"
        }
    }
    Swagger(app, template=swagger_template)

    register_error_handlers(app)

    # Config de estáticos (assets)
    PUBLIC_DIR = os.getenv("PUBLIC_DIR", "/app/public")
    ASSETS_DIR = os.path.join(PUBLIC_DIR, "assets")

    app.register_blueprint(entrega_bp)
    
    @app.get("/health")
    def health():
        """
        Healthcheck
        ---
        tags:
          - Infra
        responses:
          200:
            description: OK
        """
        return jsonify(status="ok")

    @app.get("/assets/<path:filename>")
    def serve_assets(filename: str):
        """
        Servir arquivos estáticos do diretório /assets
        ---
        tags:
          - Infra
        parameters:
          - in: path
            name: filename
            schema:
              type: string
            required: true
        responses:
          200:
            description: Arquivo estático
        """
        return send_from_directory(ASSETS_DIR, filename)

    @app.get("/menu")
    def get_menu():
        """
        Listar itens do menu
        ---
        tags:
          - Menu
        summary: Listar itens do menu
        description: Retorna a lista de itens do menu com campos principais.
        responses:
          200:
            description: Lista de itens do menu
            schema:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  nome:
                    type: string
                  categoria:
                    type: string
                    enum:
                      - entrada
                      - pizza
                      - sobremesa
                      - bebida
                  descricao:
                    type: string
                  ingredientes:
                    type: string
                    description: 'JSON em string (ex.: ["Mussarela","Tomate"])'
                  preco_cents:
                    type: integer
                  imagem:
                    type: string
                  disponivel:
                    type: integer
                  criado_em:
                    type: string
        """
        with get_conn(readonly=True) as conn:
            rows = conn.execute("""
                SELECT id, nome, categoria, descricao, ingredientes,
                       preco_cents, imagem, disponivel, criado_em
                FROM menu
                ORDER BY categoria, nome
            """).fetchall()
        return jsonify(rows)
    
    @app.get("/menu/<string:item_id>")
    def get_menu_item(item_id: str):
        """
        Obter item específico do menu
        ---
        tags:
          - Menu
        parameters:
          - in: path
            name: item_id
            type: string
            required: true
        responses:
          200:
            description: Item encontrado
            schema:
              type: object
              properties:
                id: {type: string}
                nome: {type: string}
                categoria:
                  type: string
                  enum: [entrada, pizza, sobremesa, bebida]
                descricao: {type: string}
                ingredientes:
                  type: string
                  description: 'JSON em string (ex.: ["Mussarela","Tomate"])'
                preco_cents: {type: integer}
                imagem: {type: string}
                disponivel: {type: integer}
                criado_em: {type: string}
          404:
            description: Não encontrado
        """
        with get_conn(readonly=True) as conn:
            row = conn.execute("""
                SELECT id, nome, categoria, descricao, ingredientes,
                       preco_cents, imagem, disponivel, criado_em
                FROM menu
                WHERE id = ?
            """, (item_id,)).fetchone()
        if not row:
            abort(404, description="Item não encontrado")
        return jsonify(row)

    @app.post("/menu")
    def create_menu_item():
        """
        Criar item do menu
        ---
        tags:
          - Menu
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [id, nome, categoria, preco_cents]
              properties:
                id: {type: string}
                nome: {type: string}
                categoria:
                  type: string
                  enum: [entrada, pizza, sobremesa, bebida]
                descricao: {type: string}
                ingredientes:
                  type: string
                  description: 'JSON em string (ex.: ["Mussarela","Tomate"])'
                preco_cents: {type: integer}
                imagem: {type: string}
                disponivel:
                  type: integer
                  description: '1=true, 0=false (default=1)'
        responses:
          201:
            description: Criado
          400:
            description: Requisição inválida
          409:
            description: Conflito (id já existe)
        """
        data = request.get_json(silent=True) or {}
        validate_menu_payload(data, partial=False)

        payload = {
            "id": data["id"].strip(),
            "nome": data["nome"].strip(),
            "categoria": data["categoria"],
            "descricao": data.get("descricao"),
            "ingredientes": data.get("ingredientes"),
            "preco_cents": int(data["preco_cents"]),
            "imagem": data.get("imagem"),
            "disponivel": int(data.get("disponivel", 1)),
        }

        with get_conn(readonly=False) as conn:
            # checar existência
            exists = conn.execute("SELECT 1 FROM menu WHERE id = ?", (payload["id"],)).fetchone()
            if exists:
                abort(409, description="Já existe um item com esse id")

            conn.execute("""
                INSERT INTO menu (id, nome, categoria, descricao, ingredientes,
                                  preco_cents, imagem, disponivel)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload["id"], payload["nome"], payload["categoria"], payload["descricao"],
                payload["ingredientes"], payload["preco_cents"], payload["imagem"], payload["disponivel"]
            ))
            conn.commit()

            row = conn.execute("""
                SELECT id, nome, categoria, descricao, ingredientes,
                       preco_cents, imagem, disponivel, criado_em
                FROM menu WHERE id = ?
            """, (payload["id"],)).fetchone()

        return jsonify(row), 201

    @app.put("/menu/<string:item_id>")
    def replace_menu_item(item_id: str):
        """
        Substituir (PUT) um item do menu
        ---
        tags:
          - Menu
        parameters:
          - in: path
            name: item_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [id, nome, categoria, preco_cents]
              properties:
                id: {type: string}
                nome: {type: string}
                categoria:
                  type: string
                  enum: [entrada, pizza, sobremesa, bebida]
                descricao: {type: string}
                ingredientes:
                  type: string
                  description: 'JSON em string (ex.: ["Mussarela","Tomate"])'
                preco_cents: {type: integer}
                imagem: {type: string}
                disponivel: {type: integer}
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Não encontrado
        """
        data = request.get_json(silent=True) or {}
        validate_menu_payload(data, partial=False)

        # o id do payload DEVE bater com o path (boa prática para PUT)
        if data["id"].strip() != item_id:
            abort(400, description="id do corpo deve ser igual ao id do path")

        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM menu WHERE id = ?", (item_id,)).fetchone()
            if not found:
                abort(404, description="Item não encontrado")

            conn.execute("""
                UPDATE menu
                SET nome = ?, categoria = ?, descricao = ?, ingredientes = ?,
                    preco_cents = ?, imagem = ?, disponivel = ?
                WHERE id = ?
            """, (
                data["nome"].strip(),
                data["categoria"],
                data.get("descricao"),
                data.get("ingredientes"),
                int(data["preco_cents"]),
                data.get("imagem"),
                int(data.get("disponivel", 1)),
                item_id
            ))
            conn.commit()

            row = conn.execute("""
                SELECT id, nome, categoria, descricao, ingredientes,
                       preco_cents, imagem, disponivel, criado_em
                FROM menu WHERE id = ?
            """, (item_id,)).fetchone()

        return jsonify(row)
    
    @app.patch("/menu/<string:item_id>")
    def patch_menu_item(item_id: str):
        """
        Atualizar parcialmente (PATCH) um item do menu
        ---
        tags:
          - Menu
        parameters:
          - in: path
            name: item_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                id: {type: string, description: 'Se enviar, deve bater com item_id'}
                nome: {type: string}
                categoria:
                  type: string
                  enum: [entrada, pizza, sobremesa, bebida]
                descricao: {type: string}
                ingredientes:
                  type: string
                  description: 'JSON em string (ex.: ["Mussarela","Tomate"])'
                preco_cents: {type: integer}
                imagem: {type: string}
                disponivel: {type: integer}
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Não encontrado
        """
        data = request.get_json(silent=True) or {}
        validate_menu_payload(data, partial=True)

        if "id" in data and data["id"].strip() != item_id:
            abort(400, description="Se enviar 'id' no corpo, deve ser igual ao id do path")

        with get_conn(readonly=False) as conn:
            row = conn.execute("SELECT * FROM menu WHERE id = ?", (item_id,)).fetchone()
            if not row:
                abort(404, description="Item não encontrado")

            # constrói o update dinamicamente
            fields = []
            values = []

            def add(field, value, transform=None):
                if field in data:
                    fields.append(f"{field} = ?")
                    values.append(transform(data[field]) if transform else data[field])

            add("nome", data.get("nome"), lambda v: v.strip())
            add("categoria", data.get("categoria"))
            add("descricao", data.get("descricao"))
            add("ingredientes", data.get("ingredientes"))
            add("preco_cents", data.get("preco_cents"), lambda v: int(v))
            add("imagem", data.get("imagem"))
            add("disponivel", data.get("disponivel"), lambda v: int(v))

            if not fields:
                return jsonify(row)  # nada a atualizar

            sql = f"UPDATE menu SET {', '.join(fields)} WHERE id = ?"
            values.append(item_id)

            conn.execute(sql, tuple(values))
            conn.commit()

            updated = conn.execute("""
                SELECT id, nome, categoria, descricao, ingredientes,
                       preco_cents, imagem, disponivel, criado_em
                FROM menu WHERE id = ?
            """, (item_id,)).fetchone()

        return jsonify(updated)

    @app.delete("/menu/<string:item_id>")
    def delete_menu_item(item_id: str):
        """
        Remover item do menu
        ---
        tags:
          - Menu
        parameters:
          - in: path
            name: item_id
            type: string
            required: true
        responses:
          204:
            description: Removido
          404:
            description: Não encontrado
        """
        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM menu WHERE id = ?", (item_id,)).fetchone()
            if not found:
                abort(404, description="Item não encontrado")
            conn.execute("DELETE FROM menu WHERE id = ?", (item_id,))
            conn.commit()

        return ("", 204)
    
    @app.get("/cliente/<string:cliente_id>")
    def get_cliente(cliente_id: str):
        """
        Obter cliente pelo id
        ---
        tags:
          - Cliente
        parameters:
          - in: path
            name: cliente_id
            type: string
            required: true
        responses:
          200:
            description: Cliente encontrado
            schema:
              type: object
              properties:
                id: {type: string}
                nome: {type: string}
                telefone: {type: string}
                email: {type: string}
                criado_em: {type: string}
          404:
            description: Não encontrado
        """
        with get_conn(readonly=True) as conn:
            row = conn.execute("""
                SELECT id, nome, telefone, email, criado_em
                FROM cliente
                WHERE id = ?
            """, (cliente_id,)).fetchone()
        if not row:
            abort(404, description="Cliente não encontrado")
        return jsonify(row)
    
    @app.get("/cliente")
    def list_clientes():
        """
        Listar clientes
        ---
        tags:
          - Cliente
        responses:
          200:
            description: Lista de clientes
            schema:
              type: array
              items:
                type: object
                properties:
                  id: {type: string}
                  nome: {type: string}
                  telefone: {type: string}
                  email: {type: string}
                  criado_em: {type: string}
        """
        with get_conn(readonly=True) as conn:
            rows = conn.execute("""
                SELECT id, nome, telefone, email, criado_em
                FROM cliente
                ORDER BY criado_em DESC
            """).fetchall()
        return jsonify(rows)
    
    @app.post("/cliente")
    def create_cliente():
        """
        Criar cliente
        ---
        tags:
          - Cliente
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [nome]
              properties:
                nome: {type: string}
                telefone: {type: string}
                email: {type: string}
        responses:
            201:
              description: Criado
            400:
              description: Requisição inválida
            409:
              description: Conflito (email já existe)
        """
        data = request.get_json(silent=True) or {}
        validate_cliente_payload(data, partial=False)

        nome = data["nome"].strip()
        telefone = (data.get("telefone") or None)
        email = (data.get("email").strip() if data.get("email") else None)

        with get_conn(readonly=False) as conn:
            # se email veio, verificar duplicidade
            if email:
                exists = conn.execute("SELECT 1 FROM cliente WHERE email = ?", (email,)).fetchone()
                if exists:
                    usuario = conn.execute("""
                        SELECT id, nome, telefone, email, criado_em
                        FROM cliente
                        WHERE email = ?
                    """, (email,)).fetchone()

                    return jsonify(usuario), 409


            # gerar id (usando mesmo padrão do schema SQLite: lower(hex(randomblob(16))))
            new_id = conn.execute("SELECT lower(hex(randomblob(16))) AS id").fetchone()["id"]
            conn.execute("""
                INSERT INTO cliente (id, nome, telefone, email)
                VALUES (?, ?, ?, ?)
            """, (new_id, nome, telefone, email))
            conn.commit()

            row = conn.execute("""
                SELECT id, nome, telefone, email, criado_em
                FROM cliente
                WHERE id = ?
            """, (new_id,)).fetchone()

        return jsonify(row), 201
    
    @app.put("/cliente/<string:cliente_id>")
    def replace_cliente(cliente_id: str):
        """
        Substituir (PUT) cliente
        ---
        tags:
          - Cliente
        parameters:
          - in: path
            name: cliente_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [nome]
              properties:
                nome: {type: string}
                telefone: {type: string}
                email: {type: string}
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Não encontrado
          409:
            description: Conflito (email já existe)
        """
        data = request.get_json(silent=True) or {}
        validate_cliente_payload(data, partial=False)

        nome = data["nome"].strip()
        telefone = (data.get("telefone") or None)
        email = (data.get("email").strip() if data.get("email") else None)

        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT id, email FROM cliente WHERE id = ?", (cliente_id,)).fetchone()
            if not found:
                abort(404, description="Cliente não encontrado")

            if email:
                # se email mudou, checar unicidade
                if found["email"] != email:
                    exists = conn.execute("SELECT 1 FROM cliente WHERE email = ?", (email,)).fetchone()
                    if exists:
                        usuario = conn.execute("""
                            SELECT id, nome, telefone, email, criado_em
                            FROM cliente
                            WHERE email = ?
                        """, (email,)).fetchone()

                        return jsonify(usuario), 409

            conn.execute("""
                UPDATE cliente
                SET nome = ?, telefone = ?, email = ?
                WHERE id = ?
            """, (nome, telefone, email, cliente_id))
            conn.commit()

            row = conn.execute("""
                SELECT id, nome, telefone, email, criado_em
                FROM cliente
                WHERE id = ?
            """, (cliente_id,)).fetchone()

        return jsonify(row)
    
    @app.patch("/cliente/<string:cliente_id>")
    def patch_cliente(cliente_id: str):
        """
        Atualizar parcialmente (PATCH) cliente
        ---
        tags:
          - Cliente
        parameters:
          - in: path
            name: cliente_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                nome: {type: string}
                telefone: {type: string}
                email: {type: string}
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Não encontrado
          409:
            description: Conflito (email já existe)
        """
        data = request.get_json(silent=True) or {}
        validate_cliente_payload(data, partial=True)

        with get_conn(readonly=False) as conn:
            row = conn.execute("SELECT id, nome, telefone, email, criado_em FROM cliente WHERE id = ?", (cliente_id,)).fetchone()
            if not row:
                abort(404, description="Cliente não encontrado")

            nome = row["nome"]
            telefone = row["telefone"]
            email_original = row["email"]
            email_novo = email_original

            if "nome" in data and isinstance(data["nome"], str) and data["nome"].strip():
                nome = data["nome"].strip()

            if "telefone" in data:
                telefone = (data["telefone"] if data["telefone"] else None)

            if "email" in data:
                if data["email"] is None or data["email"] == "":
                    email_novo = None
                else:
                    email_novo = data["email"].strip()
                    if email_novo != email_original:
                        exists = conn.execute("SELECT 1 FROM cliente WHERE email = ?", (email_novo,)).fetchone()
                        if exists:
                            usuario = conn.execute("""
                                SELECT id, nome, telefone, email, criado_em
                                FROM cliente
                                WHERE email = ?
                            """, (email_novo,)).fetchone()

                            return jsonify(usuario), 409

            conn.execute("""
                UPDATE cliente
                SET nome = ?, telefone = ?, email = ?
                WHERE id = ?
            """, (nome, telefone, email_novo, cliente_id))
            conn.commit()

            updated = conn.execute("""
                SELECT id, nome, telefone, email, criado_em
                FROM cliente
                WHERE id = ?
            """, (cliente_id,)).fetchone()

        return jsonify(updated)
    
    @app.delete("/cliente/<string:cliente_id>")
    def delete_cliente(cliente_id: str):
        """
        Remover cliente
        ---
        tags:
          - Cliente
        parameters:
          - in: path
            name: cliente_id
            type: string
            required: true
        responses:
          204:
            description: Removido
          404:
            description: Não encontrado
        """
        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM cliente WHERE id = ?", (cliente_id,)).fetchone()
            if not found:
                abort(404, description="Cliente não encontrado")

            # OBS: ON DELETE CASCADE está nos endereços;
            # Se no futuro quiser impedir delete caso haja pedidos, validamos aqui antes.
            conn.execute("DELETE FROM cliente WHERE id = ?", (cliente_id,))
            conn.commit()

        return ("", 204)
    
    @app.get("/enderecos")
    def list_enderecos():
        """
        Listar endereços
        ---
        tags:
          - Enderecos
        parameters:
          - in: query
            name: cliente_id
            type: string
            required: false
            description: Se informado, filtra por cliente
        responses:
          200:
            description: Lista de endereços
            schema:
              type: array
              items:
                type: object
                properties:
                  id: {type: string}
                  cliente_id: {type: string}
                  apelido: {type: string}
                  logradouro: {type: string}
                  numero: {type: string}
                  complemento: {type: string}
                  bairro: {type: string}
                  cidade: {type: string}
                  estado: {type: string}
                  cep: {type: string}
                  latitude: {type: number}
                  longitude: {type: number}
                  criado_em: {type: string}
        """
        cliente_id = request.args.get("cliente_id")
        with get_conn(readonly=True) as conn:
            if cliente_id:
                rows = conn.execute("""
                    SELECT id, cliente_id, apelido, logradouro, numero, complemento,
                           bairro, cidade, estado, cep, latitude, longitude, criado_em
                    FROM enderecos
                    WHERE cliente_id = ?
                    ORDER BY criado_em DESC
                """, (cliente_id,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT id, cliente_id, apelido, logradouro, numero, complemento,
                           bairro, cidade, estado, cep, latitude, longitude, criado_em
                    FROM enderecos
                    ORDER BY criado_em DESC
                """).fetchall()
        return jsonify(rows)
    
    @app.get("/enderecos/<string:endereco_id>")
    def get_endereco(endereco_id: str):
        """
        Obter endereço pelo id
        ---
        tags:
          - Enderecos
        parameters:
          - in: path
            name: endereco_id
            type: string
            required: true
        responses:
          200:
            description: Endereço encontrado
            schema:
              type: object
              properties:
                id: {type: string}
                cliente_id: {type: string}
                apelido: {type: string}
                logradouro: {type: string}
                numero: {type: string}
                complemento: {type: string}
                bairro: {type: string}
                cidade: {type: string}
                estado: {type: string}
                cep: {type: string}
                latitude: {type: number}
                longitude: {type: number}
                criado_em: {type: string}
          404:
            description: Não encontrado
        """
        with get_conn(readonly=True) as conn:
            row = conn.execute("""
                SELECT id, cliente_id, apelido, logradouro, numero, complemento,
                       bairro, cidade, estado, cep, latitude, longitude, criado_em
                FROM enderecos
                WHERE id = ?
            """, (endereco_id,)).fetchone()
        if not row:
            abort(404, description="Endereço não encontrado")
        return jsonify(row)
    
    @app.post("/enderecos")
    def create_endereco():
        """
        Criar endereço
        ---
        tags:
          - Enderecos
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [cliente_id, logradouro, cidade, estado]
              properties:
                cliente_id: {type: string}
                apelido: {type: string}
                logradouro: {type: string}
                numero: {type: string}
                complemento: {type: string}
                bairro: {type: string}
                cidade: {type: string}
                estado: {type: string}
                cep: {type: string}
                latitude: {type: number}
                longitude: {type: number}
        responses:
          201:
            description: Criado
          400:
            description: Requisição inválida
          404:
            description: Cliente não encontrado
        """
        data = request.get_json(silent=True) or {}
        validate_endereco_payload(data, partial=False)

        with get_conn(readonly=False) as conn:
            # validar cliente existente (FK)
            cli = conn.execute("SELECT 1 FROM cliente WHERE id = ?", (data["cliente_id"],)).fetchone()
            if not cli:
                abort(404, description="Cliente não encontrado")

            new_id = conn.execute("SELECT lower(hex(randomblob(16))) AS id").fetchone()["id"]

            conn.execute("""
                INSERT INTO enderecos (id, cliente_id, apelido, logradouro, numero, complemento,
                                       bairro, cidade, estado, cep, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_id,
                data["cliente_id"],
                data.get("apelido"),
                data["logradouro"],
                data.get("numero"),
                data.get("complemento"),
                data.get("bairro"),
                data["cidade"],
                data["estado"],
                data.get("cep"),
                float(data["latitude"]) if data.get("latitude") is not None else None,
                float(data["longitude"]) if data.get("longitude") is not None else None,
            ))
            conn.commit()

            row = conn.execute("""
                SELECT id, cliente_id, apelido, logradouro, numero, complemento,
                       bairro, cidade, estado, cep, latitude, longitude, criado_em
                FROM enderecos WHERE id = ?
            """, (new_id,)).fetchone()

        return jsonify(row), 201
    
    @app.put("/enderecos/<string:endereco_id>")
    def replace_endereco(endereco_id: str):
        """
        Substituir (PUT) endereço
        ---
        tags:
          - Enderecos
        parameters:
          - in: path
            name: endereco_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [cliente_id, logradouro, cidade, estado]
              properties:
                cliente_id: {type: string}
                apelido: {type: string}
                logradouro: {type: string}
                numero: {type: string}
                complemento: {type: string}
                bairro: {type: string}
                cidade: {type: string}
                estado: {type: string}
                cep: {type: string}
                latitude: {type: number}
                longitude: {type: number}
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Endereço ou cliente não encontrado
        """
        data = request.get_json(silent=True) or {}
        validate_endereco_payload(data, partial=False)

        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM enderecos WHERE id = ?", (endereco_id,)).fetchone()
            if not found:
                abort(404, description="Endereço não encontrado")

            cli = conn.execute("SELECT 1 FROM cliente WHERE id = ?", (data["cliente_id"],)).fetchone()
            if not cli:
                abort(404, description="Cliente não encontrado")

            conn.execute("""
                UPDATE enderecos
                SET cliente_id = ?, apelido = ?, logradouro = ?, numero = ?, complemento = ?,
                    bairro = ?, cidade = ?, estado = ?, cep = ?, latitude = ?, longitude = ?
                WHERE id = ?
            """, (
                data["cliente_id"],
                data.get("apelido"),
                data["logradouro"],
                data.get("numero"),
                data.get("complemento"),
                data.get("bairro"),
                data["cidade"],
                data["estado"],
                data.get("cep"),
                float(data["latitude"]) if data.get("latitude") is not None else None,
                float(data["longitude"]) if data.get("longitude") is not None else None,
                endereco_id
            ))
            conn.commit()

            row = conn.execute("""
                SELECT id, cliente_id, apelido, logradouro, numero, complemento,
                       bairro, cidade, estado, cep, latitude, longitude, criado_em
                FROM enderecos WHERE id = ?
            """, (endereco_id,)).fetchone()

        return jsonify(row)
    
    @app.patch("/enderecos/<string:endereco_id>")
    def patch_endereco(endereco_id: str):
        """
        Atualizar parcialmente (PATCH) endereço
        ---
        tags:
          - Enderecos
        parameters:
          - in: path
            name: endereco_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              properties:
                cliente_id: {type: string}
                apelido: {type: string}
                logradouro: {type: string}
                numero: {type: string}
                complemento: {type: string}
                bairro: {type: string}
                cidade: {type: string}
                estado: {type: string}
                cep: {type: string}
                latitude: {type: number}
                longitude: {type: number}
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Não encontrado
        """
        data = request.get_json(silent=True) or {}
        validate_endereco_payload(data, partial=True)

        with get_conn(readonly=False) as conn:
            row = conn.execute("""
                SELECT id, cliente_id, apelido, logradouro, numero, complemento, bairro,
                       cidade, estado, cep, latitude, longitude, criado_em
                FROM enderecos WHERE id = ?
            """, (endereco_id,)).fetchone()
            if not row:
                abort(404, description="Endereço não encontrado")

    @app.delete("/enderecos/<string:endereco_id>")
    def delete_endereco(endereco_id: str):
        """
        Remover endereço
        ---
        tags:
          - Enderecos
        parameters:
          - in: path
            name: endereco_id
            type: string
            required: true
        responses:
          204:
            description: Removido
          404:
            description: Não encontrado
        """
        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM enderecos WHERE id = ?", (endereco_id,)).fetchone()
            if not found:
                abort(404, description="Endereço não encontrado")

            conn.execute("DELETE FROM enderecos WHERE id = ?", (endereco_id,))
            conn.commit()

        return ("", 204)
    
    
    @app.post("/pedidos")
    def create_pedido():
      """
      Criar pedido (com itens)
      ---
      tags:
        - Pedidos
      parameters:
        - in: body
          name: body
          required: true
          schema:
            type: object
            required:
              - cliente_id
              - endereco_entrega_id
              - itens
              - tempo_estimado_min
              - tempo_estimado_max
            properties:
              cliente_id:
                type: string
              endereco_entrega_id:
                type: string
              tempo_estimado_min:
                type: integer
                example: 30
              tempo_estimado_max:
                type: integer
                example: 35
              observacoes:
                type: string
              taxa_entrega_cents:
                type: integer
              itens:
                type: array
                items:
                  type: object
                  required: [item_menu_id, quantidade]
                  properties:
                    item_menu_id:
                      type: string
                    quantidade:
                      type: integer
      responses:
        201:
          description: Pedido criado
        400:
          description: Requisição inválida
        404:
          description: Cliente/Endereço/Item do menu não encontrado
      """

      data = request.get_json(silent=True) or {}
      validate_pedido_payload(data)

      # ✅ novos campos obrigatórios (vindos do cálculo de entrega)
      tempo_min = data.get("tempo_estimado_min")
      tempo_max = data.get("tempo_estimado_max")

      if tempo_min is None or tempo_max is None:
          abort(400, description="Tempo estimado é obrigatório")

      with get_conn(readonly=False) as conn:
          # FK: cliente deve existir
          cli = conn.execute(
              "SELECT 1 FROM cliente WHERE id = ?",
              (data["cliente_id"],)
          ).fetchone()
          if not cli:
              abort(404, description="Cliente não encontrado")

          # FK: endereço deve existir
          end = conn.execute(
              "SELECT 1 FROM enderecos WHERE id = ?",
              (data["endereco_entrega_id"],)
          ).fetchone()
          if not end:
              abort(404, description="Endereço de entrega não encontrado")

          # Carregar preços do menu
          ids = [it["item_menu_id"] for it in data["itens"]]
          placeholders = ",".join(["?"] * len(ids))

          menu_rows = conn.execute(
              f"SELECT id, preco_cents FROM menu WHERE id IN ({placeholders})",
              tuple(ids)
          ).fetchall()

          preco_map = {r["id"]: int(r["preco_cents"]) for r in menu_rows}

          not_found = [i for i in ids if i not in preco_map]
          if not_found:
              abort(404, description=f"Itens do menu não encontrados: {', '.join(not_found)}")

          # Gerar ID do pedido
          pedido_id = conn.execute(
              "SELECT lower(hex(randomblob(16))) AS id"
          ).fetchone()["id"]

          # Calcular valores
          subtotal = 0
          itens_to_insert = []

          for it in data["itens"]:
              item_id = it["item_menu_id"]
              qtd = int(it["quantidade"])
              preco_unit = preco_map[item_id]
              total_item = preco_unit * qtd
              subtotal += total_item

              itens_to_insert.append((
                  pedido_id,
                  item_id,
                  qtd,
                  preco_unit,
                  total_item
              ))

          taxa = int(data.get("taxa_entrega_cents", 0))
          total = subtotal + taxa

          # Inserir pedido (agora com tempo estimado)
          conn.execute("""
              INSERT INTO pedidos (
                id,
                cliente_id,
                endereco_entrega_id,
                status,
                observacoes,
                subtotal_cents,
                taxa_entrega_cents,
                total_cents,
                tempo_estimado_min,
                tempo_estimado_max
              )
              VALUES (?, ?, ?, 'criado', ?, ?, ?, ?, ?, ?)
          """, (
              pedido_id,
              data["cliente_id"],
              data["endereco_entrega_id"],
              data.get("observacoes"),
              subtotal,
              taxa,
              total,
              tempo_min,
              tempo_max
          ))

          # Inserir itens
          conn.executemany("""
              INSERT INTO itens_pedido (
                pedido_id,
                item_menu_id,
                quantidade,
                preco_unit_cents,
                total_cents
              )
              VALUES (?, ?, ?, ?, ?)
          """, itens_to_insert)

          conn.commit()

          # Retorno detalhado
          pedido = conn.execute("""
              SELECT
                id,
                cliente_id,
                endereco_entrega_id,
                status,
                observacoes,
                subtotal_cents,
                taxa_entrega_cents,
                total_cents,
                tempo_estimado_min,
                tempo_estimado_max,
                criado_em
              FROM pedidos
              WHERE id = ?
          """, (pedido_id,)).fetchone()

          itens = conn.execute("""
              SELECT
                item_menu_id,
                quantidade,
                preco_unit_cents,
                total_cents
              FROM itens_pedido
              WHERE pedido_id = ?
          """, (pedido_id,)).fetchall()

          return jsonify({
              "pedido": pedido,
              "itens": itens
          }), 201

    
    @app.get("/pedidos/<string:pedido_id>")
    def get_pedido(pedido_id: str):
        """
        Obter pedido por id (detalhe)
        ---
        tags:
          - Pedidos
        parameters:
          - in: path
            name: pedido_id
            type: string
            required: true
        responses:
          200:
            description: OK
          404:
            description: Não encontrado
        """
        with get_conn(readonly=True) as conn:
            pedido = conn.execute("""
                SELECT                 
                id,
                cliente_id,
                endereco_entrega_id,
                status,
                observacoes,
                subtotal_cents,
                taxa_entrega_cents,
                total_cents,
                tempo_estimado_min,
                tempo_estimado_max,
                criado_em
                FROM pedidos WHERE id = ?
            """, (pedido_id,)).fetchone()
            if not pedido:
                abort(404, description="Pedido não encontrado")

            itens = conn.execute("""
                SELECT id, pedido_id, item_menu_id, quantidade, preco_unit_cents, total_cents
                FROM itens_pedido WHERE pedido_id = ?
            """, (pedido_id,)).fetchall()

        return jsonify({"pedido": pedido, "itens": itens})
    
    @app.get("/pedidos")
    def list_pedidos():
        """
        Listar pedidos por cliente
        ---
        tags:
          - Pedidos
        parameters:
          - in: query
            name: cliente_id
            schema:
              type: string
            required: true
            description: ID do cliente para filtrar os pedidos
        responses:
          200:
            description: Lista de pedidos do cliente
            schema:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  cliente_id:
                    type: string
                  endereco_entrega_id:
                    type: string
                  status:
                    type: string
                  observacoes:
                    type: string
                    nullable: true
                  subtotal_cents:
                    type: integer
                  taxa_entrega_cents:
                    type: integer
                  total_cents:
                    type: integer
                  tempo_estimado_min:
                    type: integer
                  tempo_estimado_max:
                    type: integer
                  criado_em:
                    type: string
                  itens:
                    type: array
                    items:
                      type: object
                      properties:
                        item_menu_id:
                          type: string
                        quantidade:
                          type: integer
                        preco_unit_cents:
                          type: integer
                        total_cents:
                          type: integer
          400:
            description: Requisição inválida
        """

        cliente_id = request.args.get("cliente_id")

        with get_conn(readonly=True) as conn:
            pedidos = conn.execute("""
                SELECT
                  id,
                  cliente_id,
                  endereco_entrega_id,
                  status,
                  observacoes,
                  subtotal_cents,
                  taxa_entrega_cents,
                  total_cents,
                  tempo_estimado_min,
                  tempo_estimado_max,
                  criado_em
                FROM pedidos
                WHERE cliente_id = ?
                ORDER BY criado_em DESC
            """, (cliente_id,)).fetchall()

            resultado = []
            for p in pedidos:
                itens = conn.execute("""
                    SELECT
                      item_menu_id,
                      quantidade,
                      preco_unit_cents,
                      total_cents
                    FROM itens_pedido
                    WHERE pedido_id = ?
                """, (p["id"],)).fetchall()

                resultado.append({
                    **dict(p),
                    "itens": itens
                })

        return jsonify(resultado)

    
    @app.patch("/pedidos/<string:pedido_id>/status")
    def patch_pedido_status(pedido_id: str):
        """
        Atualizar status do pedido
        ---
        tags:
          - Pedidos
        parameters:
          - in: path
            name: pedido_id
            type: string
            required: true
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [status]
              properties:
                status:
                  type: string
                  enum: [criado, preparando, a_caminho, entregue, cancelado]
        responses:
          200:
            description: Atualizado
          400:
            description: Requisição inválida
          404:
            description: Não encontrado
        """
        data = request.get_json(silent=True) or {}
        validate_status_payload(data)

        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
            if not found:
                abort(404, description="Pedido não encontrado")

            conn.execute("UPDATE pedidos SET status = ? WHERE id = ?", (data["status"], pedido_id))
            conn.commit()

            pedido = conn.execute("""
                SELECT 
                id,
                cliente_id,
                endereco_entrega_id,
                status,
                observacoes,
                subtotal_cents,
                taxa_entrega_cents,
                total_cents,
                tempo_estimado_min,
                tempo_estimado_max,
                criado_em                
                FROM pedidos WHERE id = ?
            """, (pedido_id,)).fetchone()

        return jsonify(pedido)
    
    @app.delete("/pedidos/<string:pedido_id>")
    def delete_pedido(pedido_id: str):
        """
        Remover pedido
        ---
        tags:
          - Pedidos
        parameters:
          - in: path
            name: pedido_id
            type: string
            required: true
        responses:
          204:
            description: Removido
          404:
            description: Não encontrado
        """
        with get_conn(readonly=False) as conn:
            found = conn.execute("SELECT 1 FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
            if not found:
                abort(404, description="Pedido não encontrado")

            conn.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
            conn.commit()

        return ("", 204)

    return app

# Objeto WSGI
app = create_app()

if __name__ == "__main__":
    # Para rodar sem Docker (opcional):
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_RUN_PORT", "8000")))