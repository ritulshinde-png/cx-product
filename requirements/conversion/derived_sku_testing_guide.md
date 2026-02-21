# Derived SKU — Testing Guide

## 1. Feature Overview

**Derived SKUs** are Item Codes that exist as first-class products in the catalog but do not maintain their own inventory. Inventory and pricing are computed from one or more source products.

There are **two types**:

| Type | Also Called | Relationship | Inventory Source |
|------|-----------|--------------|------------------|
| **Quantity Variant** | QTY | One parent, multiple children | Parent product |
| **Combo** | COMBO | Multiple components, one combo product | All component products |

### Quantity Variant Example

| Product | Item Code | Role |
|---------|-----------|------|
| Aata 1kg | 1001 | Parent (owns inventory) |
| Aata 500g | 1002 | Derived child (ratio = 0.5) |
| Aata 250g | 1003 | Derived child (ratio = 0.25) |

If parent has 10 units in stock:
- Aata 500g available = 10 / 0.5 = **20**
- Aata 250g available = 10 / 0.25 = **40**


### Combo Example

| Product | Item Code | Role |
|---------|-----------|------|
| Sabzi Pack | 2001 | Combo product (derived) |
| Aloo 1kg | 2002 | Component (ratio = 1) |
| Pyaaj 2kg | 2003 | Component (ratio = 2) |

If Aloo has 6 units and Pyaaj has 10 units:
- Aloo can make = 6 / 1 = 6 combos
- Pyaaj can make = 10 / 2 = 5 combos
- Combo availability = **min(6, 5) = 5**

---

## 2. Database Models

### 2.1 SKUBundle (samaan-api: `smpcm/models.py`)

Stores the bundle definition. One row per parent/combo product.

| Field | Type | Description |
|-------|------|-------------|
| `parent_product` | OneToOne → Product | QTY: master SKU. COMBO: combo SKU. |
| `variant_type` | CharField | `'QTY'` or `'COMBO'` |
| `active` | BooleanField | Whether the bundle is active |
| `created_by_id` | IntegerField | User who created |
| `updated_by_id` | IntegerField | User who last updated |

### 2.2 SKUBundleItem (samaan-api: `smpcm/models.py`)

Stores child/component mappings. Multiple rows per bundle.

| Field | Type | Description |
|-------|------|-------------|
| `bundle` | FK → SKUBundle | Parent bundle |
| `child_product` | FK → Product | QTY: derived child. COMBO: component product. |
| `quantity_ratio` | FloatField | Conversion multiplier |
| `price_multiplier` | FloatField | Pricing adjustment factor (default 1.0) |
| `active` | BooleanField | Whether this mapping is active |

**Unique constraint**: `(bundle, child_product)` — a child can only appear once per bundle.

### 2.3 SKUBundleHistory / SKUBundleItemHistory (samaan-api: `smpcm/models.py`)

Audit trail tables. A history row is created on every create/update of SKUBundle and SKUBundleItem.

### 2.4 OrderProductParent (samaan-api: `smorder/models.py`)

Tracks parent/source SKU for each order product involving derived SKUs.

| Field | Type | Description |
|-------|------|-------------|
| `order_product` | OneToOne → OrderProduct | The order line item |
| `product` | FK → Product | QTY: parent product. COMBO: combo product. |
| `variant_type` | CharField | `'QTY'` or `'COMBO'` |
| `quantity_ratio` | FloatField | Ratio at order time |
| `price_multiplier` | FloatField | Multiplier at order time |

### 2.5 SalesBillItemParent (tez-api: `apnasales/models.py`)

Tracks parent SKU for each billed item involving derived SKUs.

| Field | Type | Description |
|-------|------|-------------|
| `sales_bill_item` | OneToOne → SalesBillItem | The bill line item |
| `item_code` | IntegerField | QTY: parent item_code. COMBO: combo item_code. |
| `variant_type` | CharField | `'QTY'` or `'COMBO'` |
| `quantity_ratio` | FloatField | Ratio at billing time |
| `price_multiplier` | FloatField | Multiplier at billing time |
| `stock_pk` | BigIntegerField | Stock batch PK (QTY: parent's stock, COMBO: null) |

### 2.6 Product.piece (samaan-api: `smpcm/models.py`)

New field on the existing Product model. Used for picker display only (FnV products with g/kg units). Not used in calculations.

---

## 3. Pricing Formulas

### 3.1 Quantity Variant Pricing

```
derived_qty   = floor(parent_qty / quantity_ratio)
derived_mrp   = parent_mrp * quantity_ratio
derived_sp    = parent_sp * quantity_ratio * price_multiplier
```

**Example**: Parent Aata 1kg (MRP=100, SP=90), Child Aata 500g (ratio=0.5, price_multiplier=1.1)
- Child MRP = 100 * 0.5 = **50**
- Child SP = 90 * 0.5 * 1.1 = **49.5**

### 3.2 Combo Pricing

```
combo_qty = min(component_qty / ratio for each component)
combo_mrp = sum(component_mrp * ratio for each component)
combo_sp  = sum(component_sp * ratio * price_multiplier for each component)
```

### 3.3 Online Threshold (Inventory Availability)

```
available_inventory = max(0, inventory - online_threshold)
```

For QTY variant: `child_availability = available_inventory / quantity_ratio`
For COMBO: `combo_availability = min(available_inventory_per_component / ratio_per_component)`

---

## 4. Systems & Modules Affected

| # | System Area | Service | What Changed |
|---|-------------|---------|--------------|
| 1 | Catalog Management | samaan-api (smpcm) | SKUBundle/Item models, CSV upload APIs, validation |
| 2 | Inventory Derivation | samaan-api (smims) | Derived SKU inventory computation for online products |
| 3 | Cart Validation | samaan-api (smorder) | Derived SKU redistribution in validate_offer_cart |
| 4 | Order Creation | samaan-api (smorder) | OrderProductParent tracking, combo expansion |
| 5 | Order Display (Consumer) | samaan-api (smorder) | Combo merging on order list, order detail, reorder |
| 6 | Order Display (Bot) | samaan-api (smorder) | Combo merging on bot endpoints |
| 7 | POS Order Detail | samaan-api (smorder) | parent_mapping exposure for tez billing |
| 8 | Inventory Inward Blocking | samaan-api (smwims) | Block GRN, adjustment, conversion, movement for derived SKUs |
| 9 | Inventory Inward Blocking | tez-api (apnainventory) | Block GRN, PO, opening stock, conversion, adjustment |
| 10 | Picking Screen | tez-api (apnasales) | Derived SKU display rules (V1-V4, C1-C2) |
| 11 | Online Billing | tez-api (apnasales) | Two-pass allocation, SalesBillItemParent, derived pricing |
| 12 | Returns (Inventory Credit) | tez-api (apnasales) | QTY variant return qty conversion to parent units |
| 13 | Return Screens (Rider) | samaan-api (smreturnorder) | Derived display info on rider return screen |
| 14 | Return Screens (Picker) | samaan-api (smreturnorder) | Derived display info on picker return screen |
| 15 | Search Inventory Sync | samaan-api (smims) | Discovery status sync for derived SKUs |
| 16 | Search Inventory Sync | tez-api (_apnabase) | Actionable qty sync for derived SKUs |
| 17 | ARS Sales Attribution | samaan-api (smars) | QTY child sales re-attributed to parent |
| 18 | Offers | (none) | No changes. Offers work on item_code as-is. |

---

## 5. Test Scenarios

### 5.1 Catalog Management — Variant Mapping Upload

**API**: `POST /api/pcm/bulk_upload_variant_mapping/`
**Permission Required**: `update-product`

| # | Scenario | Input | Expected Result |
|---|----------|-------|-----------------|
| 1 | Valid variant CSV upload | CSV with valid parent_item_code, child_item_code, quantity_ratio, active | Success. SKUBundle + SKUBundleItem rows created. |
| 2 | Parent product does not exist | Non-existent parent_item_code | Row-level error: parent not found |
| 3 | Child product does not exist | Non-existent child_item_code | Row-level error: child not found |
| 4 | Parent channel not ON | Parent product with channel != 'ON' | Row-level error: channel must be ON |
| 5 | Child already in another active bundle | child_item_code already mapped to a different parent | Row-level error: child already belongs to another bundle |
| 6 | Duplicate child in same CSV | Same child_item_code appears twice in CSV | Row-level error on the second occurrence |
| 7 | quantity_ratio <= 0 | ratio = 0 or negative | Row-level error: ratio must be > 0 |
| 8 | Unit validation (g/kg) | unit_en = 'g' or 'kg' but fraction_digits = 0 | Row-level error |
| 9 | Unit validation (unit) | unit_en = 'unit' but fraction_digits != 0 | Row-level error |
| 10 | Deactivate mapping | active = false for existing mapping | SKUBundleItem.active set to false. Child freed for other bundles. |
| 11 | Reactivate mapping | active = true for previously deactivated mapping | SKUBundleItem.active set to true |
| 12 | Update quantity_ratio | Upload same child with different ratio | SKUBundleItem.quantity_ratio updated |
| 13 | Max CSV rows exceeded | CSV with > 500 rows | Error: max rows exceeded |
| 14 | Non-CSV file upload | Upload .xlsx or .txt | Error: file must be .csv |
| 15 | No file uploaded | POST with no file | Error: no CSV file provided |
| 16 | No permission | User without `update-product` permission | 403 Forbidden |
| 17 | History created | Any successful upload | SKUBundleHistory + SKUBundleItemHistory rows created |

### 5.2 Catalog Management — Combo Mapping Upload

**API**: `POST /api/pcm/bulk_upload_combo_mapping/`
**Permission Required**: `update-product`

| # | Scenario | Input | Expected Result |
|---|----------|-------|-----------------|
| 1 | Valid combo CSV upload | CSV with combo_item_code, child_item_code, quantity_ratio, active | Success. SKUBundle(COMBO) + items created. |
| 2 | quantity_ratio is not integer | ratio = 0.5 | Row-level error: combo ratio must be integer |
| 3 | child_item_code is a variant child | child already mapped as QTY variant | Row-level error: variant children cannot be combo components |
| 4 | Combo with single component | Only one child_item_code for a combo | Success (valid edge case) |
| 5 | Combo with many components | 5+ components for one combo | Success |
| 6 | Deactivate combo | active = false | Bundle deactivated. Combo no longer available. |

### 5.3 Pricing Upload

**API**: `POST /api/pcm/bulk_upload_variant_pricing/` (Permission: `update-pricing`)
**API**: `POST /api/pcm/bulk_upload_combo_pricing/` (Permission: `update-pricing`)

| # | Scenario | Input | Expected Result |
|---|----------|-------|-----------------|
| 1 | Update variant price_multiplier | CSV with parent, child, price_multiplier | SKUBundleItem.price_multiplier updated |
| 2 | price_multiplier <= 0 | multiplier = 0 or negative | Error |
| 3 | Non-existent mapping | parent/child pair that doesn't exist | Error |
| 4 | Combo pricing updates all children | CSV with combo_item_code, price_multiplier | ALL SKUBundleItems of that combo updated with same multiplier |
| 5 | No permission | User without `update-pricing` permission | 403 Forbidden |

### 5.4 Export Mappings

**API**: `GET /api/pcm/export_variant_mappings/`
**API**: `GET /api/pcm/export_combo_mappings/`

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Export variants | CSV download with parent_item_code, child_item_code, quantity_ratio, price_multiplier, active |
| 2 | Export combos | CSV download with combo_item_code, child_item_code, quantity_ratio, price_multiplier, active |
| 3 | No mappings exist | Empty CSV (headers only) |

---

### 5.5 Inventory Derivation (Online Product Availability)

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | QTY variant availability | Child qty = floor(parent_available / quantity_ratio) |
| 2 | Parent has 0 inventory | All children show qty = 0 |
| 3 | Online threshold applied | Available = parent_stock - threshold. Children computed from available. |
| 4 | Placed orders deducted before derivation | Parent stock reduced by placed-but-not-billed order qty before computing child qty |
| 5 | Combo availability | min(component_available / ratio) across all components |
| 6 | One combo component out of stock | Combo qty = 0 |
| 7 | Multiple combos sharing a component | Each combo independently computed from component stock |
| 8 | Parent also in cart as regular product | Parent qty consumed by regular cart item first, then remaining used for derived children |

### 5.6 Inventory Inward Blocking

Derived SKUs **must not** receive inventory through any inward operation.

#### samaan-api Blocking Points (smwims)

| # | Operation | API/Method | Expected Result |
|---|-----------|-----------|-----------------|
| 1 | GRN | `validate_product_batches_payloads` | Error: "Cannot create inventory for derived SKUs: {ids}" |
| 2 | Bulk Conversion | `validate_product_batches_payloads` | Same error |
| 3 | Adjustment | `create_inv_adjustment_request` | Same error |
| 4 | Movement V1 | `movement_csv_validator` | Same error |
| 5 | Movement V2 (PRD) | `_validate_prd_based_inputs` | Same error |
| 6 | Movement V2 (QTY) | `_validate_qty_based_inputs` | Same error |

#### tez-api Blocking Points (apnainventory)

| # | Operation | Caller | Expected Result |
|---|-----------|--------|-----------------|
| 1 | Purchase/GRN | `update_pi_status` | Error: "Cannot create inventory for derived SKUs" |
| 2 | New Receiving | `confirm_receiving` | Same error |
| 3 | Dropship | `create_pi_and_items` | Same error |
| 4 | Opening Stock | `bulk_create_opening_stock`, `create_opening_stock` | Same error |
| 5 | Bulk Conversion | `convert_loose_to_bulk`, `convert_bulk_to_loose` | Same error |
| 6 | Stock Adjustment | `convert_list_item` (shortage), `approve_stock_adjustment` | Same error |
| 7 | Wall-to-Wall | `wall_to_wall_adjustment` | Same error |

**Not blocked** (by design): OOS Adjustment, Sales Return, MRP/SP/Expiry change, RVP, Duplicate Migration.

---

### 5.7 Cart Validation (validate_offer_cart)

**API**: `POST /api/order/validate_offer_cart/v6/`

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Single derived SKU in cart, sufficient parent stock | Cart unchanged. Normal pricing. |
| 2 | Multiple siblings in cart, sufficient parent stock | All items present at requested quantities |
| 3 | Multiple siblings in cart, insufficient parent stock | Redistribution: items sorted by SP ascending, cheapest filled first. Higher-SP items get reduced qty or moved to remove_cart. |
| 4 | Parent product also in cart + derived children | Parent qty deducted first from resource pool, remaining distributed to children |
| 5 | Derived item reduced to qty=0 | Moved to `remove_cart` with `out_of_stock: true`, `quantity_adjusted: true`, `adjustment_reason: "parent_inventory_shared"` |
| 6 | Derived item partially reduced | Stays in `order_cart` with reduced `quantity`, `quantity_adjusted: true`, `original_quantity: <original>`, `adjustment_reason: "parent_inventory_shared"` |
| 7 | Combo in cart, all components available | Combo qty = min of component availability |
| 8 | Combo in cart, one component out of stock | Combo removed or qty reduced to 0 |
| 9 | No derived SKUs in cart | Normal flow, no redistribution |
| 10 | Offers on derived SKUs | Offers applied normally (offer system treats derived SKUs like any other SKU) |

---

### 5.8 Order Creation

**API**: `POST /api/order/create_order/` (internal, triggered by order placement)

#### Quantity Variant Orders

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Order with QTY variant child | OrderProduct created for child SKU. OrderProductParent created with parent product, type='QTY', ratio, multiplier. |
| 2 | Verify OrderProductParent data | product = parent Product, variant_type = 'QTY', quantity_ratio and price_multiplier match catalog at order time |
| 3 | Multiple QTY children in same order | Each gets its own OrderProduct + OrderProductParent |

#### Combo Orders

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 4 | Order with combo SKU | OrderProduct expanded into N component entries (one per component). Each gets OrderProductParent with product = combo Product, type='COMBO'. |
| 5 | Combo price distribution | Each component's MRP and SP proportionally split based on ratio and price_multiplier |
| 6 | OrderPlacedProduct for combo | Keeps combo product_id (not expanded) |
| 7 | Offers on combo | All component OrderProducts get offer_id. First component gets offer_savings. |

#### Mixed Orders

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 8 | Order with regular + variant + combo products | Each type handled correctly. Regular products unchanged. |

---

### 5.9 Order Display (Consumer App)

#### Order Detail / Order Tracking

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Order with combo product | Component OrderProducts merged back into single combo entry. Display name, image from combo product. |
| 2 | MRP/SP of merged combo | Sum of component MRPs/SPs (rounded to 2 decimals) |
| 3 | Offer savings on combo | Sum of component offer_savings |
| 4 | QTY variant in order detail | Displayed as child product (no merging needed) |
| 5 | Regular products unchanged | No change to display of non-derived products |

#### My Orders List (Paginated)

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 6 | Order list with combo | Component items from the same combo are deduplicated. Displayed as single entry. |
| 7 | Order list with QTY variant | Displayed as-is (child product) |

#### Reorder

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 8 | Reorder an order with combo | Cart rebuilt with combo item_code (not component item_codes) |
| 9 | Reorder an order with QTY variant | Cart rebuilt with child item_code |

#### Bot Endpoints

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 10 | get_latest_orders with combo | Component names replaced with combo display_name. Deduplicated per order. |
| 11 | get_order_items with combo | Components merged: combo display_name, summed amount, first component's quantity. |

---

### 5.10 POS Order Detail (Samaan → Tez)

**API**: `GET /api/order/get_pos_order_detail/<pk>/`

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | QTY variant order product | Response includes `parent_mapping` dict with parent_item_code, parent_display_name, parent_unit_value, parent_piece, variant_type='QTY', quantity_ratio, price_multiplier |
| 2 | COMBO component order product | Response includes `parent_mapping` with combo product info, variant_type='COMBO' |
| 3 | Regular product | No `parent_mapping` key in response |
| 4 | `piece` field | All products include `piece` field (null for non-FnV) |
| 5 | flatten_products=False | parent_mapping present |
| 6 | flatten_products=True (default) | piece field present, no parent_mapping |

---

### 5.11 Picking Screen Display

**API**: `GET /api/sales/get_new_picking_order_details/` (tez-api)

#### Quantity Variant Display Rules

| Rule | Condition | What Picker Sees |
|------|-----------|------------------|
| **V1** | unit = 'unit', parent unit_value > child unit_value | Child item details (no override) |
| **V2** | unit = 'unit', parent unit_value <= child unit_value | Parent's display name + `display_qty` = order_qty * ratio |
| **V3** | unit = 'g' or 'kg', no piece | Child item details (no override) |
| **V4** | unit = 'g' or 'kg', has piece | Child details + `piece_info` = piece * order_qty |

#### Combo Display Rules

| Rule | Condition | What Picker Sees |
|------|-----------|------------------|
| **C1** | No piece | Child/component item details (no override) |
| **C2** | unit = 'g' or 'kg', has piece | Child details + `piece_info` = piece * order_qty |

| # | Test Case | Expected Result |
|---|-----------|-----------------|
| 1 | V1: QTY, unit='unit', parent_uv=12, child_uv=6 | Show child item, order_qty as-is |
| 2 | V2: QTY, unit='unit', parent_uv=6, child_uv=12 | Show parent name, display_qty = order_qty * ratio |
| 3 | V3: QTY, unit='kg', piece=null | Show child item |
| 4 | V4: QTY, unit='kg', piece=5, order_qty=3 | Show child item + piece_info = 15 |
| 5 | C1: COMBO, piece=null | Show component item |
| 6 | C2: COMBO, unit='g', piece=4, order_qty=2 | Show component + piece_info = 8 |
| 7 | QTY child system_qty | system_qty = parent_remaining_stock / quantity_ratio |
| 8 | QTY child location | Uses parent's storage location (falls back to child's if parent has none) |
| 9 | Regular product | No derived display fields. Unchanged behavior. |

---

### 5.12 Online Billing

**API**: `POST /api/sales/complete_online_billing/` (tez-api)

#### QTY Variant Billing

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Bill a QTY variant child | Stock deducted from **parent's** stock batch. SalesBillItem created with child item_code but parent's stock_id. |
| 2 | Derived pricing | Bill item MRP = parent_mrp * ratio. SP = parent_sp * ratio * price_multiplier. Cost = parent_cost * ratio. |
| 3 | SalesBillItemParent created | One row: sales_bill_item FK, parent item_code, type='QTY', ratio, multiplier, stock_pk = parent stock PK. |
| 4 | Insufficient parent stock | QTY child marked as insufficient stock. Not billed. |
| 5 | Parent ordered + child ordered | Pass 1 bills parent. Pass 2 bills child from **remaining** parent stock. |
| 6 | Multiple QTY children from same parent | Allocated in ascending SP order (cheapest first). Each gets own SalesBillItemParent. |

#### COMBO Billing

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 7 | Bill a combo order | Each component billed from its own stock (standard flow). SalesBillItemParent created with combo item_code, type='COMBO'. |
| 8 | COMBO component insufficient stock | Component marked as insufficient. |

#### General

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 9 | Mixed order (regular + variant + combo) | Regular products billed normally. QTY variants from parent stock. COMBO components from own stock. |
| 10 | Offer validation | Offers validated on child item_code with derived mrp/sp. Offer system unaware of parent/child relationship. |
| 11 | Search sync after billing | Sync includes parent item_codes (for QTY) to update parent's search availability. |

---

### 5.13 Returns

#### tez-api Returns (`update_sale_return`)

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Return a QTY variant child | Return qty in child units on SalesBillItem.return_qty. Inventory credit = return_qty * quantity_ratio (in parent units). Credited to parent's stock batch. |
| 2 | Return a COMBO component | Normal flow. Inventory credited to component's own stock. No conversion needed. |
| 3 | Partial return of QTY variant | Proportional parent units credited. |
| 4 | Full return of QTY variant | Full parent units credited. |
| 5 | Search sync after return | Parent item_code included in sync (already happens via stock row's item_code). |

#### samaan-api Return Screens

**APIs**:
- `GET /api/returnorder/get_return_order_details/` (rider)
- `GET /api/returnorder/get_order_return_products/<ms>/` (picker)

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 6 | Rider return screen — QTY variant | Shows derived display (same V1-V4 rules as picking screen) using return_qty |
| 7 | Picker return screen — QTY variant | Shows derived display with product__piece, product__unit, product__unit_value |
| 8 | Rider return — COMBO component | Shows derived display (C1/C2 rules) |
| 9 | Regular product return | No derived display fields |
| 10 | piece_info uses return qty | piece_info = piece * return_qty (not order_qty) |

---

### 5.14 Search Inventory Sync

Two independent sync pipelines:

| Pipeline | Service | What It Syncs | Trigger |
|----------|---------|---------------|---------|
| **Discovery** | samaan-api | `discovery_status` (enabled / oos_hidden / global_hidden) | Mapping CRUD via CSV upload |
| **Availability** | tez-api | `avl` (in_stock / out_of_stock) | Inventory events (stock in/out, billing, returns) |

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | New variant mapping created | Samaan syncs discovery_status for derived SKU across all active stores. |
| 2 | Mapping deactivated | Derived SKU set to `global_hidden` across all stores. |
| 3 | ratio changed via mapping upload | Discovery re-synced with new ratio. Derived qty recomputed. |
| 4 | Parent stock changes (GRN, billing, return) | Tez syncs actionable qty for parent + all derived children. |
| 5 | Combo component stock changes | Tez syncs actionable qty for component + all combos using it. |
| 6 | Derived SKU's own visibility override | If StoreProductControl has override for derived SKU, that takes precedence. |
| 7 | `in_assortment` independent | Derived SKU's `in_assortment` = `derived_qty > 0`. Not inherited from parent. |

---

### 5.15 ARS Sales Attribution

QTY variant child sales are re-attributed to the parent for ARS calculations. COMBO variants need no re-attribution (billing already expands to components).

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | QTY child has sales | Sales quantity re-attributed to parent (multiplied by ratio). Child excluded from ARS processing. |
| 2 | COMBO parent excluded | COMBO parent item_codes excluded from ARS processing (no real sales). |
| 3 | Parent has its own sales + child sales | Both aggregated under parent item_code. |
| 4 | Child re-mapped to different parent mid-period | Most recent order's parent mapping used for attribution. |
| 5 | Newly mapped child with no order history | Falls back to current catalog ratio from SKUBundleItem. |

ARS modules affected: Utility Score Generation, Historical Potential Sales, CPD Metrics.

---

## 6. Key Business Rules Summary

| Rule | Description |
|------|-------------|
| Derived SKUs never own inventory | QTY children and COMBO parents cannot have warehouse or store inventory |
| One child, one parent | A QTY variant child can only belong to one active parent bundle |
| Combo components cannot be variant children | A product that is a QTY variant child cannot be used as a combo component |
| Channel must be ON | Parent/combo product must have channel = 'ON' to create a mapping |
| Channel lock | Once a product is mapped as a derived SKU, its channel cannot be changed |
| Offers are decoupled | Offer system works on item_code as-is. No knowledge of derived relationships needed. |
| Offline billing unaffected | POS billing works with parent/component item_codes directly. Only online orders involve derived SKU logic. |
| Combo = offline excluded | Combos are not applicable for offline billing at all |

---

## 7. API Endpoint Summary

### samaan-api Endpoints

| Endpoint | Method | Purpose | Permission |
|----------|--------|---------|------------|
| `/api/pcm/bulk_upload_variant_mapping/` | POST | Upload variant mappings | `update-product` |
| `/api/pcm/bulk_upload_combo_mapping/` | POST | Upload combo mappings | `update-product` |
| `/api/pcm/bulk_upload_variant_pricing/` | POST | Update variant pricing | `update-pricing` |
| `/api/pcm/bulk_upload_combo_pricing/` | POST | Update combo pricing | `update-pricing` |
| `/api/pcm/export_variant_mappings/` | GET | Export variant CSV | Authenticated |
| `/api/pcm/export_combo_mappings/` | GET | Export combo CSV | Authenticated |
| `/api/order/validate_offer_cart/v6/` | POST | Cart validation (modified) | Authenticated |
| `/api/order/create_order/` | POST | Order creation (modified) | Authenticated |
| `/api/order/get_pos_order_detail/<pk>/` | GET | POS order detail (modified) | Internal host |
| `/api/order/get_myorders_paginated/v2/` | GET | Order list (modified) | Authenticated |
| `/api/order/reorder_myorder/` | GET | Reorder (modified) | Authenticated |
| `/api/order/get_latest_orders/` | GET | Bot orders (modified) | No auth |
| `/api/order/get_order_items/` | GET | Bot order items (modified) | No auth |
| `/api/returnorder/get_return_order_details/` | GET | Rider return screen (modified) | Authenticated |
| `/api/returnorder/get_order_return_products/<ms>/` | GET | Picker return screen (modified) | Authenticated |

### tez-api Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sales/get_new_picking_order_details/` | GET | Picking screen (modified) |
| `/api/sales/complete_online_billing/` | POST | Online billing (modified) |
| `/api/sales/update_sale_return/` | PUT | Sale return (modified) |
| Various inventory inward endpoints | POST | Blocked for derived SKUs |

---

## 8. Out of Scope

These items are explicitly **not** part of this implementation:

| Item | Status |
|------|--------|
| Bottom sheet (combined variant view for users) | Parked by product |
| Live inventory checks on PLP/PDP/Search page | Parked by product |
| Offline billing linkage for variants | Open point, to be detailed later |
| Discovery page real-time inventory updates | Not implementing |

---

## 9. Test Data Setup — Step by Step

### Prerequisites

- Access to Samaan Dashboard (`samaan.apnama.in`)
- Access to Tez Dashboard (POS system)
- A test user with `update-product` and `update-pricing` permissions
- A test user **without** these permissions (for negative permission tests)
- At least one active store with a `pos_store_id`

---

### Step 1: Create Products in Catalog

All products (parents, children, combo SKUs, components) must already exist in the Product table before creating derived SKU mappings.

Create the following products via Samaan Dashboard (Catalog section) or via existing bulk product upload:

| # | Product Name | Item Code | Unit | unit_value | fraction_digits | piece | Channel | Purpose |
|---|-------------|-----------|------|------------|-----------------|-------|---------|---------|
| 1 | Aata 1kg | (auto) | kg | 1 | 1 | null | ON | QTY variant parent |
| 2 | Aata 500g | (auto) | kg | 0.5 | 1 | null | ON | QTY variant child |
| 3 | Aata 250g | (auto) | kg | 0.25 | 1 | null | ON | QTY variant child |
| 4 | Tomato 1kg | (auto) | kg | 1 | 1 | 4 | ON | QTY parent (with piece, for V4 test) |
| 5 | Tomato 500g | (auto) | kg | 0.5 | 1 | 2 | ON | QTY child (with piece) |
| 6 | Water Bottle 12-pack | (auto) | unit | 12 | 0 | null | ON | QTY parent (unit type, for V1/V2 test) |
| 7 | Water Bottle 6-pack | (auto) | unit | 6 | 0 | null | ON | QTY child (unit, parent_uv > child_uv → V1) |
| 8 | Water Bottle 24-pack | (auto) | unit | 24 | 0 | null | ON | QTY child (unit, parent_uv < child_uv → V2) |
| 9 | Sabzi Combo Pack | (auto) | unit | 1 | 0 | null | ON | Combo product (derived) |
| 10 | Aloo 1kg | (auto) | kg | 1 | 1 | null | ON | Combo component |
| 11 | Pyaaj 1kg | (auto) | kg | 1 | 1 | null | ON | Combo component |
| 12 | Maggi Noodles | (auto) | unit | 1 | 0 | null | ON | Combo component (unit type) |
| 13 | Ketchup 200g | (auto) | g | 200 | 1 | 3 | ON | Combo component (with piece, for C2 test) |
| 14 | Maggi+Ketchup Combo | (auto) | unit | 1 | 0 | null | ON | Combo product |

> Note the actual `item_code` values assigned after creation. You will need them for the CSV files below.

**Important product rules to remember:**
- `channel` must be `ON` for all parent and combo products
- For QTY variants with unit = g/kg: `fraction_digits` must be > 0 and `unit_value` must be != 0
- For QTY variants with unit = unit: `fraction_digits` must be = 0 and `unit_value` must be != 0

---

### Step 2: Create QTY Variant Mappings via CSV Upload

**Dashboard path**: Samaan Dashboard → Catalog → Variant / Combo Mapping → Upload Variant Mapping

Prepare a CSV file `variant_mapping.csv`:

```csv
parent_item_code,child_item_code,quantity_ratio,active
<Aata 1kg IC>,<Aata 500g IC>,0.5,true
<Aata 1kg IC>,<Aata 250g IC>,0.25,true
<Tomato 1kg IC>,<Tomato 500g IC>,0.5,true
<Water 12-pack IC>,<Water 6-pack IC>,0.5,true
<Water 12-pack IC>,<Water 24-pack IC>,2.0,true
```

Upload via `POST /api/pcm/bulk_upload_variant_mapping/` (multipart form-data, field name: `file`).

**Verify after upload:**
- SKUBundle rows created for each parent (Aata 1kg, Tomato 1kg, Water 12-pack) with `variant_type = 'QTY'`
- SKUBundleItem rows created for each child with correct `quantity_ratio`
- History rows created in SKUBundleHistory and SKUBundleItemHistory

---

### Step 3: Create Combo Mappings via CSV Upload

**Dashboard path**: Samaan Dashboard → Catalog → Variant / Combo Mapping → Upload Combo Mapping

Prepare a CSV file `combo_mapping.csv`:

```csv
combo_item_code,child_item_code,quantity_ratio,active
<Sabzi Combo IC>,<Aloo 1kg IC>,1,true
<Sabzi Combo IC>,<Pyaaj 1kg IC>,2,true
<Maggi+Ketchup Combo IC>,<Maggi Noodles IC>,2,true
<Maggi+Ketchup Combo IC>,<Ketchup 200g IC>,1,true
```

Upload via `POST /api/pcm/bulk_upload_combo_mapping/`.

> Remember: `quantity_ratio` for combos must be a positive integer.

**Verify after upload:**
- SKUBundle rows created for each combo (Sabzi Combo, Maggi+Ketchup Combo) with `variant_type = 'COMBO'`
- SKUBundleItem rows for each component with correct integer `quantity_ratio`

---

### Step 4: Upload Pricing Multipliers

**Dashboard path**: Samaan Dashboard → Pricing → Variant / Combo Pricing

#### Variant Pricing CSV (`variant_pricing.csv`):

```csv
parent_item_code,child_item_code,price_multiplier
<Aata 1kg IC>,<Aata 500g IC>,1.0
<Aata 1kg IC>,<Aata 250g IC>,1.1
<Tomato 1kg IC>,<Tomato 500g IC>,1.0
<Water 12-pack IC>,<Water 6-pack IC>,1.0
<Water 12-pack IC>,<Water 24-pack IC>,0.95
```

Upload via `POST /api/pcm/bulk_upload_variant_pricing/` (requires `update-pricing` permission).

#### Combo Pricing CSV (`combo_pricing.csv`):

```csv
combo_item_code,price_multiplier
<Sabzi Combo IC>,0.9
<Maggi+Ketchup Combo IC>,0.85
```

Upload via `POST /api/pcm/bulk_upload_combo_pricing/`.

> Note: Combo pricing applies the SAME multiplier to ALL components of that combo.

**Verify:** SKUBundleItem.price_multiplier updated for each mapping.

---

### Step 5: Create Store Inventory for Parent/Component Products

Inventory must be created **only for parent and component products** (never for derived SKUs).

Use Tez Dashboard → Inventory → Opening Stock, or the GRN flow:

| Product | Store | Quantity to Create | MRP | SP |
|---------|-------|--------------------|-----|-----|
| Aata 1kg | Test Store | 20 | 100 | 90 |
| Tomato 1kg | Test Store | 15 | 60 | 50 |
| Water Bottle 12-pack | Test Store | 10 | 240 | 200 |
| Aloo 1kg | Test Store | 25 | 40 | 35 |
| Pyaaj 1kg | Test Store | 18 | 30 | 25 |
| Maggi Noodles | Test Store | 30 | 14 | 12 |
| Ketchup 200g | Test Store | 20 | 45 | 38 |

**Verify:**
- Stock exists in Stocks table for these products at the test store
- Attempting to create opening stock for a derived SKU (e.g., Aata 500g) should return error: "Cannot create inventory for derived SKUs"

**Expected derived availability (after stock creation):**

| Derived Product | Formula | Expected Qty |
|----------------|---------|--------------|
| Aata 500g | floor(20 / 0.5) | 40 |
| Aata 250g | floor(20 / 0.25) | 80 |
| Tomato 500g | floor(15 / 0.5) | 30 |
| Water 6-pack | floor(10 / 0.5) | 20 |
| Water 24-pack | floor(10 / 2.0) | 5 |
| Sabzi Combo | min(25/1, 18/2) = min(25, 9) | 9 |
| Maggi+Ketchup Combo | min(30/2, 20/1) = min(15, 20) | 15 |

---

### Step 6: Set Online Thresholds (Optional — for threshold tests)

Set online thresholds on parent/component products via Samaan Dashboard or StoreProductControl:

| Product | Online Threshold |
|---------|-----------------|
| Aata 1kg | 2 |
| Aloo 1kg | 3 |

**Expected availability WITH thresholds:**
- Aata 1kg available = 20 - 2 = 18
  - Aata 500g = floor(18 / 0.5) = 36
  - Aata 250g = floor(18 / 0.25) = 72
- Sabzi Combo: Aloo available = 25 - 3 = 22
  - Sabzi Combo = min(22/1, 18/2) = min(22, 9) = 9 (Pyaaj is the bottleneck)

---

### Step 7: Verify Search Sync

After mapping creation and inventory setup, verify derived SKUs appear in search:

1. **Discovery status**: Derived SKUs should have `discovery_status = enabled` (if derived_qty > 0) or `oos_hidden` (if derived_qty = 0)
2. **Actionable qty**: Search should show correct computed quantities for derived SKUs
3. Test by searching for the derived product on the consumer app — it should appear with correct availability

---

### Step 8: Test User Permissions Setup

Ensure you have at least two test users:

| User | Permissions | Purpose |
|------|------------|---------|
| User A | `update-product`, `update-pricing` | Full catalog + pricing access |
| User B | No special permissions | Negative permission tests |

Test:
- User A can upload variant/combo mappings and pricing
- User B gets 403 Forbidden on mapping upload (requires `update-product`)
- User B gets 403 Forbidden on pricing upload (requires `update-pricing`)

---

### Step 9: Create a Test Order with Derived SKUs

Place an order through the consumer app (or via API) containing:

1. **Aata 500g** (QTY variant) — qty 2
2. **Sabzi Combo Pack** (COMBO) — qty 1
3. **Any regular product** — qty 1 (for comparison)

**Verify after order creation:**
- OrderProduct rows created:
  - Aata 500g: 1 row (child product), 1 OrderProductParent (parent = Aata 1kg, type='QTY', ratio=0.5)
  - Sabzi Combo: **expanded** into 2 rows (Aloo, Pyaaj), each with OrderProductParent (product = Sabzi Combo, type='COMBO')
  - Regular product: 1 row, no OrderProductParent
- OrderPlacedProduct: Sabzi Combo keeps combo product_id (not expanded)

---

### Step 10: Test Billing and Returns

After the order is placed and picked:

1. **Billing** (`complete_online_billing`):
   - Aata 500g billed from Aata 1kg's stock batch. SalesBillItemParent created.
   - Aloo and Pyaaj billed from their own stock. SalesBillItemParent created with combo info.
   - Verify derived pricing: Aata 500g MRP = Aata 1kg MRP * 0.5

2. **Returns** (after billing):
   - Return Aata 500g (qty 1): inventory credited to Aata 1kg stock as 1 * 0.5 = 0.5 units
   - Return Aloo from combo (qty 1): inventory credited to Aloo stock as-is (no conversion)

---

### Quick Reference — Sample CSV Templates

**variant_mapping.csv:**
```csv
parent_item_code,child_item_code,quantity_ratio,active
1001,1002,0.5,true
1001,1003,0.25,true
```

**combo_mapping.csv:**
```csv
combo_item_code,child_item_code,quantity_ratio,active
2001,2002,1,true
2001,2003,2,true
```

**variant_pricing.csv:**
```csv
parent_item_code,child_item_code,price_multiplier
1001,1002,1.0
1001,1003,1.1
```

**combo_pricing.csv:**
```csv
combo_item_code,price_multiplier
2001,0.9
```
