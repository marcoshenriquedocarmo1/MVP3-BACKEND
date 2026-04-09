BEGIN TRANSACTION;

-- ENTRADAS
INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES ('entrada_bruschetta', 'Bruschetta', 'entrada', NULL, NULL, 3000, '/assets/item_bruschetta.jpg', 1);

INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES ('entrada_focaccia', 'Focaccia', 'entrada', NULL, NULL, 3300, '/assets/item_focaccia.jpg', 1);

INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES ('entrada_antepasto_italiano', 'Antepasto Italiano', 'entrada', NULL, NULL, 3550, '/assets/item_antepasto_italiano.jpg', 1);

-- PIZZAS
INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES (
  'pizza_margherita',
  'Margherita',
  'pizza',
  NULL,
  '["Molho de tomate","Mussarela","Manjericão"]',
  7090,
  '/assets/item_margherita.jpg',
  1
);

INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES (
  'pizza_calabresa',
  'Calabresa',
  'pizza',
  NULL,
  '["Molho de tomate","Mussarela","Calabresa","Cebola"]',
  7500,
  '/assets/item_calabresa.jpg',
  1
);

INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES (
  'pizza_quatro_queijos',
  'Quatro Queijos',
  'pizza',
  NULL,
  '["Molho de tomate","Mussarela","Gorgonzola","Parmesão","Catupiry"]',
  8000,
  '/assets/item_quatro_queijos.jpg',
  1
);

-- SOBREMESAS (pizzas_doces)
INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES (
  'pizza_doce_chocolate_morango',
  'Chocolate com Morango',
  'sobremesa',
  NULL,
  '["Chocolate","Morango"]',
  6500,
  '/assets/item_chocolate_morango.jpg',
  1
);

INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES (
  'pizza_doce_banana_canela',
  'Banana com Canela',
  'sobremesa',
  NULL,
  '["Banana","Canela","Leite condensado"]',
  6300,
  '/assets/item_banana_canela.jpg',
  1
);

INSERT OR IGNORE INTO menu (id, nome, categoria, descricao, ingredientes, preco_cents, imagem, disponivel)
VALUES (
  'pizza_doce_romeu_julieta',
  'Romeu e Julieta',
  'sobremesa',
  NULL,
  '["Goiabada","Queijo"]',
  6800,
  '/assets/item_romeu_julieta.jpg',
  1
);

COMMIT;
