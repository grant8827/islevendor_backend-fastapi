-- Run ONCE, by a database administrator, against the marketplace database.
-- Gives the AI service (backend-fastapi) its own login: it reads the
-- catalogue and order activity it needs, and stores its own results in the
-- `ai` schema. It cannot see personal, bank or payment data, and cannot
-- change any marketplace table.
--
--   psql "$ADMIN_DATABASE_URL" -v ai_password="'<generated password>'" -f db/setup/001_ai_role.sql
--
-- Generate the password with `openssl rand -hex 32`; keep it only in the
-- AI service's DATABASE_URL. Grant more as each new AI feature needs it.

create role islevendor_ai login password :ai_password;

-- Its own schema for results (recommendations, embeddings, scores...).
create schema if not exists ai authorization islevendor_ai;
revoke all on schema ai from public;

grant usage on schema public to islevendor_ai;

-- Catalogue, ratings and what was ordered: everything in these tables.
grant select on public.master_products, public.shop_products, public.store_listings,
                public.product_ratings, public.order_items
    to islevendor_ai;

-- Orders without the delivery address, delivery photo or payment reference.
grant select (id, customer_id, reseller_store_id, warehouse_id, driver_id, shop_id,
              store_listing_id, shop_product_id, quantity, total_paid_jmd, status,
              delivery_method, created_at, delivered_at, checkout_group_id)
    on public.orders to islevendor_ai;

-- Sellers: names, places and categories only (no bank, tax or ID-document columns).
grant select (id, shop_name, slug, parish, vendor_category, primary_product_category, applicant_status)
    on public.shops to islevendor_ai;
grant select (id, name, parish, town, coverage_parishes, applicant_status)
    on public.warehouses to islevendor_ai;
grant select (id, store_name, slug, parish, reseller_type, primary_sales_channel, target_categories, applicant_status)
    on public.reseller_stores to islevendor_ai;
