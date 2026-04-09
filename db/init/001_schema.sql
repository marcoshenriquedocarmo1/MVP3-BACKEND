
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cliente (
  id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
  nome TEXT NOT NULL,
  telefone TEXT,
  email TEXT UNIQUE,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enderecos (
  id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
  cliente_id TEXT NOT NULL,
  apelido TEXT,
  logradouro TEXT NOT NULL,
  numero TEXT,
  complemento TEXT,
  bairro TEXT,
  cidade TEXT NOT NULL,
  estado TEXT NOT NULL,
  cep TEXT,
  latitude REAL,
  longitude REAL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (cliente_id) REFERENCES cliente(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS menu (
  id TEXT PRIMARY KEY NOT NULL, -- usaremos os ids fornecidos no JSON para facilitar o seed
  nome TEXT NOT NULL,
  categoria TEXT NOT NULL CHECK (categoria IN ('entrada','pizza','sobremesa','bebida')),
  descricao TEXT,
  ingredientes TEXT, -- JSON como string (ex.: ["Mussarela","Tomate"])
  preco_cents INTEGER NOT NULL CHECK (preco_cents >= 0),
  imagem TEXT, -- caminho relativo/public URL
  disponivel INTEGER NOT NULL DEFAULT 1,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pedidos (
  id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
  cliente_id TEXT,
  endereco_entrega_id TEXT,
  status TEXT NOT NULL DEFAULT 'criado',
  observacoes TEXT,
  subtotal_cents INTEGER NOT NULL DEFAULT 0,
  taxa_entrega_cents INTEGER NOT NULL DEFAULT 0,
  total_cents INTEGER NOT NULL DEFAULT 0,
  eta_minutos REAL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (cliente_id) REFERENCES cliente(id),
  FOREIGN KEY (endereco_entrega_id) REFERENCES enderecos(id)
);

CREATE TABLE IF NOT EXISTS itens_pedido (
  id TEXT PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
  pedido_id TEXT NOT NULL,
  item_menu_id TEXT NOT NULL,
  quantidade INTEGER NOT NULL CHECK (quantidade > 0),
  preco_unit_cents INTEGER NOT NULL CHECK (preco_unit_cents >= 0),
  total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
  FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
  FOREIGN KEY (item_menu_id) REFERENCES menu(id)
);

CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_enderecos_cliente ON enderecos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_itens_pedido_pedido ON itens_pedido(pedido_id);
