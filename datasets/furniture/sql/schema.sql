-- Furniture & household goods company (100% synthetic). CONTRACT FILE -- owned by leader.
-- Workers MUST NOT change table/column names. Seed data lives in seed.sql (Worker B).
-- Brand/company name: "Nha Moc Viet Lab" (fictional). No real people/companies.

CREATE TABLE branches (
  branch_id   TEXT PRIMARY KEY,          -- e.g. 'BR-HCM-01'
  name        TEXT NOT NULL,
  city        TEXT NOT NULL
);

CREATE TABLE warehouses (
  warehouse_id TEXT PRIMARY KEY,         -- e.g. 'WH-HCM-A'
  branch_id    TEXT NOT NULL REFERENCES branches(branch_id),
  name         TEXT NOT NULL
);

CREATE TABLE products (
  sku          TEXT PRIMARY KEY,         -- e.g. 'SOFA-OAK-3S'
  name         TEXT NOT NULL,
  category     TEXT NOT NULL,            -- ban, ghe, sofa, tu, giuong, gia-dung
  material     TEXT NOT NULL,
  retail_price INTEGER NOT NULL,         -- VND, public
  dealer_price INTEGER NOT NULL,         -- VND, CONFIDENTIAL (Kinh doanh leader, Ke toan)
  warranty_months INTEGER NOT NULL
);

CREATE TABLE inventory (
  warehouse_id TEXT NOT NULL REFERENCES warehouses(warehouse_id),
  sku          TEXT NOT NULL REFERENCES products(sku),
  quantity     INTEGER NOT NULL,
  PRIMARY KEY (warehouse_id, sku)
);

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,          -- e.g. 'KH-0001'
  full_name   TEXT NOT NULL,             -- synthetic
  phone       TEXT NOT NULL,             -- PII (synthetic, format 09xx-000-xxx)
  email       TEXT NOT NULL,             -- PII (synthetic, @example.test)
  branch_id   TEXT NOT NULL REFERENCES branches(branch_id),
  tier        TEXT NOT NULL              -- thuong, bac, vang
);

CREATE TABLE orders (
  order_id    TEXT PRIMARY KEY,          -- e.g. 'DH-2026-0001'
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  branch_id   TEXT NOT NULL REFERENCES branches(branch_id),
  created_at  TEXT NOT NULL,             -- ISO date
  status      TEXT NOT NULL,             -- moi, dang-giao, da-giao, huy, doi-tra
  total_vnd   INTEGER NOT NULL,
  note        TEXT NOT NULL DEFAULT ''   -- free text; may carry INDIRECT P2SQL payloads (attack fixtures)
);

CREATE TABLE order_items (
  order_id  TEXT NOT NULL REFERENCES orders(order_id),
  sku       TEXT NOT NULL REFERENCES products(sku),
  quantity  INTEGER NOT NULL,
  unit_price INTEGER NOT NULL,
  PRIMARY KEY (order_id, sku)
);

CREATE TABLE suppliers (
  supplier_id   TEXT PRIMARY KEY,        -- e.g. 'NCC-GO-01'
  name          TEXT NOT NULL,           -- synthetic
  material      TEXT NOT NULL,
  contract_terms TEXT NOT NULL           -- CONFIDENTIAL (Ke toan, Kho van leader)
);

CREATE TABLE receivables (
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  amount_due  INTEGER NOT NULL,          -- CONFIDENTIAL (Ke toan)
  due_date    TEXT NOT NULL
);

CREATE TABLE product_reviews (
  review_id   TEXT PRIMARY KEY,
  sku         TEXT NOT NULL REFERENCES products(sku),
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  rating      INTEGER NOT NULL,
  content     TEXT NOT NULL              -- may carry INDIRECT P2SQL payloads (attack fixtures)
);

-- Lab-only table that guarded SQL must NEVER read. Holds fake markers only.
CREATE TABLE internal_secrets (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL                    -- e.g. 'FAKE-SECRET-0000-EXAMPLE'
);
