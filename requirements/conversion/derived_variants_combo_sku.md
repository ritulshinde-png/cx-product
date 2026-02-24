# Derived Variants & Combo SKU Requirements

> [!IMPORTANT]
> This is a new feature where we are showing visibility for different variants of products in the app as well as any combos they are a part of.

## Context

Currently we have a system on Samaan that allows us to re-package inventory from a parent SKU to a child SKU. Say we have Fresh Tomatoes as an offline only SKU where we inward inventory in bulk. In order to sell online, we then create new SKUs like Fresh Tomatoes 500 g. Then the inventory is re-packaged from Parent into Child in Tez POS after it’s in-warded into the store. While this helps with moving inventory, but because it is a manual process, we end up facing availability issues. Specifically in case of Fruits & Vegetables, we face these challenges during the morning early hours and late night, where the moved online inventory is generally exhausted.

## Requirements

### Concept & Purpose

* **Derived SKU** is a virtual SKU created by applying a unit and price conversion on an existing Parent SKU.
* It allows merchandising of the same product in smaller/larger quantities (e.g., 500g derived from 1kg).
* These SKUs are meant for online-only selling, and will not be used for offline billing (Tez POS).
* Useful for enabling flexible pack sizes in consumer-facing (CX) apps, without duplicating full SKU workflows.

### Types of Variants

We support showing visibility for different variants of products in the app:

1. **Size Variants**
   * **Pre Packed**: E.g., Atta | 1kg, 5kg, 10kg, 20kg
   * **Loose (Weight)**: E.g., Potato | 200g, 500g, 1kg, 2kg
   * **Loose (Size)**: E.g., Watermelon | Small, Medium, Large
   * **Loose (Count)**: E.g., Banana | 1pc, 3pc, 6pc, 12pc
2. **Type Variants**
   * **Colour**: E.g., Mobile | Yellow, Blue, Black
   * **Pattern**: E.g., Dress | Blue, Brown, Black
3. **Combo Variants**
   * **Same Item (Pre Packed)**: E.g., Atta | 1kg, 1kg x 2, 1kg x 3
   * **Same Item (Loose)**: E.g., Potato | 1kg x 0.2, 1kg, 1kg x 2
   * **Different Item**: E.g., Chips + Juice + Biscuit | Milk + Bread + Egg

#### Derivation Logic

1. **Pre Packed**: Existing pack sizes of these items. They function as independent SKUs (ex: aata 1kg pack, 5kg pack, 10kg pack).
2. **Loose**: Quantities derived from a parent SKU based on a conversion factor, making a child SKU (ex: 1kg potato - with a 0.75 conversion factor will create a loose variant of 0.75kg potato).
3. **Combo**: Derived by combining multiple parent SKUs to make a child SKU (ex: parent 1 * conversion factor + parent 2 * conversion factor = child 1).

### Catalog & SKU Management

* **Derived SKU Creation**
  * A new Derived relation upload module will be built on Samaan to define relationships (e.g., Aata 1kg → Aata 500g).
  * Pricing of the Derived SKU will be calculated using the ratio of quantity conversion and pricing multiplier. The upload of pricing multiplier to be built separately.
  * Derived SKU will inherit attributes and shelf control logic from their catalogue — they can be modified independently.
* **Restrictions**
  * Unit changes for Parent SKUs are not allowed once a Derived SKU exists.
  * Derived SKU can only exist if a valid Parent SKU is present.
* **Channel Availability**
  * Derived SKUs will be available only on the online consumer app (CX).
  * They will not be supported or visible on Tez POS (offline billing platform).

### Inwarding

* Derived SKUs are not relevant for warehouse/store inwarding processes.
* All inwarding continues to happen against the Parent SKU only.
* To **BLOCK** any inwarding from variant (child) or combo SKU.

### Inventory & Visibility

* **Inventory Calculation**
  * No separate inventory is maintained for Derived SKUs.
  * Their available stock is calculated at runtime using the Parent SKU’s inventory and the defined conversion ratio. Round down on conversion.
  * Check in cart for inventory logic (Minimum price to be cut off). To add event for this (user, store, timestamp, event name, items).
* **Visibility Logic**
  * If a Derived SKU is inactive, it will not appear in search, listings, or any discovery surface.
  * If a Parent SKU is inactive, both Parent and Derived SKUs will be hidden from listings and search.
  * When a Derived SKU is marked active for the first time, it will become instantly visible where Parent SKU inventory is present:
    * Listings
    * Search results
    * Relevant category/product pages
* **OLP/ODP Behavior**
  * Even if marked inactive, Derived SKUs will not be removed from ODP (product detail) and OLP (offer listing) pages. **SKIP for now.**
* **Pricing**
  * Pricing is calculated at runtime using the Parent SKU’s price and the conversion (ratio x pricing multiplier) factor.
  * Pricing is store-level, based on Store × Stock ID.

### Offers

* **SKU-Level Offers**
  * Flat pricing is supported on Derived SKUs.
  * Use case: Sell 500g at ₹59 flat, instead of deriving from 1kg base price.
* **Unsupported Offers**
  * Percentage-based discounts (e.g., 20% off) are not supported on Derived SKUs.
  * Coupon offers (site-wide or SKU-specific) are not in scope for Derived SKUs.


### Returns

* Inventory to be added to Parent SKU, using conversion ratio.
* To exclude from audit, inward (listed in PRD), change selling, bulk conversion. Verify stock transaction.

## Core Challenges

For these scenarios, let's define:

* **Parent SKU:** Mango 1kg (inwarded in bulk)
* **Child SKU:** 2.5kg Mango Set (contains 4 pieces, total weight ~2.5kg)
* **Conversion Rate:** 1 unit of Child SKU consumes 2.5 kg of Parent SKU.
* **Total Initial Parent Inventory:** 50 kg of Mango 1kg at the store.

> [!WARNING]
> **Key Challenges for Developers:**
> 1.  **Fractional Inventory:** How to handle situations where the remaining parent inventory isn't a perfect multiple of the child SKU's weight, leading to "leftover" parent inventory that can't form a full child unit.
> 2.  **Picking Variations:** The actual weight of a "piece" of fruit can vary, making the exact conversion from parent to child unpredictable.
> 3.  **Concurrent Sales Channels:** Offline sales directly from the parent SKU or other child SKUs (if applicable) can impact the available parent inventory for re-packaging.
> 4.  **Real-time Availability:** Ensuring that online inventory accurately reflects what's truly available for purchase, given the dynamic nature of re-packaging, picking, and concurrent sales.
> 5.  **Order Fulfillment Logic:** What happens when an order is placed for a child SKU, but the underlying parent inventory becomes insufficient during picking or due to concurrent sales.

### I. Basic Conversion & Fractional Remainders

* **Scenario 1.1: Perfect Conversion**
  * **Initial State:** 50 kg Mango (Parent).
  * **Action:** Re-package 25 kg into Child SKU.
  * **Expected Outcome:** 10 units of 2.5kg Mango Set (Child) are created. 25 kg Mango (Parent) remain. No fractional issues.
* **Scenario 1.2: Fractional Remainder (Parent < Child Unit Weight)**
  * **Initial State:** 2.4 kg Mango (Parent). No Child SKU units available.
  * **Action:** System attempts to create a 2.5kg Mango Set (Child).
  * **Expected Outcome:** 0 units of Child SKU can be created. The 2.4 kg remains as parent inventory, effectively "locked" for creating a full child unit until more parent inventory is added. Online shows 0 availability for the Child SKU.
* **Scenario 1.3: Fractional Remainder (Parent > Child Unit Weight, but not enough for another full unit)**
  * **Initial State:** 27 kg Mango (Parent).
  * **Action:** System calculates how many 2.5kg Mango Sets can be created.
  * **Expected Outcome:** (27 kg / 2.5 kg/unit) = 10.8 units. 10 units of Child SKU are created. 2 kg Mango (Parent) remain. Online shows 10 units of Child SKU available. The 2 kg parent inventory is a remainder.

### II. Impact of Offline Sales

* **Scenario 2.1: Offline Sale of Parent SKU before Re-packaging**
  * **Initial State:** 50 kg Mango (Parent).
  * **Action:** Store sells 5 kg of Mango (Parent) directly offline (e.g., a customer buys 5 individual kgs).
  * **Subsequent Action:** System attempts to re-package the remaining parent inventory into Child SKU.
  * **Expected Outcome:** 45 kg Mango (Parent) remain. When re-packaging, fewer Child SKU units can be created (45 kg / 2.5 kg/unit = 18 units).
* **Scenario 2.2: Offline Sale of Parent SKU after Partial Re-packaging**
  * **Initial State:** 50 kg Mango (Parent).
  * **Action 1:** 25 kg of Mango (Parent) are re-packaged into 10 units of Child SKU. 25 kg Mango (Parent) remain.
  * **Action 2:** Store sells 3 kg of Mango (Parent) directly offline.
  * **Expected Outcome:** 22 kg Mango (Parent) remain. The 10 units of Child SKU remain available. Any further re-packaging will be based on the reduced parent inventory.
* **Scenario 2.3: Offline Sale of a "Child-like" Item from Parent Inventory**
  * **Initial State:** 10 kg Mango (Parent). No Child SKU units.
  * **Action:** An offline customer asks for "4 pieces of mangoes for about 2.5 kg" and the store clerk manually picks 4 pieces from the bulk parent inventory, which weigh 2.6 kg.
  * **Expected Outcome:** The 2.6 kg is deducted from the parent inventory. 7.4 kg Mango (Parent) remain. No Child SKU units are created or consumed by this offline transaction, but it impacts the remaining bulk parent inventory. This highlights the need for accurate offline POS integration or manual adjustment.

### III. Picking Variations & Inaccurate Weight Deductions

* **Scenario 3.1: Child SKU Order & Over-Picking (Weight Exceeds 2.5kg)**
  * **Initial State:** 1 unit of 2.5kg Mango Set (Child) is online. Parent inventory has 5 kg.
  * **Action:** An online order for 1 unit of Child SKU is placed. During picking, the 4 pieces picked for the set weigh 2.7 kg.
  * **Expected Outcome:** The 1 Child SKU unit is fulfilled. Instead of deducting 2.5 kg from parent inventory, 2.7 kg should be deducted. This reduces the parent inventory faster than anticipated, potentially leading to fewer future child units or fractional remainders sooner.
* **Scenario 3.2: Child SKU Order & Under-Picking (Weight Less Than 2.5kg)**
  * **Initial State:** 1 unit of 2.5kg Mango Set (Child) is online. Parent inventory has 5 kg.
  * **Action:** An online order for 1 unit of Child SKU is placed. During picking, the 4 pieces picked for the set weigh 2.3 kg.
  * **Expected Outcome:** The 1 Child SKU unit is fulfilled. Instead of deducting 2.5 kg from parent inventory, 2.3 kg should be deducted. This leaves slightly more parent inventory than anticipated. While seemingly good, inconsistencies can lead to overstating available online inventory.
* **Scenario 3.3: Fractional Parent Inventory at Picking Time**
  * **Initial State:** 2.6 kg Mango (Parent). 1 unit of 2.5kg Mango Set (Child) is online.
  * **Action:** An online order for 1 unit of Child SKU is placed. During picking, the 4 pieces are picked and weigh 2.5 kg.
  * **Expected Outcome:** The 1 Child SKU unit is fulfilled. The 2.5 kg is deducted. 0.1 kg Mango (Parent) remains. This highlights the "lost" fractional inventory that can't be used.
* **Scenario 3.4: Order for Multiple Child Units, Parent Inventory Becomes Insufficient During Picking**
  * **Initial State:** 7 kg Mango (Parent). 2 units of 2.5kg Mango Set (Child) are online (derived from 5kg, with 2kg parent remainder).
  * **Action:** An online order for 2 units of Child SKU is placed.
  * **Picking 1st Unit:** 2.5 kg is picked for the first unit. Parent inventory becomes 4.5 kg.
  * **Picking 2nd Unit:** The system expects to pick another 2.5 kg. However, due to previous offline sales, or an unexpected weight variation, or a system glitch, only 2 kg of actual mango is available in bulk, which is insufficient for the second 2.5kg set.
  * **Expected Outcome:** The first unit is fulfilled. The second unit fails to be picked. This necessitates a partial order fulfillment, cancellation of the second item, or a manual intervention by the store staff. The online inventory for the second unit was "available" but couldn't be fulfilled.

### IV. Race Conditions & Concurrency (Critical for Developers)

* **Scenario 4.1: Concurrent Online Orders Exhaust Parent Inventory**
  * **Initial State:** 6 kg Mango (Parent). 2 units of Child SKU are shown online.
  * **Action 1 (User A):** Places an order for 1 unit of Child SKU.
  * **Action 2 (User B):** Places an order for 1 unit of Child SKU almost simultaneously.
  * **System Logic:** If the system is not robust, both orders might initially be accepted because the online inventory showed 2 units.
  * **Expected Outcome:**
    * **Ideal:** Transactional locking or atomicity ensures only one order depletes the parent inventory first. The second order is then marked as out of stock or partially fulfilled.
    * **Problematic:** If not handled, both orders might consume the "available" inventory, leading to one order being unfulfillable during picking. This creates customer dissatisfaction.
* **Scenario 4.2: Online Order vs. Offline Sale Race**
  * **Initial State:** 3 kg Mango (Parent). 1 unit of Child SKU is shown online.
  * **Action 1 (Online User):** Places an order for 1 unit of Child SKU.
  * **Action 2 (Offline Customer):** Simultaneously buys 1 kg of Mango (Parent) directly from the store.
  * **Expected Outcome:**
    * If the offline sale is processed first, the parent inventory drops to 2 kg. The online order then becomes unfulfillable as it requires 2.5 kg.
    * If the online order is processed first, the parent inventory drops to 0.5 kg. The offline sale can still happen for 1 kg, leading to negative inventory or a manual refusal of the offline sale.
    * This highlights the need for real-time, synchronized inventory updates across all sales channels.

### V. Edge Cases & Error Handling

* **Scenario 5.1: Negative Parent Inventory (Due to Errors or Manual Adjustment)**
  * **Initial State:** 2 kg Mango (Parent).
  * **Action:** A manual adjustment or error causes the parent inventory to go to -1 kg (e.g., incorrect deduction).
  * **Expected Outcome:** How does the system handle this? Should re-packaging be allowed? What impact does this have on online availability of Child SKUs?
* **Scenario 5.2: Damaged Inventory / Spoilage**
  * **Initial State:** 10 kg Mango (Parent).
  * **Action:** 2 kg of Mango (Parent) are identified as spoiled and removed from inventory.
  * **Expected Outcome:** This should be accurately reflected in the parent inventory. If this 2 kg was supporting a Child SKU, the online availability of that Child SKU might need to be immediately reduced.
* **Scenario 5.3: Re-packaging a Child SKU Back to Parent (Rare, but possible)**
  * **Initial State:** 1 unit of 2.5kg Mango Set (Child) is available.
  * **Action:** Store decides to "un-package" the set and return the mangoes to bulk inventory (e.g., if the sets aren't selling).
  * **Expected Outcome:** The 2.5 kg (or actual weighed amount) should be added back to the Parent SKU inventory, and the Child SKU unit should be decremented.
* **Scenario 5.4: Incorrect Conversion Ratio or Data Entry**
  * **Initial State:** Conversion is set as 1 Child SKU = 2 kg Parent, but it should be 2.5 kg.
  * **Action:** Re-packaging occurs based on the incorrect ratio.
  * **Expected Outcome:** Inaccurate inventory levels. If 2 kg is deducted instead of 2.5 kg, the parent inventory will be over-stated, leading to future stock-outs.

## App Design & Flows

### [ADD] Button States

There are 2 states for the [ADD] button on listing and discovery surfaces:

1.  **Normal [ADD] Button**: Shown when no active variants exist or for simple items.
2.  **[ADD] Button with Options**: Shown as `[ADD | {x} OPTIONS]`.
    - `{x}` is dynamic and represents the total count of **in_stock** variants an item_code has, updating in real-time as stock levels change.
    - **Example**: If A, B, C, D are 4 variants mapped together:
        - **All in stock**: Button shows `[4 Options]`.
        - **B and C go out of stock**: Button shows `[2 Options]` (A and D only).
        - **B, C, and D go out of stock**: Only item A is available. The button state changes from `[4 Options]` to a **Normal [ADD] button**. Clicking it will directly add item A to the cart instead of opening the bottom sheet.

#### Interaction Logic (Normal [ADD])
- **Initial State**: `[ADD]`
- **Click [ADD]**: Adds 1 qty to cart. UI changes to quantity selector `[- 1 +]`.
- **Click [+]**: Adds 1 more qty (e.g., `[- 2 +]`).
- **Click [-]**:
    - If qty > 1: Reduces qty by 1.
    - If qty = 1: Removes item from cart and reverts to `[ADD]` state.

### Bottom Sheet: Variant Selection

Clicking on the `[ADD | {x} OPTIONS]` button opens a bottom sheet with two distinct zones:

1.  **Vertical Listing**: Items listed one below another (top section).
2.  **Horizontal Listing**: Items listed in a horizontal row (bottom section).

> [!NOTE]
> The logic to determine which items appear in the vertical vs. horizontal listing is based on relationship mapping, to be detailed in the next section.

## Relationship Mapping Logic

To enable dynamic visibility and selection, variants are mapped into four distinct major types.

### 1. Packed Variants (Existing System)
These are independent SKUs grouped together. Currently, they use a CSV upload:
`group_seed | item_code | key_1 | value_1 | display_name_1`

- **group_seed**: Common identifier for the variant group.
- **key_1**: Variant type (e.g., `color|hexcode`, `size|int`, `grams|str`, `pack-size|str`).
- **display_name_1**: Static text shown on PDP (e.g., "560g", "Medium").

#### 💡 Improvement: Dynamic Templates for Unit-Based Keys
For keys that rely on physical measurements (e.g., `grams|str`, `pack-size|str`, `volume|str`), we can automate the display name:
- **Source of Truth**: Fetch `unit` and `unit_value` from the `smpcm_product` table.
- **Dynamic Logic**:
    - `grams|str` -> Template: `{unit_value}{unit}` (e.g., `500` + `g` = `500g`)
    - `pack-size|str` -> Template: `{unit_value} {unit}` (e.g., `1` + `kg` = `1 kg`)
- **Auto-Sync**: Any change in the `smpcm_product` table for these specific item codes triggers an automatic update to the variant's display string.

> [!NOTE]
> **Manual Entry Required**: Categorical keys like `color|hexcode`, `size|str` (e.g., M | Medium), `style|str`, or `pattern-type|str` will continue to require manual entry via CSV as they do not map directly to `unit_value` fields.

---

### 2. Loose Variants (Derived)
Every loose variant is created from **one Parent SKU** via a **conversion factor**.

- **Relationship**: Parent <-> Child.
- **Example**: Parent (Potato 1kg) * 0.75 factor = Child (Potato 750g).
- **Mapping Keys**:
    - `color|hexcode`: `#899e8e | Light Green`
    - `style|str`: `Captain America | Style`
    - `grams|str`: `560g | 560g`
- **Dynamic Handling**: Since these are derived, the `unit_value` should be explicitly calculated (`Parent.unit_value * conversion_factor`) and formatted using the templates above.

---

### 3. Combo Variants (Same SKU)
Created from **multiple quantities of a single Parent SKU** to form a single Child SKU.

- **Formula**: `Parent * Quantity = Child`.
- **Example**: Potato 1kg * 2 = Potato 2kg Combo.
- **Identification**: These must be flagged as `COMBO_SAME` to distinguish them from different-item combos, as they represent bulk/multi-pack variants of the same product.

---

### 4. Combo Variants (Different SKUs)
Created from a **mix of multiple Parent SKUs** to form a single Child SKU.

- **Formula**: `(P1 * F1) + (P2 * F2) + ... = Child`.
- **Example**: `Milk 500ml + Bread 400g + Egg 3pc`.
- **Identification**: Flagged as `COMBO_DIFF`. Logic should allow for listing individual components within the combo or treating the combo as a single "style" or "bundle" variant.

---

## Data Maintenance & Feeding Strategy

### A. Unified Variant Metadata Model
Instead of type-specific tables, use a central `ProductVariantMapping` model with an `origin_type` ENUM:
- `FIXED_PACK` (Type 1)
- `DERIVED_LOOSE` (Type 2)
- `COMBO_SAME` (Type 3)
- `COMBO_DIFF` (Type 4)

### B. Intelligent Auto-Grooming
1. **Packed Variant Creator**: When a user uploads a `group_seed`, the system auto-fetches `unit`/`unit_value` for all `item_codes` and suggests the `key_1` and `display_name`.
2. **Derived Variant Listener**: When a new Derived SKU is created in Samaan (Parent-Child relationship), the system automatically adds it to the variant group of the Parent.
3. **Combo Registry**: All combo creations should automatically register their parents in the mapping table to enable "Explore Combos" visibility on the Parent PDP.

## Rendering & Visibility Logic

The app uses a gatekeeper logic to determine when to show options and how to render the bottom sheet zones.

### 1. Section Definitions

- **Primary Section (Vertical Listing)**:
    - **Source**: All items sharing the same `group_seed` as the selected item.
    - **Role**: Primary variants (Size, Color, etc.).
- **Secondary Section (Horizontal Listing)**:
    - **Source**: All combos that contain the selected item as a parent component.
    - **Role**: "Explore Combos" or bundle offers.

### 2. Visibility & Trigger Rules (The Gatekeeper)

The display of the `[ADD | {x} OPTIONS]` button and the Bottom Sheet is governed by the state of the **Primary Section**.

| Condition | Primary Section (In-Stock) | Secondary Section (In-Stock) | Result |
| :--- | :--- | :--- | :--- |
| **P1** | <= 1 item | Any count | **Normal [ADD] Button**. No Bottom Sheet. |
| **P2** | > 1 items | < 3 items | **[ADD | {x} OPTIONS]** Button. Bottom Sheet shows **Vertical Listing only**. |
| **P3** | > 1 items | >= 3 items | **[ADD | {x} OPTIONS]** Button. Bottom Sheet shows **Vertical + Horizontal Listing**. |

### 3. Critical Business Rules

1.  **Primary is Mandatory**: The bottom sheet **will NOT open** if the Primary section has 1 or fewer in-stock variants, even if multiple combos exist. It needs **at least 2 items** in stock to show.
2.  **Secondary Threshold**: The Secondary section (Horizontal Listing) requires a minimum of **3 in-stock items** to render. It needs **at least 3 items** in stock to show. If count < 3, the section is suppressed entirely.
3.  **Standalone Secondary Prohibited**: The Secondary section can never trigger the Bottom Sheet or the Options button on its own. It is always a "plus-one" to a valid Primary section.
4.  **Fallback Mechanism**: If at any point the number of in-stock items in the Primary section drops to 1, the item reverts to the normal `[ADD]` state immediately on the listing page.

## Key Takeaways for Developers

1.  **Single Source of Truth:** The parent SKU inventory (in kg) should be the ultimate source of truth for all calculations. Child SKU availability should always be derived from the parent.
2.  **Atomic Operations:** Re-packaging and sales (online/offline) must be atomic operations that update the parent inventory. This prevents race conditions.
3.  **Real-time Updates:** Inventory updates must be real-time and propagate quickly across all sales channels to prevent overselling.
4.  **Tolerance for Fractions:** The system needs to intelligently handle fractional parent inventory. This might mean:
    * Rounding down to the nearest whole unit for online display.
    * Displaying "0 units available" if the remaining parent is less than a child unit.
    * Flagging small remainders for manual reconciliation.
5.  **Actual Weight Tracking:** For picking, consider implementing actual weight capture at the POS/picking station to accurately deduct from parent inventory. If not feasible, an estimated average weight for the Child SKU should be used, with a clear understanding of potential discrepancies.
6.  **Backorder/Partial Fulfillment Logic:** How should the system respond when an order can't be fully fulfilled due to sudden inventory changes during picking?
7.  **Auditing and Reconciliation:** Tools for store staff to easily audit current inventory, identify discrepancies, and reconcile actual vs. system inventory.
8.  **User Interface Considerations:** Clearly communicate to users (both store staff and online customers) the implications of variable weights and potential partial availability. For example, "Approximately X units available."

By considering these exhaustive scenarios, developers can design a robust and reliable inventory management system that addresses the complexities of re-packaging, fractional quantities, and multi-channel sales.
